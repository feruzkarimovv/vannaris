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
from .judge.ensemble import JUDGES, make_judge_semaphores, median_overall, score_response
from .vendors.adapters import build_all
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
    digest = hashlib.sha256(
        json.dumps(queries, sort_keys=True).encode()
    ).hexdigest()[:16]
    return queries, digest


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
    client: httpx.AsyncClient, adapters, queries: list[dict]
) -> list[SearchResponse]:
    sem = asyncio.Semaphore(VENDOR_CONCURRENCY)

    async def one(adapter, q) -> SearchResponse:
        async with sem:
            return await adapter.search(client, q["text"], q["id"])

    tasks = [one(a, q) for q in queries for a in adapters]
    done = 0
    out: list[SearchResponse] = []
    for coro in asyncio.as_completed(tasks):
        out.append(await coro)
        done += 1
        print(f"\r  fetching {done}/{len(tasks)}", end="", flush=True)
    print()
    return out


async def judge_all(
    client: httpx.AsyncClient,
    keys: dict[str, str],
    responses: list[SearchResponse],
    qmap: dict[str, dict],
    today: str,
) -> dict[str, list]:
    sem = asyncio.Semaphore(RESPONSE_CONCURRENCY)
    judge_sems = make_judge_semaphores()
    scored: dict[str, list] = {}

    async def one(resp: SearchResponse):
        key = f"{resp.query_id}::{resp.vendor}"
        if not resp.ok:
            return key, []
        q = qmap[resp.query_id]
        async with sem:
            return key, await score_response(
                client, keys, resp, q["text"], q.get("gold_answer"), today, judge_sems
            )

    tasks = [one(r) for r in responses]
    done = 0
    for coro in asyncio.as_completed(tasks):
        key, scores = await coro
        scored[key] = scores
        done += 1
        print(f"\r  judging {done}/{len(tasks)}", end="", flush=True)
    print()
    return scored


def load_responses(conn, run_id: str) -> list[SearchResponse]:
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
    from .vendors.base import SearchResult

    rows = conn.execute(
        "SELECT query_id, vendor, response_mode, answer, citations, results, "
        "latency_ms, cost_usd, error, raw_payload FROM raw_responses WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    if not rows:
        raise SystemExit(f"no stored responses for run {run_id!r}")

    out: list[SearchResponse] = []
    for (query_id, vendor, mode, answer, citations, results,
         latency_ms, cost_usd, error, raw) in rows:
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
            # Deliberately zeroed. This run did not buy these responses; the run
            # that fetched them did, and counting the spend twice would overstate
            # what the benchmark costs to operate.
            cost_usd=0.0,
            error=error,
        )
        resp.raw = json.loads(raw) if raw else {}
        out.append(resp)
    return out


def persist(conn, run_id, week, digest, queries, responses, scored,
            started_at, trigger, heldout_set=None) -> None:
    cur = conn.cursor()
    # started_at is the real start, threaded in from main(). It used to be
    # stamped here, at persist time, which made every run look instantaneous
    # and put `ran_at` on the published site an hour or so late.
    cur.execute(
        "INSERT INTO runs (id, started_at, finished_at, week, query_set_hash, trigger, "
        "heldout_set) VALUES (?,?,?,?,?,?,?)",
        (run_id, started_at, now(), week, digest, trigger, heldout_set),
    )
    for q in queries:
        cur.execute(
            "INSERT OR REPLACE INTO queries "
            "(id, category, text, source, gold_answer, rotates, held_out) "
            "VALUES (?,?,?,?,?,?,?)",
            # `rotates` was written as a literal 0 here, which quietly threw
            # away the flag the query set carries — every freshness question in
            # full-v1.json is marked rotates=1 and every one of them landed in
            # the database as 0. Nothing published read it, so nothing caught
            # it; the column exists to record which questions are meant to be
            # regenerated each cycle, and it now records that.
            (q["id"], q["category"], q["text"], q.get("source"), q.get("gold_answer"),
             int(q.get("rotates", 0)), int(bool(q.get("held_out")))),
        )

    for r in responses:
        rid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO raw_responses (id, run_id, query_id, vendor, response_mode, answer, "
            "citations, results, latency_ms, cost_usd, cost_source, error, raw_payload, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rid, run_id, r.query_id, r.vendor, r.response_mode.value, r.answer,
                json.dumps(r.citations),
                json.dumps([{"url": x.url, "rank": x.rank, "title": x.title,
                             "snippet": x.snippet, "published_at": x.published_at}
                            for x in r.results]),
                r.latency_ms, r.cost_usd, r.cost_source, r.error, json.dumps(r.raw), now(),
            ),
        )
        for s in scored.get(f"{r.query_id}::{r.vendor}", []):
            if s.error:
                continue
            cur.execute(
                "INSERT INTO judge_scores (id, response_id, judge_model, judge_family, relevance, "
                "freshness, citation_quality, overall, rationale, scored_chars, prompt_tokens, "
                "output_tokens, judge_model_returned, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), rid, s.judge_model, s.judge_family, s.relevance,
                 s.freshness, s.citation_quality, s.overall, s.rationale,
                 s.scored_chars, s.prompt_tokens, s.output_tokens,
                 s.judge_model_returned, now()),
            )
    conn.commit()


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
    print("\n  A single run cannot separate this from question difficulty.")
    print("  It is only evidence once the same vendor shows the same sign for weeks.")


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


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(ROOT / "src" / "queries" / "pilot.json"))
    ap.add_argument("--limit", type=int, default=None, help="cap queries, for smoke tests")
    # Recorded on the run, not just used for logging: the site's cadence claim
    # is derived from whether scheduled runs exist (see storage/schema.sql).
    ap.add_argument("--trigger", choices=("manual", "scheduled"),
                    default=os.environ.get("SB_TRIGGER", "manual"),
                    help="how this run was invoked; CI passes 'scheduled'")
    # The withheld set runs by default. Making it opt-in would mean the honest
    # configuration is the one nobody remembers to pass, and the overfitting
    # check would exist in the repository rather than in the data.
    ap.add_argument("--heldout", default="auto",
                    help="'auto' (the registered active set), 'off', or a path")
    # Re-judge a stored run instead of calling the vendors again. The judge
    # stage fails for reasons that have nothing to do with the vendors — rate
    # limits, truncated JSON, an expired key — and re-fetching to recover from
    # that costs money and, worse, re-issues identical queries into vendor
    # caches within minutes, which corrupts the latency column. See
    # load_responses.
    ap.add_argument("--rejudge", metavar="RUN_ID", default=None,
                    help="re-judge a stored run's responses; makes no vendor calls")
    args = ap.parse_args()
    # argparse only validates `choices` for values that arrive on the command
    # line, so a typo'd SB_TRIGGER would sail through into the evidence layer.
    if args.trigger not in ("manual", "scheduled"):
        raise SystemExit(f"SB_TRIGGER must be 'manual' or 'scheduled', got {args.trigger!r}")

    load_dotenv(ROOT / ".env")
    env = dict(os.environ)
    keys = {
        "anthropic": env.get("ANTHROPIC_API_KEY", ""),
        "openai": env.get("OPENAI_API_KEY", ""),
        "google": env.get("GOOGLE_API_KEY", ""),
    }

    queries, digest = load_queries(Path(args.queries))
    if args.limit:
        queries = queries[: args.limit]
    # The public set's hash is computed before the withheld set is folded in,
    # so it keeps identifying the published questions and nothing else. A
    # reader recomputing it from queries.csv has to get the same string.
    private, heldout_id = load_heldout(args.heldout)
    if args.limit:
        private = private[: args.limit]
    queries = queries + private
    qmap = {q["id"]: q for q in queries}
    cats = list(dict.fromkeys(q["category"] for q in queries))

    adapters = build_all(env)
    run_id, week = str(uuid.uuid4()), iso_week()
    started_at = now()
    # The date the judges are told. Interpolated into the rubric so a judge does
    # not read post-cutoff search results as fabricated — see build_prompt.
    today = datetime.now(timezone.utc).strftime("%d %B %Y")

    print(f"run {run_id[:8]}  week {week}  queryset {digest}  trigger {args.trigger}")
    if heldout_id:
        print(f"held-out set {heldout_id}: {len(private)} withheld questions, hash verified")

    if args.rejudge:
        conn = connect()
        responses = load_responses(conn, args.rejudge)
        conn.close()
        print(f"re-judging {len(responses)} stored responses from run "
              f"{args.rejudge[:8]} — no vendor calls, no vendor spend")
        async with httpx.AsyncClient(timeout=90.0) as client:
            scored = await judge_all(client, keys, responses, qmap, today)
    else:
        print(f"{len(queries)} queries x {len(adapters)} vendors x {len(JUDGES)} judges "
              f"= {len(queries) * len(adapters)} calls, "
              f"{len(queries) * len(adapters) * len(JUDGES)} judgements\n")
        async with httpx.AsyncClient(timeout=90.0) as client:
            responses = await fetch_all(client, adapters, queries)
            ok = sum(1 for r in responses if r.ok)
            print(f"  {ok}/{len(responses)} vendor calls ok")
            scored = await judge_all(client, keys, responses, qmap, today)

    conn = connect()
    persist(conn, run_id, week, digest, queries, responses, scored, started_at,
            args.trigger, heldout_id)
    # Public responses only. A published cell has to be recomputable from the
    # published questions, so a withheld question must never enter one — the
    # withheld set is reported separately, as a gap.
    public = [r for r in responses if not qmap[r.query_id].get("held_out")]
    means = aggregate(conn, week, run_id, public, scored, qmap)
    conn.close()

    report(means, public, scored, qmap, cats)
    report_heldout(responses, scored, qmap)
    print(f"\n  vendor spend this run: ${sum(r.cost_usd or 0 for r in responses):.4f}")
    print(f"  stored: {DB_PATH}")

    problems = validity(scored, responses)
    if problems:
        print("\n  RUN NOT PUBLISHABLE:")
        for p in problems:
            print(f"    - {p}")
        print("  Everything above is stored; the export will not select this run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
