"""The released-data path refuses ambiguous joins and preserves observations."""

from __future__ import annotations

import csv
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import recompute_publication as recompute
from src import export, inference


class TestReleasedEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.week = "2099-W01"
        self.queries = {f"{cat}-{i}": {"id": f"{cat}-{i}", "category": cat, "text": "FIXTURE QUERY",
                                     "source": "fixture", "gold_answer": None, "rotates": 0}
                        for cat in export.CATEGORY_ORDER for i in range(2)}
        self.responses = []
        self.scores = []
        for qid, q in self.queries.items():
            self.responses.append({"week": self.week, "query_id": qid, "category": q["category"],
                                   "held_out": "0", "vendor": "fixture", "response_mode": "ranked_results",
                                   "n_results": "10", "latency_ms": "100", "cost_usd": "0.01",
                                   "cost_source": "estimated", "complete_ensemble": "1",
                                   "median_overall": "8.0", "error": ""})
            for fam, model in export.JUDGES:
                self.scores.append({"week": self.week, "query_id": qid, "category": q["category"],
                                    "held_out": "0", "vendor": "fixture", "judge_family": fam,
                                    "judge_model": model, "relevance": "8", "freshness": "8",
                                    "citation_quality": "8", "overall": "8", "scored_chars": "100",
                                    "prompt_tokens": "100", "output_tokens": "20"})
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        for name, rows in [(f"responses-{self.week}.csv", self.responses),
                           (f"judge-scores-{self.week}.csv", self.scores)]:
            with (self.directory / name).open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

    def load(self):
        return recompute.load_observations(self.directory, self.week, self.queries)

    def publication_site(self):
        """A fully derived, explicitly synthetic local publication for CLI tests."""
        site = self.directory / "site"
        directory = site / "export"
        directory.mkdir(parents=True)
        (site / "data").mkdir()
        for name in (f"responses-{self.week}.csv", f"judge-scores-{self.week}.csv"):
            shutil.copyfile(self.directory / name, directory / name)
        with (directory / "queries.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(next(iter(self.queries.values()))))
            writer.writeheader()
            writer.writerows(self.queries.values())
        inputs = {p.name: recompute.sha256(p) for p in directory.iterdir()}
        original = {"week": self.week, "run_id": "fixture-original", "ran_at": "2099-01-04T12:00:00Z",
                    "trigger": "manual", "query_set_hash": "fixture-commitment", "n_queries": 12,
                    "n_vendors": 1, "n_heldout_queries": 0, "vendor_spend_usd": 0.12,
                    "completeness": {"responses": 12, "complete_ensembles": 12}}
        revised = recompute.revise_week(original, self.load(), {}, inputs)
        export.write_json(site / "data" / f"{self.week}.json", revised)
        (site / "data" / "bundle.js").write_text("window.SB_DATA = " + json.dumps({"latest": revised}) + ";\n")
        return site

    def run_cli(self, site, mode="--check"):
        with patch.object(sys, "argv", ["recompute", "--site-root", str(site), mode]), \
             patch.object(recompute.heldout, "load_manifest", return_value={}), \
             contextlib.redirect_stdout(io.StringIO()):
            return recompute.main()

    def test_original_run_identity_and_retrieval_time_are_preserved(self):
        rows = self.load()
        original = {"week": self.week, "run_id": "fixture-original", "ran_at": "2099-01-04T12:00:00Z",
                    "trigger": "manual", "query_set_hash": "fixture-commitment", "n_queries": 12,
                    "n_vendors": 1, "n_heldout_queries": 0, "vendor_spend_usd": 0.12,
                    "completeness": {"responses": 12, "complete_ensembles": 12}}
        revised = recompute.revise_week(original, rows, {}, {"fixture.csv": "fixture-sha"})
        for field in ("week", "run_id", "ran_at", "trigger", "query_set_hash"):
            self.assertEqual(revised[field], original[field])
        self.assertEqual(revised["analysis"]["version"], inference.VERSION)
        self.assertEqual(revised["analysis_revision"]["input_sha256"], {"fixture.csv": "fixture-sha"})
        self.assertEqual(revised["vendor_spend_usd"], 0.12)

    def test_duplicate_response_is_refused(self):
        self.responses.append(dict(self.responses[0]))
        self.write()
        with self.assertRaisesRegex(ValueError, "duplicate response"):
            self.load()

    def test_duplicate_family_cannot_manufacture_a_complete_ensemble(self):
        self.scores[2]["judge_family"] = self.scores[0]["judge_family"]
        self.write()
        with self.assertRaisesRegex(ValueError, "duplicate judge family"):
            self.load()

    def test_contradictory_response_median_is_refused(self):
        self.responses[0]["median_overall"] = "10"
        self.write()
        with self.assertRaisesRegex(ValueError, "contradicts individual scores"):
            self.load()

    def test_non_finite_score_is_refused(self):
        self.scores[0]["overall"] = "nan"
        self.write()
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.load()

    def test_orphan_score_is_refused(self):
        self.scores[0]["query_id"] = "unobserved"
        self.write()
        with self.assertRaisesRegex(ValueError, "orphan score"):
            self.load()

    def test_legacy_missing_dimension_is_retained_as_missing(self):
        # Some released legacy Google scores contain overall but no citation
        # dimension. Preserve this limitation; never infer a missing score.
        self.scores[0]["citation_quality"] = ""
        self.write()
        rows = self.load()
        self.assertIsNone(rows[0]["judges"][export.JUDGES[0][0]]["citation_quality"])
        self.assertEqual(rows[0]["median"], 8.0)

    def test_withheld_rows_never_enter_public_cells(self):
        private = dict(self.responses[0], query_id="fixture-private", held_out="1", median_overall="2")
        self.responses.append(private)
        for score in self.scores[:3]:
            self.scores.append(dict(score, query_id="fixture-private", held_out="1", overall="2"))
        self.write()
        rows = self.load()
        public = [r for r in rows if not r["held_out"]]
        cells = export.build_cells(public)
        self.assertTrue(all(c["score"] == 8.0 for c in cells))
        self.assertEqual(sum(c["n_queries"] for c in cells), 12)

    def test_check_rejects_changed_prompt_tokens_even_if_summaries_match(self):
        site = self.publication_site()
        self.assertEqual(self.run_cli(site), 0)
        score_file = site / "export" / f"judge-scores-{self.week}.csv"
        scores = recompute.read_csv(score_file, {"prompt_tokens"})
        scores[0]["prompt_tokens"] = "101"
        with score_file.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(scores[0]))
            writer.writeheader()
            writer.writerows(scores)
        with self.assertRaisesRegex(ValueError, "recorded input hash mismatch"):
            self.run_cli(site)

    def test_in_place_cannot_silently_accept_changed_numerical_evidence(self):
        site = self.publication_site()
        publication = site / "data" / f"{self.week}.json"
        original_bytes = publication.read_bytes()
        score_file = site / "export" / f"judge-scores-{self.week}.csv"
        score_file.write_bytes(score_file.read_bytes().replace(b",100,100,20", b",100,101,20", 1))
        with self.assertRaisesRegex(ValueError, "recorded input hash mismatch"):
            self.run_cli(site, "--in-place")
        self.assertEqual(publication.read_bytes(), original_bytes)

    def test_materialized_query_snapshot_can_verify_shared_original_hash(self):
        site = self.publication_site()
        shared = site / "export" / "queries.csv"
        snapshot = site / "export" / f"queries-{self.week}.csv"
        shutil.copyfile(shared, snapshot)
        # The shared current snapshot can move on; the dated copy is the exact
        # original evidence recorded under its former shared filename.
        shared.unlink()
        self.assertEqual(self.run_cli(site), 0)

    def test_publication_revision_without_source_hashes_is_refused(self):
        site = self.publication_site()
        path = site / "data" / f"{self.week}.json"
        revised = json.loads(path.read_text())
        del revised["analysis_revision"]["input_sha256"]
        export.write_json(path, revised)
        with self.assertRaisesRegex(ValueError, "lacks recorded input hashes"):
            self.run_cli(site)


if __name__ == "__main__":
    unittest.main()
