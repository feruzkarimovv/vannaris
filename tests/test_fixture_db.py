"""The fixture has to keep covering what it claims to cover.

`scripts/check-all.sh` runs the export against a generated fixture when no real
database is present, which is what turned a SKIPPED gate into a real one. But
"the export ran clean" is a weaker statement than it looks: an export over a
fixture that had lost its suppressed cell, its rejected runs and its scheduled
trigger would still run clean, and the gate would stay green while checking
less. That silent narrowing is exactly the failure mode `AUTONOMY.md` is
written against, so the coverage claims are asserted here rather than trusted.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import export  # noqa: E402
from src.judge.ensemble import JUDGES  # noqa: E402


def _build(out: Path) -> Path:
    """Run the generator as a subprocess, the way check-all.sh does.

    Importing it would test a slightly different thing than the gate runs.
    """
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_fixture_db.py"),
         "--out", str(out), "--quiet"],
        check=True, capture_output=True,
    )
    return out / "fixture.db"


class TestFixtureGeneration(unittest.TestCase):
    """The generator itself: deterministic, and unmistakably synthetic."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name)
        cls.db = _build(cls.dir / "a")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def _dump(db: Path) -> list[str]:
        conn = sqlite3.connect(db)
        rows = []
        for table in ("runs", "queries", "raw_responses", "judge_scores"):
            rows += [str(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
        conn.close()
        return rows

    def test_is_deterministic(self):
        # A fixture that differs between runs cannot distinguish a regression
        # from a coin flip, and the failure would land on whoever changed
        # something unrelated.
        other = _build(self.dir / "b")
        self.assertEqual(self._dump(self.db), self._dump(other))

    def test_nothing_is_mistakable_for_a_measurement(self):
        conn = sqlite3.connect(self.db)
        vendors = {r[0] for r in conn.execute("SELECT DISTINCT vendor FROM raw_responses")}
        self.assertTrue(all(v.startswith("fixture_") for v in vendors), vendors)

        weeks = {r[0] for r in conn.execute("SELECT DISTINCT week FROM runs")}
        self.assertTrue(all(w.startswith("2099-") for w in weeks), weeks)

        for (text,) in conn.execute("SELECT text FROM queries"):
            self.assertTrue(text.startswith("FIXTURE QUERY"), text)

        # Retrieved content is the part someone could most plausibly mistake for
        # real, so it is pinned to a TLD that is guaranteed never to resolve.
        for (results,) in conn.execute(
                "SELECT results FROM raw_responses WHERE results IS NOT NULL LIMIT 20"):
            for r in json.loads(results):
                self.assertIn("example.invalid", r["url"])

        for (notes,) in conn.execute("SELECT notes FROM runs"):
            self.assertIn("SYNTHETIC FIXTURE", notes)
        conn.close()

    def test_raw_payload_is_never_populated(self):
        # Nothing in the fixture should teach anyone that filling this column is
        # normal — schema.sql marks it NOT EXPORTED, and the export's own
        # assertion is the only thing standing between it and publication.
        conn = sqlite3.connect(self.db)
        n = conn.execute(
            "SELECT COUNT(*) FROM raw_responses WHERE raw_payload IS NOT NULL").fetchone()[0]
        conn.close()
        self.assertEqual(n, 0)


class TestFixtureCoverage(unittest.TestCase):
    """What the export actually sees. These are the gate's coverage claims."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        out = Path(cls._tmp.name)
        db = _build(out)
        queries = {q["id"]: q for q in json.loads((out / "queries.json").read_text())["queries"]}
        query_set = json.loads((out / "queries.json").read_text())
        conn = export.connect(db)
        cls.bundle = export.build_bundle(conn, queries, query_set, {})
        cls.runs = export.candidate_runs(conn)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_covers_every_category_and_several_vendors(self):
        week = self.bundle["all_weeks"][self.bundle["weeks"][0]]
        self.assertEqual({c["category"] for c in week["cells"]}, set(export.CATEGORY_META))
        self.assertGreaterEqual(len({c["vendor"] for c in week["cells"]}), 3)

    def test_has_both_complete_and_incomplete_ensembles(self):
        week = self.bundle["all_weeks"][self.bundle["weeks"][0]]
        comp = week["completeness"]
        self.assertGreater(comp["complete_ensembles"], 0)
        self.assertLess(comp["complete_ensembles"], comp["responses"],
                        "no incomplete ensemble — the coverage arithmetic is untested")

    def test_has_a_vendor_error(self):
        week = self.bundle["all_weeks"][self.bundle["weeks"][0]]
        self.assertGreater(week["completeness"]["vendor_errors"], 0)

    def test_a_cell_is_suppressed_below_the_coverage_floor(self):
        suppressed = [c for w in self.bundle["all_weeks"].values()
                      for c in w["cells"] if c["score"] is None]
        self.assertTrue(suppressed, "no suppressed cell — MIN_CELL_COVERAGE is untested")
        for c in suppressed:
            self.assertLess(c["coverage"], export.MIN_CELL_COVERAGE)
            # Suppressed, not softened: the cell still states its coverage so a
            # reader can see why the number is missing.
            self.assertIn("coverage", c)

    def test_a_run_fails_selection_for_too_few_queries(self):
        rejected = [r for r in self.runs
                    if r["min_per_category"] < export.MIN_QUERIES_PER_CATEGORY]
        self.assertTrue(rejected)
        for r in rejected:
            self.assertIsNot(export.canonical_run(self.runs, r["week"]), r)

    def test_a_run_fails_selection_for_too_few_complete_ensembles(self):
        rejected = [r for r in self.runs
                    if r["completeness"] < export.MIN_RUN_COMPLETENESS]
        self.assertTrue(rejected, "no run below MIN_RUN_COMPLETENESS — that floor is untested")
        for r in rejected:
            self.assertIsNot(export.canonical_run(self.runs, r["week"]), r)

    def test_rejected_runs_stay_in_the_published_record(self):
        # "Chosen, not inherited" is only checkable if the candidates that lost
        # are published next to the one that won.
        ids = {r["id"] for r in self.bundle["runs_considered"]}
        self.assertEqual(ids, {r["id"] for r in self.runs})

    def test_track_record_spans_two_weeks_with_a_scheduled_one(self):
        tr = self.bundle["track_record"]
        self.assertEqual(tr["weeks_published"], 2)
        self.assertEqual(tr["scheduled_weeks"], 1)
        self.assertTrue(tr["schedule_started"])

    def test_judge_disagreement_is_measurable(self):
        judging = self.bundle["all_weeks"][self.bundle["weeks"][0]]["judging"]
        self.assertEqual(len(judging["judges"]), len(JUDGES))
        self.assertIsNotNone(judging["family_spread"])
        self.assertIsNotNone(judging["mean_disagreement"])
        self.assertGreater(judging["responses_over_3pts"], 0)

    def test_export_carries_no_vendor_content(self):
        # The fixture's raw layer holds titles, URLs and snippets exactly as the
        # real one does, so this is a real exercise of the assertion rather than
        # a tautology over an empty raw layer.
        export._assert_no_vendor_content(self.bundle)


if __name__ == "__main__":
    unittest.main()
