"""Measure the 240 v3 candidates and pick the 150 that actually turned out hard.

docs/16 established that the saturation is caused by the queries, so a hard tier
that is not hard would waste the whole exercise. Authoring cannot verify its own
difficulty; this can. Every candidate is put to two vendors and scored by the
real ensemble, and difficulty becomes a measurement rather than a claim.

Two vendors, not five: the pilot only has to rank candidates against each other,
and 240 x 5 would cost as much as a full week for a question that 240 x 2
answers. Exa is included because it is the strongest vendor on the standard
tier - a query Exa handles well is not hard, whatever a weaker vendor does with
it. Serper is included because it is the cheapest and architecturally the least
like Exa, so agreement between the two is a stronger signal than agreement
between two similar products.

Selection rule, per category, in order:

  1. Drop candidates where BOTH vendors score below 3. A query nobody can answer
     at all is usually broken, ambiguous, or carrying a wrong gold answer - not
     hard. Keeping those would hit the median target while making the tier
     measure nothing, which is the exact failure this pilot exists to avoid.
  2. Rank what remains by mean score ascending and keep 25.

Writes nothing to data/vannaris.db. This is not a run and must never become one:
a 240-query two-vendor pass would be selected as a week's canonical run by
export.canonical_run if it ever landed in the runs table.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/feruzkarimov/Desktop/searchbench")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.judge.ensemble import JUDGES, make_judge_semaphores, score_response  # noqa: E402
from src.vendors.adapters import REGISTRY  # noqa: E402

PILOT_VENDORS = ["exa", "serper"]
KEEP_PER_CATEGORY = 25
FLOOR = 3.0          # below this from BOTH vendors, the query is suspect not hard
TODAY = "2026-08-17"
CANDIDATES = ROOT / "src" / "queries" / "candidates-v3.json"


def build_pilot_adapters(env):
    out = []
    for name in PILOT_VENDORS:
        cls, env_var = REGISTRY[name]
        key = (env.get(env_var) or "").strip()
        if not key:
            raise SystemExit(f"missing {env_var} for pilot vendor {name}")
        out.append((name, cls(api_key=key)))
    return out


async def main() -> int:
    load_dotenv(ROOT / ".env")
    env = dict(os.environ)
    queries = json.loads(CANDIDATES.read_text())["queries"]
    if len(sys.argv) > 1:                       # smoke test: N per category
        n = int(sys.argv[1])
        seen = defaultdict(int)
        subset = []
        for q in queries:
            if seen[q["category"]] < n:
                seen[q["category"]] += 1
                subset.append(q)
        queries = subset
    adapters = build_pilot_adapters(env)
    keys = {"anthropic": env["ANTHROPIC_API_KEY"],
            "openai": env["OPENAI_API_KEY"],
            "google": env["GOOGLE_API_KEY"]}

    print(f"{len(queries)} candidates x {len(adapters)} vendors = "
          f"{len(queries) * len(adapters)} vendor calls, "
          f"{len(queries) * len(adapters) * len(JUDGES)} judge calls\n")

    sems = make_judge_semaphores()
    fetch_gate = asyncio.Semaphore(8)
    judge_gate = asyncio.Semaphore(16)
    rows: list[dict] = []
    done = 0

    async with httpx.AsyncClient(timeout=90) as client:
        async def one(name, adapter, q):
            nonlocal done
            async with fetch_gate:
                try:
                    resp = await adapter.search(client, q["text"], q["id"])
                except Exception as exc:                      # noqa: BLE001
                    resp = None
                    err = f"{type(exc).__name__}: {exc}"
            if resp is None or not resp.ok:
                done += 1
                return {"query_id": q["id"], "category": q["category"], "vendor": name,
                        "score": None,
                        "error": err if resp is None else resp.error}
            async with judge_gate:
                scores = await score_response(
                    client, keys, resp, q["text"], q.get("gold_answer"), TODAY, sems)
            vals = [s.overall for s in scores if s.overall is not None]
            done += 1
            print(f"\r  {done}/{len(queries) * len(adapters)}", end="", flush=True)
            return {"query_id": q["id"], "category": q["category"], "vendor": name,
                    "score": statistics.median(vals) if len(vals) == len(JUDGES) else None,
                    "n_results": len(resp.results), "error": None}

        tasks = [one(name, a, q) for q in queries for name, a in adapters]
        for coro in asyncio.as_completed(tasks):
            rows.append(await coro)
    print()

    (OUT / "pilot_v3_raw.json").write_text(json.dumps(rows, indent=1))

    # ---------------------------------------------------------------- select
    by_q = defaultdict(dict)
    cat = {}
    for r in rows:
        by_q[r["query_id"]][r["vendor"]] = r["score"]
        cat[r["query_id"]] = r["category"]

    scored, dropped_nodata, dropped_floor = {}, [], []
    for qid, per in by_q.items():
        vals = [v for v in per.values() if v is not None]
        if not vals:
            dropped_nodata.append(qid)
            continue
        if max(vals) < FLOOR:
            dropped_floor.append(qid)
            continue
        scored[qid] = {"mean": statistics.mean(vals),
                       "spread": (max(vals) - min(vals)) if len(vals) > 1 else None,
                       "per_vendor": per}

    keep, shortfall = [], {}
    for c in sorted({cat[q] for q in scored}):
        ranked = sorted([q for q in scored if cat[q] == c],
                        key=lambda q: scored[q]["mean"])
        keep.extend(ranked[:KEEP_PER_CATEGORY])
        if len(ranked) < KEEP_PER_CATEGORY:
            shortfall[c] = len(ranked)

    all_means = [scored[q]["mean"] for q in scored]
    kept_means = [scored[q]["mean"] for q in keep]
    spreads = [scored[q]["spread"] for q in keep if scored[q]["spread"] is not None]

    summary = {
        "n_candidates": len(queries),
        "n_scored": len(scored),
        "dropped_no_data": dropped_nodata,
        "dropped_below_floor": dropped_floor,
        "shortfall_by_category": shortfall,
        "all_candidates_median": round(statistics.median(all_means), 3),
        "kept_median": round(statistics.median(kept_means), 3),
        "kept_mean": round(statistics.mean(kept_means), 3),
        "kept_mean_vendor_spread": round(statistics.mean(spreads), 3) if spreads else None,
        "kept_by_category": {
            c: {"n": sum(1 for q in keep if cat[q] == c),
                "median": round(statistics.median(
                    [scored[q]["mean"] for q in keep if cat[q] == c]), 3)}
            for c in sorted({cat[q] for q in keep})},
        "keep": sorted(keep),
    }
    (OUT / "pilot_v3_selection.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "keep"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
