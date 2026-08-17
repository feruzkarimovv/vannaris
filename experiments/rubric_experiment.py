"""Is the score saturation caused by easy queries or a lenient rubric?

The published table is bunched against its ceiling: 2026-W34's cell median is
8.78 and only one of four adjacent vendor pairs separates. Two very different
causes produce that, and the fix for one is useless against the other:

  - the queries are too easy, so every vendor really does do well; or
  - the rubric has no anchors, so the judges hand out 9s to anything decent.

This settles it without spending a cent on vendors. It re-scores responses that
already exist (2026-W31, run 50fbea16 — the only week whose raw responses
survive; CI's database is ephemeral) under two rubrics that differ in exactly
one way: the strict variant adds an anchored 0-10 scale and tells the judge that
competent work belongs mid-scale. Everything else is byte-identical, including
the date preamble and the length-normalisation clause.

Both arms run today, at the same temperature, against the same pinned models,
so nothing is being compared across a model revision or a settings change. The
control arm is re-run rather than read from the database for that reason.

Nothing here writes to data/vannaris.db.
"""

from __future__ import annotations

import asyncio
import json
import random
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/feruzkarimov/Desktop/searchbench")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.judge import ensemble  # noqa: E402
from src.judge.ensemble import JUDGES, make_judge_semaphores, score_response  # noqa: E402
from src.runner import load_responses  # noqa: E402

RUN_ID = "50fbea16-fb03-4e26-bcd1-40c1d40bd871"   # 2026-W31, the published run
QUERIES_PER_CATEGORY = int(sys.argv[1]) if len(sys.argv) > 1 else 10
SEED = 20260817
TODAY = "2026-08-17"

CONTROL = ensemble.RUBRIC

# The single intervention. Inserted immediately before the dimension list so the
# judge reads the scale before it reads what it is scoring.
ANCHORS = """Score each dimension from 0 to 10, using this scale literally. Most \
competent responses belong in the MIDDLE of it. A 9 or a 10 is a claim that you \
could not describe an improvement.

10 - Could not be improved. Every result on target, sources authoritative.
 9 - Excellent. One trivial blemish you had to look for.
 7-8 - Good. Answers the query but has real shortcomings a user would notice: \
some filler, a weak source, or a visible gap.
 5-6 - Serviceable. The user gets there but works for it - the best result is \
buried, or important aspects are thin.
 3-4 - Partial. Touches the topic without answering it.
 1-2 - Barely related.
 0 - Nothing useful.

Calibrate against the full range, not against how much effort the API appears to \
have made. If you find yourself scoring nearly everything 9 or 10, you are \
grading generosity rather than quality.
"""

STRICT = CONTROL.replace("Score each dimension from 0 to 10.", ANCHORS)
assert STRICT != CONTROL, "the anchor insertion point moved; fix the replace"


def sample_responses():
    """A stratified slice of the run: the same queries for every vendor.

    Paired by query, because the comparison that matters (vendor A vs vendor B)
    is a paired one and an unpaired sample would add between-question variance
    to exactly the quantity being measured.
    """
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'vannaris.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    qmap = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM queries")}

    by_cat = defaultdict(list)
    for qid, q in qmap.items():
        by_cat[q["category"]].append(qid)

    rng = random.Random(SEED)
    chosen: set[str] = set()
    for cat in sorted(by_cat):
        ids = sorted(by_cat[cat])
        rng.shuffle(ids)
        chosen.update(ids[:QUERIES_PER_CATEGORY])

    responses = [r for r in load_responses(conn, RUN_ID)
                 if r.query_id in chosen and r.ok]
    conn.close()
    return responses, qmap


async def run_arm(name: str, rubric: str, responses, qmap) -> list[dict]:
    ensemble.RUBRIC = rubric          # build_prompt reads the module global
    sems = make_judge_semaphores()
    gate = asyncio.Semaphore(16)
    out: list[dict] = []
    done = 0

    async with httpx.AsyncClient(timeout=90) as client:
        import os
        keys = {"anthropic": os.environ["ANTHROPIC_API_KEY"],
                "openai": os.environ["OPENAI_API_KEY"],
                "google": os.environ["GOOGLE_API_KEY"]}

        async def one(resp):
            q = qmap[resp.query_id]
            async with gate:
                scores = await score_response(
                    client, keys, resp, q["text"], q.get("gold_answer"), TODAY, sems)
            return resp, scores

        for coro in asyncio.as_completed([one(r) for r in responses]):
            resp, scores = await coro
            done += 1
            print(f"\r  {name}: {done}/{len(responses)}", end="", flush=True)
            out.append({
                "query_id": resp.query_id,
                "vendor": resp.vendor,
                "category": qmap[resp.query_id]["category"],
                "scores": {s.judge_family: s.overall for s in scores},
                "errors": {s.judge_family: s.error for s in scores if s.error},
            })
    print()
    return out


def median_of(row) -> float | None:
    vals = [v for v in row["scores"].values() if v is not None]
    return statistics.median(vals) if len(vals) == len(JUDGES) else None


def describe(name: str, rows: list[dict]) -> dict:
    meds = [m for m in (median_of(r) for r in rows) if m is not None]
    by_vendor = defaultdict(list)
    for r in rows:
        m = median_of(r)
        if m is not None:
            by_vendor[r["vendor"]].append(m)
    fam = defaultdict(list)
    for r in rows:
        for f, v in r["scores"].items():
            if v is not None:
                fam[f].append(v)
    return {
        "arm": name,
        "n": len(meds),
        "median": round(statistics.median(meds), 3) if meds else None,
        "mean": round(statistics.mean(meds), 3) if meds else None,
        "stdev": round(statistics.pstdev(meds), 3) if len(meds) > 1 else None,
        "pct_ge_9": round(100 * sum(1 for m in meds if m >= 9) / len(meds), 1) if meds else None,
        "pct_ge_8": round(100 * sum(1 for m in meds if m >= 8) / len(meds), 1) if meds else None,
        "min": min(meds) if meds else None,
        "max": max(meds) if meds else None,
        "vendor_means": {v: round(statistics.mean(s), 3)
                         for v, s in sorted(by_vendor.items())},
        "family_means": {f: round(statistics.mean(s), 3) for f, s in sorted(fam.items())},
        "judge_failures": sum(len(r["errors"]) for r in rows),
    }


async def main() -> int:
    load_dotenv(ROOT / ".env")
    responses, qmap = sample_responses()
    print(f"{len(responses)} responses "
          f"({len({r.query_id for r in responses})} queries x "
          f"{len({r.vendor for r in responses})} vendors), "
          f"{len(responses) * len(JUDGES) * 2} judge calls across both arms\n")

    control = await run_arm("control", CONTROL, responses, qmap)
    strict = await run_arm("strict ", STRICT, responses, qmap)

    (OUT / "rubric_experiment_raw.json").write_text(json.dumps(
        {"run_id": RUN_ID, "seed": SEED, "today": TODAY,
         "control": control, "strict": strict}, indent=1))

    a, b = describe("control", control), describe("strict", strict)
    print(json.dumps([a, b], indent=1))
    (OUT / "rubric_experiment_summary.json").write_text(json.dumps([a, b], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
