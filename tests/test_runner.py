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
import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    begin_judging_attempt,
    finish_judging_attempt,
    fetch_all,
    judge_all,
    load_run_queries,
    mark_retrieval_complete,
    persist_response,
)
from src import runner
from src.storage import lifecycle
from src.judge.ensemble import FamilyLimiter
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
        self.conn.executemany(
            "INSERT INTO runs (id,started_at,week,query_set_hash) VALUES (?,?,?,?)",
            [(name, "2099-01-01", "2099-W01", "fixture")
             for name in ("run-full", "run-smoke", "run-a", "run-b")],
        )
        self.conn.commit()

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

    def test_recovery_preserves_price_separately_from_incremental_judge_spend(self):
        self.store()
        recovered = load_responses(self.conn, "run-a")
        self.assertEqual([r.cost_usd for r in recovered], [0.001] * 4)

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
        call = self.conn.execute("SELECT status,error FROM judge_call_attempts").fetchone()
        self.assertEqual(call, ("failed", "quota exhausted, not rate-limited"))

    def test_a_score_for_an_unstored_response_is_dropped_not_raised(self):
        # `response_id` is NOT NULL, so writing an orphan would abort the whole
        # commit and lose every other judgement in it.
        responses, ids = self.store(n=1)
        scored = {"q0::fixture_alpha": ensemble(),
                  "q99::never_fetched": ensemble()}
        persist_scores(self.conn, "run-a", ids, scored)
        self.assertEqual(self.count("judge_scores"), len(FAMILIES))

    def test_a_second_run_does_not_disturb_the_first(self):
        # Independent retrieval runs coexist; rejudging no longer creates a copy.
        self.store("run-a")
        self.store("run-b")
        self.assertEqual(len(load_responses(self.conn, "run-a")), 4)
        self.assertEqual(len(load_responses(self.conn, "run-b")), 4)
        self.assertEqual(self.count("raw_responses"), 8)


class TestImmutableRunQueries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = storage.connect(Path(self.tmp.name) / "snapshot.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_later_wording_category_and_privacy_do_not_rewrite_old_evidence(self):
        original = [{"id": "q1", "category": "general_facts", "text": "original question",
                     "gold_answer": "original answer", "held_out": False}]
        replacement = [{"id": "q1", "category": "long_tail", "text": "replacement question",
                        "gold_answer": None, "held_out": True}]
        persist_run(self.conn, "original", "2099-W01", "hash-a", original, [resp()],
                    "2099-01-01T00:00:00+00:00", "scheduled")
        persist_run(self.conn, "later", "2099-W02", "hash-b", replacement, [resp()],
                    "2099-01-08T00:00:00+00:00", "manual")
        rows = self.conn.execute(
            "SELECT run_id,category,text,gold_answer,held_out,snapshot_source "
            "FROM response_queries ORDER BY run_id").fetchall()
        self.assertEqual(rows, [
            ("later", "long_tail", "replacement question", None, 1, "snapshot"),
            ("original", "general_facts", "original question", "original answer", 0, "snapshot"),
        ])
        self.assertEqual(load_run_queries(self.conn, "original")[0]["text"], "original question")

    def test_snapshot_cannot_be_updated_or_deleted(self):
        import sqlite3
        persist_run(self.conn, "original", "2099-W01", "hash-a",
                    [{"id": "q1", "category": "general_facts", "text": "original"}], [],
                    "2099-01-01T00:00:00+00:00", "manual")
        for statement in ("UPDATE run_queries SET text='replacement'", "DELETE FROM run_queries"):
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                self.conn.execute(statement)
            self.conn.rollback()

    def test_failure_creating_snapshots_rolls_back_the_run_atomically(self):
        import sqlite3
        queries = [{"id": "q1", "category": "general_facts", "text": "first"},
                   {"id": "q2", "category": "general_facts", "text": "second", "source": {"invalid": True}}]
        with self.assertRaises(sqlite3.ProgrammingError):
            persist_run(self.conn, "invalid", "2099-W01", "hash", queries, [],
                        "2099-01-01T00:00:00+00:00", "manual")
        for table in ("runs", "queries", "run_queries"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)


class TestCheckpointedRecovery(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "recovery.db"
        self.conn = storage.connect(self.db)
        self.queries = [{"id": "q1", "category": "general_facts", "text": "original question"}]
        self.response = resp()
        self.response.cost_source = "reported"
        self.response.cost_usd = 0.007
        self.ids = persist_run(self.conn, "retrieval", "2099-W01", "original-hash", self.queries,
                               [self.response], "2099-01-01T03:00:00+00:00", "scheduled")
        self.limits = {fam: FamilyLimiter(4, 0) for fam, _ in JUDGES}

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    async def test_cancelled_judging_retains_completed_family_and_resume_only_fills_holes(self):
        completed = asyncio.Event()
        attempt = begin_judging_attempt(self.conn, "retrieval")

        async def interrupted_score(client, keys, family, model, prompt, chars, sem):
            if family == FAMILIES[0]:
                completed.set()
                return JudgeScore(judge_family=family, judge_model=model, overall=8,
                                  prompt_tokens=123, output_tokens=12)
            await asyncio.sleep(60)

        with contextlib.redirect_stdout(io.StringIO()), patch.object(runner, "score_one", interrupted_score):
            task = asyncio.create_task(judge_all(None, {}, [self.response], {"q1": self.queries[0]},
                                                "01 January 2099", conn=self.conn, run_id="retrieval",
                                                attempt_id=attempt, judge_sems=self.limits))
            await asyncio.wait_for(completed.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finish_judging_attempt(self.conn, attempt, status="interrupted")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM judge_scores").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT status FROM judging_attempts WHERE id=?", (attempt,)).fetchone()[0],
                         "interrupted")
        requested = []

        async def recovered_score(client, keys, family, model, prompt, chars, sem):
            requested.append(family)
            return JudgeScore(judge_family=family, judge_model=model, overall=7)

        recovered_attempt = begin_judging_attempt(self.conn, "retrieval")
        with contextlib.redirect_stdout(io.StringIO()), patch.object(runner, "score_one", recovered_score):
            scored = await judge_all(None, {}, load_responses(self.conn, "retrieval"),
                                     {"q1": self.queries[0]}, "01 January 2099", conn=self.conn,
                                     run_id="retrieval", attempt_id=recovered_attempt, judge_sems=self.limits)
        finish_judging_attempt(self.conn, recovered_attempt)
        self.assertCountEqual(requested, FAMILIES[1:])
        self.assertEqual(len(scored["q1::fixture_alpha"]), len(JUDGES))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT cost_usd,cost_source FROM raw_responses").fetchone(),
                         (0.007, "reported"))

    async def test_fetch_stage_failure_keeps_each_completed_response(self):
        queries = [{"id": "q1", "category": "general_facts", "text": "first"},
                   {"id": "q2", "category": "general_facts", "text": "second"}]
        persist_run(self.conn, "fetch", "2099-W01", "hash", queries, [],
                    "2099-01-01T00:00:00+00:00", "manual")

        class Adapter:
            name = "fixture_alpha"

            async def search(self, client, text, qid):
                if qid == "q2":
                    await asyncio.sleep(0.02)
                    raise RuntimeError("unexpected adapter failure")
                return resp(qid)

        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "unexpected adapter"):
                await fetch_all(None, [Adapter()], queries,
                                on_response=lambda r: persist_response(self.conn, "fetch", r))
        other = storage.connect(self.db)
        try:
            self.assertEqual([r.query_id for r in load_responses(other, "fetch")], ["q1"])
        finally:
            other.close()

    async def test_rejudge_cli_uses_original_run_metadata_and_ignores_current_query_file(self):
        prompts = []

        async def synthetic_score(client, keys, family, model, prompt, chars, sem):
            prompts.append(prompt)
            return JudgeScore(judge_family=family, judge_model=model, overall=7)

        original = self.conn.execute(
            "SELECT id,week,started_at,query_set_hash,trigger,retrieval_finished_at FROM runs").fetchone()
        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--rejudge", "retrieval",
                                        "--queries", "/nonexistent-current-query-file.json"]), \
             patch.object(runner, "score_one", synthetic_score), \
             patch.object(runner, "make_judge_semaphores", return_value=self.limits), \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            result = await runner.main()
        self.assertEqual(result, 0)
        self.assertEqual(self.conn.execute(
            "SELECT id,week,started_at,query_set_hash,trigger,retrieval_finished_at FROM runs").fetchone(), original)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
        self.assertTrue(all("01 January 2099" in prompt and "original question" in prompt for prompt in prompts))
        self.assertEqual(self.conn.execute("SELECT cost_usd,cost_source FROM raw_responses").fetchone(),
                         (0.007, "reported"))

    async def test_changed_protocol_cannot_mix_with_accepted_checkpointed_scores(self):
        persist_scores(self.conn, "retrieval", self.ids,
                       {"q1::fixture_alpha": [ensemble()[0]]})
        with patch.object(runner.judge, "RUBRIC", "changed rubric"):
            with self.assertRaisesRegex(ValueError, "different judging protocol"):
                begin_judging_attempt(self.conn, "retrieval")

    async def test_checkpoint_storage_failure_cancels_sibling_judge_calls(self):
        attempt = begin_judging_attempt(self.conn, "retrieval")
        live = []

        async def synthetic_score(client, keys, family, model, prompt, chars, sem):
            if family == FAMILIES[0]:
                await asyncio.sleep(0)
                return JudgeScore(judge_family=family, judge_model=model, overall=7)
            live.append(asyncio.current_task())
            await asyncio.Event().wait()

        with patch.object(runner, "score_one", synthetic_score), \
             patch.object(runner, "complete_judge_call", side_effect=RuntimeError("storage failed")), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "storage failed"):
                await judge_all(None, {}, [self.response], {"q1": self.queries[0]}, "01 January 2099",
                                conn=self.conn, run_id="retrieval", attempt_id=attempt, judge_sems=self.limits)
        self.assertEqual(len(live), 2)
        self.assertTrue(all(task.done() and task.cancelled() for task in live))
        finish_judging_attempt(self.conn, attempt, status="interrupted")

    async def test_protocol_fingerprint_covers_parser_and_score_schema(self):
        original = lifecycle.judging_protocol()

        def changed_parser(text):
            return {"overall": 10}

        def changed_validator(data, **kwargs):
            return data

        with patch.object(runner.judge, "_extract", changed_parser):
            self.assertNotEqual(lifecycle.judging_protocol(), original)
        with patch.object(runner.judge, "_validate_scores", changed_validator):
            self.assertNotEqual(lifecycle.judging_protocol(), original)

    async def test_a_judging_attempt_cannot_attach_calls_to_another_retrieval(self):
        other_ids = persist_run(self.conn, "other", "2099-W01", "other-hash", self.queries,
                                [resp()], "2099-01-01T04:00:00+00:00", "manual")
        attempt = begin_judging_attempt(self.conn, "retrieval")
        with self.assertRaisesRegex(ValueError, "own retrieval run"):
            lifecycle.begin_judge_call(self.conn, attempt, other_ids["q1::fixture_alpha"],
                                       FAMILIES[0], JUDGE_MODEL[FAMILIES[0]], "fixture prompt", 14)
    async def test_database_lock_rejects_overlapping_cli_invocations(self):
        with lifecycle.exclusive_database(self.db):
            with self.assertRaisesRegex(RuntimeError, "another benchmark process"):
                with lifecycle.exclusive_database(self.db):
                    self.fail("overlapping invocation acquired the lock")
        with lifecycle.exclusive_database(self.db):
            pass

    async def test_explicit_recovery_marks_abandoned_running_attempt_interrupted(self):
        abandoned = begin_judging_attempt(self.conn, "retrieval")
        lifecycle.begin_judge_call(self.conn, abandoned, self.ids["q1::fixture_alpha"],
                                   FAMILIES[0], JUDGE_MODEL[FAMILIES[0]], "fixture prompt", 14)

        async def synthetic_score(client, keys, family, model, prompt, chars, sem):
            return JudgeScore(judge_family=family, judge_model=model, overall=7)

        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--rejudge", "retrieval"]), \
             patch.object(runner, "score_one", synthetic_score), \
             patch.object(runner, "make_judge_semaphores", return_value=self.limits), \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(await runner.main(), 0)
        self.assertEqual(self.conn.execute("SELECT status,error FROM judging_attempts WHERE id=?",
                                           (abandoned,)).fetchone(),
                         ("interrupted", "superseded by explicit recovery"))
        self.assertEqual(self.conn.execute("SELECT status FROM judge_call_attempts "
                                           "WHERE judging_attempt_id=?", (abandoned,)).fetchone()[0], "interrupted")

    async def test_retrieval_resume_can_start_from_zero_checkpoints(self):
        persist_run(self.conn, "empty", "2099-W01", "snapshot-hash", self.queries, [],
                    "2099-01-01T00:00:00+00:00", "manual",
                    provenance={"vendors": ["fixture_alpha"]})
        requested = []

        class Adapter:
            name = "fixture_alpha"

            async def search(self, client, query, query_id):
                requested.append(query_id)
                return resp(query_id)

        async def synthetic_score(client, keys, family, model, prompt, chars, sem):
            return JudgeScore(judge_family=family, judge_model=model, overall=7)

        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--resume", "empty"]), \
             patch.object(runner, "build_all", return_value=[Adapter()]), \
             patch.object(runner, "iso_week", return_value="2099-W01"), \
             patch.object(runner, "retrieval_date_is_current", return_value=True), \
             patch.object(runner, "score_one", synthetic_score), \
             patch.object(runner, "make_judge_semaphores", return_value=self.limits), \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(await runner.main(), 0)
        self.assertEqual(requested, ["q1"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM raw_responses WHERE run_id='empty'").fetchone()[0], 1)

    async def test_retrieval_resume_does_not_repeat_checkpointed_vendor_calls(self):
        queries = self.queries + [{"id": "q2", "category": "general_facts", "text": "second question"}]
        persist_run(self.conn, "partial", "2099-W01", "hash", queries, [],
                    "2099-01-01T00:00:00+00:00", "manual",
                    provenance={"vendors": ["fixture_alpha"]})
        persist_response(self.conn, "partial", resp("q1"))
        requested = []

        class Adapter:
            name = "fixture_alpha"

            async def search(self, client, query, query_id):
                requested.append(query_id)
                return resp(query_id)

        async def synthetic_score(client, keys, family, model, prompt, chars, sem):
            return JudgeScore(judge_family=family, judge_model=model, overall=7)

        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--resume", "partial"]), \
             patch.object(runner, "build_all", return_value=[Adapter()]), \
             patch.object(runner, "iso_week", return_value="2099-W01"), \
             patch.object(runner, "retrieval_date_is_current", return_value=True), \
             patch.object(runner, "score_one", synthetic_score), \
             patch.object(runner, "make_judge_semaphores", return_value=self.limits), \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(await runner.main(), 0)
        self.assertEqual(requested, ["q2"])

    async def test_missing_vendor_responses_cannot_be_backfilled_in_a_later_week(self):
        persist_run(self.conn, "old-empty", "2000-W01", "hash", self.queries, [],
                    "2000-01-01T00:00:00+00:00", "scheduled",
                    provenance={"vendors": ["fixture_alpha"]})
        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--resume", "old-empty"]), \
             patch.object(runner, "fetch_all") as fetch, \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "past week"):
                await runner.main()
        fetch.assert_not_called()

    async def test_retrieval_resume_cannot_mix_different_days_in_the_same_week(self):
        persist_run(self.conn, "older-day", "2099-W01", "hash", self.queries, [],
                    "2099-01-01T00:00:00+00:00", "manual",
                    provenance={"vendors": ["fixture_alpha"]})
        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--resume", "older-day"]), \
             patch.object(runner, "iso_week", return_value="2099-W01"), \
             patch.object(runner, "retrieval_date_is_current", return_value=False), \
             patch.object(runner, "fetch_all") as fetch, \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "original UTC retrieval date"):
                await runner.main()
        fetch.assert_not_called()

    async def test_rejudged_partial_retrieval_remains_incomplete_and_exits_nonzero(self):
        queries = self.queries + [{"id": "q2", "category": "general_facts", "text": "second question"}]
        persist_run(self.conn, "partial-rejudge", "2099-W01", "hash", queries, [],
                    "2099-01-01T00:00:00+00:00", "manual",
                    provenance={"vendors": ["fixture_alpha"]})
        persist_response(self.conn, "partial-rejudge", resp("q1"))

        async def synthetic_score(client, keys, family, model, prompt, chars, sem):
            return JudgeScore(judge_family=family, judge_model=model, overall=7)

        with patch.object(sys, "argv", ["runner", "--db", str(self.db), "--rejudge", "partial-rejudge"]), \
             patch.object(runner, "score_one", synthetic_score), \
             patch.object(runner, "make_judge_semaphores", return_value=self.limits), \
             patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(await runner.main(), 1)
        self.assertEqual(self.conn.execute("SELECT status,retrieval_finished_at FROM runs "
                                           "WHERE id='partial-rejudge'").fetchone(), ("incomplete", None))

    async def test_stage_marker_recovery_uses_last_checkpoint_instead_of_judging_date(self):
        persist_run(self.conn, "marker-missing", "2099-W01", "hash", self.queries, [],
                    "2099-01-01T00:00:00+00:00", "manual")
        persist_response(self.conn, "marker-missing", resp())
        checkpoint = self.conn.execute("SELECT created_at FROM raw_responses WHERE run_id='marker-missing'").fetchone()[0]
        mark_retrieval_complete(self.conn, "marker-missing")
        self.assertEqual(self.conn.execute("SELECT retrieval_finished_at FROM runs WHERE id='marker-missing'").fetchone()[0],
                         checkpoint)


if __name__ == "__main__":
    unittest.main()
