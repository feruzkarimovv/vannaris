"""The two runner functions that decide what becomes published data.

`validity()` is what tells a scheduler "this run is not fit to publish" by way
of a non-zero exit. On Monday morning that decision runs unattended, with
nobody reading the console, and it is the only thing standing between a
degraded run and a row on the site. It had no test.

`aggregate()` carries the downgrade guard, which exists because the failure it
prevents already happened once: a two-query smoke test overwrote a 150-query
result and left behind a published-looking cell computed from two queries.
`schema.sql` says so in as many words. That guard had no test either.

Both are the same category of bug — they do not crash, they publish. Nothing
here makes a network call or spends anything.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import storage  # noqa: E402
from src.judge.ensemble import JUDGES, JudgeScore  # noqa: E402
from src.runner import MIN_COMPLETE_SHARE, aggregate, validity  # noqa: E402
from src.vendors.base import ResponseMode, SearchResponse, SearchResult  # noqa: E402

FAMILIES = [f for f, _ in JUDGES]


def ensemble(overall=7.0, families=None, missing=()):
    """One response's worth of judge scores."""
    out = []
    for fam in (families or FAMILIES):
        out.append(JudgeScore(judge_family=fam, judge_model="m",
                              overall=None if fam in missing else overall))
    return out


def resp(query_id="q1", vendor="fixture_alpha", ok=True, latency=100, cost=0.001):
    return SearchResponse(
        vendor=vendor, query_id=query_id, response_mode=ResponseMode.RANKED_RESULTS,
        results=[SearchResult(url="https://example.invalid/a", rank=0)],
        latency_ms=latency, cost_usd=cost,
        error=None if ok else "FIXTURE ERROR: synthetic",
    )


def run_of(n_queries, vendor="fixture_alpha", complete=True, ok=True):
    """n responses for one vendor, with or without full ensembles."""
    responses = [resp(f"q{i}", vendor, ok=ok) for i in range(n_queries)]
    scored = {
        f"q{i}::{vendor}": ensemble(missing=() if complete else {FAMILIES[-1]})
        for i in range(n_queries)
    }
    return responses, scored


# ------------------------------------------------------- the publish decision

class TestValidity(unittest.TestCase):
    """Empty means publishable. Every other return value stops a week."""

    def test_a_healthy_run_is_publishable(self):
        responses, scored = run_of(10)
        self.assertEqual(validity(scored, responses), [])

    def test_nothing_judged_at_all(self):
        # The shape a total judge-side outage takes. Reported as one problem
        # rather than as every downstream symptom.
        self.assertEqual(validity({}, [resp()]), ["no response was judged at all"])

    def test_empty_score_lists_count_as_nothing_judged(self):
        # scored can carry keys whose value is an empty list when every judge
        # call for that response failed. Those are not judged responses, and
        # counting them would divide by a larger denominator and understate the
        # damage.
        self.assertEqual(validity({"q1::v": [], "q2::v": []}, [resp()]),
                         ["no response was judged at all"])

    def test_a_missing_judge_family_stops_the_run(self):
        # AUTONOMY.md item 1: the cross-family split IS the bias mitigation.
        # Two families is not a degraded ensemble, it is a different
        # methodology, and it must not be published as though it were the same.
        responses = [resp(f"q{i}") for i in range(10)]
        scored = {f"q{i}::fixture_alpha": ensemble(families=FAMILIES[:2])
                  for i in range(10)}
        problems = validity(scored, responses)
        self.assertTrue(any(FAMILIES[2] in p for p in problems), problems)

    def test_every_missing_family_is_named_not_just_the_first(self):
        responses = [resp(f"q{i}") for i in range(10)]
        scored = {f"q{i}::fixture_alpha": ensemble(families=FAMILIES[:1])
                  for i in range(10)}
        problems = validity(scored, responses)
        for fam in FAMILIES[1:]:
            self.assertTrue(any(fam in p for p in problems), (fam, problems))

    def test_a_family_present_but_scoring_nothing_still_counts_as_missing(self):
        # A judge that answered every call with unparseable output produces
        # rows with overall=None. It is present in the data and absent from the
        # methodology, and the second is what matters.
        responses = [resp(f"q{i}") for i in range(10)]
        scored = {f"q{i}::fixture_alpha": ensemble(missing={FAMILIES[0]})
                  for i in range(10)}
        problems = validity(scored, responses)
        self.assertTrue(any(FAMILIES[0] in p for p in problems), problems)

    def test_completeness_below_the_floor_stops_the_run(self):
        responses = [resp(f"q{i}") for i in range(10)]
        scored = {f"q{i}::fixture_alpha": ensemble(missing=() if i < 5 else {FAMILIES[0]})
                  for i in range(10)}
        problems = validity(scored, responses)
        self.assertTrue(any("complete ensemble" in p for p in problems), problems)

    def test_completeness_exactly_at_the_floor_is_allowed(self):
        # The floor is a floor, not a threshold to clear. A run landing exactly
        # on it is publishable, and this pins `<` rather than `<=`.
        n = 10
        n_complete = int(MIN_COMPLETE_SHARE * n)
        responses = [resp(f"q{i}") for i in range(n)]
        scored = {f"q{i}::fixture_alpha":
                  ensemble(missing=() if i < n_complete else {FAMILIES[0]})
                  for i in range(n)}
        # Every family still appears somewhere, so the only rule in play is the
        # completeness share.
        problems = [p for p in validity(scored, responses) if "complete ensemble" in p]
        self.assertEqual(problems, [])

    def test_every_vendor_call_failing_stops_the_run(self):
        responses = [resp(f"q{i}", ok=False) for i in range(10)]
        scored = {f"q{i}::fixture_alpha": ensemble() for i in range(10)}
        self.assertIn("every vendor call failed", validity(scored, responses))

    def test_one_vendor_failing_does_not_stop_the_run(self):
        # Failure tolerance is the design: a vendor outage is data about that
        # vendor, not a reason to lose the week.
        responses = ([resp(f"q{i}", "fixture_alpha") for i in range(10)] +
                     [resp(f"q{i}", "fixture_bravo", ok=False) for i in range(10)])
        scored = {f"q{i}::fixture_alpha": ensemble() for i in range(10)}
        scored.update({f"q{i}::fixture_bravo": ensemble() for i in range(10)})
        self.assertEqual(validity(scored, responses), [])

    def test_problems_accumulate_rather_than_short_circuiting(self):
        # An operator reading a failed scheduled run gets the whole picture in
        # one log, not one problem per re-run.
        responses = [resp(f"q{i}", ok=False) for i in range(10)]
        scored = {f"q{i}::fixture_alpha": ensemble(families=FAMILIES[:1])
                  for i in range(10)}
        self.assertGreater(len(validity(scored, responses)), 1)


# ------------------------------------------------------------ downgrade guard

class TestAggregateDowngradeGuard(unittest.TestCase):
    """A smoke run must never overwrite a full run's cell. It did, once."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = storage.connect(Path(self._tmp.name) / "t.db")
        self.qmap = {f"q{i}": {"category": "general_facts"} for i in range(200)}

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def cell(self, vendor="fixture_alpha", category="general_facts"):
        return self.conn.execute(
            "SELECT n_queries, median_score, run_id FROM weekly_scores "
            "WHERE week=? AND vendor=? AND category=?",
            ("2099-W01", vendor, category)).fetchone()

    def test_a_run_writes_its_cell(self):
        responses, scored = run_of(20)
        aggregate(self.conn, "2099-W01", "run-full", responses, scored, self.qmap)
        n_queries, score, run_id = self.cell()
        self.assertEqual(n_queries, 20)
        self.assertEqual(run_id, "run-full")
        self.assertEqual(score, 7.0)

    def test_a_smaller_run_does_not_overwrite_a_larger_one(self):
        big, big_scored = run_of(20)
        aggregate(self.conn, "2099-W01", "run-full", big, big_scored, self.qmap)

        small = [resp("q0"), resp("q1")]
        small_scored = {"q0::fixture_alpha": ensemble(1.0),
                        "q1::fixture_alpha": ensemble(1.0)}
        aggregate(self.conn, "2099-W01", "run-smoke", small, small_scored, self.qmap)

        n_queries, score, run_id = self.cell()
        self.assertEqual(n_queries, 20, "a 2-query run overwrote a 20-query cell")
        self.assertEqual(score, 7.0)
        self.assertEqual(run_id, "run-full")

    def test_a_larger_run_does_overwrite(self):
        small, small_scored = run_of(5)
        aggregate(self.conn, "2099-W01", "run-smoke", small, small_scored, self.qmap)
        big = [resp(f"q{i}") for i in range(20)]
        big_scored = {f"q{i}::fixture_alpha": ensemble(9.0) for i in range(20)}
        aggregate(self.conn, "2099-W01", "run-full", big, big_scored, self.qmap)

        n_queries, score, run_id = self.cell()
        self.assertEqual(n_queries, 20)
        self.assertEqual(score, 9.0)
        self.assertEqual(run_id, "run-full")

    def test_a_rerun_of_the_same_size_replaces(self):
        # Equal coverage is a re-run, not a downgrade. Refusing it would make a
        # legitimate repeat impossible without hand-editing the database.
        first, first_scored = run_of(10)
        aggregate(self.conn, "2099-W01", "run-a", first, first_scored, self.qmap)
        second = [resp(f"q{i}") for i in range(10)]
        second_scored = {f"q{i}::fixture_alpha": ensemble(8.0) for i in range(10)}
        aggregate(self.conn, "2099-W01", "run-b", second, second_scored, self.qmap)
        self.assertEqual(self.cell()[2], "run-b")

    def test_the_guard_is_per_cell_not_per_run(self):
        # A run can be larger in one category and smaller in another. Each cell
        # is judged on its own coverage.
        qmap = {"q0": {"category": "general_facts"}, "q1": {"category": "general_facts"},
                "q2": {"category": "long_tail"}}
        big = [resp("q0"), resp("q1")]
        aggregate(self.conn, "2099-W01", "run-a", big,
                  {"q0::fixture_alpha": ensemble(), "q1::fixture_alpha": ensemble()}, qmap)
        mixed = [resp("q0"), resp("q2")]
        aggregate(self.conn, "2099-W01", "run-b", mixed,
                  {"q0::fixture_alpha": ensemble(2.0), "q2::fixture_alpha": ensemble(2.0)},
                  qmap)
        # general_facts went 2 -> 1 and is protected; long_tail is new and lands.
        self.assertEqual(self.cell()[0], 2)
        self.assertEqual(self.cell(category="long_tail")[0], 1)

    def test_a_response_without_a_full_ensemble_contributes_nothing(self):
        # aggregate() goes through median_overall, which returns None for an
        # incomplete ensemble. If that ever changed, cells would start being
        # computed two different ways with no visible symptom.
        responses, scored = run_of(10, complete=False)
        aggregate(self.conn, "2099-W01", "run-a", responses, scored, self.qmap)
        self.assertIsNone(self.cell())

    def test_delta_from_best_is_measured_against_the_leader(self):
        responses = ([resp(f"q{i}", "fixture_alpha") for i in range(5)] +
                     [resp(f"q{i}", "fixture_bravo") for i in range(5)])
        scored = {f"q{i}::fixture_alpha": ensemble(9.0) for i in range(5)}
        scored.update({f"q{i}::fixture_bravo": ensemble(6.0) for i in range(5)})
        aggregate(self.conn, "2099-W01", "run-a", responses, scored, self.qmap)
        deltas = dict(self.conn.execute(
            "SELECT vendor, delta_from_best FROM weekly_scores WHERE week=?",
            ("2099-W01",)))
        self.assertEqual(deltas["fixture_alpha"], 0.0)
        self.assertEqual(deltas["fixture_bravo"], 3.0)

    def test_errored_responses_are_counted_but_not_scored(self):
        responses = [resp(f"q{i}") for i in range(8)] + \
                    [resp(f"q{i}", ok=False) for i in range(8, 10)]
        scored = {f"q{i}::fixture_alpha": ensemble() for i in range(8)}
        aggregate(self.conn, "2099-W01", "run-a", responses, scored, self.qmap)
        n_queries, _, _ = self.cell()
        n_errors = self.conn.execute(
            "SELECT n_errors FROM weekly_scores WHERE week=?", ("2099-W01",)).fetchone()[0]
        self.assertEqual(n_queries, 10, "the denominator must include failed calls")
        self.assertEqual(n_errors, 2)


if __name__ == "__main__":
    unittest.main()
