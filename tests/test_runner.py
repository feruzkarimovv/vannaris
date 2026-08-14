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
from src.runner import (  # noqa: E402
    MIN_COMPLETE_SHARE,
    aggregate,
    load_responses,
    persist_run,
    persist_scores,
    validity,
)
from src.vendors.base import ResponseMode, SearchResponse, SearchResult  # noqa: E402

FAMILIES = [f for f, _ in JUDGES]
JUDGE_MODEL = dict(JUDGES)


def ensemble(overall=7.0, families=None, missing=()):
    """One response's worth of judge scores.

    Each family carries its own pinned model rather than a shared placeholder.
    That is not cosmetic: `judge_scores` is UNIQUE on (response_id,
    judge_model), so three scores sharing one model string are one score as far
    as the database is concerned, and a fixture that pretends otherwise cannot
    exercise persistence at all.
    """
    out = []
    for fam in (families or FAMILIES):
        out.append(JudgeScore(judge_family=fam, judge_model=JUDGE_MODEL.get(fam, fam),
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


# ------------------------------------------- surviving a failure while judging

class TestPersistenceSurvivesJudging(unittest.TestCase):
    """The vendor calls must outlive the stage most likely to kill the run.

    Everything used to be written in one call *after* judging returned. Judging
    is the stage that fails — rate limits, an exhausted balance, the workflow's
    90-minute timeout — so a failure there discarded all 750 vendor calls and
    the `--rejudge` recovery with them, because `--rejudge` reads a stored run
    and there was none. 2026-W32 is the hole that made.

    These tests are about the crash, not the happy path: the assertion that
    matters is that a run interrupted between the two writes is still on disk
    and still re-judgeable.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "t.db"
        self.conn = storage.connect(self.db)
        self.queries = [{"id": f"q{i}", "category": "general_facts",
                         "text": f"question {i}", "source": "authored"}
                        for i in range(4)]

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def store(self, run_id="run-a", n=4, vendor="fixture_alpha"):
        responses = [resp(f"q{i}", vendor) for i in range(n)]
        ids = persist_run(self.conn, run_id, "2099-W01", "hash0", self.queries,
                          responses, "2099-01-01T00:00:00+00:00", "scheduled")
        return responses, ids

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_the_responses_are_on_disk_before_any_judging(self):
        self.store()
        self.assertEqual(self.count("raw_responses"), 4)
        self.assertEqual(self.count("judge_scores"), 0)

    def test_an_interrupted_run_has_no_finished_at(self):
        # This is what tells a later reader — or a later session — that the run
        # stopped rather than completed with nothing to say.
        self.store()
        finished = self.conn.execute(
            "SELECT finished_at FROM runs WHERE id=?", ("run-a",)).fetchone()[0]
        self.assertIsNone(finished)

    def test_finishing_the_scores_closes_the_run(self):
        responses, ids = self.store()
        scored = {f"q{i}::fixture_alpha": ensemble() for i in range(4)}
        persist_scores(self.conn, "run-a", ids, scored)
        finished = self.conn.execute(
            "SELECT finished_at FROM runs WHERE id=?", ("run-a",)).fetchone()[0]
        self.assertIsNotNone(finished)
        self.assertEqual(self.count("judge_scores"), 4 * len(FAMILIES))

    def test_a_run_that_dies_during_judging_is_still_re_judgeable(self):
        # The whole point, modelled as it actually happens: responses stored,
        # judging raises, the process ends, and a later invocation reopens the
        # database and finds the run waiting.
        self.store()
        try:
            raise TimeoutError("the job timed out mid-judging")
        except TimeoutError:
            pass
        self.conn.close()

        conn = storage.connect(self.db)
        try:
            recovered = load_responses(conn, "run-a")
        finally:
            conn.close()
        self.conn = storage.connect(self.db)   # for tearDown

        self.assertEqual(len(recovered), 4)
        self.assertEqual({r.query_id for r in recovered},
                         {"q0", "q1", "q2", "q3"})

    def test_the_recovered_responses_carry_what_a_judge_needs(self):
        self.store()
        recovered = load_responses(self.conn, "run-a")
        one = next(r for r in recovered if r.query_id == "q0")
        self.assertEqual(one.vendor, "fixture_alpha")
        self.assertEqual([x.url for x in one.results],
                         ["https://example.invalid/a"])
        self.assertEqual(one.latency_ms, 100)

    def test_re_judging_a_recovered_run_costs_no_vendor_money(self):
        # The claim printed on the console at the point of failure. Counting the
        # spend twice would overstate what the benchmark costs to operate.
        self.store()
        recovered = load_responses(self.conn, "run-a")
        self.assertEqual([r.cost_usd for r in recovered], [0.0] * 4)

    def test_every_response_gets_an_id_the_scores_can_use(self):
        responses, ids = self.store()
        self.assertEqual(set(ids), {f"q{i}::fixture_alpha" for i in range(4)})
        self.assertEqual(len(set(ids.values())), 4, "ids must be distinct")

    def test_the_scores_land_on_their_own_response(self):
        responses, ids = self.store()
        scored = {f"q{i}::fixture_alpha": ensemble(float(i)) for i in range(4)}
        persist_scores(self.conn, "run-a", ids, scored)
        rows = dict(self.conn.execute(
            "SELECT r.query_id, j.overall FROM judge_scores j "
            "JOIN raw_responses r ON r.id = j.response_id GROUP BY r.query_id"))
        self.assertEqual(rows, {"q0": 0.0, "q1": 1.0, "q2": 2.0, "q3": 3.0})

    def test_a_judge_that_errored_is_not_stored_as_a_score(self):
        responses, ids = self.store(n=1)
        failed = JudgeScore(judge_family=FAMILIES[0], judge_model="m")
        failed.error = "quota exhausted, not rate-limited"
        scored = {"q0::fixture_alpha": [failed]}
        persist_scores(self.conn, "run-a", ids, scored)
        self.assertEqual(self.count("judge_scores"), 0)

    def test_a_score_for_an_unstored_response_is_dropped_not_raised(self):
        # `response_id` is NOT NULL, so writing an orphan would abort the whole
        # commit and lose every other judgement in it.
        responses, ids = self.store(n=1)
        scored = {"q0::fixture_alpha": ensemble(),
                  "q99::never_fetched": ensemble()}
        persist_scores(self.conn, "run-a", ids, scored)
        self.assertEqual(self.count("judge_scores"), len(FAMILIES))

    def test_a_second_run_does_not_disturb_the_first(self):
        # `--rejudge` stores the recovered responses under a new run id, so both
        # have to coexist: the original stays exactly as it was.
        self.store("run-a")
        self.store("run-b")
        self.assertEqual(len(load_responses(self.conn, "run-a")), 4)
        self.assertEqual(len(load_responses(self.conn, "run-b")), 4)
        self.assertEqual(self.count("raw_responses"), 8)


if __name__ == "__main__":
    unittest.main()
