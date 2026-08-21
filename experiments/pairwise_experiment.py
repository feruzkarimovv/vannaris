"""Does comparative judging separate vendors that absolute scoring cannot?

The instrument is saturating and cannot resolve its own top two. 2026-W34 ties
74.0% of queries, puts Exa and Perplexity in one tier (+0.014, se 0.086), and
its ranking flips when either Anthropic or OpenAI is dropped from the panel.
Two earlier attempts to fix that failed: an anchored rubric moved the mean and
separated nothing (docs/16), and a harder query tier landed at median 8.50
against a target of 6.00 (docs/17). Both changed *what* is scored or *how
generously*. Neither changed the protocol.

docs/04 chose pointwise scoring over pairwise on cost — "a 4x cost multiplier"
at 8-9 vendors — and not on discrimination. That leaves the obvious lever
untested, and one number says it is worth testing: on the 50 pairs the absolute
ensemble scored as near-ties, the human labeller still picked a winner on 48 of
them (96%). The information separating those responses is *in* them. Absolute
scoring is not extracting it.

Two arms, both against 2026-W31 (run 50fbea16) — the only week whose raw vendor
responses survive, because CI's database is ephemeral and W33/W34's are gone.

  A. VALIDATION. Re-judge the exact 280 screens of calibration set 96afde9bfef3
     comparatively, in the same left/right orientation the human saw, and
     compare against that human's choices. The absolute ensemble scores 79.1%
     [71.8, 84.8] on this set, and it earns that number the awkward way: by
     having its pairwise *choice* derived from a gap between two independent
     absolute scores. A comparative judge answers the human's question directly.
     The set's own `swapped` (50) and `repeat` (30) strata measure this judge's
     position bias and self-consistency under the same design used on the human.

  B. DISCRIMINATION. Exa vs Perplexity on all 150 W31 queries, both orders,
     three families. The pair the published table cannot resolve.

Only the protocol changes. The date preamble, the three dimension definitions,
the length-normalisation clause and the 500-character snippet cap are spliced
out of `ensemble.RUBRIC` at import and asserted, so an edit to the production
rubric breaks this file rather than silently comparing two different things.

`today` is pinned to the run's own date, not to the date this is executed. The
responses were retrieved on 2026-07-31; telling the judge it is three weeks
later would make genuinely fresh results read as stale and would score the
delay rather than the vendor.

Nothing here writes to data/vannaris.db. It is opened read-only.

Usage:  python experiments/pairwise_experiment.py [--pilot N] [--arm a|b|both]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.judge.ensemble import (  # noqa: E402
    JUDGES,
    RUBRIC,
    SNIPPET_CHARS,
    _call_with_retry,
    build_prompt,
    make_judge_semaphores,
)
from src.vendors.base import ResponseMode, SearchResponse, SearchResult  # noqa: E402

RUN_ID = "50fbea16-fb03-4e26-bcd1-40c1d40bd871"   # 2026-W31, the published run
SET_ID = "96afde9bfef3"                            # the human-labelled pairwise set
TODAY = "2026-07-31"                               # the run's date — see docstring
PAIR_B = ("exa", "perplexity")                     # the pair the table cannot resolve

# What the human's 280 screens established, for comparison in the report.
HUMAN = {"concordance": 0.7905, "ci95": [0.7180, 0.8483], "n_scored": 148,
         "position_bias_side_rate": 0.0, "self_agreement": 1.0}


# --------------------------------------------------------------- the prompt
# Spliced, not retyped. Every one of these asserts has one job: if someone edits
# `ensemble.RUBRIC`, this file must fail loudly rather than quietly compare a
# comparative judge against a rubric that has moved underneath it.

def _slice(start: str, end: str) -> str:
    i, j = RUBRIC.find(start), RUBRIC.find(end)
    assert i != -1, f"rubric marker moved: {start!r}"
    assert j > i, f"rubric marker moved: {end!r}"
    return RUBRIC[i:j]


DATE_BLOCK = _slice("TODAY'S DATE IS", "Query: {query}").strip()
DIMENSIONS = _slice("relevance —", "overall —").strip()
LENGTH_NORM = _slice("LENGTH NORMALISATION:", "Return ONLY").strip()

# The human's instruction, verbatim from src/calibrate_pair_ui.html, so the
# comparative judge is answering the same question the human answered rather
# than a reworded cousin of it.
HUMAN_INSTRUCTION = (
    "You are judging the search results, not writing an answer yourself. Both "
    "responses answer the same question. Pick the one that would serve a reader "
    "better — and say they are about the same whenever that is the honest "
    "answer. A forced choice between two responses you cannot separate is a "
    "coin flip."
)

PAIRWISE_RUBRIC = """You are comparing how well two web-search APIs answered the \
same query. You are grading the SEARCH RESULTS, not writing an answer yourself.

{date_block}

Query: {query}
{gold_block}
{instruction}

Weigh the same three things the reader would:

{dimensions}

{length_norm}

=== RESPONSE A === ({n_a} result(s))
{payload_a}

=== RESPONSE B === ({n_b} result(s))
{payload_b}

Return ONLY a JSON object, no prose, no markdown fence:
{{"choice": "<A, B, or same>", "rationale": "<one short sentence, max 20 words>"}}"""


def _payload(resp: SearchResponse) -> str:
    """The vendor payload exactly as the absolute judge renders it.

    Mirrors build_prompt's body rather than importing it, because build_prompt
    returns a whole rubric. The assertion below is what keeps the two honest:
    build_prompt publishes the payload length it scored, so any drift in
    formatting, ordering or the snippet cap shows up as a mismatch here.
    """
    lines: list[str] = []
    if resp.answer:
        lines.append("SYNTHESIZED ANSWER:")
        lines.append(resp.answer.strip())
        lines.append("")
    if resp.results:
        lines.append("RESULTS:")
        for r in resp.results:
            date = f" [{r.published_at}]" if r.published_at else ""
            title = r.title or "(no title)"
            lines.append(f"{r.rank + 1}. {title}{date}")
            lines.append(f"   {r.url}")
            if r.snippet:
                lines.append(f"   {r.snippet.strip()[:SNIPPET_CHARS]}")
    return "\n".join(lines) if lines else "(the API returned nothing)"


def check_payload_matches_production(responses: dict[str, SearchResponse]) -> None:
    for resp in responses.values():
        _, scored_chars = build_prompt(resp, "x", None, TODAY)
        assert len(_payload(resp)) == scored_chars, (
            f"payload rendering drifted from build_prompt for "
            f"{resp.vendor}/{resp.query_id}: {len(_payload(resp))} != {scored_chars}"
        )


def build_pair_prompt(a: SearchResponse, b: SearchResponse,
                      query: str, gold: str | None) -> str:
    return PAIRWISE_RUBRIC.format(
        date_block=DATE_BLOCK.format(today=TODAY),
        query=query,
        gold_block=(f"Known correct answer (for your reference): {gold}\n" if gold else ""),
        instruction=HUMAN_INSTRUCTION,
        dimensions=DIMENSIONS,
        length_norm=LENGTH_NORM,
        n_a=len(a.results), payload_a=_payload(a),
        n_b=len(b.results), payload_b=_payload(b),
    )


# ------------------------------------------------------------------- loading

def load_by_id(conn, run_id: str) -> dict[str, SearchResponse]:
    """`runner.load_responses`, but keyed by row id.

    The calibration pairs reference responses by id, and load_responses does not
    return one. Reconstruction is otherwise identical.
    """
    out: dict[str, SearchResponse] = {}
    for row in conn.execute(
        "SELECT id, query_id, vendor, response_mode, answer, citations, results, "
        "error FROM raw_responses WHERE run_id = ?", (run_id,)
    ):
        resp = SearchResponse(
            vendor=row["vendor"], query_id=row["query_id"],
            response_mode=ResponseMode(row["response_mode"]),
            results=[SearchResult(url=x["url"], rank=x["rank"], title=x.get("title"),
                                  snippet=x.get("snippet"),
                                  published_at=x.get("published_at"))
                     for x in json.loads(row["results"] or "[]")],
            answer=row["answer"], citations=json.loads(row["citations"] or "[]"),
            cost_usd=0.0, error=row["error"],
        )
        out[row["id"]] = resp
    return out


# ------------------------------------------------------------------- judging

_VALID = {"a": "A", "b": "B", "same": "same", "tie": "same", "neither": "same"}


def parse_choice(data: dict) -> str | None:
    raw = data.get("choice")
    if not isinstance(raw, str):
        return None
    return _VALID.get(raw.strip().lower().strip('."'))


async def judge_pair(client, keys, sems, family, model, prompt) -> dict:
    # Held across the retries, exactly as score_one does it. The first run of
    # this file took `sems` and never acquired it, and lost 49% of OpenAI's
    # calls in arm A and 70% in arm B to 429s — the same failure the production
    # path was hardened against twice (JUDGE_LIMITS, and the W33 post-mortem in
    # ensemble.py). These prompts carry two payloads at ~3,200 tokens against
    # the single-payload rubric's ~1,624, so the token-rate ceiling binds about
    # twice as hard here, not half as much.
    try:
        async with sems[family]:
            data, pt, ot, served = await _call_with_retry(family, client, keys[family],
                                                          model, prompt)
    except Exception as exc:  # noqa: BLE001 — a judge failing is data, not a crash
        return {"family": family, "choice": None, "error": type(exc).__name__ + ": " + str(exc)[:120]}
    return {"family": family, "choice": parse_choice(data),
            "rationale": str(data.get("rationale", ""))[:200] or None,
            "prompt_tokens": pt, "output_tokens": ot, "model_returned": served,
            "error": None if parse_choice(data) else f"unparsed choice: {data.get('choice')!r}"}


async def judge_all(client, keys, sems, jobs: list[dict], label: str) -> list[dict]:
    """One job = one (pair, orientation). All three families judge it."""
    gate = asyncio.Semaphore(16)
    done = 0

    async def one(job):
        async with gate:
            votes = await asyncio.gather(*(
                judge_pair(client, keys, sems, fam, mdl, job["prompt"])
                for fam, mdl in JUDGES))
        return job, votes

    out = []
    for coro in asyncio.as_completed([one(j) for j in jobs]):
        job, votes = await coro
        done += 1
        print(f"\r  {label}: {done}/{len(jobs)} screens", end="", flush=True)
        out.append({k: v for k, v in job.items() if k != "prompt"} |
                   {"votes": [{k: v for k, v in w.items()
                               if k in ("family", "choice", "error")} for w in votes],
                    "tokens": sum((w.get("prompt_tokens") or 0) + (w.get("output_tokens") or 0)
                                  for w in votes)})
    print()
    return out


def majority(votes: list[dict]) -> str | None:
    """The ensemble's comparative verdict: a strict majority of the three.

    No majority is `None` — an unresolved screen, not a tie. A tie is three
    judges agreeing the responses are the same; a None is three judges failing
    to agree on anything, and collapsing the two would report disagreement as
    a finding about the vendors.
    """
    counts = defaultdict(int)
    for v in votes:
        if v["choice"]:
            counts[v["choice"]] += 1
    if not counts:
        return None
    top, n = max(counts.items(), key=lambda kv: kv[1])
    return top if n >= 2 else None


# ------------------------------------------------------------------ analysis

def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def analyse_a(rows: list[dict], human: dict[str, str], strata: dict[str, str]) -> dict:
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_stratum[strata.get(r["pair_id"], "?")].append(r)

    out: dict = {"arm": "A — validation against the human labels"}

    # Concordance on the stratum the human's own headline number is computed on.
    dec = by_stratum["decisive"]
    agree = n = 0
    unresolved = 0
    for r in dec:
        m = majority(r["votes"])
        h = human.get(r["pair_id"])
        if m is None:
            unresolved += 1
            continue
        if h is None or h == "same":
            continue
        n += 1
        agree += int(m == h)
    lo, hi = wilson(agree, n)
    out["decisive"] = {
        "n_scored": n, "agree": agree,
        "concordance": round(agree / n, 4) if n else None,
        "ci95": [lo, hi], "unresolved_by_ensemble": unresolved,
        "human_absolute_baseline": HUMAN["concordance"],
        "human_absolute_ci95": HUMAN["ci95"],
        "beats_absolute": (lo > HUMAN["ci95"][1]) if n else None,
    }

    # Position bias, measured the way the human's was: the swapped stratum is
    # the same comparison presented the other way round.
    sw = [r for r in by_stratum["swapped"] if r.get("source_pair_id")]
    src = {r["pair_id"]: majority(r["votes"]) for r in rows}
    same_side = same_response = comparable = 0
    for r in sw:
        a, b = majority(r["votes"]), src.get(r["source_pair_id"])
        if a is None or b is None:
            continue
        comparable += 1
        same_side += int(a == b)              # same side of the screen = bias
        same_response += int(a != b or a == "same")
    out["position_bias"] = {
        "n": comparable, "picked_same_side": same_side,
        "side_rate": round(same_side / comparable, 4) if comparable else None,
        "ci95": list(wilson(same_side, comparable)),
        "human_side_rate": HUMAN["position_bias_side_rate"],
    }

    # Self-agreement: the repeat stratum is the identical screen shown twice.
    rep = [r for r in by_stratum["repeat"] if r.get("source_pair_id")]
    ag = comp = 0
    for r in rep:
        a, b = majority(r["votes"]), src.get(r["source_pair_id"])
        if a is None or b is None:
            continue
        comp += 1
        ag += int(a == b)
    out["self_agreement"] = {
        "n": comp, "agree": ag,
        "rate": round(ag / comp, 4) if comp else None,
        "ci95": list(wilson(ag, comp)),
        "human_rate": HUMAN["self_agreement"],
    }

    # The reason this experiment exists: the absolute ensemble called these
    # near-ties, and the human separated 48 of 50. Can a comparative judge?
    nt = by_stratum["near_tie"]
    seps = sum(1 for r in nt if majority(r["votes"]) in ("A", "B"))
    out["near_tie"] = {
        "n": len(nt), "separated": seps,
        "separates_pct": round(seps / len(nt), 4) if nt else None,
        "ci95": list(wilson(seps, len(nt))),
        "human_separates_pct": 0.96,
        "note": "the absolute ensemble scored every one of these as a near-tie",
    }

    # Per-family, because a verdict that only holds with one family in the panel
    # is the instability this project already publishes about its own ranking.
    fam: dict[str, dict] = {}
    for f, _ in JUDGES:
        a = n2 = 0
        for r in dec:
            h = human.get(r["pair_id"])
            c = next((v["choice"] for v in r["votes"] if v["family"] == f), None)
            if not c or c == "same" or h is None or h == "same":
                continue
            n2 += 1
            a += int(c == h)
        fam[f] = {"n": n2, "agree": a,
                  "concordance": round(a / n2, 4) if n2 else None,
                  "ci95": list(wilson(a, n2))}
    out["per_family"] = fam
    out["judge_errors"] = sum(1 for r in rows for v in r["votes"] if v["error"])
    return out


def analyse_b(rows: list[dict]) -> dict:
    """Exa vs Perplexity, counting a preference only when both orders agree.

    docs/04's mandated mitigation: every comparison is run in both orders and a
    preference counts only if the verdict survives the swap. Disagreement
    between the orders is recorded as position-dependent, not resolved.
    """
    a_name, b_name = PAIR_B
    by_query: dict[str, dict[str, str | None]] = defaultdict(dict)
    for r in rows:
        by_query[r["query_id"]][r["orientation"]] = majority(r["votes"])

    wins = {a_name: 0, b_name: 0}
    tie = order_dependent = unresolved = 0
    per_cat: dict[str, dict] = defaultdict(lambda: {a_name: 0, b_name: 0, "tie": 0})
    cats = {r["query_id"]: r["category"] for r in rows}

    for qid, o in by_query.items():
        fwd, rev = o.get("a_first"), o.get("b_first")
        if fwd is None or rev is None:
            unresolved += 1
            continue
        # In b_first the vendors are swapped, so "A" there means the second vendor.
        fwd_v = {"A": a_name, "B": b_name, "same": "same"}[fwd]
        rev_v = {"A": b_name, "B": a_name, "same": "same"}[rev]
        if fwd_v != rev_v:
            order_dependent += 1
            continue
        if fwd_v == "same":
            tie += 1
            per_cat[cats[qid]]["tie"] += 1
        else:
            wins[fwd_v] += 1
            per_cat[cats[qid]][fwd_v] += 1

    decided = wins[a_name] + wins[b_name]
    lo, hi = wilson(wins[a_name], decided)
    n_all = len(by_query)
    return {
        "arm": f"B — discrimination, {a_name} vs {b_name}",
        "n_queries": n_all,
        "wins": wins, "tie": tie,
        "order_dependent": order_dependent, "unresolved": unresolved,
        "tie_rate_pct": round(100 * tie / n_all, 1) if n_all else None,
        "decided": decided,
        f"{a_name}_share_of_decided": round(wins[a_name] / decided, 4) if decided else None,
        "ci95_on_share": [lo, hi],
        "separated": bool(decided and (lo > 0.5 or hi < 0.5)),
        "absolute_baseline": {
            "note": "2026-W34 published exa - perplexity = +0.014, se 0.086, "
                    "CI [-0.156, +0.183]; tie rate 74.0%; not separated",
        },
        "per_category": {k: dict(v) for k, v in sorted(per_cat.items())},
        "judge_errors": sum(1 for r in rows for v in r["votes"] if v["error"]),
    }


# ---------------------------------------------------------------------- main

async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=0,
                    help="run only N screens per arm, to validate parsing cheaply")
    ap.add_argument("--arm", choices=["a", "b", "both"], default="both")
    ap.add_argument("--estimate", action="store_true", help="cost only, no calls")
    ap.add_argument("--strip-answer", action="store_true",
                    help="blank every synthesized answer before judging, so both "
                         "sides are results-only (isolates the format confound)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'vannaris.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    responses = load_by_id(conn, RUN_ID)
    # Always against the unmodified responses: this asserts the renderer matches
    # production, and it has to run before anything is blanked or it would be
    # asserting the counterfactual instead.
    check_payload_matches_production(responses)
    queries = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM queries")}

    # The format confound, isolated. Perplexity returns a synthesized answer on
    # 150/150 responses and every other cleared vendor on 0/150, so no subset of
    # the real data holds format constant for this pair — the only way to ask
    # the question is to remove the answer and judge the results list that sits
    # underneath it. That list is real: 10 results on every Perplexity response,
    # snippets on 1,363 of 1,500. This is a counterfactual about what Perplexity
    # RETRIEVED, not a measurement of what it returns, and the write-up says so.
    if args.strip_answer:
        blanked = 0
        for r in responses.values():
            if r.answer:
                r.answer = None
                blanked += 1
        print(f"stripped {blanked} synthesized answers — both sides are results-only\n")

    # ---- Arm A jobs: the human's screens, in the human's orientation.
    pairs = list(conn.execute(
        "SELECT * FROM calibration_pairs WHERE set_id = ? ORDER BY position", (SET_ID,)))
    strata = {p["pair_id"]: p["stratum"] for p in pairs}
    human = {r["pair_id"]: r["choice"] for r in conn.execute(
        "SELECT pair_id, choice FROM pair_labels WHERE set_id = ? AND labeller_kind = 'human'",
        (SET_ID,))}
    # The UI records left/right; the analysis speaks A/B. Left is A.
    human = {k: {"left": "A", "right": "B", "same": "same"}.get(v, v) for k, v in human.items()}

    jobs_a = []
    for p in pairs:
        left, right = responses[p["left_response_id"]], responses[p["right_response_id"]]
        q = queries[left.query_id]
        jobs_a.append({
            "pair_id": p["pair_id"], "stratum": p["stratum"],
            "source_pair_id": p["source_pair_id"], "query_id": left.query_id,
            "category": q["category"],
            "prompt": build_pair_prompt(left, right, q["text"], q.get("gold_answer")),
        })

    # ---- Arm B jobs: exa vs perplexity, every query, both orders.
    a_name, b_name = PAIR_B
    by_qv = {(r.query_id, r.vendor): r for r in responses.values()}
    jobs_b = []
    for qid, q in sorted(queries.items()):
        ra, rb = by_qv.get((qid, a_name)), by_qv.get((qid, b_name))
        if not ra or not rb or ra.error or rb.error:
            continue
        for orient, (x, y) in (("a_first", (ra, rb)), ("b_first", (rb, ra))):
            jobs_b.append({
                "pair_id": f"{qid}:{orient}", "query_id": qid, "category": q["category"],
                "orientation": orient,
                "prompt": build_pair_prompt(x, y, q["text"], q.get("gold_answer")),
            })
    conn.close()

    if args.pilot:
        jobs_a, jobs_b = jobs_a[:args.pilot], jobs_b[:args.pilot * 2]
    if args.arm == "a":
        jobs_b = []
    elif args.arm == "b":
        jobs_a = []

    # ---- Cost, from this repository's own measured basis: W31's judging was
    # 2,217 calls for ~$2.07, i.e. $0.00093/call at a mean prompt of ~1,624
    # tokens. These prompts carry two payloads, so they are priced by their
    # actual measured token count rather than by that per-call average.
    all_jobs = jobs_a + jobs_b
    chars = sum(len(j["prompt"]) for j in all_jobs)
    approx_tokens = chars / 4
    per_call = 0.00093 * (approx_tokens / len(all_jobs) / 1624) if all_jobs else 0
    n_calls = len(all_jobs) * len(JUDGES)
    print(f"arm A: {len(jobs_a)} screens · arm B: {len(jobs_b)} screens "
          f"({len(jobs_b)//2} queries x 2 orders)")
    print(f"{n_calls} judge calls · mean prompt ~{approx_tokens/max(1,len(all_jobs)):.0f} tokens "
          f"· estimated ${per_call * n_calls:.2f}\n")
    if args.estimate:
        return 0

    keys = {"anthropic": os.environ["ANTHROPIC_API_KEY"],
            "openai": os.environ["OPENAI_API_KEY"],
            "google": os.environ["GOOGLE_API_KEY"]}
    sems = make_judge_semaphores()

    # One real call per family before spending anything, and abort unless all
    # three answer. scripts/check_keys.py exists because a run that loses one
    # family mid-flight does not fail — it publishes a thinner panel that looks
    # like a result. This file skipped that lesson on 2026-08-21 and proved it
    # again: the Anthropic balance emptied partway through, 155 of arm B's 300
    # screens fell to a single judge, and $2.40 bought a table that could not be
    # read. A two-family majority is not the ensemble this measures.
    async with httpx.AsyncClient(timeout=60) as client:
        probes = await asyncio.gather(*(
            judge_pair(client, keys, sems, fam, mdl,
                       'Reply with ONLY this JSON: {"choice": "same", "rationale": "probe"}')
            for fam, mdl in JUDGES))
    dead = [f"{p['family']}: {p['error']}" for p in probes if p["error"]]
    if dead:
        print("preflight failed — nothing was spent:")
        for d in dead:
            print("   " + d)
        return 1
    print(f"preflight ok: {', '.join(p['family'] for p in probes)}\n")

    report: dict = {"run_id": RUN_ID, "set_id": SET_ID, "today": TODAY,
                    "judges": [{"family": f, "model": m} for f, m in JUDGES],
                    "pilot": args.pilot or None}
    async with httpx.AsyncClient(timeout=90) as client:
        if jobs_a:
            rows_a = await judge_all(client, keys, sems, jobs_a, "arm A")
            (OUT / "pairwise-2026-08-21-arm-a-raw.json").write_text(json.dumps(rows_a, indent=1))
            report["A"] = analyse_a(rows_a, human, strata)
        if jobs_b:
            rows_b = await judge_all(client, keys, sems, jobs_b, "arm B")
            (OUT / (f"pairwise-2026-08-21-arm-b{'-stripped' if args.strip_answer else ''}-raw.json")).write_text(json.dumps(rows_b, indent=1))
            report["B"] = analyse_b(rows_b)

    print(json.dumps(report, indent=1))
    (OUT / (f"pairwise-2026-08-21{'-stripped' if args.strip_answer else ''}-summary.json")).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
