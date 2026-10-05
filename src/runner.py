"""Benchmark runner: fetch -> store raw -> judge -> aggregate -> report.

Design note on failure handling: nothing here aborts the run. A vendor timing
out, a judge returning malformed JSON, a rate limit — all are recorded and the
run continues. A weekly benchmark that dies on the 87th of 100 calls produces
no data at all, and the whole credibility claim rests on the run actually
happening every week. A failed call is also itself a reliability data point.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import sqlite3
import statistics
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from . import heldout, storage
from .storage.lifecycle import (
    begin_judge_call, begin_judging_attempt, complete_judge_call,
    exclusive_database, finish_judging_attempt, interrupt_open_attempts,
    load_responses, load_run_queries, load_scores,
    mark_retrieval_complete, persist_response, persist_run, persist_scores,
    response_id_map, retrieval_is_complete, runtime_provenance, validate_queries,
)
from .judge import ensemble as judge
from .judge.ensemble import JUDGES, JudgeScore, build_prompt, make_judge_semaphores, median_overall, score_one
from .vendors.adapters import TOP_K, build_all
from .vendors.base import ResponseMode, SearchResponse

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "vannaris.db"

# Kept low deliberately: several vendors publish per-minute caps well under
# what unbounded asyncio.gather would produce, and tripping a rate limit
# corrupts a weekly datapoint in a way that is not worth the wall-clock saving.
VENDOR_CONCURRENCY = 4
# How many responses may be mid-judging at once. This is a memory bound, not a
# rate limit: the rate limits are per judge family and live in
# ensemble.JUDGE_LIMITS, because the three families have different ceilings and
# one shared number has to be set for the lowest of them.
#
# It has to stay comfortably above the largest per-family concurrency or it
# becomes the binding constraint by the back door: a response holds its slot
# here until all three of its judges return, so a cap near OpenAI's would leave
# Anthropic and Google idling behind a response still waiting on OpenAI. That
# is what the old shared cap of 6 was doing, and it is why OpenAI's real rate
# was invisible until it was measured — the head-of-line blocking was throttling
# OpenAI by accident, at the cost of the other two families' throughput.
RESPONSE_CONCURRENCY = 16

# Share of responses that must carry a complete three-judge ensemble for the
# run to be worth publishing. Matches export.MIN_CELL_COVERAGE, which is the
# floor a cell has to clear there — a run that cannot clear it anywhere is a
# failed run, and under a scheduler nobody is watching the console, so it has
# to be an exit code rather than a line of output.
MIN_COMPLETE_SHARE = 0.60


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_week(dt: datetime | None = None) -> str:
    d = dt or datetime.now(timezone.utc)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def connect() -> sqlite3.Connection:
    return storage.connect(DB_PATH)


def load_queries(path: Path) -> tuple[list[dict], str]:
    payload = json.loads(path.read_text())
    queries = payload["queries"]
    # Hash pins exactly which queries produced a given run, so a published
    # number can always be traced to the question set behind it.
    validate_queries(queries)
    return queries, query_digest(queries)


def query_digest(queries: list[dict]) -> str:
    return hashlib.sha256(json.dumps(queries, sort_keys=True).encode()).hexdigest()[:16]


def load_heldout(mode: str) -> tuple[list[dict], str | None]:
    """The withheld questions to run alongside the public set, if any.

    Returns them tagged `held_out`, which is what keeps them out of every
    published cell downstream. Three outcomes, and the difference between the
    second and third matters:

      - `--heldout off`      — deliberately not running it. Silent.
      - text not on this machine — the ordinary case for anyone who is not the
        maintainer. Says so and carries on, because the runner has to work for
        a contributor who will never hold the set.
      - text present         — verified against the hash committed to git
        before the set ever ran, and refused outright if it does not match.
    """
    if mode == "off":
        return [], None
    a = heldout.active()
    if not a:
        print("  no held-out set is registered — running the public set alone")
        return [], None

    path = Path(mode) if mode not in ("auto",) else None
    queries = heldout.load_queries(a["id"], path)
    if queries is None:
        print(f"  held-out set {a['id']} is registered but its questions are not on "
              f"this machine — running the public set alone")
        return [], None

    # The commitment is only worth something if it is checked. A set edited
    # after registration stops the run rather than quietly producing a number.
    heldout.verify(a["id"], queries)
    return [{**q, "held_out": True} for q in queries], a["id"]


async def fetch_all(
    client: httpx.AsyncClient, adapters, queries: list[dict], *,
    on_response=None, existing: set[tuple[str, str]] | None = None,
) -> list[SearchResponse]:
    sem = asyncio.Semaphore(VENDOR_CONCURRENCY)

    async def one(adapter, q) -> SearchResponse:
        async with sem:
            return await adapter.search(client, q["text"], q["id"])

    existing = existing or set()
    tasks = [asyncio.create_task(one(a, q)) for q in queries for a in adapters
             if (q["id"], a.name) not in existing]
    done = 0
    out: list[SearchResponse] = []
    try:
        for coro in asyncio.as_completed(tasks):
            response = await coro
            if on_response is not None:
                on_response(response)
            out.append(response)
            done += 1
            print(f"\r  fetching {done}/{len(tasks)}", end="", flush=True)
    finally:
        # A storage error or cancellation must not leave chargeable requests
        # running after the caller has abandoned the stage.
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    print()
    return out


async def judge_all(
    client: httpx.AsyncClient,
    keys: dict[str, str],
    responses: list[SearchResponse],
    qmap: dict[str, dict],
    today: str,
    *, conn=None, run_id: str | None = None, attempt_id: str | None = None,
    judge_sems=None,
) -> dict[str, list]:
    sem = asyncio.Semaphore(RESPONSE_CONCURRENCY)
    judge_sems = judge_sems if judge_sems is not None else make_judge_semaphores()
    if conn is not None and (run_id is None or attempt_id is None):
        raise ValueError("checkpointed judging requires run_id and attempt_id")
    scored = load_scores(conn, run_id) if conn is not None else {}
    response_ids = response_id_map(conn, run_id) if conn is not None else {}

    async def one(resp: SearchResponse):
        key = f"{resp.query_id}::{resp.vendor}"
        if not resp.ok:
            return key, []
        previous = scored.get(key, [])
        accepted = {(s.judge_family, s.judge_model) for s in previous
                    if s.overall is not None and not s.error}
        missing = [(fam, mdl) for fam, mdl in JUDGES if (fam, mdl) not in accepted]
        if not missing:
            return key, previous
        q = qmap[resp.query_id]
        async with sem:
            prompt, chars = build_prompt(resp, q["text"], q.get("gold_answer"), today)

            async def family_one(fam, model):
                call_id = None
                if conn is not None:
                    call_id = begin_judge_call(conn, attempt_id, response_ids[key], fam,
                                               model, prompt, chars)
                score = await score_one(client, keys, fam, model, prompt, chars, judge_sems[fam])
                if conn is not None:
                    complete_judge_call(conn, call_id, attempt_id, response_ids[key], score)
                return score

            family_tasks = [asyncio.create_task(family_one(fam, mdl)) for fam, mdl in missing]
            try:
                new = await asyncio.gather(*family_tasks)
            finally:
                for task in family_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*family_tasks, return_exceptions=True)
            return key, previous + list(new)

    tasks = [asyncio.create_task(one(r)) for r in responses]
    done = 0
    try:
        for coro in asyncio.as_completed(tasks):
            key, scores = await coro
            scored[key] = scores
            done += 1
            print(f"\r  judging {done}/{len(tasks)}", end="", flush=True)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    print()
    return scored



def aggregate(conn, week, run_id, responses, scored, qmap) -> dict[tuple[str, str], float]:
    """Collapse per-response medians into (vendor, category) cells.

    Guarded against downgrade. A `--limit 2` smoke test and a full 150-query
    run write to the same (week, vendor, category) key, and the smoke test used
    to win simply by being later — leaving a published-looking cell computed
    from two queries. A cell is only overwritten by a run covering at least as
    many queries as the one already there.
    """
    cells: dict[tuple[str, str], list[float]] = {}
    for r in responses:
        m = median_overall(scored.get(f"{r.query_id}::{r.vendor}", []))
        if m is not None:
            cells.setdefault((r.vendor, qmap[r.query_id]["category"]), []).append(m)

    means = {k: statistics.mean(v) for k, v in cells.items()}
    best_by_cat: dict[str, float] = {}
    for (vendor, cat), val in means.items():
        best_by_cat[cat] = max(best_by_cat.get(cat, 0.0), val)

    cur = conn.cursor()
    skipped = 0
    for (vendor, cat), val in means.items():
        rs = [r for r in responses if r.vendor == vendor and qmap[r.query_id]["category"] == cat]
        lat = [r.latency_ms for r in rs if r.latency_ms is not None]

        prior = cur.execute(
            "SELECT n_queries FROM weekly_scores WHERE week=? AND vendor=? AND category=?",
            (week, vendor, cat),
        ).fetchone()
        if prior and prior[0] > len(rs):
            skipped += 1
            continue

        cur.execute(
            "INSERT OR REPLACE INTO weekly_scores (id, week, run_id, vendor, category, "
            "median_score, n_queries, n_errors, p50_latency_ms, total_cost_usd, "
            "delta_from_best, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), week, run_id, vendor, cat, round(val, 3), len(rs),
             sum(1 for r in rs if not r.ok),
             int(statistics.median(lat)) if lat else None,
             round(sum(r.cost_usd or 0 for r in rs), 5),
             round(best_by_cat[cat] - val, 3), now()),
        )
    conn.commit()
    if skipped:
        print(f"  {skipped} cell(s) left alone — an existing cell covers more queries "
              f"than this run. Smoke runs do not overwrite full runs.")
    return means


def report(means, responses, scored, qmap, cats) -> None:
    print("\n" + "=" * 74)
    print("SCORES BY CATEGORY  (median across 3-judge ensemble, 0-10)")
    print("=" * 74)

    for cat in cats:
        rows = sorted(
            ((v, s) for (v, c), s in means.items() if c == cat),
            key=lambda x: -x[1],
        )
        if not rows:
            continue
        best = rows[0][1]
        print(f"\n{cat}")
        print(f"  {'vendor':<13}{'score':<9}{'gap to #1':<12}{'p50 ms':<9}cost")
        print("  " + "-" * 54)
        for vendor, score in rows:
            rs = [r for r in responses if r.vendor == vendor and qmap[r.query_id]["category"] == cat]
            lat = [r.latency_ms for r in rs if r.latency_ms is not None]
            p50 = int(statistics.median(lat)) if lat else 0
            cost = sum(r.cost_usd or 0 for r in rs)
            gap = best - score
            print(f"  {vendor:<13}{score:<9.2f}{('—' if gap == 0 else f'-{gap:.2f}'):<12}{p50:<9}${cost:.4f}")
        print(f"  spread #1 to #{len(rows)}: {best - rows[-1][1]:.2f} points")

    # Judge agreement — the number that says whether to trust any of the above.
    print("\n" + "=" * 74)
    print("JUDGE AGREEMENT")
    print("=" * 74)
    spreads, per_family = [], {f: [] for f, _ in JUDGES}
    fails = 0
    for scores in scored.values():
        vals = [s.overall for s in scores if s.overall is not None]
        fails += sum(1 for s in scores if s.error)
        if len(vals) > 1:
            spreads.append(max(vals) - min(vals))
        for s in scores:
            if s.overall is not None:
                per_family[s.judge_family].append(s.overall)
    if spreads:
        print(f"  mean disagreement (max-min per response): {statistics.mean(spreads):.2f} pts")
        print(f"  responses where judges differ by >3 pts:  "
              f"{sum(1 for s in spreads if s > 3)}/{len(spreads)}")
    expected = len(scored)
    for fam, vals in per_family.items():
        status = "" if len(vals) == expected else f"  <-- {expected - len(vals)} MISSING"
        mean = f"{statistics.mean(vals):.2f}" if vals else "  n/a"
        print(f"  {fam:<11} mean {mean}  (n={len(vals)}/{expected}){status}")

    if fails:
        print(f"\n  {fails} judge call(s) failed. Distinct causes:")
        seen: set[str] = set()
        for scores in scored.values():
            for s in scores:
                if s.error and s.error[:90] not in seen:
                    seen.add(s.error[:90])
                    print(f"    [{s.judge_family}] {s.error[:150]}")
        # An ensemble missing a whole family is not an ensemble — the
        # cross-family split IS the bias mitigation (docs/04), so say so
        # loudly rather than letting a 2-of-3 run look like a clean result.
        dead = [f for f, v in per_family.items() if not v]
        if dead:
            print(f"\n  WARNING: no scores at all from {', '.join(dead)}.")
            print("  These numbers are NOT methodologically valid — the cross-family")
            print("  ensemble is the bias mitigation, not a nice-to-have. Do not publish.")


def report_heldout(responses, scored, qmap) -> None:
    """Public score against withheld score, per vendor.

    This is the overfitting check made legible at the console. A vendor that
    has tuned for the 150 published questions scores better on them than on
    questions it has never seen a list of, and the difference shows up here as
    a positive gap. One run of it proves nothing — the gap has to be read
    across weeks, and a set only has to be big enough to move the mean, not to
    be significant on its own. It is a smoke alarm, not a verdict.
    """
    def mean_for(vendor, held):
        vals = []
        for r in responses:
            if r.vendor != vendor or bool(qmap[r.query_id].get("held_out")) != held:
                continue
            m = median_overall(scored.get(f"{r.query_id}::{r.vendor}", []))
            if m is not None:
                vals.append(m)
        return statistics.mean(vals) if vals else None

    vendors = sorted({r.vendor for r in responses})
    rows = []
    for v in vendors:
        pub, priv = mean_for(v, False), mean_for(v, True)
        if pub is not None and priv is not None:
            rows.append((v, pub, priv, pub - priv))
    if not rows:
        return

    print("\n" + "=" * 74)
    print("PUBLIC vs HELD-OUT  (positive gap = better on the published questions)")
    print("=" * 74)
    print(f"  {'vendor':<13}{'public':<10}{'held-out':<11}gap")
    print("  " + "-" * 54)
    for v, pub, priv, gap in sorted(rows, key=lambda r: -r[3]):
        print(f"  {v:<13}{pub:<10.2f}{priv:<11.2f}{gap:+.2f}")
    print("\n  This is a descriptive distribution-gap diagnostic.")
    print("  Neither one run nor a repeated gap isolates overfitting from question difficulty.")


def validity(scored: dict[str, list], responses: list[SearchResponse]) -> list[str]:
    """Reasons this run must not become published data. Empty means publishable.

    Separate from report() because report() is for a human reading a console and
    this is for a scheduler that is not reading anything. Everything is stored
    either way — the run is still evidence about vendor and judge reliability,
    it just does not get to feed the export.
    """
    problems: list[str] = []
    judged = {k: v for k, v in scored.items() if v}
    if not judged:
        return ["no response was judged at all"]

    families = {f for f, _ in JUDGES}
    seen = {s.judge_family for v in judged.values() for s in v if s.overall is not None}
    # The cross-family split IS the bias mitigation (docs/04). Two families is
    # not a degraded ensemble, it is a different methodology.
    for fam in sorted(families - seen):
        problems.append(f"judge family {fam!r} produced no usable scores")

    complete = sum(
        1 for v in judged.values()
        if len([s for s in v if s.overall is not None]) == len(JUDGES)
    )
    share = complete / len(judged)
    if share < MIN_COMPLETE_SHARE:
        problems.append(
            f"only {share:.0%} of judged responses have a complete ensemble "
            f"(floor {MIN_COMPLETE_SHARE:.0%})"
        )

    if not any(r.ok for r in responses):
        problems.append("every vendor call failed")
    return problems


def vendor_configuration(adapter) -> dict:
    """Record request-affecting configuration without inspecting credentials."""
    try:
        source = inspect.getsource(type(adapter))
    except (OSError, TypeError):
        source = ""
    return {"adapter": f"{type(adapter).__module__}.{type(adapter).__qualname__}",
            "adapter_source_sha256": hashlib.sha256(source.encode()).hexdigest() if source else None,
            "response_mode": adapter.response_mode.value, "top_k": TOP_K,
            "model": getattr(adapter, "model", None),
            "timeout_seconds": getattr(adapter, "_timeout", None),
            "estimated_cost_per_query_usd": adapter.cost_per_query_usd}


def retrieval_date_is_current(started_at: str) -> bool:
    return (datetime.fromisoformat(started_at).astimezone(timezone.utc).date()
            == datetime.now(timezone.utc).date())


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH), help="private SQLite evidence database")
    ap.add_argument("--queries", default=str(ROOT / "src" / "queries" / "pilot.json"))
    ap.add_argument("--limit", type=int, default=None, help="cap queries, for smoke tests")
    ap.add_argument("--trigger", choices=("manual", "scheduled"),
                    default=os.environ.get("SB_TRIGGER", "manual"))
    ap.add_argument("--heldout", default="auto",
                    help="'auto' (the registered active set), 'off', or a path")
    recovery = ap.add_mutually_exclusive_group()
    recovery.add_argument("--rejudge", metavar="RUN_ID", help="resume missing judges; no vendor calls")
    recovery.add_argument("--resume", metavar="RUN_ID", help="resume incomplete retrieval and judging")
    args = ap.parse_args()
    if args.trigger not in ("manual", "scheduled"):
        raise SystemExit("SB_TRIGGER must be 'manual' or 'scheduled'")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    if (args.rejudge or args.resume) and args.limit is not None:
        raise SystemExit("recovery uses the recorded query snapshot; --limit is not supported")

    load_dotenv(ROOT / ".env")
    env = dict(os.environ)
    keys = {"anthropic": env.get("ANTHROPIC_API_KEY", ""),
            "openai": env.get("OPENAI_API_KEY", ""), "google": env.get("GOOGLE_API_KEY", "")}
    db_path = Path(args.db)
    with exclusive_database(db_path):
        return await execute_run(args, env, keys, db_path)


async def execute_run(args, env, keys, db_path: Path) -> int:
    conn = storage.connect(db_path)
    attempt_id = None
    run_id = args.rejudge or args.resume
    try:
        if run_id:
            row = conn.execute(
                "SELECT week,query_set_hash,started_at,trigger,heldout_set,provenance "
                "FROM runs WHERE id=?", (run_id,),
            ).fetchone()
            if row is None:
                raise SystemExit(f"unknown retrieval run: {run_id}")
            interrupt_open_attempts(conn, run_id)
            week, digest, started_at, trigger, heldout_id, saved_provenance = row
            queries = load_run_queries(conn, run_id)
            provenance = json.loads(saved_provenance) if saved_provenance else {}
            if any(q["snapshot_source"] == "legacy_fallback" for q in queries):
                print("  legacy query text was not versioned; recovery uses the preserved legacy registry")
            responses = load_responses(conn, run_id, allow_empty=bool(args.resume))
            print(f"recovering retrieval {run_id} from {week}; original dates and prices preserved")
            if args.resume:
                vendors = provenance.get("vendors")
                if not vendors:
                    raise SystemExit("legacy run has no recorded vendor selection; use --rejudge for stored responses")
                adapters = [a for a in build_all(env) if a.name in vendors]
                missing_keys = sorted(set(vendors) - {a.name for a in adapters})
                existing = {(r.query_id, r.vendor) for r in responses}
                missing = {(q["id"], v) for q in queries for v in vendors} - existing
                if missing and week != iso_week():
                    raise SystemExit("cannot fetch missing responses for a past week; --rejudge can recover stored evidence")
                if missing and not retrieval_date_is_current(started_at):
                    raise SystemExit("cannot fetch missing responses after the original UTC retrieval date; use --rejudge")
                if missing and missing_keys:
                    raise SystemExit(f"missing credentials for retrieval vendors: {', '.join(missing_keys)}")
                if missing:
                    configurations = provenance.get("vendor_configuration")
                    if configurations and any(configurations[a.name] != vendor_configuration(a) for a in adapters):
                        raise SystemExit("vendor configuration changed; cannot mix retrieval protocols in a recovery")
                    try:
                        with conn:
                            conn.execute("UPDATE runs SET status='fetching' WHERE id=?", (run_id,))
                        async with httpx.AsyncClient(timeout=90.0) as client:
                            await fetch_all(client, adapters, queries, existing=existing,
                                            on_response=lambda r: persist_response(conn, run_id, r))
                    except BaseException:
                        with conn:
                            conn.execute("UPDATE runs SET status='interrupted' WHERE id=?", (run_id,))
                        raise
                    responses = load_responses(conn, run_id)
            if retrieval_is_complete(conn, run_id) is True:
                mark_retrieval_complete(conn, run_id)
        else:
            queries, _ = load_queries(Path(args.queries))
            if args.limit is not None:
                queries = queries[:args.limit]
            digest = query_digest(queries)
            private, heldout_id = load_heldout(args.heldout)
            if args.limit is not None:
                private = private[:args.limit]
            queries += private
            validate_queries(queries)
            adapters = build_all(env)
            if not adapters:
                raise SystemExit("no cleared vendor credentials are configured")
            run_id, week, started_at, trigger = str(uuid.uuid4()), iso_week(), now(), args.trigger
            provenance = {**runtime_provenance(), "vendors": [a.name for a in adapters],
                          "vendor_configuration": {a.name: vendor_configuration(a) for a in adapters},
                          "query_snapshot": "immutable_per_run"}
            persist_run(conn, run_id, week, digest, queries, [], started_at, trigger,
                        heldout_id, provenance=provenance)
            print(f"retrieval {run_id} week {week} queryset {digest} trigger {trigger}")
            print(f"{len(queries)} queries x {len(adapters)} vendors; checkpointing each result")
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    await fetch_all(client, adapters, queries,
                                    on_response=lambda r: persist_response(conn, run_id, r))
            except BaseException:
                with conn:
                    conn.execute("UPDATE runs SET status='interrupted' WHERE id=?", (run_id,))
                raise
            mark_retrieval_complete(conn, run_id)
            responses = load_responses(conn, run_id)

        qmap = {q["id"]: q for q in queries}
        cats = list(dict.fromkeys(q["category"] for q in queries))
        # Freshness is judged against when the retrieval happened, even when the
        # missing family is recovered weeks later.
        today = datetime.fromisoformat(started_at).strftime("%d %B %Y")
        attempt_id = begin_judging_attempt(conn, run_id,
                                          provenance={"kind": "recovery" if args.rejudge or args.resume else "initial"})
        print(f"  judging attempt {attempt_id}; accepted scores are reused")
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                scored = await judge_all(client, keys, responses, qmap, today,
                                         conn=conn, run_id=run_id, attempt_id=attempt_id)
        except BaseException as exc:
            finish_judging_attempt(conn, attempt_id, status="interrupted", error=type(exc).__name__)
            raise
        finish_judging_attempt(conn, attempt_id)
        public = [r for r in responses if not qmap[r.query_id].get("held_out")]
        means = aggregate(conn, week, run_id, public, scored, qmap)
        report(means, public, scored, qmap, cats)
        report_heldout(responses, scored, qmap)
        print(f"\n  original retrieval vendor spend: ${sum(r.cost_usd or 0 for r in responses):.4f}")
        print(f"  stored: {db_path}")
        print(f"  resume missing judges with: python -m src.runner --db {db_path} --rejudge {run_id}")
        problems = validity(scored, responses)
        if retrieval_is_complete(conn, run_id) is False:
            problems.append("retrieval is missing planned query/vendor responses")
        if problems:
            print("\n  RUN NOT PUBLISHABLE:")
            for problem in problems:
                print(f"    - {problem}")
            print("  Responses, accepted scores, and failed attempts were checkpointed.")
            return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
