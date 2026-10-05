"""The free demo must prove real recovery without touching measured data."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from src.demo import KIND, ROOT, WARNING, WEEK, SyntheticTransport, build_demo


class TestOfflineRecoveryDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="vannaris-demo-test-")
        cls.output = Path(cls.directory.name) / "demo"
        cls.measured_before = {
            path.relative_to(ROOT / "site").as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for name in ("data", "export") for path in (ROOT / "site" / name).rglob("*") if path.is_file()
        }
        # A real key in the process environment must have no influence on a
        # demo. Any accidental ordinary HTTP connection is a test failure.
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "DO-NOT-USE-THIS-ENV-KEY"}), \
                patch("httpx.AsyncHTTPTransport.handle_async_request",
                      side_effect=AssertionError("Demo tried to open a network connection")), \
                contextlib.redirect_stdout(io.StringIO()):
            cls.manifest = build_demo(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def database(self):
        conn = sqlite3.connect(f"file:{self.output / 'fixture.db'}?mode=ro", uri=True)
        self.addCleanup(conn.close)
        return conn

    def test_recovery_reuses_successes_and_keeps_the_failed_provider(self):
        conn = self.database()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT week,status FROM runs").fetchone(), (WEEK, "completed"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0], 360)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_responses WHERE error IS NOT NULL").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM judge_scores").fetchone()[0], 359 * 3)
        attempts = conn.execute("SELECT id,status FROM judging_attempts ORDER BY started_at").fetchall()
        self.assertEqual([row[1] for row in attempts], ["partial", "completed"])
        self.assertEqual(conn.execute(
            "SELECT judge_family,COUNT(*) FROM judge_call_attempts WHERE judging_attempt_id=? "
            "GROUP BY judge_family", (attempts[1][0],),
        ).fetchall(), [("google", 359)])
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM judge_scores WHERE judging_attempt_id=?", (attempts[0][0],),
        ).fetchone()[0], 359 * 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM run_queries").fetchone()[0], 120)
        self.assertEqual(conn.execute("SELECT COUNT(DISTINCT vendor) FROM raw_responses").fetchone()[0], 3)
        self.assertTrue(self.manifest["recovery"]["original_cost_preserved"])
        self.assertEqual(self.manifest["recovery"]["vendor_calls_repeated"], 0)

    def test_the_first_export_refuses_and_the_recovered_export_is_explicitly_synthetic(self):
        self.assertIn("Nothing exported", (self.output / "export-refusal.log").read_text())
        latest = json.loads((self.output / "site" / "data" / "latest.json").read_text())
        self.assertEqual(latest["week"], WEEK)
        self.assertEqual(latest["completeness"]["complete_ensembles"], 359)
        self.assertTrue(latest["synthetic"])
        self.assertEqual(latest["synthetic_warning"], WARNING)
        for page in (self.output / "site").rglob("*.html"):
            self.assertIn(WARNING, page.read_text(), page.name)
        bundle = (self.output / "site" / "data" / "bundle.js").read_text()
        self.assertIn('"synthetic": true', bundle)
        self.assertIn("fixture_alpha", bundle)
        self.assertFalse((self.output / "site" / "data" / "2026-W35.json").exists())
        self.assertEqual(self.manifest["kind"], KIND)
        self.assertEqual(self.manifest["totals"]["actual_api_spend_usd"], 0)
        self.assertGreater(self.manifest["totals"]["simulated_vendor_cost_usd"], 0)

    def test_manifest_hashes_match_the_artifacts_and_measured_site_is_untouched(self):
        for name, expected in self.manifest["hashes"].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), expected, name)
        for name, url in self.manifest["artifacts"].items():
            self.assertTrue((self.output / "site" / url).is_file(), name)
        measured_after = {
            path.relative_to(ROOT / "site").as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for name in ("data", "export") for path in (ROOT / "site" / name).rglob("*") if path.is_file()
        }
        self.assertEqual(measured_after, self.measured_before)
        requests = [json.loads(row) for row in (self.output / "requests.jsonl").read_text().splitlines()]
        self.assertEqual(sum(row["stage"] == "fetch" for row in requests), 360)
        self.assertEqual(sum(row["stage"] == "judge" for row in requests), 359 * 3)
        self.assertNotIn("DO-NOT-USE-THIS-ENV-KEY", (self.output / "manifest.json").read_text())

    def test_output_guard_preserves_production_and_unrelated_files(self):
        for destination in (ROOT / "site" / "data", ROOT / "data", ROOT / "src"):
            with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, "separate"):
                build_demo(destination)
        unrelated = Path(self.directory.name) / "unrelated"
        unrelated.mkdir()
        content = unrelated / "user-file.txt"
        content.write_text("Preserve this file.")
        with self.assertRaisesRegex(ValueError, "non-demo"):
            build_demo(unrelated)
        self.assertEqual(content.read_text(), "Preserve this file.")

    def test_mock_transport_fails_closed_for_unknown_destinations(self):
        request = httpx.Request("POST", "https://unrecognised.example.invalid/api", json={})
        with self.assertRaisesRegex(AssertionError, "unrecognised"):
            SyntheticTransport(7).handle(request)

    def test_seeded_scores_do_not_depend_on_async_request_order(self):
        def request(index):
            return httpx.Request("POST", "https://api.openai.com/v1/chat/completions", json={
                "messages": [{"content": f"FIXTURE QUERY FX-{index:03d}; SYNTHETIC fixture_bravo"}],
            })
        first, reordered, other_seed = SyntheticTransport(7), SyntheticTransport(7), SyntheticTransport(8)
        expected = first.handle(request(12)).json()
        reordered.handle(request(3))
        reordered.handle(request(41))
        self.assertEqual(reordered.handle(request(12)).json(), expected)
        self.assertNotEqual(other_seed.handle(request(12)).json(), expected)


if __name__ == "__main__":
    unittest.main()
