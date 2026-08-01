"""Database open/migrate, shared by the runner and the exporter.

Lives here rather than in the runner because the exporter also writes (it can
repair the aggregate layer), and two modules applying their own idea of the
schema is how a benchmark ends up with two shapes of the same table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "searchbench.db"
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
]


def migrate(conn: sqlite3.Connection) -> None:
    for table, column, decl in _MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if cols and column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def connect(db_path: Path | str = DB_PATH, *, create: bool = True) -> sqlite3.Connection:
    path = Path(db_path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    if create:
        conn.executescript(SCHEMA.read_text())
    migrate(conn)
    return conn
