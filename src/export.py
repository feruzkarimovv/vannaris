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
import re
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

from . import storage
from .judge.ensemble import JUDGES, RUBRIC
from .vendors.adapters import REGISTRY, TOP_K

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "vannaris.db"

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

# Set this when the repository is actually public. Until then the site says
# "not yet public" rather than linking somewhere that isn't the source — a
# benchmark whose credibility rests on being inspectable should not ship a
# "Source" link that goes nowhere useful.
REPO_URL: str | None = None

VENDOR_META = {
    "exa":        {"label": "Exa",        "docs": "https://exa.ai"},
    "perplexity": {"label": "Perplexity", "docs": "https://docs.perplexity.ai",
                   "note": "Sonar. Returns prose and a ranked list; scored on the list."},
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
        stats = conn.execute(
            """
            SELECT COUNT(*) AS responses,
                   SUM(CASE WHEN n = ? THEN 1 ELSE 0 END) AS complete,
                   COUNT(DISTINCT query_id) AS queries,
                   COUNT(DISTINCT vendor) AS vendors
            FROM (SELECT rr.id, rr.query_id, rr.vendor, COUNT(js.id) AS n
                  FROM raw_responses rr
                  LEFT JOIN judge_scores js ON js.response_id = rr.id
                  WHERE rr.run_id = ?
                  GROUP BY rr.id)
            """,
            (len(JUDGES), r["id"]),
        ).fetchone()
        per_cat = conn.execute(
            """
            SELECT q.category, COUNT(DISTINCT rr.query_id) AS n
            FROM raw_responses rr JOIN queries q ON q.id = rr.query_id
            WHERE rr.run_id = ? GROUP BY q.category
            """,
            (r["id"],),
        ).fetchall()
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
            "responses": responses,
            "complete": complete,
            "completeness": round(complete / responses, 3) if responses else 0.0,
            "queries": stats["queries"] or 0,
            "vendors": stats["vendors"] or 0,
            "min_per_category": min([c["n"] for c in per_cat], default=0),
            "categories": len(per_cat),
        })
    return runs


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
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda r: (r["complete"], r["started_at"]))


# ------------------------------------------------------------------ recompute

def load_run(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """Per-response rows for one run, with each judge's `overall` attached."""
    rows = conn.execute(
        """
        SELECT rr.id, rr.query_id, rr.vendor, rr.response_mode, rr.latency_ms,
               rr.cost_usd, rr.error, rr.results, q.category
        FROM raw_responses rr JOIN queries q ON q.id = rr.query_id
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
            "vendor": r["vendor"],
            "response_mode": r["response_mode"],
            "n_results": n_results,
            "latency_ms": r["latency_ms"],
            "cost_usd": r["cost_usd"],
            "error": r["error"],
            "judges": {s["judge_family"]: s for s in js},
            "complete": len(overalls) == len(JUDGES),
            "median": _median(overalls) if len(overalls) == len(JUDGES) else None,
        })
    return out


def build_cells(rows: list[dict]) -> list[dict]:
    """(vendor, category) cells, recomputed from per-judge scores."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        grouped.setdefault((r["vendor"], r["category"]), []).append(r)

    cells = []
    for (vendor, category), rs in grouped.items():
        scored = [r["median"] for r in rs if r["median"] is not None]
        coverage = len(scored) / len(rs) if rs else 0.0
        lat = [r["latency_ms"] for r in rs if r["latency_ms"] is not None]
        cells.append({
            "vendor": vendor,
            "category": category,
            # Suppressed rather than approximated when coverage is thin.
            "score": round(statistics.mean(scored), 3) if coverage >= MIN_CELL_COVERAGE else None,
            "n_queries": len(rs),
            "n_scored": len(scored),
            "coverage": round(coverage, 3),
            "n_errors": sum(1 for r in rs if r["error"]),
            "p50_latency_ms": int(statistics.median(lat)) if lat else None,
            "cost_usd": round(sum(r["cost_usd"] or 0 for r in rs), 5),
        })

    # Gap to the best vendor in the same category — the number that decides
    # whether routing on quality is worth anything at all.
    best = {}
    for c in cells:
        if c["score"] is not None:
            best[c["category"]] = max(best.get(c["category"], 0.0), c["score"])
    for c in cells:
        top = best.get(c["category"])
        if c["score"] is not None and top:
            c["delta_from_best"] = round(top - c["score"], 3)
            c["pct_of_best"] = round(100 * c["score"] / top, 1)
        else:
            c["delta_from_best"] = None
            c["pct_of_best"] = None
    return sorted(cells, key=lambda c: (CATEGORY_ORDER.index(c["category"]), -(c["score"] or 0)))


def build_vendor_totals(rows: list[dict], cells: list[dict]) -> list[dict]:
    """Per-vendor roll-up.

    The overall score is the mean of a vendor's six *category* scores, not the
    mean of its 150 query scores. Those differ whenever coverage differs by
    category, and the category mean is the one that matches what the table
    above it shows.
    """
    vendors = sorted({r["vendor"] for r in rows})
    per_query_best: dict[str, tuple[str, float]] = {}
    for r in rows:
        if r["median"] is None:
            continue
        cur = per_query_best.get(r["query_id"])
        if cur is None or r["median"] > cur[1]:
            per_query_best[r["query_id"]] = (r["vendor"], r["median"])

    totals = []
    for v in vendors:
        vcells = [c for c in cells if c["vendor"] == v and c["score"] is not None]
        vrows = [r for r in rows if r["vendor"] == v]
        lat = [r["latency_ms"] for r in vrows if r["latency_ms"] is not None]
        scored = [r for r in vrows if r["median"] is not None]
        totals.append({
            "vendor": v,
            "label": VENDOR_META.get(v, {}).get("label", v),
            "score": round(statistics.mean(c["score"] for c in vcells), 3) if vcells else None,
            "p50_latency_ms": int(statistics.median(lat)) if lat else None,
            "cost_usd": round(sum(r["cost_usd"] or 0 for r in vrows), 5),
            "cost_per_query_usd": round(sum(r["cost_usd"] or 0 for r in vrows) / len(vrows), 6) if vrows else None,
            "n_queries": len(vrows),
            "n_scored": len(scored),
            "n_errors": sum(1 for r in vrows if r["error"]),
            "wins": sum(1 for winner, _ in per_query_best.values() if winner == v),
            "response_mode": vrows[0]["response_mode"] if vrows else None,
        })
    return sorted(totals, key=lambda t: -(t["score"] or 0))


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
    expected = len(rows)

    for r in rows:
        vals = []
        for fam, s in r["judges"].items():
            if s["overall"] is not None:
                families.setdefault(fam, []).append(s["overall"])
                models[fam] = s["judge_model"]
                vals.append(s["overall"])
        if len(vals) > 1:
            spreads.append(max(vals) - min(vals))

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
    }


# ------------------------------------------------------------------- assembly

def build_week(conn: sqlite3.Connection, run: dict, queries: dict[str, dict],
               week_runs: list[dict] | None = None) -> dict:
    rows = load_run(conn, run["id"])
    cells = build_cells(rows)
    totals = build_vendor_totals(rows, cells)
    complete = sum(1 for r in rows if r["complete"])

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
        }
        for r in rows
    ]

    return {
        "week": run["week"],
        "run_id": run["id"],
        "ran_at": run["started_at"],
        "trigger": run.get("trigger"),
        "query_set_hash": run["query_set_hash"],
        "n_queries": run["queries"],
        "n_vendors": run["vendors"],
        "n_judges": len(JUDGES),
        "n_judgements": complete * len(JUDGES),
        "completeness": {
            "responses": len(rows),
            "complete_ensembles": complete,
            "pct": round(100 * complete / len(rows), 1) if rows else 0.0,
            "vendor_errors": sum(1 for r in rows if r["error"]),
        },
        "vendor_spend_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
        "cells": cells,
        "vendors": totals,
        "judging": build_judge_stats(rows),
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
                 query_set: dict, history: dict[str, dict] | None = None) -> dict:
    runs = candidate_runs(conn)
    history = history or {}

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
            week_payloads[w] = build_week(conn, run, queries, merged)
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
    """Fail the build if anything vendor-written reached the export."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _FORBIDDEN_KEYS:
                raise AssertionError(
                    f"vendor content key {k!r} present at {path} — the raw layer "
                    f"must not be exported (src/storage/schema.sql)"
                )
            _assert_no_vendor_content(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            _assert_no_vendor_content(v, f"{path}[{i}]")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def export_csvs(conn: sqlite3.Connection, out: Path, week: str, run_id: str,
                queries: dict[str, dict]) -> list[dict]:
    """The three published CSVs, plus the query set itself.

    Column choice is the publication policy made concrete: every scoring input
    a reader needs to recompute the headline numbers, and nothing a vendor
    wrote.
    """
    written = []

    scores = conn.execute(
        """
        SELECT rr.query_id, q.category, rr.vendor, js.judge_family, js.judge_model,
               js.relevance, js.freshness, js.citation_quality, js.overall,
               js.scored_chars, js.prompt_tokens, js.output_tokens
        FROM judge_scores js
        JOIN raw_responses rr ON rr.id = js.response_id
        JOIN queries q ON q.id = rr.query_id
        WHERE rr.run_id = ?
        ORDER BY q.category, rr.query_id, rr.vendor, js.judge_family
        """,
        (run_id,),
    ).fetchall()
    p = out / f"judge-scores-{week}.csv"
    write_csv(p, ["week", "query_id", "category", "vendor", "judge_family", "judge_model",
                  "relevance", "freshness", "citation_quality", "overall",
                  "scored_chars", "prompt_tokens", "output_tokens"],
              [[week, *list(r)] for r in scores])
    written.append({"file": p.name, "rows": len(scores),
                    "what": "Every individual judge score. One row per (query, vendor, judge)."})

    rows = load_run(conn, run_id)
    p = out / f"responses-{week}.csv"
    write_csv(p, ["week", "query_id", "category", "vendor", "response_mode", "n_results",
                  "latency_ms", "cost_usd", "complete_ensemble", "median_overall", "error"],
              [[week, r["query_id"], r["category"], r["vendor"], r["response_mode"],
                r["n_results"], r["latency_ms"], r["cost_usd"],
                int(r["complete"]), r["median"], r["error"] or ""] for r in rows])
    written.append({"file": p.name, "rows": len(rows),
                    "what": "One row per API call: timing, cost, result count, ensemble median. No retrieved content."})

    cells = build_cells(rows)
    p = out / f"weekly-scores-{week}.csv"
    write_csv(p, ["week", "vendor", "category", "score", "n_queries", "n_scored",
                  "coverage", "p50_latency_ms", "cost_usd", "delta_from_best", "pct_of_best"],
              [[week, c["vendor"], c["category"], c["score"], c["n_queries"], c["n_scored"],
                c["coverage"], c["p50_latency_ms"], c["cost_usd"],
                c["delta_from_best"], c["pct_of_best"]] for c in cells])
    written.append({"file": p.name, "rows": len(cells),
                    "what": "The published table: one row per vendor per category."})

    p = out / "queries.csv"
    qs = sorted(queries.values(), key=lambda q: (CATEGORY_ORDER.index(q["category"]), q["id"]))
    write_csv(p, ["id", "category", "source", "rotates", "text", "gold_answer"],
              [[q["id"], q["category"], q.get("source", ""), q.get("rotates", 0),
                q["text"], q.get("gold_answer") or ""] for q in qs])
    written.append({"file": p.name, "rows": len(qs),
                    "what": "The full query set. Authored in-house, so it ships with no dataset-licence encumbrance."})

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
    ap.add_argument("--rebuild-weekly", action="store_true",
                    help="also rewrite weekly_scores from each week's canonical run")
    ap.add_argument("--no-history", action="store_true",
                    help="ignore previously exported weeks; publish only what this database holds")
    args = ap.parse_args()

    query_set = json.loads(Path(args.queries).read_text())
    queries = {q["id"]: q for q in query_set["queries"]}

    out = Path(args.out)
    data_dir, export_dir = out / "data", out / "export"

    # Weeks published by earlier runs, which in CI is every week but the one
    # that just ran. Read before the database is touched so a failure here is
    # about the history rather than about the run.
    history = {} if args.no_history else load_history(data_dir)

    conn = connect(Path(args.db))
    bundle = build_bundle(conn, queries, query_set, history)
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
        files = export_csvs(conn, export_dir, latest["week"], latest["run_id"], queries)
    else:
        # The newest published week came from history, not from this database —
        # so its CSVs were written by the export that produced it and are still
        # correct. Regenerating them from a database that does not hold that run
        # would replace real files with empty ones.
        manifest = export_dir / "manifest.json"
        if not manifest.is_file():
            raise SystemExit(
                f"week {latest['week']} comes from history but {manifest} is missing — "
                "cannot describe an export whose files this run did not write."
            )
        prior = json.loads(manifest.read_text())
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

    # Machine-readable: one file per week plus a stable `latest.json`.
    for week, payload in bundle["all_weeks"].items():
        write_json(data_dir / f"{week}.json", payload)
    write_json(data_dir / "latest.json", bundle["latest"])

    # What the pages read. A plain script assignment rather than fetch(), so
    # the site works when opened from disk as well as over http — a benchmark
    # whose dashboard needs a web server to inspect is less inspectable.
    site = {k: v for k, v in bundle.items()
            if k not in ("all_weeks", "latest", "_weeks_from_db")}
    site["latest"] = {k: v for k, v in bundle["latest"].items() if k != "detail"}
    (data_dir / "bundle.js").write_text(
        "// Generated by src/export.py — do not edit.\n"
        "window.SB_DATA = " + json.dumps(site, indent=1) + ";\n"
    )
    (data_dir / "detail.js").write_text(
        "// Generated by src/export.py — do not edit.\n"
        "window.SB_DETAIL = " + json.dumps({
            "week": bundle["latest"]["week"],
            "judges": [f for f, _ in JUDGES],
            "rows": bundle["latest"]["detail"],
            "queries": [
                {"id": q["id"], "c": q["category"], "t": q["text"],
                 "g": q.get("gold_answer"), "r": q.get("rotates", 0)}
                for q in sorted(queries.values(),
                                key=lambda q: (CATEGORY_ORDER.index(q["category"]), q["id"]))
            ],
        }, separators=(",", ":")) + ";\n"
    )

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
