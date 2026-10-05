"""Database open/migrate, shared by the runner and the exporter.

Lives here rather than in the runner because the exporter also writes (it can
repair the aggregate layer), and two modules applying their own idea of the
schema is how a benchmark ends up with two shapes of the same table.
"""

from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "vannaris.db"
SCHEMA = ROOT / "src" / "storage" / "schema.sql"

# Columns added to schema.sql after a database already existed. CREATE TABLE IF
# NOT EXISTS will not add them, so they are applied explicitly. Append-only:
# each entry is (table, column, type) and is applied once, if missing.
_MIGRATIONS: list[tuple[str, str, str]] = [
    # Records which run produced a published cell. Added after a two-query
    # smoke test silently overwrote a 150-query result — without this column
    # there was no way to tell from the aggregate table alone which run a
    # published number came from.
    ("weekly_scores", "run_id", "TEXT"),
    # How the run was invoked: 'manual' or 'scheduled'. The only honest basis
    # for saying the benchmark runs weekly is that scheduled runs exist in the
    # data, so the claim is recorded as evidence at the moment it becomes true
    # rather than written into a page by hand (CLAUDE.md). Deliberately without
    # the schema's DEFAULT: runs that pre-date the column get NULL, meaning
    # "unknown", which is the truth. Backfilling them to 'manual' would be a
    # guess written into the evidence layer.
    ("runs", "trigger", "TEXT"),
    # 'human' or 'model'. The calibration set exists to measure whether the LLM
    # judges track human judgement; a label produced by a model answers a
    # different question entirely, and the two must never pool. Deliberately
    # without a DEFAULT so rows written before this column read NULL — unknown,
    # which is the truth — rather than being backfilled to 'human' on a guess.
    ("human_labels", "labeller_kind", "TEXT"),
    # Whether a query belongs to the withheld set (src/heldout.py). Published
    # scores are computed from the public set alone, so this column is what
    # keeps the two apart — without it a held-out question would silently enter
    # a published cell and the table would stop being reproducible from the
    # published questions. NULL on rows written before the column means public,
    # which is true: every query that existed then was.
    ("queries", "held_out", "INTEGER"),
    # Which held-out set a run used, by id. Checkable against the manifest's
    # pre-registered hash, so "this run included the set committed on that
    # date" is a claim a reader can verify rather than take.
    ("runs", "heldout_set", "TEXT"),
    # The model string the provider returned, as distinct from the one asked
    # for. Pinning a model is only a guarantee if the pin is checked, and two of
    # the three pins are aliases. NULL on rows written before the column, which
    # is the truth: it was not recorded.
    ("judge_scores", "judge_model_returned", "TEXT"),
    # Whether a response's cost came from the vendor or from a price list.
    # SearchResponse has carried this since the adapters were written and it was
    # never persisted, so the export could not distinguish a measured cost from
    # an assumed one — while the business case leaned on the ratio between them.
    ("raw_responses", "cost_source", "TEXT"),
    # 'absolute' or 'pairwise'. Absolute scoring is what the first calibration
    # pass used and it hit a ceiling: twelve of fifteen human scores were 9 or
    # 10, leaving a correlation whose interval excluded nothing. Pairwise sets
    # ask which of two responses is better instead, and the two kinds must not
    # be pooled or compared -- they are different measurements with different
    # statistics. NULL on sets written before the column means absolute, which
    # is what they were, but the reader is told rather than assumed at.
    ("calibration_sets", "kind", "TEXT"),
    ("runs", "retrieval_finished_at", "TEXT"),
    ("runs", "status", "TEXT"),
    ("runs", "provenance", "TEXT"),
    ("judge_scores", "judging_attempt_id", "TEXT REFERENCES judging_attempts(id)"),
]


def _backfill_cost_source(conn: sqlite3.Connection) -> None:
    """Recover cost provenance for rows written before the column existed.

    This is a backfill and the other migrations above deliberately refuse to do
    one, so the difference matters. `trigger` and `labeller_kind` are *not*
    backfilled because the information was never recorded anywhere — filling
    them would be writing a guess into the evidence layer. Cost provenance is
    different: the vendor's own payload is stored on every row, and it either
    contains a billed figure or it does not. This reads that, so it recovers a
    fact rather than inventing one.

    Idempotent, and only ever writes rows that are currently NULL.
    """
    import json

    cols = {r[1] for r in conn.execute("PRAGMA table_info(raw_responses)")}
    if "cost_source" not in cols:
        return
    todo = conn.execute(
        "SELECT id, raw_payload FROM raw_responses WHERE cost_source IS NULL"
    ).fetchall()
    for rid, raw in todo:
        try:
            payload = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            payload = {}
        usage = payload.get("usage") if isinstance(payload, dict) else None
        cost_dollars = payload.get("costDollars") if isinstance(payload, dict) else None
        reported = (
            (isinstance(cost_dollars, dict) and cost_dollars.get("total") is not None)
            or (isinstance(usage, dict) and usage.get("cost") is not None)
        )
        conn.execute("UPDATE raw_responses SET cost_source = ? WHERE id = ?",
                     ("reported" if reported else "estimated", rid))
    if todo:
        conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    for table, column, decl in _MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if cols and column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()
    _backfill_cost_source(conn)


def connect(db_path: Path | str = DB_PATH, *, create: bool = True) -> sqlite3.Connection:
    path = Path(db_path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.is_file():
        # sqlite3.connect() creates the file whether or not the schema is then
        # applied, so `create=False` alone did not mean what its one caller
        # needed it to mean. src/export.py passes it precisely so that exporting
        # can never be the thing that brings a database into existence — an
        # empty export is a signal, not something to paper over — and that
        # comment described an intention the code did not carry out.
        #
        # The consequence was not theoretical. One export against a missing
        # database left a zero-byte data/vannaris.db behind, and from then on
        # `ls data/*.db` in scripts/check-all.sh matched, so the export gate
        # routed to the real database forever and failed on every run. A stray
        # empty file is a bad reason for a gate to be red.
        raise SystemExit(
            f"no database at {path} — nothing to export. Run the benchmark first "
            f"(python -m src.runner), or pass --db to point at one."
        )
    conn = sqlite3.connect(path)
    # Existing databases also need additive lifecycle tables/views. Their old
    # evidence is not backfilled into snapshots or invented attempt records.
    conn.executescript(SCHEMA.read_text())
    migrate(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        warnings.warn(
            f"database contains {len(violations)} legacy foreign-key violation(s); "
            "existing evidence was preserved and new writes enforce foreign keys",
            RuntimeWarning,
            stacklevel=2,
        )
    return conn
