"""Recompute published analyses from released numerical CSVs, without API keys.

    python scripts/recompute_publication.py --check
    python scripts/recompute_publication.py --out /tmp/vannaris-recomputed
    python scripts/recompute_publication.py --in-place

The default is read-only verification. This is an analysis revision, never a
new retrieval run: identities, dates, query commitments and measured inputs
are retained. Judge/response CSV bytes are copied unchanged and hashed. The
script refuses duplicate joins, invalid scores and contradictory ensemble
metadata instead of silently manufacturing complete observations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import export, heldout, inference  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_recorded_inputs(original: dict, query_file: Path,
                           current_inputs: dict[str, str]) -> None:
    """Refuse changed evidence even when the headline aggregates stay equal.

    The original shared queries.csv can later be materialized under a dated
    filename. Verify its recorded bytes against the selected matching snapshot
    rather than treating the filename change as a new observation.
    """
    revision = original.get("analysis_revision") or {}
    recorded = revision.get("input_sha256")
    if not revision:
        return  # First analysis revision establishes the released-input hashes.
    if not isinstance(recorded, dict) or not recorded:
        raise ValueError(f"{original['week']}: analysis revision lacks recorded input hashes")
    week = original["week"]
    numerical = {f"responses-{week}.csv", f"judge-scores-{week}.csv"}
    query_names = {"queries.csv", f"queries-{week}.csv"}
    if not numerical.issubset(recorded) or not (query_names & recorded.keys()):
        raise ValueError(f"{week}: incomplete recorded input hashes")
    if set(recorded) - numerical - query_names:
        raise ValueError(f"{week}: unexpected recorded input filename")
    for filename, expected in recorded.items():
        selected = query_file.name if filename in query_names else filename
        actual = current_inputs.get(selected)
        if (not isinstance(expected, str) or len(expected) != 64
                or any(c not in "0123456789abcdef" for c in expected)
                or actual != expected):
            raise ValueError(f"{week}: recorded input hash mismatch for {filename}; "
                             "numerical evidence changed, restore the recorded inputs "
                             "or perform a separately reviewed evidence repair")


def read_csv(path: Path, required: set[str]) -> list[dict]:
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path.name}: missing required columns")
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError(f"{path.name}: malformed CSV row")
    return rows


def number(value: str, field: str, *, optional: bool = False,
           integer: bool = False, score: bool = False) -> float | int | None:
    if value == "" and optional:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(parsed) or (score and not 0 <= parsed <= 10):
        raise ValueError(f"non-finite or out-of-range {field}")
    if not score and parsed < 0:
        raise ValueError(f"negative {field}")
    if integer and parsed != int(parsed):
        raise ValueError(f"non-integer {field}")
    return int(parsed) if integer else parsed


def load_queries(path: Path) -> dict[str, dict]:
    rows = read_csv(path, {"id", "category", "text", "gold_answer", "source", "rotates"})
    result = {}
    for r in rows:
        if not r["id"] or r["id"] in result or r["category"] not in export.CATEGORY_META:
            raise ValueError("duplicate/invalid public query")
        result[r["id"]] = {**r, "gold_answer": r["gold_answer"] or None,
                           "rotates": number(r["rotates"], "rotates", integer=True)}
    return result


def load_observations(directory: Path, week: str, queries: dict[str, dict]) -> list[dict]:
    """Validate the one-response / one-family-score grain before any analysis."""
    responses = read_csv(directory / f"responses-{week}.csv", {
        "week", "query_id", "category", "held_out", "vendor", "response_mode", "n_results",
        "latency_ms", "cost_usd", "cost_source", "complete_ensemble", "median_overall", "error"})
    scores = read_csv(directory / f"judge-scores-{week}.csv", {
        "week", "query_id", "category", "held_out", "vendor", "judge_family", "judge_model",
        "relevance", "freshness", "citation_quality", "overall", "scored_chars", "prompt_tokens", "output_tokens"})
    families = {fam for fam, _ in export.JUDGES}
    joined = {}
    query_membership = {}
    for r in responses:
        key = r["query_id"], r["vendor"]
        if r["week"] != week or key in joined or r["category"] not in export.CATEGORY_META:
            raise ValueError("duplicate response, unknown category or mismatched week")
        if r["held_out"] not in ("0", "1") or r["complete_ensemble"] not in ("0", "1"):
            raise ValueError("invalid response flags")
        membership = r["category"], r["held_out"]
        if r["query_id"] in query_membership and query_membership[r["query_id"]] != membership:
            raise ValueError("query membership differs between vendors")
        query_membership[r["query_id"]] = membership
        private = r["held_out"] == "1"
        if not private and (r["query_id"] not in queries or queries[r["query_id"]]["category"] != r["category"]):
            raise ValueError("public response does not match published query snapshot")
        if private and r["query_id"] in queries:
            raise ValueError("withheld query appears in public query snapshot")
        joined[key] = {
            "response_id": f"{week}:{r['query_id']}:{r['vendor']}",
            "query_id": r["query_id"], "category": r["category"], "vendor": r["vendor"],
            "held_out": private, "response_mode": r["response_mode"],
            "n_results": number(r["n_results"], "n_results", integer=True),
            "latency_ms": number(r["latency_ms"], "latency_ms", optional=True, integer=True),
            "cost_usd": number(r["cost_usd"], "cost_usd", optional=True),
            "cost_source": r["cost_source"], "error": r["error"] or None,
            "declared_complete": r["complete_ensemble"] == "1",
            "declared_median": number(r["median_overall"], "median_overall", optional=True, score=True),
            "judges": {},
        }
    for s in scores:
        key = s["query_id"], s["vendor"]
        if s["week"] != week or key not in joined:
            raise ValueError("orphan score or mismatched week")
        r = joined[key]
        fam = s["judge_family"]
        if fam not in families or fam in r["judges"]:
            raise ValueError("unknown or duplicate judge family")
        if s["category"] != r["category"] or s["held_out"] != str(int(r["held_out"])):
            raise ValueError("score membership does not match response")
        r["judges"][fam] = {
            "judge_family": fam, "judge_model": s["judge_model"],
            **{dimension: number(s[dimension], dimension, score=True, optional=dimension != "overall")
               for dimension in ("relevance", "freshness", "citation_quality", "overall")},
            **{field: number(s[field], field, optional=True, integer=True)
               for field in ("scored_chars", "prompt_tokens", "output_tokens")},
            "judge_model_returned": s.get("judge_model_returned") or None,
        }
    for r in joined.values():
        r["complete"] = set(r["judges"]) == families and not r["error"]
        r["median"] = statistics.median(s["overall"] for s in r["judges"].values()) if r["complete"] else None
        if r["complete"] != r.pop("declared_complete") or r["median"] != r.pop("declared_median"):
            raise ValueError("released ensemble metadata contradicts individual scores")
    if {r["query_id"] for r in joined.values() if not r["held_out"]} != set(queries):
        raise ValueError("published query snapshot does not match response population")
    return list(joined.values())


def revise_week(original: dict, rows: list[dict], manifest: dict, inputs: dict[str, str]) -> dict:
    public = [r for r in rows if not r["held_out"]]
    if (original["n_queries"] != len({r["query_id"] for r in public})
            or original["n_vendors"] != len({r["vendor"] for r in public})
            or original["completeness"]["responses"] != len(public)
            or original["completeness"]["complete_ensembles"] != sum(r["complete"] for r in public)):
        raise ValueError("original publication counts contradict released observations")
    if not math.isclose(original["vendor_spend_usd"], sum(r["cost_usd"] or 0 for r in rows), abs_tol=0.0001):
        raise ValueError("original spend contradicts released observations")
    method = original.get("methodology")
    if not method:
        # This is a documented legacy classification, not reconstructed model
        # parameters. Unknown runs stay unknown rather than inheriting today.
        version = {"2026-W31": "retrieval-v1", "2026-W33": "retrieval-v2",
                   "2026-W34": "retrieval-v2", "2026-W35": "retrieval-v2"}.get(original["week"], "legacy_unrecorded")
        method = {"version": version, "provenance_status": "legacy_partial",
                  "version_source": "published methodology changelog",
                  "query_set_hash": original["query_set_hash"],
                  "note": "individual served models and complete original request configuration remain unknown"}
    run = {"id": original["run_id"], "week": original["week"], "started_at": original["ran_at"],
           "trigger": original.get("trigger"), "query_set_hash": original["query_set_hash"],
           "queries": original["n_queries"], "vendors": original["n_vendors"],
           "heldout_queries": original.get("n_heldout_queries", 0),
           "heldout_set": ((original.get("heldout") or {}).get("set") or {}).get("id"),
           "methodology": method}
    revised = export.build_week_from_rows(rows, run, original.get("runs_considered"), manifest)
    previous_revision = original.get("analysis_revision") or {}
    revised["analysis_revision"] = {
        "version": inference.VERSION,
        "revised_at": previous_revision.get("revised_at") or export._now(),
        "source": "released numerical judge and response CSVs; no new retrieval or judging",
        "input_sha256": inputs,
        "previous_analysis_version": previous_revision.get("previous_analysis_version", "legacy_unversioned"),
        "original_retrieval_at": original["ran_at"],
    }
    for key in ("ran_at", "run_id", "week", "trigger", "query_set_hash", "n_queries", "n_vendors", "n_heldout_queries"):
        if revised.get(key) != original.get(key):
            raise ValueError(f"reanalysis changed original retrieval metadata: {key}")
    return revised


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site-root", type=Path, default=ROOT / "site")
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="verify derived publication without writes (default)")
    modes.add_argument("--out", type=Path, help="write a recomputed data/export tree")
    modes.add_argument("--in-place", action="store_true", help="write an explicit derived-analysis revision")
    args = ap.parse_args()
    source = args.site_root.resolve()
    target = source if args.in_place else args.out
    if target is not None and target.resolve() == source and not args.in_place:
        raise ValueError("use --in-place explicitly to revise the existing publication")
    old_bundle = json.loads((source / "data" / "bundle.js").read_text().split("window.SB_DATA = ", 1)[1].rstrip().removesuffix(";"))
    manifest = heldout.load_manifest()
    history = export.load_history(source / "data")
    if not history:
        raise ValueError("no published retrieval runs")
    revised, snapshots = {}, {}
    for week, original in history.items():
        directory = source / "export"
        query_file = directory / f"queries-{week}.csv"
        if not query_file.is_file():
            # Legacy publications shared one static question commitment.
            if original["query_set_hash"] != old_bundle["latest"]["query_set_hash"]:
                raise ValueError(f"{week}: historical public query snapshot is unavailable")
            query_file = directory / "queries.csv"
        queries = load_queries(query_file)
        inputs = {p.name: sha256(p) for p in (query_file, directory / f"responses-{week}.csv",
                                              directory / f"judge-scores-{week}.csv")}
        verify_recorded_inputs(original, query_file, inputs)
        rows = load_observations(directory, week, queries)
        revised[week] = revise_week(original, rows, manifest, inputs)
        revised[week]["export"]["files"].append({"file": query_file.name, "rows": len(queries),
                                              "what": "Public question snapshot matching this run's commitment."})
        snapshots[week] = queries
        if target is None:
            for field in ("cells", "vendors", "judging", "wins", "robustness", "routing", "heldout",
                          "availability", "separation", "completeness", "analysis", "methodology"):
                if original.get(field) != revised[week].get(field):
                    raise ValueError(f"{week}: {field} differs from released-input recomputation; run --out or --in-place")
        print(f"{week}: verified {len(rows)} original observations; {sum(r['complete'] for r in rows)} complete ensembles", flush=True)
    if target is None:
        print(f"Verified {len(revised)} published analyses ({inference.VERSION}); no files written.")
        return 0
    target = target.resolve()
    (target / "export").mkdir(parents=True, exist_ok=True)
    (target / "data").mkdir(parents=True, exist_ok=True)
    if target != source:
        for path in (source / "export").iterdir():
            if path.is_file():
                shutil.copyfile(path, target / "export" / path.name)
    for week, payload in revised.items():
        export.write_weekly_csv(target / "export" / f"weekly-scores-{week}.csv", week, payload["cells"])
    # No fabricated raw database is needed to compose an accumulated bundle.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE runs (id TEXT, started_at TEXT)")
    latest_week = sorted(revised)[-1]
    bundle = export.build_bundle(conn, snapshots[latest_week], old_bundle["query_set"], revised, manifest)
    conn.close()
    bundle["generated_at"] = old_bundle["generated_at"]  # Analysis revision is separately dated.
    bundle["query_set"] = old_bundle["query_set"]
    bundle["export"] = old_bundle["export"]
    bundle["analysis_revision"] = revised[latest_week]["analysis_revision"]
    export._assert_no_vendor_content(bundle)
    export.write_site_data(target / "data", bundle, snapshots)
    metadata = json.loads((source / "export" / "manifest.json").read_text())
    metadata["analysis_revision"] = revised[metadata["week"]]["analysis_revision"]
    export.write_json(target / "export" / "manifest.json", metadata)
    export.assert_heldout_withheld(target, manifest)
    print(f"Wrote {inference.VERSION} to {target}; retrieval dates and numerical evidence retained.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, AssertionError) as exc:
        print(f"recomputation refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
