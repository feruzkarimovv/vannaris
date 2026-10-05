"""Durable retrieval identity, immutable questions, and recoverable judging.

The runner owns asynchronous scheduling. This module owns evidence transactions:
each completed result can outlive the process that produced it, while recovery
adds missing judgments without inventing a second retrieval or rewriting data.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..judge import ensemble as judge
from ..judge.ensemble import JUDGES, JudgeScore, median_overall
from ..vendors.base import ResponseMode, SearchResponse

ROOT = Path(__file__).resolve().parent.parent.parent


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def exclusive_database(db_path: Path):
    """Keep overlapping CLI processes from issuing duplicate paid calls.

    Linux/macOS advisory flock is released by the OS even after SIGKILL. It
    locks the database inode, so no extra secret-bearing lock file is needed.
    SQLite's transaction locks remain responsible for individual writes.
    """
    import fcntl

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("another benchmark process is using this database") from None
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_queries(queries: list[dict]) -> None:
    seen = set()
    for q in queries:
        for field in ("id", "category", "text"):
            if not isinstance(q.get(field), str) or not q[field].strip():
                raise ValueError(f"query requires a nonempty {field}")
        if q["id"] in seen:
            raise ValueError(f"duplicate query id: {q['id']}")
        seen.add(q["id"])


def load_responses(conn, run_id: str, *, allow_empty: bool = False) -> list[SearchResponse]:
    """Rehydrate a stored run's vendor responses, so judging can be redone.

    Why this exists: MIN_COMPLETE_SHARE is all-or-nothing, so a judge-stage
    failure used to force re-running the whole thing — all 750 vendor calls
    included — and that is not free in either money or validity. On 2026-07-31
    two full runs went out twelve minutes apart for exactly this reason, and
    Exa's own telemetry shows the second was served from its cache: server-side
    search time under 50ms on 62 of 150 calls against 0 of 150 in the first,
    and its published breaking-news p50 fell from 1368ms to 298ms. That number
    reached the site as the fastest cell on it.

    The vendor's answer to a query does not change because a judge returned
    malformed JSON. Re-judging reads the stored payload instead.
    """
    from ..vendors.base import SearchResult

    rows = conn.execute(
        "SELECT query_id, vendor, response_mode, answer, citations, results, "
        "latency_ms, cost_usd, cost_source, error, raw_payload FROM raw_responses WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    if not rows and not allow_empty:
        raise SystemExit(f"no stored responses for run {run_id!r}")

    out: list[SearchResponse] = []
    for (query_id, vendor, mode, answer, citations, results,
         latency_ms, cost_usd, cost_source, error, raw) in rows:
        resp = SearchResponse(
            vendor=vendor,
            query_id=query_id,
            response_mode=ResponseMode(mode),
            results=[SearchResult(url=x["url"], rank=x["rank"], title=x.get("title"),
                                  snippet=x.get("snippet"),
                                  published_at=x.get("published_at"))
                     for x in json.loads(results or "[]")],
            answer=answer,
            citations=json.loads(citations or "[]"),
            latency_ms=latency_ms,
            # Price is an attribute of the original retrieval, not incremental
            # spend from judging it. Recovery never creates a new retrieval.
            cost_usd=cost_usd,
            cost_source=cost_source or "estimated",
            error=error,
        )
        resp.raw = json.loads(raw) if raw else None
        out.append(resp)
    return out


def persist_run(conn, run_id, week, digest, queries, responses,
                started_at, trigger, heldout_set=None, *, provenance=None) -> dict[str, str]:
    """Create a retrieval run and freeze its questions before any calls.

    Passing responses is retained for fixture/import callers. Live runs pass an
    empty list and checkpoint each result through persist_response instead.
    """
    validate_queries(queries)
    with conn:
        cur = conn.cursor()
        # started_at is the real start, threaded in from main(). It used to be
        # stamped here, at persist time, which made every run look instantaneous
        # and put `ran_at` on the published site an hour or so late.
        cur.execute(
            "INSERT INTO runs (id, started_at, finished_at, week, query_set_hash, trigger, "
            "heldout_set, status, provenance) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, started_at, None, week, digest, trigger, heldout_set, "fetching",
             json.dumps(provenance) if provenance is not None else None),
        )
        for q in queries:
            cur.execute(
                "INSERT OR IGNORE INTO queries "
                "(id, category, text, source, gold_answer, rotates, held_out) "
                "VALUES (?,?,?,?,?,?,?)",
                (q["id"], q["category"], q["text"], q.get("source"), q.get("gold_answer"),
                 int(q.get("rotates", 0)), int(bool(q.get("held_out")))),
            )
            cur.execute(
                "INSERT INTO run_queries (run_id, query_id, category, text, source, gold_answer, "
                "gold_urls, rotates, held_out, tier) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, q["id"], q["category"], q["text"], q.get("source"), q.get("gold_answer"),
                 json.dumps(q["gold_urls"]) if q.get("gold_urls") is not None else None,
                 int(q.get("rotates", 0)), int(bool(q.get("held_out"))), q.get("tier")),
            )
    ids = {f"{r.query_id}::{r.vendor}": persist_response(conn, run_id, r) for r in responses}
    if responses and retrieval_is_complete(conn, run_id):
        mark_retrieval_complete(conn, run_id)
    return ids


def persist_response(conn, run_id: str, response: SearchResponse) -> str:
    """Checkpoint an immutable retrieved response, including failures."""
    previous = conn.execute(
        "SELECT id FROM raw_responses WHERE run_id=? AND query_id=? AND vendor=?",
        (run_id, response.query_id, response.vendor),
    ).fetchone()
    if previous:
        return previous[0]
    if not conn.execute("SELECT 1 FROM run_queries WHERE run_id=? AND query_id=?",
                        (run_id, response.query_id)).fetchone():
        raise ValueError("cannot checkpoint a response without its run query snapshot")
    rid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO raw_responses (id, run_id, query_id, vendor, response_mode, answer, "
            "citations, results, latency_ms, cost_usd, cost_source, error, raw_payload, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, run_id, response.query_id, response.vendor, response.response_mode.value,
             response.answer, json.dumps(response.citations),
             json.dumps([{"url": x.url, "rank": x.rank, "title": x.title,
                          "snippet": x.snippet, "published_at": x.published_at}
                         for x in response.results]),
             response.latency_ms, response.cost_usd, response.cost_source, response.error,
             json.dumps(response.raw), now()),
        )
    return rid


def response_id_map(conn, run_id: str) -> dict[str, str]:
    return {f"{qid}::{vendor}": rid for rid, qid, vendor in conn.execute(
        "SELECT id, query_id, vendor FROM raw_responses WHERE run_id=?", (run_id,))}


def mark_retrieval_complete(conn, run_id: str) -> None:
    if retrieval_is_complete(conn, run_id) is not True:
        raise ValueError("retrieval is missing planned query/vendor responses")
    # This also recovers a process killed after the last result checkpoint but
    # before its stage marker: use the last observed checkpoint, not today.
    completed_at = conn.execute("SELECT MAX(created_at) FROM raw_responses WHERE run_id=?",
                                (run_id,)).fetchone()[0]
    with conn:
        conn.execute("UPDATE runs SET retrieval_finished_at=COALESCE(retrieval_finished_at, ?), "
                     "status='retrieved' WHERE id=?", (completed_at, run_id))


def retrieval_is_complete(conn, run_id: str) -> bool | None:
    """Check planned pairs, or return unknown for a run predating snapshots."""
    query_ids = {r[0] for r in conn.execute("SELECT query_id FROM run_queries WHERE run_id=?", (run_id,))}
    if not query_ids:
        return None
    row = conn.execute("SELECT provenance FROM runs WHERE id=?", (run_id,)).fetchone()
    provenance = json.loads(row[0]) if row and row[0] else {}
    pairs = {(qid, vendor) for qid, vendor in conn.execute(
        "SELECT query_id,vendor FROM raw_responses WHERE run_id=?", (run_id,))}
    vendors = set(provenance.get("vendors") or [vendor for _, vendor in pairs])
    return bool(vendors) and pairs == {(qid, vendor) for qid in query_ids for vendor in vendors}


def load_run_queries(conn, run_id: str) -> list[dict]:
    """Read the original questions; never load a current query file on recovery.

    Legacy rows are explicitly labelled because their original text cannot be
    reconstructed honestly if the former global registry was overwritten.
    """
    columns = ("query_id", "category", "text", "source", "gold_answer", "gold_urls",
               "rotates", "held_out", "tier", "snapshot_source")
    rows = conn.execute(
        "SELECT query_id, category, text, source, gold_answer, gold_urls, rotates, held_out, "
        "tier, 'snapshot' FROM run_queries WHERE run_id=? ORDER BY query_id", (run_id,),
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT DISTINCT query_id, category, text, source, gold_answer, gold_urls, "
            "rotates, held_out, tier, snapshot_source FROM response_queries "
            "WHERE run_id=? ORDER BY query_id", (run_id,),
        ).fetchall()
    if not rows:
        raise ValueError(f"no recorded queries for run {run_id}")
    queries = []
    for row in rows:
        q = dict(zip(columns, row))
        q["id"] = q.pop("query_id")
        q["gold_urls"] = json.loads(q["gold_urls"]) if q["gold_urls"] else None
        queries.append(q)
    return queries


def load_scores(conn, run_id: str) -> dict[str, list[JudgeScore]]:
    fields = ("judge_family", "judge_model", "relevance", "freshness", "citation_quality",
              "overall", "rationale", "scored_chars", "prompt_tokens", "output_tokens",
              "judge_model_returned")
    out: dict[str, list[JudgeScore]] = {}
    for row in conn.execute(
        "SELECT rr.query_id, rr.vendor, js.judge_family, js.judge_model, js.relevance, "
        "js.freshness, js.citation_quality, js.overall, js.rationale, js.scored_chars, "
        "js.prompt_tokens, js.output_tokens, js.judge_model_returned "
        "FROM judge_scores js JOIN raw_responses rr ON rr.id=js.response_id WHERE rr.run_id=?",
        (run_id,),
    ):
        values = dict(zip(fields, row[2:]))
        if (values["judge_family"], values["judge_model"]) in JUDGES:
            out.setdefault(f"{row[0]}::{row[1]}", []).append(JudgeScore(**values))
    return out


def runtime_provenance() -> dict:
    """An allowlist of execution metadata; never copy the process environment."""
    source_commit = os.environ.get("GITHUB_SHA")
    if not source_commit:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        source_commit = result.stdout.strip() if result.returncode == 0 else None
    out = {"source_commit": source_commit, "python_version": sys.version.split()[0],
           "httpx_version": httpx.__version__}
    for field in ("GITHUB_EVENT_NAME", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY"):
        if os.environ.get(field):
            out[field.lower()] = os.environ[field]
    return out


def judging_protocol() -> dict:
    def source_hash(function):
        try:
            return hashlib.sha256(inspect.getsource(function).encode()).hexdigest()
        except (OSError, TypeError):
            return None

    return {"judges": JUDGES, "rubric": judge.RUBRIC, "seed": judge.JUDGE_SEED,
            "snippet_chars": judge.SNIPPET_CHARS,
            "prompt_builder_sha256": source_hash(judge.build_prompt),
            "score_validator_sha256": source_hash(judge.score_one),
            "reply_parser_sha256": source_hash(judge._extract),
            "score_schema_sha256": source_hash(judge._validate_scores),
            "json_object_validator_sha256": source_hash(judge._unique_object),
            "provider_request_sha256": {family: source_hash(function)
                                        for family, function in judge._DISPATCH.items()}}


def begin_judging_attempt(conn, run_id: str, *, provenance=None) -> str:
    protocol = judging_protocol()
    digest = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
    prior = {r[0] for r in conn.execute(
        "SELECT DISTINCT ja.protocol_hash FROM judging_attempts ja "
        "JOIN judge_scores js ON js.judging_attempt_id=ja.id WHERE ja.run_id=?", (run_id,))}
    if prior and prior != {digest}:
        raise ValueError("cannot resume accepted scores with a different judging protocol")
    if not conn.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone():
        raise ValueError(f"unknown retrieval run: {run_id}")
    attempt_id = str(uuid.uuid4())
    metadata = {**runtime_provenance(), **(provenance or {}), "protocol": protocol}
    legacy = conn.execute(
        "SELECT COUNT(*) FROM judge_scores js JOIN raw_responses rr ON rr.id=js.response_id "
        "WHERE rr.run_id=? AND js.judging_attempt_id IS NULL", (run_id,),
    ).fetchone()[0]
    metadata["legacy_scores_without_protocol"] = legacy
    with conn:
        conn.execute(
            "INSERT INTO judging_attempts (id,run_id,started_at,status,protocol_hash,provenance) "
            "VALUES (?,?,?,?,?,?)",
            (attempt_id, run_id, now(), "running", digest, json.dumps(metadata)),
        )
        conn.execute("UPDATE runs SET status='judging' WHERE id=?", (run_id,))
    return attempt_id


def begin_judge_call(conn, attempt_id, response_id, family, model, prompt, chars) -> str:
    identity = conn.execute(
        "SELECT ja.run_id,rr.run_id,ja.status FROM judging_attempts ja "
        "JOIN raw_responses rr ON rr.id=? WHERE ja.id=?", (response_id, attempt_id),
    ).fetchone()
    if identity is None or identity[0] != identity[1]:
        raise ValueError("a judging call must reference its own retrieval run")
    if identity[2] != "running":
        raise ValueError("cannot add a call to a closed judging attempt")
    call_id = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO judge_call_attempts (id,judging_attempt_id,response_id,judge_model,"
            "judge_family,started_at,status,prompt_hash,scored_chars) VALUES (?,?,?,?,?,?,?,?,?)",
            (call_id, attempt_id, response_id, model, family, now(), "running",
             hashlib.sha256(prompt.encode()).hexdigest(), chars),
        )
    return call_id


def _accept_score(conn, response_id, attempt_id, score) -> None:
    if score.error or score.overall is None:
        return
    # Accepted evidence is append-only. A recovery may fill a hole, never
    # replace a successful score merely because it ran later.
    conn.execute(
        "INSERT OR IGNORE INTO judge_scores (id,response_id,judge_model,judge_family,relevance,"
        "freshness,citation_quality,overall,rationale,scored_chars,prompt_tokens,output_tokens,"
        "judge_model_returned,judging_attempt_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), response_id, score.judge_model, score.judge_family, score.relevance,
         score.freshness, score.citation_quality, score.overall, score.rationale, score.scored_chars,
         score.prompt_tokens, score.output_tokens, score.judge_model_returned, attempt_id, now()),
    )


def complete_judge_call(conn, call_id, attempt_id, response_id, score) -> None:
    identity = conn.execute(
        "SELECT judging_attempt_id,response_id,judge_family,judge_model,status "
        "FROM judge_call_attempts WHERE id=?", (call_id,),
    ).fetchone()
    if identity is None or tuple(identity[:4]) != (attempt_id, response_id, score.judge_family, score.judge_model):
        raise ValueError("judge outcome does not match the recorded call")
    if identity[4] != "running":
        raise ValueError("judge call outcome has already been finalized")
    error = score.error or ("judge produced no usable overall score" if score.overall is None else None)
    with conn:
        conn.execute(
            "UPDATE judge_call_attempts SET finished_at=?,status=?,error=?,prompt_tokens=?,"
            "output_tokens=?,judge_model_returned=? WHERE id=?",
            (now(), "failed" if error else "succeeded", error, score.prompt_tokens,
             score.output_tokens, score.judge_model_returned, call_id),
        )
        _accept_score(conn, response_id, attempt_id, score)


def finish_judging_attempt(conn, attempt_id: str, *, status=None, error=None) -> str:
    row = conn.execute("SELECT run_id FROM judging_attempts WHERE id=?", (attempt_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown judging attempt: {attempt_id}")
    states = [r[0] for r in conn.execute(
        "SELECT status FROM judge_call_attempts WHERE judging_attempt_id=?", (attempt_id,))]
    if status is None:
        status = ("interrupted" if "running" in states else
                  "partial" if "failed" in states and "succeeded" in states else
                  "failed" if "failed" in states else "completed")
    if status not in ("completed", "partial", "failed", "interrupted"):
        raise ValueError("invalid judging attempt status")
    run_id = row[0]
    responses = load_responses(conn, run_id, allow_empty=True)
    scores = load_scores(conn, run_id)
    complete = (retrieval_is_complete(conn, run_id) is not False and
                all(not r.ok or median_overall(scores.get(f"{r.query_id}::{r.vendor}", [])) is not None
                    for r in responses) and bool(responses))
    with conn:
        conn.execute("UPDATE judging_attempts SET finished_at=?,status=?,error=? WHERE id=?",
                     (now(), status, error, attempt_id))
        if status == "interrupted":
            conn.execute("UPDATE judge_call_attempts SET status='interrupted',finished_at=?,"
                         "error=COALESCE(error,'interrupted before a result was checkpointed') "
                         "WHERE judging_attempt_id=? AND status='running'", (now(), attempt_id))
        conn.execute("UPDATE runs SET finished_at=?,status=? WHERE id=?",
                     (now(), "completed" if complete else "incomplete", run_id))
    return status


def interrupt_open_attempts(conn, run_id: str) -> None:
    """Explicit recovery closes records left running by an exited process.

    The CLI holds exclusive_database while calling this. No provider result or
    token count is invented for a call whose result never reached its checkpoint.
    """
    attempts = [r[0] for r in conn.execute(
        "SELECT id FROM judging_attempts WHERE run_id=? AND status='running'", (run_id,))]
    for attempt_id in attempts:
        finish_judging_attempt(conn, attempt_id, status="interrupted",
                               error="superseded by explicit recovery")


def persist_scores(conn, run_id, response_ids: dict[str, str], scored) -> None:
    """Compatibility importer with the same durable attempt semantics as live judging."""
    attempt_id = begin_judging_attempt(conn, run_id, provenance={"kind": "score_import"})
    for key, scores in scored.items():
        rid = response_ids.get(key)
        if rid is None:
            continue
        for score in scores:
            call_id = begin_judge_call(conn, attempt_id, rid, score.judge_family,
                                       score.judge_model, "", score.scored_chars)
            complete_judge_call(conn, call_id, attempt_id, rid, score)
    finish_judging_attempt(conn, attempt_id)
