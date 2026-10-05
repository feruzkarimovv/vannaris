"""Content-safe operational status; never serialize questions, payloads or errors.

The weekly workflow may publish this summary, whereas the recovery database
requires a separate confidential storage boundary. Reading uses SQLite's
read-only mode and does not migrate or create a database.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3


def publication_health(latest: dict, now: dt.datetime) -> dict:
    year, week, _ = now.isocalendar()
    expected = f"{year}-W{week:02d}"
    published = latest.get("week")
    gap = None
    if isinstance(published, str):
        try:
            yy, ww = published.split("-W")
            monday = dt.date.fromisocalendar(int(yy), int(ww), 1)
            current = dt.date.fromisocalendar(year, week, 1)
            gap = (current - monday).days // 7
        except (ValueError, TypeError):
            pass
    current = published == expected
    scheduled = latest.get("trigger") == "scheduled"
    return {
        "expected_week": expected,
        "published_week": published,
        "weeks_behind": gap,
        "scheduled": scheduled,
        "healthy": current and scheduled,
        "state": "current" if current and scheduled else "manual_only" if current else "stale",
    }


def summarize(db: Path, site: Path, now: dt.datetime | None = None,
              publication_outcome: str | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    result = {
        "schema_version": 1,
        "kind": "sanitized_run_status",
        "generated_at": now.isoformat(),
        "contains_raw_content": False,
        "run": None,
        "state": "not_started",
        "automation": {key.removeprefix("GITHUB_").lower(): os.environ[key]
                       for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME")
                       if key in os.environ},
    }
    if db.is_file():
        with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if {"runs", "raw_responses", "judge_scores"} <= tables:
                columns = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
                status_column = ", status" if "status" in columns else ""
                row = conn.execute("SELECT id, week, started_at, finished_at, trigger, query_set_hash" + status_column + " FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
                if row:
                    run = dict(row)
                    responses = conn.execute("SELECT COUNT(*), SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) FROM raw_responses WHERE run_id=?", (row["id"],)).fetchone()
                    complete = conn.execute("SELECT COUNT(*) FROM (SELECT rr.id FROM raw_responses rr LEFT JOIN judge_scores js ON js.response_id=rr.id WHERE rr.run_id=? AND rr.error IS NULL GROUP BY rr.id HAVING COUNT(DISTINCT js.judge_family)=3)", (row["id"],)).fetchone()[0]
                    run.update(responses=responses[0], vendor_errors=responses[1] or 0, complete_ensembles=complete)
                    result["run"] = run
                    result["state"] = run.get("status") or ("legacy_finished" if row["finished_at"] else "interrupted")
                    if "judging_attempts" in tables:
                        attempt = conn.execute("SELECT id, started_at, finished_at, status FROM judging_attempts WHERE run_id=? ORDER BY started_at DESC LIMIT 1", (row["id"],)).fetchone()
                        result["latest_judging_attempt"] = dict(attempt) if attempt else None
    latest_path = site / "data" / "latest.json"
    latest = json.loads(latest_path.read_text()) if latest_path.is_file() else {}
    result["publication"] = publication_health(latest, now)
    result["publication"]["source"] = "checked-out or generated static export; deployment not verified"
    if publication_outcome is not None:
        if publication_outcome not in {"success", "failure", "skipped", "cancelled"}:
            raise ValueError("invalid publication outcome")
        result["generated_export"] = dict(result["publication"])
        result["publication"]["delivery_outcome"] = publication_outcome
        if publication_outcome != "success":
            result["publication"].update(healthy=False, state="not_published")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/vannaris.db"))
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--heartbeat", action="store_true")
    parser.add_argument("--publication-outcome", choices=("success", "failure", "skipped", "cancelled"))
    args = parser.parse_args()
    payload = summarize(args.db, args.site, publication_outcome=args.publication_outcome)
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    else:
        print(rendered, end="")
    return int(args.heartbeat and not payload["publication"]["healthy"])


if __name__ == "__main__":
    raise SystemExit(main())
