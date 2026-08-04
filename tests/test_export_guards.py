"""The export's publication guards, tested directly rather than only in passing.

`tests/test_fixture_db.py` drives `src/export.py` end to end and asserts the
shape of what comes out. That proves the guards do not fire on good data. It
proves nothing about whether they fire on bad data — and a guard only ever
observed saying "ok" is indistinguishable from one that always says "ok".

The one that matters most is `_assert_no_vendor_content`. It is the last thing
standing between the raw layer and the public export, and `docs/03` is why:
retrieved URLs, titles, snippets and synthesized answers are stored for
reproducibility and never republished. That is a copyright and ToS-exposure
decision, not a formatting preference. Every run it has ever made was over data
that was already clean.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import export  # noqa: E402


def row(vendor="fixture_alpha", category="general_facts", median=7.0,
        latency=100, cost=0.001, error=None, complete=True):
    return {"vendor": vendor, "category": category, "median": median,
            "latency_ms": latency, "cost_usd": cost, "error": error,
            "complete": complete, "query_id": "q", "judges": {},
            "response_id": "r", "response_mode": "ranked_results", "n_results": 10}


# ------------------------------------------------- the raw-content firewall

class TestNoVendorContent(unittest.TestCase):
    """docs/03: derived scores are published, retrieved content is not."""

    def test_clean_payload_passes(self):
        export._assert_no_vendor_content(
            {"week": "2099-W01", "cells": [{"vendor": "v", "score": 7.0}]})

    def test_every_forbidden_key_is_actually_caught(self):
        # Driven from the set itself rather than from a list someone typed, so
        # adding a key to _FORBIDDEN_KEYS cannot leave it untested.
        for key in export._FORBIDDEN_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(AssertionError):
                    export._assert_no_vendor_content({key: "anything"})

    def test_a_snippet_buried_deep_is_caught(self):
        # The realistic shape. Nobody adds `snippet` at the top level; it
        # arrives four levels down inside a detail row someone extended.
        payload = {"all_weeks": {"2099-W01": {"detail": [
            {"q": "q1", "snippet": "vendor-written text"}]}}}
        with self.assertRaises(AssertionError):
            export._assert_no_vendor_content(payload)

    def test_the_error_names_where_it_found_it(self):
        # A build that fails with "vendor content present" and no path sends
        # someone hunting through a 40,000-line JSON file.
        payload = {"weeks": [{"cells": [{"url": "https://example.invalid/a"}]}]}
        with self.assertRaises(AssertionError) as caught:
            export._assert_no_vendor_content(payload)
        message = str(caught.exception)
        self.assertIn("url", message)
        self.assertIn("weeks", message)

    def test_a_forbidden_key_with_a_null_value_still_fails(self):
        # The key is the leak, not the value: `"answer": null` today is
        # `"answer": "..."` after one upstream change.
        with self.assertRaises(AssertionError):
            export._assert_no_vendor_content({"answer": None})

    def test_it_walks_into_lists_of_dicts(self):
        with self.assertRaises(AssertionError):
            export._assert_no_vendor_content([{"ok": 1}, {"title": "leak"}])

    def test_a_leak_past_the_first_fifty_entries_is_caught(self):
        # This is what found the bug. The walk used to stop at 50 entries per
        # list, which made it unsound precisely where it mattered: a published
        # week carries 750 detail rows, so anything past the 51st was invisible
        # to the only check standing between the raw layer and the public
        # export. A firewall with a sampling rate is not a firewall.
        payload = {"detail": [{"ok": i} for i in range(60)] + [{"title": "leak"}]}
        with self.assertRaises(AssertionError):
            export._assert_no_vendor_content(payload)

    def test_a_leak_in_the_last_row_of_a_full_sized_week_is_caught(self):
        # 750 rows is the real shape of one published week's detail array.
        rows = [{"q": f"q{i}", "m": 7.0} for i in range(750)]
        rows[-1]["snippet"] = "vendor-written text"
        with self.assertRaises(AssertionError):
            export._assert_no_vendor_content({"all_weeks": {"2099-W01": {"detail": rows}}})


# ------------------------------------------------------ suppression arithmetic

class TestBuildCells(unittest.TestCase):
    """A thin cell is published as null with its coverage stated, not softened."""

    def test_a_full_cell_gets_a_score(self):
        cells = export.build_cells([row() for _ in range(10)])
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]["score"], 7.0)
        self.assertEqual(cells[0]["coverage"], 1.0)

    def test_a_cell_under_the_floor_is_suppressed_not_averaged(self):
        rows = [row(median=7.0) for _ in range(5)] + \
               [row(median=None) for _ in range(5)]
        cell = export.build_cells(rows)[0]
        self.assertIsNone(cell["score"])
        self.assertEqual(cell["coverage"], 0.5)

    def test_a_suppressed_cell_still_states_its_coverage_and_counts(self):
        # Suppressed, not hidden. A reader has to be able to see why the number
        # is missing and apply a stricter bar themselves.
        rows = [row(median=7.0)] + [row(median=None) for _ in range(9)]
        cell = export.build_cells(rows)[0]
        self.assertIsNone(cell["score"])
        self.assertEqual(cell["n_queries"], 10)
        self.assertEqual(cell["n_scored"], 1)

    def test_a_cell_exactly_on_the_floor_is_published(self):
        n = 10
        scored = int(export.MIN_CELL_COVERAGE * n)
        rows = [row(median=7.0) for _ in range(scored)] + \
               [row(median=None) for _ in range(n - scored)]
        self.assertIsNotNone(export.build_cells(rows)[0]["score"])

    def test_errors_count_toward_the_denominator(self):
        rows = [row() for _ in range(8)] + \
               [row(median=None, error="FIXTURE ERROR") for _ in range(2)]
        cell = export.build_cells(rows)[0]
        self.assertEqual(cell["n_errors"], 2)
        self.assertEqual(cell["n_queries"], 10)

    def test_delta_from_best_is_measured_within_a_category(self):
        rows = [row("fixture_alpha", median=9.0) for _ in range(10)] + \
               [row("fixture_bravo", median=6.0) for _ in range(10)]
        cells = {c["vendor"]: c for c in export.build_cells(rows)}
        self.assertEqual(cells["fixture_alpha"]["delta_from_best"], 0.0)
        self.assertEqual(cells["fixture_bravo"]["delta_from_best"], 3.0)
        self.assertEqual(cells["fixture_bravo"]["pct_of_best"], 66.7)

    def test_a_suppressed_cell_has_no_delta(self):
        # A gap against the leader computed from a number that was withheld
        # would reintroduce the withheld number by the back door.
        rows = [row("fixture_alpha", median=9.0) for _ in range(10)] + \
               [row("fixture_bravo", median=None) for _ in range(10)]
        cells = {c["vendor"]: c for c in export.build_cells(rows)}
        self.assertIsNone(cells["fixture_bravo"]["delta_from_best"])
        self.assertIsNone(cells["fixture_bravo"]["pct_of_best"])

    def test_cells_are_ordered_easiest_category_first(self):
        # The site renders them in this order so the quality cliff reads as a
        # slope rather than an alphabetical accident.
        rows = [row(category=c) for c in ("long_tail", "general_facts", "multi_hop")]
        order = [c["category"] for c in export.build_cells(rows)]
        self.assertEqual(order, ["general_facts", "multi_hop", "long_tail"])


class TestVendorTotals(unittest.TestCase):
    def test_the_overall_score_is_the_mean_of_category_scores(self):
        # Not the mean of query scores. The two differ whenever coverage differs
        # by category, and only the category mean matches the table above it on
        # the page. Here: one category with 10 queries at 9, one with 2 at 3.
        # Category mean is 6.0; a query-weighted mean would be 8.0.
        rows = ([row(category="general_facts", median=9.0) for _ in range(10)] +
                [row(category="long_tail", median=3.0) for _ in range(10)])
        cells = export.build_cells(rows)
        totals = export.build_vendor_totals(rows, cells)
        self.assertEqual(totals[0]["score"], 6.0)

    def test_a_suppressed_category_is_left_out_of_the_vendor_score(self):
        rows = ([row(category="general_facts", median=8.0) for _ in range(10)] +
                [row(category="long_tail", median=None) for _ in range(10)])
        totals = export.build_vendor_totals(rows, export.build_cells(rows))
        self.assertEqual(totals[0]["score"], 8.0)

    def test_outright_wins_count_queries_one_vendor_took_alone(self):
        rows = []
        for i in range(3):
            a = row("fixture_alpha", median=9.0); a["query_id"] = f"q{i}"
            b = row("fixture_bravo", median=6.0); b["query_id"] = f"q{i}"
            rows += [a, b]
        totals = {t["vendor"]: t for t in
                  export.build_vendor_totals(rows, export.build_cells(rows))}
        self.assertEqual(totals["fixture_alpha"]["outright_wins"], 3)
        self.assertEqual(totals["fixture_alpha"]["shared_best"], 3)
        self.assertEqual(totals["fixture_bravo"]["outright_wins"], 0)
        self.assertEqual(totals["fixture_bravo"]["shared_best"], 0)

    def test_a_tie_is_credited_to_neither_vendor_outright(self):
        """The case the old fixture could not express, and the bug it hid.

        The previous version of this test scored 9.0 against 6.0, which can
        never tie, so it passed against an implementation that awarded every
        tied query to whichever vendor happened to be iterated first. On the
        real run that was two thirds of the query set, and it credited one
        vendor with 55 wins where it had won a single query alone.
        """
        rows = []
        for i in range(4):
            a = row("fixture_alpha", median=8.0); a["query_id"] = f"q{i}"
            b = row("fixture_bravo", median=8.0); b["query_id"] = f"q{i}"
            rows += [a, b]
        totals = {t["vendor"]: t for t in
                  export.build_vendor_totals(rows, export.build_cells(rows))}
        for v in ("fixture_alpha", "fixture_bravo"):
            self.assertEqual(totals[v]["outright_wins"], 0, v)
            self.assertEqual(totals[v]["shared_best"], 4, v)

    def test_win_counts_do_not_depend_on_row_order(self):
        """The defect was a readout of iteration order. Assert it cannot be."""
        rows = []
        for i in range(5):
            a = row("fixture_alpha", median=7.0); a["query_id"] = f"q{i}"
            b = row("fixture_bravo", median=7.0 if i % 2 else 9.0); b["query_id"] = f"q{i}"
            rows += [a, b]
        forward = {t["vendor"]: (t["outright_wins"], t["shared_best"]) for t in
                   export.build_vendor_totals(rows, export.build_cells(rows))}
        reversed_ = {t["vendor"]: (t["outright_wins"], t["shared_best"]) for t in
                     export.build_vendor_totals(list(reversed(rows)),
                                                export.build_cells(list(reversed(rows))))}
        self.assertEqual(forward, reversed_)

    def test_tie_rate_is_published(self):
        rows = []
        for i in range(4):
            a = row("fixture_alpha", median=8.0); a["query_id"] = f"q{i}"
            # q0 separates; q1-q3 tie.
            b = row("fixture_bravo", median=6.0 if i == 0 else 8.0); b["query_id"] = f"q{i}"
            rows += [a, b]
        stats = export.build_win_stats(rows)
        self.assertEqual(stats["n_queries_compared"], 4)
        self.assertEqual(stats["n_tied"], 3)
        self.assertEqual(stats["n_separated"], 1)
        self.assertEqual(stats["tie_rate_pct"], 75.0)


# ----------------------------------------------------------- history strictness

class TestLoadHistory(unittest.TestCase):
    """The published track record lives in git, so reading it is load-bearing."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, payload):
        (self.dir / name).write_text(json.dumps(payload))

    def test_week_files_are_loaded(self):
        self.write("2099-W01.json", {"week": "2099-W01"})
        self.write("2099-W02.json", {"week": "2099-W02"})
        self.assertEqual(set(export.load_history(self.dir)), {"2099-W01", "2099-W02"})

    def test_generated_siblings_are_not_mistaken_for_weeks(self):
        # latest.json sits in the same directory and is a copy of one week. Read
        # as a week it would double-count and inflate weeks_published.
        self.write("latest.json", {"week": "2099-W01"})
        self.assertEqual(export.load_history(self.dir), {})

    def test_a_mislabelled_week_file_is_fatal_not_skipped(self):
        # Silently dropping it would shorten the published track record, which
        # is the one number this project cannot get wrong in either direction.
        self.write("2099-W01.json", {"week": "2099-W99"})
        with self.assertRaises(SystemExit):
            export.load_history(self.dir)

    def test_a_missing_directory_is_empty_not_an_error(self):
        # A first-ever export has no history and that is not a failure.
        self.assertEqual(export.load_history(self.dir / "nope"), {})


class TestCanonicalRun(unittest.TestCase):
    """Chosen, not inherited — the most recent run must not win by being last."""

    @staticmethod
    def run(rid, week="2099-W01", complete=100, min_cat=10, completeness=0.9,
            started="2099-01-04T06:00:00+00:00"):
        return {"id": rid, "week": week, "complete": complete,
                "min_per_category": min_cat, "completeness": completeness,
                "categories": len(export.CATEGORY_META), "started_at": started}

    def test_the_most_complete_eligible_run_wins(self):
        runs = [self.run("a", complete=50), self.run("b", complete=140)]
        self.assertEqual(export.canonical_run(runs, "2099-W01")["id"], "b")

    def test_a_later_smoke_test_does_not_win_by_being_later(self):
        runs = [self.run("full", complete=140),
                self.run("smoke", complete=6, min_cat=2,
                         started="2099-01-04T23:00:00+00:00")]
        self.assertEqual(export.canonical_run(runs, "2099-W01")["id"], "full")

    def test_too_few_queries_per_category_is_ineligible(self):
        runs = [self.run("smoke", min_cat=export.MIN_QUERIES_PER_CATEGORY - 1)]
        self.assertIsNone(export.canonical_run(runs, "2099-W01"))

    def test_exactly_the_minimum_per_category_is_eligible(self):
        runs = [self.run("edge", min_cat=export.MIN_QUERIES_PER_CATEGORY)]
        self.assertIsNotNone(export.canonical_run(runs, "2099-W01"))

    def test_too_few_complete_ensembles_is_ineligible(self):
        runs = [self.run("thin", completeness=export.MIN_RUN_COMPLETENESS - 0.01)]
        self.assertIsNone(export.canonical_run(runs, "2099-W01"))

    def test_a_missing_category_is_ineligible(self):
        # Five of six categories is not a partial week, it is a different
        # query set, and publishing it in the same table would compare
        # differently-shaped runs.
        run = self.run("partial")
        run["categories"] = len(export.CATEGORY_META) - 1
        self.assertIsNone(export.canonical_run([run], "2099-W01"))

    def test_runs_from_another_week_are_not_considered(self):
        runs = [self.run("other", week="2099-W02", complete=999)]
        self.assertIsNone(export.canonical_run(runs, "2099-W01"))

    def test_no_runs_at_all_is_none_not_a_crash(self):
        self.assertIsNone(export.canonical_run([], "2099-W01"))


if __name__ == "__main__":
    unittest.main()
