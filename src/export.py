"""Public data export.

This module is the only thing allowed to turn the database into published
numbers. Everything the site shows is generated here, so there is exactly one
place where "what do we publish" is decided, and no page can quietly hand-write
a figure that the data does not support.

Three rules are enforced in code rather than left to discipline:

1. **No vendor content leaves the raw layer.** `schema.sql` says the raw layer
   is never exported, and `docs/03` recommends publishing derived scores rather
   than republishing retrieved content — that is both the copyright and the
   ToS-storage exposure reduced at once. So the export carries latency, cost,
   result *counts* and scores, and never a URL, title, snippet or synthesized
   answer. `_assert_no_vendor_content` fails the build if that ever slips.

2. **A run is published whole, or not at all.** `weekly_scores` is
   last-writer-wins by (week, vendor, category), which means a two-query smoke
   test can overwrite a 150-query result and leave a published cell that looks
   identical to a real one. The export therefore ignores `weekly_scores` and
   recomputes from `judge_scores` for one explicitly chosen canonical run.

3. **Published weeks accumulate outside the database.** The scheduled run in CI
   starts from a fresh checkout with no database, so the database only ever
   holds the week that just ran. The track record therefore lives in the
   exported per-week JSON committed to the repository, and this module merges
   that history back in. The database is the evidence layer and wins for any
   week it holds; git holds the published record. Committing the database
   instead would mean committing raw vendor content, which is precisely what
   `docs/03` says not to publish.

4. **Cells below the completeness floor are suppressed, not softened.** A cell
   whose queries mostly lack a full three-judge ensemble is published as null
   with its coverage stated, because `median_overall(require_full=True)` exists
   for the same reason: a differently-computed number sitting in the same
   column as a properly-computed one is worse than a missing one.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import statistics
from itertools import combinations
from datetime import datetime, timezone
from pathlib import Path

from . import heldout, storage, inference
from .judge.ensemble import JUDGES, RUBRIC, SNIPPET_CHARS
from .vendors.adapters import REGISTRY, TOP_K

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "vannaris.db"

# Where `python -m src.calibrate export` writes a labelled set. Committed, and
# read from here rather than from the database for the same reason the week
# history is: CI exports from a fresh checkout that has never held a labelling
# session, and a figure that only exists on one laptop is not published.
LABELS_DIR = ROOT / "labels"

# A (vendor, category) cell needs this share of its queries carrying a complete
# three-judge ensemble before it is published. 0.6 is deliberately permissive —
# the point is to catch a smoke run or a rate-limit collapse, not to reject a
# real run that lost a handful of calls. The actual coverage is published next
# to every cell regardless, so a reader can apply a stricter bar themselves.
MIN_CELL_COVERAGE = 0.60

# A run must cover at least this many queries per category to be a candidate
# for publication at all. Below it the run is a smoke test.
MIN_QUERIES_PER_CATEGORY = 10

# ...and at least this share of its responses must carry a complete three-judge
# ensemble. Same floor as MIN_CELL_COVERAGE and as runner.MIN_COMPLETE_SHARE,
# deliberately: the runner tells a scheduler "this run is not publishable" by
# exiting non-zero, and that statement is only true if this module agrees. A
# run below the floor would otherwise still be selected as its week's canonical
# run and then publish a table of suppressed nulls.
MIN_RUN_COMPLETENESS = 0.60

# Files in the data directory that are a published week, as opposed to the
# generated bundle/latest files that sit beside them.
_WEEK_FILE = re.compile(r"^(\d{4}-W\d{2})\.json$")

# The repository, public since 2026-08-04. Six sentences across the site promise
# the reader can go and read the harness — including the one that says the
# withheld set's hash is committed before it runs, which is the entire basis for
# trusting a private score and was unverifiable by anyone outside while this was
# None. scripts/check-quality.mjs now fails the build if those claims are on a
# page while this is unset, so the two cannot drift apart again.
REPO_URL: str | None = "https://github.com/feruzkarimovv/vannaris"

# What each vendor's per-query cost in this benchmark actually is, and on what
# assumption. This exists because the headline "23x cheaper" figure divided a
# vendor-reported invoice by a hardcoded constant, and the constant was the
# least-verified price in the whole analysis: Serper's $0.0003 is its top
# volume tier, which needs a commitment in the low thousands per month, while
# Exa's $0.007 is list. Like for like — both pay-as-you-go — the spread is
# closer to 7x. That is still the strongest finding on the site; it is just not
# 23x, and the difference is the kind a reader checks in one click.
#
# `basis` is what the benchmark is billed at, `payg` is the undiscounted rate.
PRICING = {
    "exa": {"basis_per_query_usd": 0.007, "payg_per_query_usd": 0.007,
            "tier": "list / pay-as-you-go", "source": "https://exa.ai/pricing",
            "reported_by_vendor": True},
    "perplexity": {"basis_per_query_usd": 0.008, "payg_per_query_usd": 0.008,
                   "tier": "Sonar, low search context", "source": "https://docs.perplexity.ai/guides/pricing",
                   "reported_by_vendor": True},
    "serper": {"basis_per_query_usd": 0.0003, "payg_per_query_usd": 0.001,
               "tier": "top volume tier ($0.30/1,000); PAYG is ~$1/1,000",
               "source": "https://serper.dev/pricing", "reported_by_vendor": False},
    "linkup": {"basis_per_query_usd": 0.005, "payg_per_query_usd": 0.005,
               "tier": "standard depth", "source": "https://linkup.so/pricing",
               "reported_by_vendor": False},
    "youcom": {"basis_per_query_usd": 0.005, "payg_per_query_usd": 0.005,
               "tier": "flat $5/1,000 calls", "source": "https://api.you.com",
               "reported_by_vendor": False},
}


def build_cost_spread(totals: list[dict]) -> dict:
    """The cost spread, on both bases, so neither is quotable alone."""
    priced = [t for t in totals if t.get("cost_per_query_usd")]
    if len(priced) < 2:
        return {}
    dearest = max(priced, key=lambda t: t["cost_per_query_usd"])
    cheapest = min(priced, key=lambda t: t["cost_per_query_usd"])

    def payg(v):
        p = PRICING.get(v)
        return p["payg_per_query_usd"] if p else None

    a, b = payg(dearest["vendor"]), payg(cheapest["vendor"])
    return {
        "dearest": dearest["vendor"], "cheapest": cheapest["vendor"],
        "dearest_per_query_usd": dearest["cost_per_query_usd"],
        "cheapest_per_query_usd": cheapest["cost_per_query_usd"],
        # As billed to this benchmark, which is what the run measured.
        "as_billed_ratio": round(dearest["cost_per_query_usd"] / cheapest["cost_per_query_usd"], 1),
        # Both at undiscounted rates, which is what a reader signing up today
        # would pay, and the honest number to lead with.
        "like_for_like_ratio": round(a / b, 1) if a and b else None,
        "cheapest_tier": (PRICING.get(cheapest["vendor"]) or {}).get("tier"),
    }


VENDOR_META = {
    "exa":        {"label": "Exa",        "docs": "https://exa.ai"},
    "perplexity": {"label": "Perplexity", "docs": "https://docs.perplexity.ai",
                   "note": "Sonar. Returns prose and a ranked list; both are included in the historical judge payload."},
    "serper":     {"label": "Serper",     "docs": "https://serper.dev"},
    "linkup":     {"label": "Linkup",     "docs": "https://linkup.so",
                   "note": "Standard depth, not deep search — a different product tier."},
    "youcom":     {"label": "You.com",    "docs": "https://api.you.com"},
}

CATEGORY_META = {
    "general_facts":  {"label": "General facts",
                       "blurb": "Short factual questions with a known answer and a checkable source."},
    "breaking_news":  {"label": "Breaking news",
                       "blurb": "Perpetually-current questions with no fixed answer. Graded on source recency, not answer match."},
    "code_technical": {"label": "Code & technical",
                       "blurb": "Version-specific library and API questions, where documentation drift shows up."},
    "local_shopping": {"label": "Local & shopping",
                       "blurb": "Product and place queries where the answer is a live listing rather than a document."},
    "multi_hop":      {"label": "Multi-hop",
                       "blurb": "Questions that need two or more facts connected across separate sources."},
    "long_tail":      {"label": "Long-tail research",
                       "blurb": "Obscure questions where the answer exists but is not the first page of results."},
}

# Order the site displays categories in: easiest to hardest, so the quality
# cliff at the bottom is legible as a slope rather than an alphabetical accident.
CATEGORY_ORDER = ["general_facts", "breaking_news", "local_shopping",
                  "code_technical", "multi_hop", "long_tail"]

# Anything a vendor wrote. Never allowed into an exported row.
_FORBIDDEN_KEYS = {"answer", "citations", "results", "raw_payload", "snippet",
                   "title", "url", "rationale"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _median(vals: list[float]) -> float:
    vals = sorted(vals)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def connect(db: Path) -> sqlite3.Connection:
    # create=False: exporting must never be the thing that brings a database
    # into existence. An empty export is a signal, not something to paper over.
    conn = storage.connect(db, create=False)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------- run selection

def candidate_runs(conn: sqlite3.Connection) -> list[dict]:
    """Every run, annotated with how complete it actually is.

    Completeness here means responses carrying all three judges, because that
    is the only kind of response that contributes to a published score.
    """
    runs = []
    for r in conn.execute("SELECT * FROM runs ORDER BY started_at"):
        # Public questions only. Every figure below decides either what gets
        # published or whether a run is fit to publish, and both have to be
        # true of the questions a reader can actually see — a run that covered
        # every category only by counting withheld questions is not a run whose
        # table anyone can reproduce. Held-out coverage is counted separately.
        stats = conn.execute(
            """
            SELECT COUNT(*) AS responses,
                   SUM(CASE WHEN n = ? THEN 1 ELSE 0 END) AS complete,
                   COUNT(DISTINCT query_id) AS queries,
                   COUNT(DISTINCT vendor) AS vendors
            FROM (SELECT rr.id, rr.query_id, rr.vendor, COUNT(js.id) AS n
                  FROM raw_responses rr
                  JOIN response_queries q ON q.response_id = rr.id
                  LEFT JOIN judge_scores js ON js.response_id = rr.id
                  WHERE rr.run_id = ? AND COALESCE(q.held_out, 0) = 0
                  GROUP BY rr.id)
            """,
            (len(JUDGES), r["id"]),
        ).fetchone()
        per_cat = conn.execute(
            """
            SELECT q.category, COUNT(DISTINCT rr.query_id) AS n
            FROM raw_responses rr JOIN response_queries q ON q.response_id = rr.id
            WHERE rr.run_id = ? AND COALESCE(q.held_out, 0) = 0
            GROUP BY q.category
            """,
            (r["id"],),
        ).fetchall()
        held = conn.execute(
            """
            SELECT COUNT(DISTINCT rr.query_id) AS queries, COUNT(*) AS responses
            FROM raw_responses rr JOIN response_queries q ON q.response_id = rr.id
            WHERE rr.run_id = ? AND COALESCE(q.held_out, 0) = 1
            """,
            (r["id"],),
        ).fetchone()
        responses, complete = stats["responses"] or 0, stats["complete"] or 0
        runs.append({
            "id": r["id"],
            "week": r["week"],
            "started_at": r["started_at"],
            "query_set_hash": r["query_set_hash"],
            # NULL for runs that pre-date the column — reported as "unknown"
            # rather than assumed, since this field is what the site's cadence
            # claim rests on.
            "trigger": r["trigger"] if "trigger" in r.keys() else None,
            # Which withheld set ran with it, if any. Same treatment: NULL means
            # a run from before the set existed, not a run that skipped it.
            "heldout_set": r["heldout_set"] if "heldout_set" in r.keys() else None,
            "retrieval_finished_at": r["retrieval_finished_at"] if "retrieval_finished_at" in r.keys() else None,
            "status": r["status"] if "status" in r.keys() else None,
            "methodology": run_methodology(conn, r["id"], r["query_set_hash"]),
            "responses": responses,
            "complete": complete,
            "completeness": round(complete / responses, 3) if responses else 0.0,
            "queries": stats["queries"] or 0,
            "vendors": stats["vendors"] or 0,
            "heldout_queries": held["queries"] or 0,
            "min_per_category": min([c["n"] for c in per_cat], default=0),
            "categories": len(per_cat),
        })
    return runs


def run_methodology(conn: sqlite3.Connection, run_id: str, query_hash: str) -> dict:
    """Known recorded provenance; never fill old protocol gaps from today's code."""
    columns = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
    raw = conn.execute("SELECT provenance FROM runs WHERE id=?", (run_id,)).fetchone()[0] if "provenance" in columns else None
    provenance = json.loads(raw) if raw else None
    has_attempts = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='judging_attempts'").fetchone()
    attempts = []
    if has_attempts:
        for attempt in conn.execute("SELECT protocol_hash, provenance FROM judging_attempts WHERE run_id=? ORDER BY started_at", (run_id,)):
            metadata = json.loads(attempt[1]) if attempt[1] else {}
            attempts.append({"protocol_hash": attempt[0], **metadata})
    return {
        "version": attempts[-1]["protocol_hash"] if attempts else "legacy_unrecorded",
        "query_set_hash": query_hash,
        "provenance_status": "recorded" if provenance and attempts else "legacy_partial",
        "retrieval_provenance": provenance,
        "judging_protocols": attempts,
    }


def canonical_run(runs: list[dict], week: str) -> dict | None:
    """The one run per week whose numbers get published.

    Chosen, not inherited: a week can contain smoke tests, aborted runs and one
    real run, and picking "the most recent" would publish whichever happened to
    be last. Eligibility is a floor on coverage; among eligible runs the one
    with the most complete three-judge responses wins.
    """
    eligible = [
        r for r in runs
        if r["week"] == week
        and r["min_per_category"] >= MIN_QUERIES_PER_CATEGORY
        and r["categories"] >= len(CATEGORY_META)
        and r["completeness"] >= MIN_RUN_COMPLETENESS
        and retrieval_is_publishable(r)
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda r: (r["complete"], r["started_at"]))


def retrieval_is_publishable(run: dict) -> bool:
    """New runs must finish the planned retrieval, not only judge its subset.

    The legacy NULL marker means unknown because it was never recorded. New
    runs freeze the full workload before fetching; their NULL marker means an
    interrupted retrieval, even when every response so far has three scores.
    """
    provenance = (run.get("methodology") or {}).get("retrieval_provenance") or {}
    return (provenance.get("query_snapshot") != "immutable_per_run"
            or bool(run.get("retrieval_finished_at")))


# ------------------------------------------------------------------ recompute

def load_run(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """Per-response rows for one run, with each judge's `overall` attached."""
    rows = conn.execute(
        """
        SELECT rr.id, rr.query_id, rr.vendor, rr.response_mode, rr.latency_ms,
               rr.cost_usd, rr.cost_source, rr.error, rr.results, q.category,
               COALESCE(q.held_out, 0) AS held_out
        FROM raw_responses rr JOIN response_queries q ON q.response_id = rr.id
        WHERE rr.run_id = ?
        """,
        (run_id,),
    ).fetchall()

    scores: dict[str, list[sqlite3.Row]] = {}
    for s in conn.execute(
        """
        SELECT js.* FROM judge_scores js
        JOIN raw_responses rr ON rr.id = js.response_id
        WHERE rr.run_id = ?
        """,
        (run_id,),
    ):
        scores.setdefault(s["response_id"], []).append(s)

    out = []
    for r in rows:
        js = scores.get(r["id"], [])
        overalls = [s["overall"] for s in js if s["overall"] is not None]
        # n_results is a count, not content — safe to publish, and it is the
        # only way a reader can see that every vendor was scored at the same
        # depth rather than taking the top-10 normalisation on trust.
        try:
            n_results = len(json.loads(r["results"] or "[]"))
        except (TypeError, ValueError):
            n_results = 0
        out.append({
            "response_id": r["id"],
            "query_id": r["query_id"],
            "category": r["category"],
            "held_out": bool(r["held_out"]),
            "vendor": r["vendor"],
            "response_mode": r["response_mode"],
            "n_results": n_results,
            "latency_ms": r["latency_ms"],
            "cost_usd": r["cost_usd"],
            "cost_source": r["cost_source"],
            "error": r["error"],
            "judges": {s["judge_family"]: s for s in js},
            "complete": len(overalls) == len(JUDGES),
            "median": _median(overalls) if len(overalls) == len(JUDGES) else None,
        })
    return out


def paired_difference(rows: list[dict], a: str, b: str,
                      category: str | None = None) -> dict | None:
    """Category-balanced paired-query estimate; multiplicity is applied below.

    A comparison is formed on matched complete ensembles, not two independently
    retained vendor means. Overall estimates require every declared category;
    a vendor missing a category cannot silently receive a different workload.
    """
    cats = [category] if category is not None else CATEGORY_ORDER
    by_query: dict[tuple[str, str], dict[str, float]] = {}
    for r in rows:
        if r["category"] not in cats or r["median"] is None or r["vendor"] not in (a, b):
            continue
        by_query.setdefault((r["category"], r["query_id"]), {})[r["vendor"]] = r["median"]
    grouped = []
    counts = {}
    for cat in cats:
        diffs = tuple(q[a] - q[b] for (c, _), q in sorted(by_query.items())
                      if c == cat and a in q and b in q)
        counts[cat] = len(diffs)
        if len(diffs) < 2:
            return None
        grouped.append(diffs)
    groups = tuple(grouped)
    label = f"paired:{category or 'overall'}:{a}:{b}:{groups}"
    interval = inference.bootstrap_mean(groups, label)
    tested = inference.paired_sign_flip(groups, label)
    mean = statistics.mean(statistics.mean(g) for g in groups)
    return {
        "n_common": sum(counts.values()),
        "n_by_category": counts,
        "mean_diff": round(mean, 3),
        "se": interval["se"],
        "ci95": interval["ci95"],
        "interval_method": "paired query bootstrap, percentile 95%",
        **tested,
        # Standalone estimates make no selection-adjusted separation claim.
        "p_adjusted": None,
        "separated": False,
    }


def comparison_key(a: str, b: str, category: str | None = None) -> tuple:
    return category, *sorted((a, b))


def build_comparisons(rows: list[dict]) -> dict[tuple, dict]:
    """One fixed Holm family: all pairs x (every category plus overall).

    Even a suppressed or unmatched comparison occupies its predeclared slot.
    Neither the winner nor the size of the family is chosen from p-values.
    """
    vendors = sorted({r["vendor"] for r in rows})
    qualified = {}
    for vendor in vendors:
        for cat in CATEGORY_ORDER:
            rs = [r for r in rows if r["vendor"] == vendor and r["category"] == cat]
            qualified[vendor, cat] = bool(rs) and sum(r["median"] is not None for r in rs) / len(rs) >= MIN_CELL_COVERAGE
    entries = {}
    for category in [None, *CATEGORY_ORDER]:
        needed = [category] if category is not None else CATEGORY_ORDER
        for a, b in combinations(vendors, 2):
            eligible = all(qualified.get((v, c)) for v in (a, b) for c in needed)
            cmp = paired_difference(rows, a, b, category) if eligible else None
            entries[comparison_key(a, b, category)] = {
                "above": a, "below": b, "category": category,
                "status": "estimated" if cmp else "insufficient_coverage_or_pairs",
                **(cmp or {"n_common": 0, "ci95": None, "mean_diff": None,
                           "p_value": None, "p_adjusted": None, "separated": False}),
            }
    adjusted = inference.holm_adjust([c["p_value"] for c in entries.values()])
    for cmp, p in zip(entries.values(), adjusted):
        cmp["p_adjusted"] = round(p, 6) if p is not None else None
        cmp["comparison_family_size"] = len(entries)
        cmp["multiplicity"] = "Holm family-wise alpha 0.05"
        ci = cmp["ci95"]
        cmp["separated"] = bool(p is not None and p <= inference.ALPHA
                                and ci and (ci[0] > 0 or ci[1] < 0))
    return entries


def orient_comparison(comparisons: dict[tuple, dict], a: str, b: str,
                      category: str | None = None) -> dict | None:
    cmp = comparisons.get(comparison_key(a, b, category))
    if cmp is None or cmp["status"] != "estimated":
        return None
    cmp = {**cmp, "above": a, "below": b}
    if a > b:
        cmp["mean_diff"] = -cmp["mean_diff"]
        if cmp.get("ci95"):
            cmp["ci95"] = [-cmp["ci95"][1], -cmp["ci95"][0]]
    return cmp


def build_tiers(rows: list[dict], ranking: list[str],
                category: str | None = None,
                comparisons: dict[tuple, dict] | None = None) -> list[dict]:
    """Display groups with no resolved internal comparison, never equivalence.

    Non-significance is not transitive. Check every existing member, not only
    the group's leader, and disclose that unresolved also includes thin pairs.
    """
    comparisons = comparisons if comparisons is not None else build_comparisons(rows)
    tiers: list[dict] = []
    leader: str | None = None
    for vendor in ranking:
        if leader is None:
            tiers.append({"tier": 1, "vendors": [vendor]})
            leader = vendor
            continue
        resolved = any((orient_comparison(comparisons, member, vendor, category) or {}).get("separated")
                       for member in tiers[-1]["vendors"])
        if resolved:
            tiers.append({"tier": len(tiers) + 1, "vendors": [vendor]})
            leader = vendor
        else:
            tiers[-1]["vendors"].append(vendor)
    return tiers


def build_cells(rows: list[dict], comparisons: dict[tuple, dict] | None = None) -> list[dict]:
    """(vendor, category) cells, recomputed from per-judge scores."""
    comparisons = comparisons if comparisons is not None else build_comparisons(rows)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        grouped.setdefault((r["vendor"], r["category"]), []).append(r)

    cells = []
    for (vendor, category), rs in grouped.items():
        scored = [r["median"] for r in rs if r["median"] is not None]
        coverage = len(scored) / len(rs) if rs else 0.0
        lat = [r["latency_ms"] for r in rs if r["latency_ms"] is not None]
        # How much the queries inside a cell disagree with each other. A cell is
        # at most 25 questions scored on a coarse integer scale, so a published
        # difference of 0.03 between two cells is not a difference; without a
        # dispersion figure beside it there is no way for a reader to know that,
        # and the site was rendering three decimals and a rank badge over it.
        sd = statistics.stdev(scored) if len(scored) > 1 else None
        se = sd / math.sqrt(len(scored)) if sd is not None else None
        interval = inference.bootstrap_mean((tuple(sorted(scored)),), f"cell:{vendor}:{category}")
        n_errors = sum(1 for r in rs if r["error"])
        cells.append({
            "vendor": vendor,
            "category": category,
            # Suppressed rather than approximated when coverage is thin.
            "score": round(statistics.mean(scored), 3) if coverage >= MIN_CELL_COVERAGE else None,
            "ci95": interval["ci95"] if coverage >= MIN_CELL_COVERAGE else None,
            "interval_method": "query bootstrap, percentile 95%",
            "status": "published" if coverage >= MIN_CELL_COVERAGE else "insufficient_judge_coverage",
            "sd": round(sd, 3) if sd is not None else None,
            "se": round(se, 3) if se is not None else None,
            "n_queries": len(rs),
            "n_scored": len(scored),
            "coverage": round(coverage, 3),
            "n_errors": n_errors,
            "n_vendor_success": len(rs) - n_errors,
            "availability": round((len(rs) - n_errors) / len(rs), 4) if rs else None,
            "n_missing_judgements": sum(r["median"] is None and not r["error"] for r in rs),
            "p50_latency_ms": int(statistics.median(lat)) if lat else None,
            "cost_usd": round(sum(r["cost_usd"] or 0 for r in rs), 5),
        })

    # Gap to the best vendor in the same category — the number that decides
    # whether routing on quality is worth anything at all.
    best: dict[str, tuple[str, float]] = {}
    for c in cells:
        if c["score"] is not None:
            cur = best.get(c["category"])
            if cur is None or c["score"] > cur[1]:
                best[c["category"]] = (c["vendor"], c["score"])
    for c in cells:
        top = best.get(c["category"])
        if c["score"] is not None and top:
            leader, top_score = top
            c["delta_from_best"] = round(top_score - c["score"], 3)
            c["pct_of_best"] = round(100 * c["score"] / top_score, 1) if top_score else None
            c["relative_score_note"] = "ratio of rubric scores; not a percentage of task quality"
            c["best_vendor"] = leader
            # Whether that gap is a gap. Four of six category leaders on the
            # first run are not distinguishable from second place, and the
            # deltas were being published to three decimals with no way to tell
            # which ones meant anything.
            if c["vendor"] == leader:
                c["separated_from_best"] = None      # not a comparison with itself
                c["paired"] = None
            else:
                cmp = orient_comparison(comparisons, leader, c["vendor"], c["category"])
                c["separated_from_best"] = cmp["separated"] if cmp else None
                c["paired"] = cmp
        else:
            c["delta_from_best"] = None
            c["pct_of_best"] = None
            c["best_vendor"] = None
            c["separated_from_best"] = None
            c["paired"] = None
    return sorted(cells, key=lambda c: (CATEGORY_ORDER.index(c["category"]), -(c["score"] or 0)))


def build_routing_gain(cells: list[dict], by_category: list[dict]) -> dict:
    """What routing on quality per category is actually worth.

    The question this project was started to answer, answered against its own
    data. A per-category oracle -- send each category to whichever vendor scores
    highest in it -- is compared against the best single vendor used for
    everything. Where one vendor is top everywhere the two are the same table
    and the gain is zero, which is a fact about the routing product and not a
    quality claim about the vendor.

    Rounded last, from unrounded means. Rounding either side first produces a
    gain of -0.0 on exactly the run this exists to describe.
    """
    published: dict[str, dict[str, float]] = {}
    for c in cells:
        if c["score"] is not None:
            published.setdefault(c["category"], {})[c["vendor"]] = c["score"]
    cats = [c for c in CATEGORY_ORDER if c in published]
    if len(cats) < 2:
        return {}

    # Only vendors with a published cell in every category. A vendor missing a
    # cell has its overall averaged over a different set than the oracle is, so
    # the difference would not be a routing gain.
    complete = sorted(v for v in {v for cat in cats for v in published[cat]}
                      if all(v in published[cat] for cat in cats))
    if not complete:
        return {}

    leaders = [{"category": cat,
                "vendor": max(published[cat], key=lambda v: published[cat][v]),
                "score": max(published[cat].values())}
               for cat in cats]
    oracle = statistics.mean(l["score"] for l in leaders)
    overall = {v: statistics.mean(published[cat][v] for cat in cats) for v in complete}
    best = max(overall, key=lambda v: overall[v])
    gain = round(oracle - overall[best], 3)
    if gain == 0:
        gain = 0.0                      # never publish -0.0

    led: dict[str, int] = {}
    for l in leaders:
        led[l["vendor"]] = led.get(l["vendor"], 0) + 1

    # How many category leads the run can actually resolve, and who shares the
    # top tier. A tier of one is a lead separated from second place.
    top_tier: dict[str, int] = {}
    separated = 0
    for e in by_category:
        first = e["tiers"][0]["vendors"] if e["tiers"] else []
        if len(first) == 1:
            separated += 1
        for v in first:
            top_tier[v] = top_tier.get(v, 0) + 1

    n = len(cats)
    return {
        "n_categories": n,
        "leaders": leaders,
        "categories_led": led,
        "single_leader": next((v for v, k in led.items() if k == n), None),
        "oracle_score": round(oracle, 3),
        "best_single_vendor": best,
        "best_single_score": round(overall[best], 3),
        "gain_points": gain,
        "categories_separated": separated,
        "top_tier_counts": top_tier,
        "top_tier_everywhere": sorted(v for v, k in top_tier.items() if k == n),
    }


def _per_query_winners(rows: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    """Who was best on each query, counting ties as ties.

    Returns (outright, shared): `outright` counts queries where a vendor was the
    sole highest median; `shared` counts queries where it was among the highest,
    ties included.

    This used to be one number, computed by walking the rows and keeping the
    first strict maximum. That is only correct if ties are rare, and here they
    are the norm — the judges emit whole numbers, five vendors are being scored
    on a query set most of them answer well, and roughly two thirds of queries
    end with two or more vendors on the same median. Resolving those by
    iteration order meant `wins` reported the order vendors are declared in
    REGISTRY rather than anything about quality: one vendor was credited with 55
    wins on this run and had won a single query outright.

    So the tie is not broken. It is counted, and published as two columns, and
    the share of queries that tie is published beside them — because a query set
    that cannot separate its vendors on two thirds of its questions is a more
    useful thing to know than any ranking derived from pretending it can.
    """
    by_query: dict[str, dict[str, float]] = {}
    for r in rows:
        if r["median"] is None:
            continue
        by_query.setdefault(r["query_id"], {})[r["vendor"]] = r["median"]

    outright: dict[str, int] = {}
    shared: dict[str, int] = {}
    # Sorted so the result cannot depend on row order even in principle.
    for qid in sorted(by_query):
        scores = by_query[qid]
        top = max(scores.values())
        winners = sorted(v for v, m in scores.items() if m == top)
        if len(winners) == 1:
            outright[winners[0]] = outright.get(winners[0], 0) + 1
        for v in winners:
            shared[v] = shared.get(v, 0) + 1
    return outright, shared


def build_win_stats(rows: list[dict]) -> dict:
    """How often the query set actually separates the vendors.

    Published because it is the honest headline of a five-vendor comparison
    scored on a coarse integer scale: the tie rate bounds how much any
    per-query routing decision could possibly be worth.
    """
    by_query: dict[str, dict[str, float]] = {}
    for r in rows:
        if r["median"] is None:
            continue
        by_query.setdefault(r["query_id"], {})[r["vendor"]] = r["median"]

    # Only queries where more than one vendor was scored can tie or separate;
    # a query with a single surviving ensemble says nothing either way.
    comparable = {q: s for q, s in by_query.items() if len(s) > 1}
    tied = sum(1 for s in comparable.values()
               if sum(1 for m in s.values() if m == max(s.values())) > 1)
    n = len(comparable)
    return {
        "n_queries_compared": n,
        "n_tied": tied,
        "n_separated": n - tied,
        "tie_rate_pct": round(100 * tied / n, 1) if n else None,
    }


def build_vendor_totals(rows: list[dict], cells: list[dict],
                        required_categories: list[str] | None = None) -> list[dict]:
    """Per-vendor roll-up.

    The overall score is the mean of a vendor's six *category* scores, not the
    mean of its 150 query scores. Those differ whenever coverage differs by
    category, and the category mean is the one that matches what the table
    above it shows.
    """
    required = required_categories if required_categories is not None else CATEGORY_ORDER
    vendors = sorted({r["vendor"] for r in rows})
    outright, shared = _per_query_winners(rows)

    totals = []
    for v in vendors:
        vcells = [c for c in cells if c["vendor"] == v and c["score"] is not None]
        vrows = [r for r in rows if r["vendor"] == v]
        lat = [r["latency_ms"] for r in vrows if r["latency_ms"] is not None]
        scored = [r for r in vrows if r["median"] is not None]
        included = [cat for cat in required if any(c["category"] == cat for c in vcells)]
        complete_categories = len(included) == len(required)
        groups = tuple(tuple(sorted(r["median"] for r in scored if r["category"] == cat))
                       for cat in required)
        interval = inference.bootstrap_mean(groups, f"overall:{v}") if complete_categories else {"ci95": None}
        n_errors = sum(1 for r in vrows if r["error"])
        totals.append({
            "vendor": v,
            "label": VENDOR_META.get(v, {}).get("label", v),
            "score": round(statistics.mean(statistics.mean(g) for g in groups), 3) if complete_categories and groups else None,
            "ci95": interval["ci95"],
            "interval_method": "category-stratified query bootstrap, percentile 95%",
            "status": "complete" if complete_categories else "incomplete_categories",
            "included_categories": included,
            "required_categories": list(required),
            "category_coverage": round(len(included) / len(required), 4) if required else 0.0,
            "coverage": round(len(scored) / len(vrows), 4) if vrows else 0.0,
            "p50_latency_ms": int(statistics.median(lat)) if lat else None,
            "cost_usd": round(sum(r["cost_usd"] or 0 for r in vrows), 5),
            "cost_per_query_usd": round(sum(r["cost_usd"] or 0 for r in vrows) / len(vrows), 6) if vrows else None,
            "n_queries": len(vrows),
            "n_scored": len(scored),
            "n_errors": n_errors,
            "n_vendor_success": len(vrows) - n_errors,
            "availability": round((len(vrows) - n_errors) / len(vrows), 4) if vrows else None,
            "n_missing_judgements": sum(r["median"] is None and not r["error"] for r in vrows),
            # Two columns, because one cannot carry this honestly. See
            # _per_query_winners: on this query set most queries end in a tie,
            # and the difference between "won it" and "was among the best" is
            # the difference between 28 and 115.
            "outright_wins": outright.get(v, 0),
            "shared_best": shared.get(v, 0),
            "response_mode": vrows[0]["response_mode"] if vrows else None,
        })
    return sorted(totals, key=lambda t: -(t["score"] or 0))


def _overall_by_vendor(rows: list[dict], score_of) -> dict[str, float]:
    """Vendor overall scores under an alternative scoring rule.

    Mirrors the published aggregation exactly — per-query score, averaged
    within a category, then averaged across categories — so that a ranking
    computed here differs from the published one only because of the judges
    used, never because of how the averaging was done. Cell-coverage
    suppression is deliberately not applied: it would drop different cells for
    different sub-panels and make the variants incomparable with each other.
    """
    cells: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        s = score_of(r)
        if s is not None:
            cells.setdefault((r["vendor"], r["category"]), []).append(s)
    per_vendor: dict[str, list[float]] = {}
    for (vendor, _cat), vals in cells.items():
        per_vendor.setdefault(vendor, []).append(statistics.mean(vals))
    return {v: round(statistics.mean(cs), 3) for v, cs in per_vendor.items()}


def build_robustness(rows: list[dict]) -> dict:
    """Does the ranking survive dropping or isolating a judge family?

    This exists because the site used to assert that it does — "every vendor
    faces every judge, so the ranking survives the spread" — and the export
    published the data that disproves it. The reasoning behind the claim was
    the error: it treats judge bias as a constant offset per judge, when the
    bias interacts with the vendor. One family scoring alone reverses the top
    pair on this run.

    Two different questions, and only one of them has a comfortable answer:

      - *per_family* — score with one family alone. This is the hostile
        reading, and the ranking does not survive it.
      - *leave_one_out* — drop one family, keep the other two. This is the
        question that actually bears on the published number, since the
        published number is a three-judge median, and the ranking does survive
        it.

    Publishing both is the point. The weaker claim is true and checkable; the
    stronger one was neither.
    """
    fams = [f for f, _ in JUDGES]

    def score_of(r, use: set[str]) -> float | None:
        vals = sorted(s["overall"] for f, s in r["judges"].items()
                      if f in use and s["overall"] is not None)
        # Require the whole sub-panel, for the same reason median_overall does:
        # a two-of-three mean sitting beside a three-of-three median in one
        # column is a differently-computed number, not a missing one.
        if len(vals) < len(use):
            return None
        n = len(vals)
        return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2

    def variant(use: set[str]) -> dict:
        means = _overall_by_vendor(rows, lambda r: score_of(r, use))
        return {"means": means, "ranking": sorted(means, key=lambda v: -means[v])}

    base = variant(set(fams))
    per_family = [{"family": f, **variant({f})} for f in fams]
    leave_one_out = [{"dropped": f, **variant(set(fams) - {f})} for f in fams]

    def inverts(v):
        return v["ranking"] != base["ranking"]

    def stable_prefix(variants: list[dict]) -> int:
        """How many leading positions every variant agrees on.

        The blunt "is the whole ranking identical" flag is the wrong resolution
        to publish, and getting this wrong in the safe direction is just as bad
        as getting it wrong in the flattering one. On this run, dropping one
        family leaves the top three untouched and swaps fourth and fifth — so
        "the ranking survives" is false and "nothing survives" is false too.
        What is true, and worth saying, is how deep the agreement goes.
        """
        depth = 0
        for i in range(len(base["ranking"])):
            if all(len(v["ranking"]) > i and v["ranking"][i] == base["ranking"][i]
                   for v in variants):
                depth += 1
            else:
                break
        return depth

    return {
        "baseline_ranking": base["ranking"],
        "per_family": per_family,
        "leave_one_out": leave_one_out,
        "stable_under_single_family": not any(inverts(v) for v in per_family),
        "stable_under_leave_one_out": not any(inverts(v) for v in leave_one_out),
        # The honest resolution: positions agreed on by every variant.
        "stable_prefix_single_family": stable_prefix(per_family),
        "stable_prefix_leave_one_out": stable_prefix(leave_one_out),
        "n_vendors": len(base["ranking"]),
        "families_that_invert_it": [v["family"] for v in per_family if inverts(v)],
        "n_families_that_invert_it": sum(1 for v in per_family if inverts(v)),
        "n_families": len(fams),
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return round(num / (dx * dy), 3) if dx and dy else None


def build_payload_effect(rows: list[dict]) -> dict:
    """Does a bigger payload buy a better score?

    The rubric tells the judges not to reward verbosity, and the obvious
    objection is that saying so does not make it true — especially here, where
    the judge-visible payload differs almost fourfold between the largest and
    smallest vendor. The answer is in the data and was never computed, which
    meant the accusation had no reply.

    Reported two ways, because they answer different questions. *Within* a
    vendor, does a longer response score better — the direct verbosity test,
    free of any vendor effect. *Across* vendors, does mean payload size track
    mean score — which conflates verbosity with whatever else differs between
    vendors, and is the weaker of the two.
    """
    per_vendor = []
    for vendor in sorted({r["vendor"] for r in rows}):
        vrows = [r for r in rows
                 if r["vendor"] == vendor and r["median"] is not None and r["judges"]]
        chars, scores, nres = [], [], []
        for r in vrows:
            sizes = [j["scored_chars"] for j in r["judges"].values()
                     if j["scored_chars"] is not None]
            if not sizes:
                continue
            chars.append(float(max(sizes)))
            scores.append(float(r["median"]))
            nres.append(r["n_results"])
        if not chars:
            continue
        per_vendor.append({
            "vendor": vendor,
            "mean_scored_chars": round(statistics.mean(chars), 1),
            "mean_n_results": round(statistics.mean(nres), 2) if nres else None,
            "mean_score": round(statistics.mean(scores), 3),
            "r_chars_vs_score": _pearson(chars, scores),
            "n": len(chars),
        })

    across = _pearson([v["mean_scored_chars"] for v in per_vendor],
                      [v["mean_score"] for v in per_vendor]) if len(per_vendor) > 2 else None
    within = [v["r_chars_vs_score"] for v in per_vendor if v["r_chars_vs_score"] is not None]
    return {
        "per_vendor": per_vendor,
        "within_vendor_r_min": min(within) if within else None,
        "within_vendor_r_max": max(within) if within else None,
        "across_vendor_r": across,
        "snippet_chars_cap": SNIPPET_CHARS,
        "results_per_query": TOP_K,
    }


def build_judge_stats(rows: list[dict]) -> dict:
    """Judge-family means and disagreement.

    Published on the dashboard rather than buried in the methodology page: a
    1.2-point spread between judge families is the single largest caveat on
    every other number here, and hiding it would make this benchmark exactly
    the kind of thing it exists to be an alternative to.
    """
    families: dict[str, list[float]] = {}
    models: dict[str, str] = {}
    spreads: list[float] = []
    partial_spreads: list[float] = []
    panel_counts: dict[int, int] = {}
    by_cat: dict[str, list[float]] = {}
    pairs: dict[tuple[str, str], list[float]] = {}
    expected = len(rows)

    for r in rows:
        vals = []
        scored: dict[str, float] = {}
        for fam, s in r["judges"].items():
            if s["overall"] is not None:
                families.setdefault(fam, []).append(s["overall"])
                models[fam] = s["judge_model"]
                vals.append(s["overall"])
                scored[fam] = s["overall"]
        panel_counts[len(vals)] = panel_counts.get(len(vals), 0) + 1
        if len(vals) == len(JUDGES) and set(scored) == {f for f, _ in JUDGES}:
            spread = max(vals) - min(vals)
            spreads.append(spread)
            by_cat.setdefault(r["category"], []).append(spread)
            fams = sorted(scored)
            for i, a in enumerate(fams):
                for b in fams[i + 1:]:
                    pairs.setdefault((a, b), []).append(abs(scored[a] - scored[b]))
        elif len(vals) > 1:
            partial_spreads.append(max(vals) - min(vals))

    judges = []
    for fam, model in JUDGES:
        vals = families.get(fam, [])
        judges.append({
            "family": fam,
            "model": models.get(fam, model),
            "mean": round(statistics.mean(vals), 3) if vals else None,
            "n": len(vals),
            "coverage": round(len(vals) / expected, 3) if expected else 0.0,
        })

    means = [j["mean"] for j in judges if j["mean"] is not None]
    return {
        "judges": judges,
        "family_spread": round(max(means) - min(means), 3) if len(means) > 1 else None,
        "mean_disagreement": round(statistics.mean(spreads), 3) if spreads else None,
        "responses_over_3pts": sum(1 for s in spreads if s > 3),
        "n_compared": len(spreads),
        "denominator": "responses with every required judge family",
        "panel_counts": {str(n): panel_counts.get(n, 0) for n in range(len(JUDGES) + 1)},
        "partial_panels": {
            "n_compared": len(partial_spreads),
            "mean_disagreement": round(statistics.mean(partial_spreads), 3) if partial_spreads else None,
            "over_2pt": _rate(partial_spreads, 2),
            "over_3pt": _rate(partial_spreads, 3),
            "note": "available partial panels only; excluded from full-ensemble disagreement",
        },
        # The same disagreement expressed as rates rather than as a mean, and
        # published rather than kept for the methodology page's footnotes.
        #
        # A mean of 1.2 points is easy to read as "the judges broadly agree",
        # which is a claim about the distribution that a mean cannot support:
        # it is equally consistent with every response splitting the judges by
        # a little and with most agreeing exactly while a tenth split by five.
        # Those are different benchmarks. The share of responses over each
        # threshold says which one this is, and it is the number a vendor
        # disputing a rank will go looking for — better that they find it here
        # than derive it from the export and ask why it was not stated.
        "disagreement_rates": {
            "over_1pt": _rate(spreads, 1),
            "over_2pt": _rate(spreads, 2),
            "over_3pt": _rate(spreads, 3),
            "unanimous": round(sum(1 for s in spreads if s == 0) / len(spreads), 4)
                         if spreads else None,
            "median_spread": round(statistics.median(spreads), 3) if spreads else None,
            "p90_spread": round(_pct(spreads, 90), 3) if spreads else None,
        },
        # Where the judges disagree, not just how often. Disagreement is not
        # uniform across the taxonomy — it concentrates in the categories where
        # "good" is least well defined — and a per-category rate is what lets a
        # reader discount the categories the ensemble is least sure about
        # instead of discounting the whole table.
        "disagreement_by_category": [
            {"category": c, "mean": round(statistics.mean(v), 3),
             "over_2pt": _rate(v, 2), "n": len(v)}
            for c, v in sorted(by_cat.items(),
                               key=lambda kv: CATEGORY_ORDER.index(kv[0])
                               if kv[0] in CATEGORY_ORDER else 99)
        ],
        # Which two families disagree, in points of mean absolute difference on
        # responses all three scored. A single "the judges disagree by 1.2"
        # hides whether one family is the outlier or all three are scattered.
        "family_pairs": [
            {"pair": f"{a}/{b}", "mean_abs_diff": round(statistics.mean(d), 3), "n": len(d)}
            for (a, b), d in sorted(pairs.items())
        ],
    }


def _rate(vals: list[float], threshold: float) -> float | None:
    return round(sum(1 for v in vals if v > threshold) / len(vals), 4) if vals else None


def _pct(vals: list[float], p: float) -> float:
    s = sorted(vals)
    if not s:
        return 0.0
    i = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
    return s[i]


def build_heldout(rows: list[dict], run: dict, manifest: dict) -> dict | None:
    """An unmatched public/private distribution-gap diagnostic.

    Equal category weights control category proportions, not question hardness
    within categories. Repeating this gap cannot by itself establish tuning or
    causal overfitting. Its conditional public mean also uses a different
    coverage policy from the publishable overall leaderboard.
    """
    held = [r for r in rows if r["held_out"]]
    if not held:
        return None
    public = [r for r in rows if not r["held_out"]]

    def by_category(rs: list[dict]) -> dict[str, float]:
        cats: dict[str, list[float]] = {}
        for r in rs:
            if r["median"] is not None:
                cats.setdefault(r["category"], []).append(r["median"])
        return {c: statistics.mean(v) for c, v in cats.items()}

    vendors = []
    for v in sorted({r["vendor"] for r in rows}):
        pub = by_category([r for r in public if r["vendor"] == v])
        priv = by_category([r for r in held if r["vendor"] == v])
        shared = sorted(set(pub) & set(priv))
        n_scored = sum(1 for r in held if r["vendor"] == v and r["median"] is not None)
        p = statistics.mean(pub[c] for c in shared) if shared else None
        h = statistics.mean(priv[c] for c in shared) if shared else None
        vendors.append({
            "vendor": v,
            "label": VENDOR_META.get(v, {}).get("label", v),
            "public": round(p, 3) if p is not None else None,
            "heldout": round(h, 3) if h is not None else None,
            "gap": round(p - h, 3) if p is not None and h is not None else None,
            "n_heldout_scored": n_scored,
            "n_categories": len(shared),
            "included_categories": shared,
            "public_mean_policy": "complete ensembles in matched categories; no leaderboard suppression",
        })

    gaps = [v["gap"] for v in vendors if v["gap"] is not None]
    e = next((s for s in manifest.get("sets", []) if s["id"] == run.get("heldout_set")), None)
    return {
        "interpretation": "distribution_gap_diagnostic",
        "supports_overfitting_inference": False,
        "limitations": "question difficulty is unmatched; repeated gaps do not establish vendor tuning",
        "set": e and {
            **{k: e.get(k) for k in ("id", "sha256", "n_queries", "categories",
                                     "committed_at", "retired_week")},
            # Derived, not stored: a set is published exactly when its questions
            # have been written into the repository, and that is the file entry.
            "published": bool(e.get("file")),
        },
        "n_responses": len(held),
        "n_scored": sum(1 for r in held if r["median"] is not None),
        "vendors": sorted(vendors, key=lambda v: -(v["gap"] if v["gap"] is not None else -99)),
        "max_gap": round(max(gaps), 3) if gaps else None,
        "mean_gap": round(statistics.mean(gaps), 3) if gaps else None,
    }


def build_calibration(labels_dir: Path) -> dict | None:
    """The judge-vs-human result, read off the committed label exports.

    This is the one figure on the site that measures the instrument rather than
    the vendors, and until 2026-08-16 it did not exist: every page said the
    judges were unaudited, `docs/12` explained why an agreement figure between
    two models is a weaker and different quantity, and `check-all.sh` held the
    copy down until a human pass cleared chance. One has, so the copy has to
    move — and it moves from here, because a hand-typed 79% would be exactly the
    "encouraging interim number" that gate was written to prevent.

    Three constraints on what leaves this function:

    1. **Read from `labels/`, not from the database.** The labels are committed;
       the database is not, and CI exports from a fresh checkout that has never
       seen a labelling session. The same reason the week history lives in git.
    2. **The same definition of "cleared" as the gate**, field for field —
       `cleared_chance` on a set whose labellers are all human. Two definitions
       of the same word is how a gate ends up guarding a different claim than
       the one on the page.
    3. **Aggregates only.** The per-label notes are a human describing what they
       read, which means they quote vendor-retrieved content; `docs/03` keeps
       that out of the export, and `_assert_no_vendor_content` would not catch
       it because it is prose in a field nobody declared as vendor content.

    Returns None when no human pass has cleared, which is the state every page's
    copy branched on before this existed and still does.
    """
    sets = []
    for f in sorted(labels_dir.glob("*.json")) if labels_dir.is_dir() else []:
        try:
            d = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        # Mirrors scripts/check-all.sh's `cleared`. A set carrying model labels
        # alongside human ones is excluded rather than filtered down to its
        # human rows: the precomputed block would then describe a subset of a
        # file this function cannot re-derive, and `docs/12` is explicit that
        # the two kinds of pass are not the same measurement.
        if d.get("cleared_chance") is not True or d.get("labeller_kinds") != ["human"]:
            continue
        dec = d.get("decisive") or {}
        if not dec.get("n_scored"):
            continue
        sets.append((d.get("created_at") or "", d, f.stem))
    if not sets:
        return None

    _, d, set_id = sorted(sets)[-1]
    labellers = {l.get("labeller") for l in d.get("labels", [])
                 if l.get("labeller_kind") == "human"}
    keep = lambda block, fields: (
        {k: block[k] for k in fields if block.get(k) is not None} if block else None)
    return {
        "set_id": set_id,
        "kind": d.get("kind", "pairwise"),
        # Which run's responses were judged. The calibration is a statement
        # about the ensemble on the material of one run, not a standing
        # property of the judges, and a reader cannot check that without it.
        "run_id": d.get("run_id"),
        "registered_at": d.get("created_at"),
        "blinding": d.get("blinding"),
        "n_screens": d.get("n_items"),
        "n_labellers": len(labellers),
        "n_cleared_sets": len(sets),
        "clears_chance": True,
        # The only stratum an agreement figure may be quoted from — src/calibrate.py
        # prints that above the number and the split survives into the export,
        # because a pooled figure answers neither question the two strata ask.
        "decisive": keep(d.get("decisive"),
                         ("n", "n_scored", "n_human_tied", "agree", "concordance",
                          "ci95", "clears_chance")),
        # Diagnostics, published beside the headline for the same reason the
        # judge-disagreement rates are: self-agreement is the ceiling the
        # headline should be read against, and position bias is the failure that
        # would make the whole exercise meaningless if it were present.
        "near_tie": keep(d.get("near_tie"),
                         ("n", "n_human_separated", "human_separates_pct")),
        "position_bias": keep(d.get("position_bias"),
                              ("n", "picked_same_side", "picked_same_response",
                               "side_rate", "ci95")),
        "self_agreement": keep(d.get("self_agreement"), ("n", "agree", "rate", "ci95")),
    }


# ------------------------------------------------------------------- assembly

def build_availability(rows: list[dict]) -> dict:
    panels: dict[str, set[str]] = {}
    vendors = {r["vendor"] for r in rows}
    for r in rows:
        panels.setdefault(r["query_id"], set())
        if r["median"] is not None:
            panels[r["query_id"]].add(r["vendor"])
    errors = sum(bool(r["error"]) for r in rows)
    return {
        "n_attempted": len(rows),
        "n_vendor_success": len(rows) - errors,
        "n_vendor_errors": errors,
        "vendor_success_rate": round((len(rows) - errors) / len(rows), 4) if rows else None,
        "n_missing_judgements": sum(r["median"] is None and not r["error"] for r in rows),
        "n_queries_all_vendors_scored": sum(len(v) == len(vendors) for v in panels.values()),
        "n_queries": len(panels),
        "quality_policy": "complete judge ensembles conditional on API success; failures are not zero scores",
    }


def build_week(conn: sqlite3.Connection, run: dict, queries: dict[str, dict],
               week_runs: list[dict] | None = None,
               manifest: dict | None = None) -> dict:
    return build_week_from_rows(load_run(conn, run["id"]), run, week_runs, manifest)


def build_week_from_rows(all_rows: list[dict], run: dict,
                         week_runs: list[dict] | None = None,
                         manifest: dict | None = None) -> dict:
    """Shared analysis for original DB observations and verified released CSVs.

    Recalculating derived statistics is not a new retrieval run. The original
    run identity, timestamp and question commitment are always carried forward.
    """
    # Every published figure below is computed from the public questions alone.
    # This one line is the whole publication policy for the withheld set: a
    # reader holding queries.csv and the judge scores must be able to rebuild
    # the table exactly, and they cannot do that if a question they cannot see
    # is inside it. The withheld responses are published too — as scores, in
    # the CSVs, and as the public-versus-held-out gap — just never mixed in.
    rows = [r for r in all_rows if not r["held_out"]]
    comparisons = build_comparisons(rows)
    cells = build_cells(rows, comparisons)
    totals = build_vendor_totals(rows, cells)
    complete = sum(1 for r in rows if r["complete"])
    ranked = [t for t in totals if t["score"] is not None]

    # Per-response detail, for the query-level table on the dashboard. Scores
    # and identifiers only — the query text comes from the published query set,
    # and the vendor's actual results are deliberately not here.
    detail = [
        {
            "q": r["query_id"],
            "v": r["vendor"],
            "s": [
                (r["judges"][fam]["overall"] if fam in r["judges"] else None)
                for fam, _ in JUDGES
            ],
            "m": round(r["median"], 2) if r["median"] is not None else None,
            "l": r["latency_ms"],
            "n": r["n_results"],
            "e": bool(r["error"]),
            "missing_judges": [fam for fam, _ in JUDGES
                               if fam not in r["judges"] or r["judges"][fam]["overall"] is None],
        }
        for r in rows
    ]

    # What the ranking can and cannot resolve, published beside it rather than
    # left for a reader to derive from the CSV and then ask why it was not
    # stated. `tiers` is what the table renders instead of five distinct rank
    # badges; `adjacent` is every neighbouring pair with its paired interval, so
    # the specific claim "this vendor beat that one" is checkable one row at a
    # time. Lifted out of the returned literal because `routing` is computed
    # from `by_category` and the two must not diverge.
    separation = {
        "tier_interpretation": "unresolved comparisons; not evidence of equivalence",
        "incomplete_vendors": [t["vendor"] for t in totals if t["score"] is None],
        "comparisons": list(comparisons.values()),
        "overall_tiers": build_tiers(rows, [t["vendor"] for t in ranked], comparisons=comparisons),
        "adjacent": [
            {
                "above": a["vendor"], "below": b["vendor"],
                **(orient_comparison(comparisons, a["vendor"], b["vendor"]) or {}),
            }
            for a, b in zip(ranked, ranked[1:])
        ],
        "by_category": [
            {
                "category": cat,
                "tiers": build_tiers(
                    rows,
                    [c["vendor"] for c in cells
                     if c["category"] == cat and c["score"] is not None],
                    cat, comparisons),
            }
            for cat in CATEGORY_ORDER
            if any(c["category"] == cat and c["score"] is not None for c in cells)
        ],
    }

    return {
        "week": run["week"],
        "run_id": run["id"],
        "ran_at": run["started_at"],
        "trigger": run.get("trigger"),
        "query_set_hash": run["query_set_hash"],
        "analysis": inference.protocol(),
        "export": {
            "week": run["week"], "licence": "CC BY 4.0",
            "files": [
                {"file": f"judge-scores-{run['week']}.csv", "rows": sum(len(r["judges"]) for r in all_rows),
                 "what": "Original individual judge measurements, including flagged withheld rows."},
                {"file": f"responses-{run['week']}.csv", "rows": len(all_rows),
                 "what": "Original response metadata; no retrieved content."},
                {"file": f"weekly-scores-{run['week']}.csv", "rows": len(cells),
                 "what": "Derived category scores and uncertainty under publication-v3."},
            ],
        },
        "methodology": run.get("methodology") or {
            "version": "legacy_unrecorded",
            "provenance_status": "legacy_partial",
            "query_set_hash": run["query_set_hash"],
            "note": "original scoring settings were not stored as a complete run manifest",
        },
        # Public questions. The site says "N queries go to M vendors" next to a
        # link to the query set, so N has to be the number of questions that
        # link actually contains.
        "n_queries": run["queries"],
        "n_heldout_queries": run.get("heldout_queries", 0),
        "n_vendors": run["vendors"],
        "n_judges": len(JUDGES),
        "n_judgements": complete * len(JUDGES),
        "completeness": {
            "responses": len(rows),
            "complete_ensembles": complete,
            "pct": round(100 * complete / len(rows), 1) if rows else 0.0,
            "vendor_errors": sum(1 for r in rows if r["error"]),
            "n_missing_judgements": sum(r["median"] is None and not r["error"] for r in rows),
            "status": "complete" if complete == len(rows) else "degraded",
        },
        "availability": build_availability(rows),
        # The whole run's spend, public and withheld — this is what the week
        # cost to produce, and understating it by the third of the queries
        # nobody can see would be a strange place to start being imprecise.
        "vendor_spend_usd": round(sum(r["cost_usd"] or 0 for r in all_rows), 4),
        "cells": cells,
        "vendors": totals,
        "judging": build_judge_stats(rows),
        "wins": build_win_stats(rows),
        "robustness": build_robustness([r for r in rows if r["median"] is not None
                                        and r["vendor"] in {v["vendor"] for v in ranked}]),
        "cost_spread": build_cost_spread(totals),
        "payload_effect": build_payload_effect(rows),
        "separation": separation,
        # The measured answer to the question this project was started to ask.
        # A per-category routing table is compared against one vendor for
        # everything; on a run where one vendor is top in every category the two
        # are the same table. Published because the answer came back no, and a
        # benchmark that hides the result running against its own product is the
        # thing this project exists to be an alternative to.
        "routing": build_routing_gain(cells, separation["by_category"]),
        "heldout": build_heldout(all_rows, run, manifest or {}),
        "detail": detail,
        # Every run this week produced, not just the one that won selection —
        # the claim "chosen, not inherited" is only checkable if the rejected
        # candidates are published alongside the chosen one. It lives in the
        # week payload rather than only in the bundle because CI runs against a
        # fresh database: a list assembled from the database alone holds
        # whichever run just executed and nothing else, so the run behind the
        # published numbers would drop out of the record the week after it ran.
        "runs_considered": week_runs if week_runs is not None else [run],
    }


def load_history(data_dir: Path) -> dict[str, dict]:
    """Weeks published by earlier exports, read back from `site/data`.

    These files were produced by `build_week` and already passed the vendor
    content assertion when they were written; they are re-checked on the way
    out anyway. A malformed one is fatal rather than skipped — silently
    dropping a week would shorten the published track record, which is the one
    number this project is not allowed to get wrong in either direction.
    """
    history: dict[str, dict] = {}
    if not data_dir.is_dir():
        return history
    for path in sorted(data_dir.glob("*.json")):
        m = _WEEK_FILE.match(path.name)
        if not m:
            continue
        payload = json.loads(path.read_text())
        if payload.get("week") != m.group(1):
            raise SystemExit(f"{path} declares week {payload.get('week')!r}")
        history[m.group(1)] = payload
    return history


def build_bundle(conn: sqlite3.Connection, queries: dict[str, dict],
                 query_set: dict, history: dict[str, dict] | None = None,
                 manifest: dict | None = None,
                 labels_dir: Path | None = None) -> dict:
    runs = candidate_runs(conn)
    history = history or {}
    manifest = manifest if manifest is not None else heldout.load_manifest()

    # The database wins for any week it holds — it is the evidence layer, and a
    # re-export of a week present in both should reflect the scores, not the
    # last file written. History supplies only the weeks this checkout's
    # database has never seen.
    week_payloads = {w: p for w, p in history.items()}
    from_db = []
    for w in sorted({r["week"] for r in runs}):
        # Recomputing a week replaces its scores from evidence, but its
        # candidate list is append-only: a run considered by an earlier export
        # is a fact about the record, and this database may not be the one that
        # saw it. CI's never is — it starts from a fresh checkout.
        prior = {r["id"]: r for r in (history.get(w) or {}).get("runs_considered", [])}
        prior.update({r["id"]: r for r in runs if r["week"] == w})
        merged = sorted(prior.values(), key=lambda r: r["started_at"])

        run = canonical_run(runs, w)
        if run:
            week_payloads[w] = build_week(conn, run, queries, merged, manifest)
            from_db.append(w)
        elif w in week_payloads:
            # A run against a week whose numbers came from an earlier export —
            # a smoke test on the current week is the ordinary case. Its scores
            # stay exactly as published; only the record of what was considered
            # and rejected grows, and it has to grow in the week file, because
            # that is the artefact that survives to the next export.
            week_payloads[w] = {**week_payloads[w], "runs_considered": merged}
    published = sorted(week_payloads)

    # Weeks whose runs all failed selection have no payload to carry the record
    # forward, so their candidates are only visible while they sit in this
    # database. Published here so a week that produced nothing publishable is
    # still visible as a week that ran.
    considered: dict[str, dict] = {}
    for w in published:
        for r in week_payloads[w].get("runs_considered", []):
            considered[r["id"]] = r
    for r in runs:
        considered.setdefault(r["id"], r)
    all_runs = sorted(considered.values(), key=lambda r: r["started_at"])

    scheduled_weeks = [w for w in published
                       if week_payloads[w].get("trigger") == "scheduled"]
    scheduled = len(scheduled_weeks)

    # Weeks that actually ran a withheld set, as opposed to weeks that existed
    # after one was registered. The overfitting gap means nothing until several
    # of these have accumulated, so the count is what the copy reads from.
    heldout_weeks = [w for w in published if week_payloads[w].get("heldout")]

    vendors = []
    for vid in REGISTRY:
        meta = VENDOR_META.get(vid, {})
        vendors.append({
            "id": vid,
            "label": meta.get("label", vid),
            "docs": meta.get("docs"),
            "note": meta.get("note"),
        })

    counts: dict[str, int] = {}
    for q in queries.values():
        counts[q["category"]] = counts.get(q["category"], 0) + 1

    # The week whose responses were labelled, if it is one this export publishes.
    # Named rather than left as a run id, because "measured on the run behind
    # week X" is the part a reader can go and check.
    calibration = build_calibration(labels_dir if labels_dir is not None else LABELS_DIR)
    if calibration:
        calibration["week"] = next(
            (w for w in published
             if week_payloads[w].get("run_id") == calibration["run_id"]), None)

    return {
        "generated_at": _now(),
        "repo_url": REPO_URL,
        # The claim this file is allowed to support. `weeks_published` is the
        # only honest basis for any "continuously run" language anywhere on the
        # site, so it is computed here and the copy reads from it.
        #
        # `schedule_started` is likewise derived, not asserted: it is true only
        # once a run that the scheduler itself invoked exists in the data. It
        # was a hard-coded False, which was true when written and would have
        # quietly become a lie the first time the cron fired.
        "track_record": {
            "weeks_published": len(published),
            "first_week": published[0] if published else None,
            "latest_week": published[-1] if published else None,
            "scheduled_weeks": scheduled,
            "first_scheduled_week": scheduled_weeks[0] if scheduled_weeks else None,
            "schedule_started": scheduled > 0,
        },
        "vendors": vendors,
        "categories": [
            {"id": c, **CATEGORY_META[c], "n_queries": counts.get(c, 0)}
            for c in CATEGORY_ORDER if c in CATEGORY_META
        ],
        "judges": [{"family": f, "model": m} for f, m in JUDGES],
        # The withheld-set register: every set's hash, size and shape, when it
        # was committed, and whether its questions have been published yet.
        # Published in full here rather than described on a page, because the
        # commitment is only worth as much as a reader's ability to check it
        # against the repository at the date it was made.
        #
        # `interpretable` is the guard on over-reading a single week. One run's
        # gap between two question sets is not evidence of anything, and the
        # copy is derived from this flag rather than trusting whoever writes a
        # page to keep remembering that.
        "heldout": {
            **heldout.public_view(manifest),
            "weeks_with_set": heldout_weeks,
            "interpretable": False,
            "supports_overfitting_inference": False,
            "interpretation": "unmatched distribution-gap diagnostic",
            "limitations": "equal category weights do not match question difficulty; repeated gaps do not establish tuning",
        },
        # Judge against human. None until a human pass clears chance, and every
        # sentence about the judges on every page branches on that rather than
        # asserting either state — the copy said "unaudited" for two published
        # weeks and would have gone on saying it after it stopped being true.
        "calibration": calibration,
        # Published so the methodology page shows the rubric and thresholds the
        # code actually used, rather than a prose description of them that can
        # drift. The placeholders are left in — the page is documenting the
        # template, not one rendered instance of it.
        "config": {
            "top_k": TOP_K,
            "min_cell_coverage": MIN_CELL_COVERAGE,
            "min_queries_per_category": MIN_QUERIES_PER_CATEGORY,
            "min_run_completeness": MIN_RUN_COMPLETENESS,
            "rubric": RUBRIC,
        },
        "query_set": {
            "name": query_set.get("set_name"),
            "n": len(queries),
            "note": query_set.get("note"),
        },
        "weeks": published,
        "latest": week_payloads[published[-1]] if published else None,
        "all_weeks": week_payloads,
        "runs_considered": all_runs,
        # Which weeks this checkout recomputed from evidence, as opposed to
        # carrying forward from a previous export. Not published — main() uses
        # it to decide whether regenerating the CSVs would be an improvement or
        # would overwrite good files with empty ones.
        "_weeks_from_db": from_db,
    }


# --------------------------------------------------------------------- output

def _assert_no_vendor_content(obj, path: str = "$") -> None:
    """Fail the build if anything vendor-written reached the export.

    Every element is walked, not a sample of them. This used to stop at the
    first 50 entries of any list, which made it unsound exactly where it
    mattered: a published week carries 750 detail rows, so a leak anywhere past
    the 51st was invisible to the one check standing between the raw layer and
    the public export. `docs/03` treats that boundary as a copyright and
    ToS-exposure decision rather than a formatting one, and a firewall with a
    sampling rate is not a firewall.

    The cap was presumably there for speed, and there was none to save: the
    whole bundle is a few tens of thousands of small dicts even after a year of
    weeks, and this runs once per export.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _FORBIDDEN_KEYS:
                raise AssertionError(
                    f"vendor content key {k!r} present at {path} — the raw layer "
                    f"must not be exported (src/storage/schema.sql)"
                )
            _assert_no_vendor_content(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_vendor_content(v, f"{path}[{i}]")


def assert_heldout_withheld(site_root: Path, manifest: dict | None = None) -> int:
    """Fail the build if a live held-out question appears in anything published.

    The commitment in `src/heldout.py` is a promise about what is *not* on the
    site, and the only promises worth making in this repository are the ones
    something checks. Every published file is read back and searched for the
    literal text of every question in the active set — bundle, per-week JSON,
    CSVs and the pages themselves — because the ways a withheld question could
    leak are not all obvious in advance: a debug field, a per-query table that
    starts carrying text, a copy-pasted example in a page.

    Returns the number of questions checked. Zero means the active set's text
    is not on this machine, which is the ordinary case in CI on a fork and for
    anyone who is not the maintainer — it cannot leak what it does not hold.
    A set that has retired is deliberately not checked: publishing it is the
    point by then, and it is published from this same module.
    """
    a = heldout.active(manifest)
    if not a:
        return 0
    queries = heldout.load_queries(a["id"], manifest=manifest)
    if queries is None:
        return 0
    heldout.verify(a["id"], queries, manifest)

    texts = {q["text"] for q in queries} | {
        q["gold_answer"] for q in queries if q.get("gold_answer")
    }
    leaked: list[str] = []
    for p in sorted(site_root.rglob("*")):
        if not p.is_file() or p.suffix not in (".json", ".js", ".csv", ".html"):
            continue
        # queries-heldout-retired.csv legitimately carries retired sets. It
        # never carries the active one — but if it ever did, this is the check
        # that has to notice, so it is read like every other file.
        body = p.read_text(errors="ignore")
        for t in texts:
            if t and t in body:
                leaked.append(f"{p.relative_to(site_root)}: {t[:60]}...")
    if leaked:
        raise AssertionError(
            f"held-out set {a['id']} leaked into the published site:\n  "
            + "\n  ".join(leaked[:10])
            + "\nThe set is withheld until it retires; publishing its questions "
              "early makes every gap measured against it meaningless."
        )
    return len(queries)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def queries_for_run(conn: sqlite3.Connection, run_id: str) -> dict[str, dict]:
    return {r["id"]: dict(r) for r in conn.execute(
        "SELECT DISTINCT query_id AS id,category,text,source,gold_answer,rotates "
        "FROM response_queries WHERE run_id=? AND COALESCE(held_out,0)=0", (run_id,))}


def write_site_data(data_dir: Path, bundle: dict,
                    queries_by_week: dict[str, dict[str, dict]]) -> None:
    """Write snapshots and per-run detail; never attach today's text to old IDs."""
    for week, payload in bundle["all_weeks"].items():
        write_json(data_dir / f"{week}.json", payload)
        if week not in queries_by_week:
            continue  # Preserve a previously generated historical detail file.
        qs = queries_by_week[week]
        detail = {
            "week": week, "judges": [f for f, _ in JUDGES], "rows": payload["detail"],
            "queries": [{"id": q["id"], "c": q["category"], "t": q["text"],
                         "g": q.get("gold_answer"), "r": q.get("rotates", 0)}
                        for q in sorted(qs.values(), key=lambda q: (CATEGORY_ORDER.index(q["category"]), q["id"]))],
        }
        text = "// Generated by src/export.py — do not edit.\nwindow.SB_DETAIL = " + json.dumps(detail, separators=(",", ":")) + ";\n"
        (data_dir / f"detail-{week}.js").write_text(text)
        if week == bundle["latest"]["week"]:
            (data_dir / "detail.js").write_text(text)
    write_json(data_dir / "latest.json", bundle["latest"])
    site = {k: v for k, v in bundle.items() if k not in ("all_weeks", "latest", "_weeks_from_db")}
    site["all_weeks"] = {w: browser_week(payload)
                         for w, payload in sorted(bundle["all_weeks"].items())}
    site["latest"] = site["all_weeks"][bundle["latest"]["week"]]
    (data_dir / "bundle.js").write_text(
        "// Generated by src/export.py — do not edit.\nwindow.SB_DATA = " + json.dumps(site, separators=(",", ":")) + ";\n")


def browser_week(payload: dict) -> dict:
    """Keep rendered summaries small; downloads retain every paired test.

    Detail loads separately for the selected week. The complete comparison
    family is an audit artifact in the unchanged week/latest JSON downloads;
    charts use its already computed tiers and category summaries.
    """
    result = {k: v for k, v in payload.items() if k != "detail"}
    if "separation" in result:
        result["separation"] = {k: v for k, v in result["separation"].items()
                                if k != "comparisons"}
    return result


def write_weekly_csv(path: Path, week: str, cells: list[dict]) -> None:
    """The same derived numeric table for DB export and CSV reanalysis."""
    header = ["week", "vendor", "category", "score", "sd", "se", "n_queries", "n_scored",
              "coverage", "p50_latency_ms", "cost_usd", "delta_from_best", "pct_of_best",
              "best_vendor", "separated_from_best", "n_common_with_best", "ci95_low", "ci95_high",
              "status", "n_vendor_success", "n_missing_judgements", "availability", "analysis_version"]
    output = []
    for c in cells:
        ci = c.get("ci95") or [None, None]
        output.append([week, c["vendor"], c["category"], c["score"], c["sd"], c["se"],
                       c["n_queries"], c["n_scored"], c["coverage"], c["p50_latency_ms"],
                       c["cost_usd"], c["delta_from_best"], c["pct_of_best"], c.get("best_vendor"),
                       "" if c.get("separated_from_best") is None else int(c["separated_from_best"]),
                       (c.get("paired") or {}).get("n_common", ""), *ci, c["status"],
                       c["n_vendor_success"], c["n_missing_judgements"], c["availability"], inference.VERSION])
    write_csv(path, header, output)


def export_csvs(conn: sqlite3.Connection, out: Path, week: str, run_id: str,
                queries: dict[str, dict], manifest: dict | None = None) -> list[dict]:
    """The three published CSVs, plus the query set itself.

    Column choice is the publication policy made concrete: every scoring input
    a reader needs to recompute the headline numbers, and nothing a vendor
    wrote.
    """
    written = []
    # The response snapshot wins over a current query file with reused IDs.
    queries = queries_for_run(conn, run_id)

    # Held-out rows are in both of the next two files, flagged rather than
    # removed. What the withheld set withholds is the question text, not the
    # measurement: a reader can recompute the public table (held_out = 0), the
    # overfitting gap (both), and check that neither was cherry-picked. Their
    # text arrives when the set retires, in the file written further down.
    scores = conn.execute(
        """
        SELECT rr.query_id, q.category, COALESCE(q.held_out, 0), rr.vendor,
               js.judge_family, js.judge_model,
               js.relevance, js.freshness, js.citation_quality, js.overall,
               js.scored_chars, js.prompt_tokens, js.output_tokens, js.judge_model_returned
        FROM judge_scores js
        JOIN raw_responses rr ON rr.id = js.response_id
        JOIN response_queries q ON q.response_id = rr.id
        WHERE rr.run_id = ?
        ORDER BY q.category, rr.query_id, rr.vendor, js.judge_family
        """,
        (run_id,),
    ).fetchall()
    p = out / f"judge-scores-{week}.csv"
    write_csv(p, ["week", "query_id", "category", "held_out", "vendor",
                  "judge_family", "judge_model",
                  "relevance", "freshness", "citation_quality", "overall",
                  "scored_chars", "prompt_tokens", "output_tokens", "judge_model_returned"],
              [[week, *list(r)] for r in scores])
    written.append({"file": p.name, "rows": len(scores),
                    "what": "Every individual judge score. One row per (query, vendor, judge). "
                            "held_out=1 marks a withheld question, scored but not yet named."})

    rows = load_run(conn, run_id)
    p = out / f"responses-{week}.csv"
    write_csv(p, ["week", "query_id", "category", "held_out", "vendor", "response_mode",
                  "n_results", "latency_ms", "cost_usd", "cost_source", "complete_ensemble",
                  "median_overall", "error"],
              [[week, r["query_id"], r["category"], int(r["held_out"]), r["vendor"],
                r["response_mode"], r["n_results"], r["latency_ms"], r["cost_usd"],
                r.get("cost_source") or "unknown",
                int(r["complete"]), r["median"], r["error"] or ""] for r in rows])
    written.append({"file": p.name, "rows": len(rows),
                    "what": "One row per API call: timing, cost, result count, ensemble median. No retrieved content."})

    # The published table is the public questions alone, so the cells file has
    # to be built from those alone — this is the same split build_week makes,
    # and the two would be a confusing pair of numbers if they disagreed.
    rows = [r for r in rows if not r["held_out"]]
    cells = build_cells(rows)
    p = out / f"weekly-scores-{week}.csv"
    # sd/se and the separation flag ship with the score. A published number and
    # the reason not to over-read it belong in the same row: a reader who has to
    # go and derive the dispersion themselves will usually just take the mean.
    write_weekly_csv(p, week, cells)
    written.append({"file": p.name, "rows": len(cells),
                    "what": "The published table: one row per vendor per category."})

    # The price basis behind every cost figure on the site. Shipped as its own
    # file because the cost spread is the strongest claim the benchmark makes
    # and it rests on which tier each vendor is billed at — a reader who cannot
    # check that has to take the ratio on trust, which is the thing this project
    # says vendors should not ask of anyone.
    p = out / "pricing.json"
    write_json(p, {
        "generated_at": _now(),
        "note": ("basis_per_query_usd is what this benchmark is billed at; "
                 "payg_per_query_usd is the undiscounted rate. They differ for "
                 "vendors whose cheapest tier requires a volume commitment. "
                 "reported_by_vendor says whether the vendor returns a billed "
                 "figure on the call itself — where it does, cost_usd in the "
                 "responses export is measured rather than derived."),
        "vendors": {v: {**meta, "label": VENDOR_META.get(v, {}).get("label", v)}
                    for v, meta in sorted(PRICING.items())},
    })
    written.append({"file": p.name, "rows": len(PRICING),
                    "what": "Per-vendor price basis, tier and source URL behind every cost figure."})

    p = out / "queries.csv"
    qs = sorted(queries.values(), key=lambda q: (CATEGORY_ORDER.index(q["category"]), q["id"]))
    write_csv(p, ["id", "category", "source", "rotates", "text", "gold_answer"],
              [[q["id"], q["category"], q.get("source", ""), q.get("rotates", 0),
                q["text"], q.get("gold_answer") or ""] for q in qs])
    written.append({"file": p.name, "rows": len(qs),
                    "what": "The full public query set. Authored in-house, so it ships with no dataset-licence encumbrance."})
    archived = out / f"queries-{week}.csv"
    archived.write_bytes(p.read_bytes())
    written.append({"file": archived.name, "rows": len(qs),
                    "what": "Immutable public question snapshot for this retrieval run."})

    # The disclosure half of the held-out design. A set is withheld while it
    # runs and published in full when it rotates out, so this file grows by one
    # set every rotation and never shrinks. Written even when empty: a reader
    # should be able to see that the promise exists and has not come due yet,
    # rather than wonder whether the file is missing or the promise is.
    retired = []
    for s in (manifest or heldout.load_manifest()).get("sets", []):
        if not s.get("retired_week"):
            continue
        for q in heldout.load_queries(s["id"], manifest=manifest) or []:
            retired.append([s["id"], s["retired_week"], s["sha256"], q["id"],
                            q["category"], q.get("source", ""),
                            q["text"], q.get("gold_answer") or ""])
    p = out / "queries-heldout-retired.csv"
    write_csv(p, ["set_id", "retired_week", "set_sha256", "id", "category",
                  "source", "text", "gold_answer"], retired)
    written.append({"file": p.name, "rows": len(retired),
                    "what": "Held-out questions, published in full once their set retires. "
                            "Each set's hash was committed before it ever ran."})

    return written


def rebuild_weekly(conn: sqlite3.Connection, bundle: dict) -> int:
    """Rewrite `weekly_scores` from the canonical run of each published week.

    Repair path for cells written before runner.aggregate() was guarded, when a
    smoke test could overwrite a full run's cell. Idempotent: it recomputes
    from judge_scores, which is the layer that actually holds the evidence.
    """
    cur = conn.cursor()
    written = 0
    for week, payload in bundle["all_weeks"].items():
        # Only weeks this database actually holds. A week carried forward from
        # history has no run row here, and writing its cells would leave the
        # aggregate layer pointing at a run_id that does not exist locally.
        if week not in bundle["_weeks_from_db"]:
            continue
        for c in payload["cells"]:
            if c["score"] is None:
                continue
            cur.execute(
                "INSERT OR REPLACE INTO weekly_scores (id, week, run_id, vendor, category, "
                "median_score, n_queries, n_errors, p50_latency_ms, total_cost_usd, "
                "delta_from_best, created_at) VALUES ("
                "  COALESCE((SELECT id FROM weekly_scores WHERE week=? AND vendor=? AND category=?),"
                "           lower(hex(randomblob(16)))),"
                "  ?,?,?,?,?,?,?,?,?,?,?)",
                (week, c["vendor"], c["category"],
                 week, payload["run_id"], c["vendor"], c["category"], c["score"],
                 c["n_scored"], c["n_errors"], c["p50_latency_ms"], c["cost_usd"],
                 c["delta_from_best"], _now()),
            )
            written += 1
    conn.commit()
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the public data export.")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default=str(ROOT / "site"), help="site root")
    ap.add_argument("--queries", default=str(ROOT / "src" / "queries" / "full-v1.json"))
    # The held-out register to publish and to check against. Overridable for the
    # same reason --queries is: the generated fixture has to be able to exercise
    # this path without borrowing the real repository's commitments.
    ap.add_argument("--heldout-manifest", default=None)
    # Same reason as above: a fixture export must be able to exercise both the
    # "no calibration has cleared" and "one has" branches without borrowing the
    # real repository's labels.
    ap.add_argument("--labels", default=str(LABELS_DIR),
                    help="directory of exported calibration labels")
    ap.add_argument("--rebuild-weekly", action="store_true",
                    help="also rewrite weekly_scores from each week's canonical run")
    ap.add_argument("--no-history", action="store_true",
                    help="ignore previously exported weeks; publish only what this database holds")
    args = ap.parse_args()

    query_set = json.loads(Path(args.queries).read_text())
    queries = {q["id"]: q for q in query_set["queries"]}
    manifest = heldout.load_manifest(args.heldout_manifest)

    out = Path(args.out)
    data_dir, export_dir = out / "data", out / "export"

    # Weeks published by earlier runs, which in CI is every week but the one
    # that just ran. Read before the database is touched so a failure here is
    # about the history rather than about the run.
    history = {} if args.no_history else load_history(data_dir)

    conn = connect(Path(args.db))
    bundle = build_bundle(conn, queries, query_set, history, manifest,
                          Path(args.labels))
    _assert_no_vendor_content(bundle)

    if not bundle["weeks"]:
        raise SystemExit(
            "no run in the database clears the publication floor "
            f"(>= {MIN_QUERIES_PER_CATEGORY} queries in each of "
            f"{len(CATEGORY_META)} categories, >= {MIN_RUN_COMPLETENESS:.0%} "
            "complete ensembles), and no published week exists on disk. "
            "Nothing exported."
        )

    # CSVs first: the data page lists them with their real row counts, so the
    # manifest has to exist before the bundle the page reads is written.
    latest = bundle["latest"]
    export_week, export_run = latest["week"], latest["run_id"]
    if latest["week"] in bundle["_weeks_from_db"]:
        files = export_csvs(conn, export_dir, latest["week"], latest["run_id"],
                            queries, manifest)
    else:
        # The newest published week came from history, not from this database —
        # so its CSVs were written by the export that produced it and are still
        # correct. Regenerating them from a database that does not hold that run
        # would replace real files with empty ones.
        # Not `manifest`: that name already holds the held-out manifest loaded
        # in main(), and rebinding it here left assert_heldout_withheld() below
        # receiving a Path. That is the guard against a withheld question
        # reaching a published file, and it crashed rather than ran on every
        # export whose newest week came from history instead of this database.
        prior_manifest = export_dir / "manifest.json"
        if not prior_manifest.is_file():
            raise SystemExit(
                f"week {latest['week']} comes from history but {prior_manifest} is missing — "
                "cannot describe an export whose files this run did not write."
            )
        prior = json.loads(prior_manifest.read_text())
        files = prior["files"]
        # The manifest keeps naming the week the CSVs actually came from, not
        # the newest week on the site. A manifest headed 2026-W32 listing
        # 2026-W31 files is the sort of small mislabel that a reader checking
        # the work would find first.
        export_week, export_run = prior["week"], prior["run_id"]
        print(f"note: CSVs left as-is at {export_week}; "
              f"{latest['week']} is not in this database")

    bundle["export"] = {
        "licence": "CC BY 4.0",
        "week": export_week,
        "files": files,
        "excluded": [
            "Retrieved URLs, titles and snippets",
            "Synthesized prose answers",
            "Raw vendor response payloads",
        ],
    }

    query_snapshots = {w: queries_for_run(conn, bundle["all_weeks"][w]["run_id"])
                       for w in bundle["_weeks_from_db"]}
    write_site_data(data_dir, bundle, query_snapshots)

    if args.rebuild_weekly:
        n = rebuild_weekly(conn, bundle)
        print(f"rebuilt {n} weekly_scores cell(s) from canonical runs")

    write_json(export_dir / "manifest.json", {
        "generated_at": bundle["generated_at"],
        "week": export_week,
        "run_id": export_run,
        "query_set_hash": bundle["all_weeks"][export_week]["query_set_hash"],
        "licence": "CC BY 4.0",
        "excluded_by_policy": (
            "Retrieved URLs, titles, snippets and synthesized answers are stored "
            "for reproducibility but never published. See data.html."
        ),
        "files": files,
    })
    conn.close()

    # Last, and against the files as written rather than against the structures
    # that produced them — the promise is about what is on disk.
    checked = assert_heldout_withheld(out, manifest)
    if checked:
        print(f"held-out: {checked} withheld question(s) confirmed absent from the export")

    print(f"week {latest['week']}  run {latest['run_id'][:8]}  "
          f"{latest['completeness']['complete_ensembles']}/{latest['completeness']['responses']} "
          f"complete ensembles ({latest['completeness']['pct']}%)")
    # The candidates that bear on this export: the published week's, plus any
    # run whose week produced nothing publishable — that second group is the
    # one an operator is looking for when a run does not appear on the site.
    for r in [r for r in bundle["runs_considered"]
              if r["week"] == latest["week"] or r["week"] not in bundle["weeks"]]:
        mark = "  <- published" if r["id"] == latest["run_id"] else ""
        print(f"  run {r['id'][:8]}  {r['week']}  {r['complete']:>4}/{r['responses']:<4} complete"
              f"  min/cat {r['min_per_category']:>3}{mark}")

    tr = bundle["track_record"]
    print(f"\ntrack record: {tr['weeks_published']} published week(s) "
          f"{tr['first_week']}..{tr['latest_week']}, "
          f"{tr['scheduled_weeks']} from the scheduler")
    for w in bundle["weeks"]:
        origin = "recomputed" if w in bundle["_weeks_from_db"] else "carried forward"
        trig = bundle["all_weeks"][w].get("trigger") or "unknown"
        print(f"  {w}  {origin:<15} trigger {trig}")
    print(f"\nwrote {data_dir} and {export_dir}")


if __name__ == "__main__":
    main()
