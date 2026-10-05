"""Opening the database is where "read-only" has to actually mean read-only.

`src/export.py` opens with `create=False` on purpose: exporting must never be
the thing that brings a database into existence, because an empty export is a
signal that something upstream did not run. `sqlite3.connect()` creates the file
regardless, so that intention lived only in a comment until these tests.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import storage  # noqa: E402


class TestConnect(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_false_on_a_missing_database_refuses(self):
        path = self.dir / "absent.db"
        with self.assertRaises(SystemExit) as caught:
            storage.connect(path, create=False)
        # The message has to name the path. The failure it replaces was silent,
        # and a caller who cannot see which database was expected will go
        # looking in the wrong directory.
        self.assertIn(str(path), str(caught.exception))

    def test_create_false_leaves_no_file_behind(self):
        # The whole point. A zero-byte database left by a failed export is
        # indistinguishable from a real one to `ls data/*.db`, which is what
        # scripts/check-all.sh routes on.
        path = self.dir / "absent.db"
        with self.assertRaises(SystemExit):
            storage.connect(path, create=False)
        self.assertFalse(path.exists())

    def test_create_false_opens_an_existing_database(self):
        path = self.dir / "present.db"
        storage.connect(path).close()
        conn = storage.connect(path, create=False)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.assertIn("runs", tables)
        self.assertIn("judge_scores", tables)

    def test_create_true_still_creates_the_parent_directory(self):
        path = self.dir / "nested" / "deeper" / "new.db"
        conn = storage.connect(path)
        conn.close()
        self.assertTrue(path.is_file())

    def test_create_true_applies_the_schema(self):
        conn = storage.connect(self.dir / "new.db")
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        # The three publication layers schema.sql separates, plus the
        # calibration layer. Named individually rather than counted, so adding a
        # table does not silently satisfy this while dropping one does not fail.
        for t in ("runs", "queries", "raw_responses", "judge_scores",
                  "weekly_scores", "calibration_sets", "calibration_items",
                  "human_labels"):
            self.assertIn(t, tables)

    def test_migrations_are_applied_to_an_older_database(self):
        # A database created before `runs.trigger` existed. The site's entire
        # cadence claim is derived from that column, so a migration that quietly
        # failed to apply would leave every run reading as trigger-unknown.
        path = self.dir / "old.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE runs (id TEXT PRIMARY KEY, started_at TEXT, week TEXT,"
            " query_set_hash TEXT);"
            "CREATE TABLE weekly_scores (id TEXT PRIMARY KEY, week TEXT);"
        )
        conn.commit()
        conn.close()

        conn = storage.connect(path, create=False)
        runs = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
        weekly = {r[1] for r in conn.execute("PRAGMA table_info(weekly_scores)")}
        conn.close()
        self.assertIn("trigger", runs)
        self.assertIn("run_id", weekly)

    def test_migrating_twice_is_a_no_op(self):
        # _MIGRATIONS is append-only and applied on every open, so re-running it
        # has to be safe — a second ALTER TABLE for the same column would raise.
        path = self.dir / "twice.db"
        storage.connect(path).close()
        storage.connect(path, create=False).close()
        conn = storage.connect(path, create=False)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(runs)")]
        conn.close()
        self.assertEqual(len(cols), len(set(cols)))

    def test_foreign_keys_reject_new_orphan_evidence(self):
        conn = storage.connect(self.dir / "integrity.db")
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO judge_scores (id,response_id,judge_model,judge_family,overall,created_at) "
                "VALUES ('orphan','missing-response','fixture','fixture',7,'2099-01-01')")
        conn.close()

    def test_legacy_queries_remain_explicit_fallback_without_invented_snapshots(self):
        path = self.dir / "legacy.db"
        conn = sqlite3.connect(path)
        # The previous schema, before lifecycle tables and immutable snapshots.
        conn.executescript(
            "CREATE TABLE runs (id TEXT PRIMARY KEY,started_at TEXT NOT NULL,finished_at TEXT,"
            "week TEXT NOT NULL,query_set_hash TEXT NOT NULL,trigger TEXT,heldout_set TEXT,notes TEXT);"
            "CREATE TABLE queries (id TEXT PRIMARY KEY,category TEXT NOT NULL,text TEXT NOT NULL,"
            "source TEXT,gold_answer TEXT,gold_urls TEXT,rotates INTEGER DEFAULT 0,held_out INTEGER DEFAULT 0);"
            "CREATE TABLE raw_responses (id TEXT PRIMARY KEY,run_id TEXT REFERENCES runs(id),"
            "query_id TEXT REFERENCES queries(id),vendor TEXT,response_mode TEXT,answer TEXT,"
            "citations TEXT,results TEXT,latency_ms INTEGER,cost_usd REAL,cost_source TEXT,"
            "error TEXT,raw_payload TEXT,created_at TEXT,UNIQUE(run_id,query_id,vendor));"
            "CREATE TABLE judge_scores (id TEXT PRIMARY KEY,response_id TEXT REFERENCES raw_responses(id),"
            "judge_model TEXT,judge_family TEXT,relevance REAL,freshness REAL,citation_quality REAL,"
            "overall REAL,rationale TEXT,scored_chars INTEGER,prompt_tokens INTEGER,output_tokens INTEGER,"
            "judge_model_returned TEXT,created_at TEXT,UNIQUE(response_id,judge_model));"
        )
        conn.execute("INSERT INTO runs (id,started_at,week,query_set_hash) "
                     "VALUES ('legacy','2099-01-01','2099-W01','old-hash')")
        conn.execute("INSERT INTO queries (id,category,text,gold_answer) "
                     "VALUES ('q1','general_facts','legacy question','legacy answer')")
        conn.execute("INSERT INTO raw_responses (id,run_id,query_id,vendor,response_mode,created_at) "
                     "VALUES ('r1','legacy','q1','fixture','ranked_results','2099-01-01')")
        conn.commit()
        conn.close()
        conn = storage.connect(path, create=False)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM run_queries").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM judging_attempts").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT text,snapshot_source FROM response_queries").fetchone(),
                         ("legacy question", "legacy_fallback"))
        self.assertIsNone(conn.execute("SELECT retrieval_finished_at FROM runs").fetchone()[0])
        conn.close()


if __name__ == "__main__":
    unittest.main()
