"""The withheld question set, and the three promises it makes.

`src/heldout.py` claims that a held-out set is withheld rather than hidden:
its hash is committed before it runs, its questions are published when it
retires, and its scores are never withheld at all. Each of those is a promise
about behaviour under conditions that do not arise on a good day — a set edited
after registration, a question that leaks into a published file, a held-out
score creeping into a published cell. Those are exactly the paths that a test
suite driving only clean data never touches.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import export, heldout  # noqa: E402


QUERIES = [
    {"id": "t-001", "category": "general_facts", "text": "a withheld question"},
    {"id": "t-002", "category": "long_tail", "text": "another withheld question",
     "gold_answer": "a withheld answer"},
]


def manifest(**over) -> dict:
    entry = {
        "id": "test-set",
        "sha256": heldout.digest(QUERIES),
        "n_queries": len(QUERIES),
        "categories": heldout.shape(QUERIES),
        "committed_at": "2099-01-01",
        "first_week": None,
        "retired_week": None,
        "file": None,
    }
    entry.update(over)
    return {"rotate_after_weeks": 4, "sets": [entry]}


class TestCommitment(unittest.TestCase):
    """The hash is the whole design. If it can drift, nothing else matters."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "test-set.json"
        self.path.write_text(json.dumps({"queries": QUERIES}))

    def test_digest_is_order_independent(self):
        # Canonicalised on sort_keys, so a reformatted file is the same set —
        # otherwise every whitespace change would look like tampering and the
        # check would be trained away.
        shuffled = [{k: q[k] for k in reversed(list(q))} for q in QUERIES]
        self.assertEqual(heldout.digest(QUERIES), heldout.digest(shuffled))

    def test_digest_changes_when_a_question_changes(self):
        edited = [dict(QUERIES[0], text="a different question"), QUERIES[1]]
        self.assertNotEqual(heldout.digest(QUERIES), heldout.digest(edited))

    def test_verify_accepts_the_registered_set(self):
        heldout.verify("test-set", QUERIES, manifest())

    def test_verify_refuses_a_set_edited_after_registration(self):
        # The failure this exists for: a bad week, and someone swapping the
        # questions before the next run. It has to stop the run, not warn.
        edited = [dict(QUERIES[0], text="an easier question"), QUERIES[1]]
        with self.assertRaises(SystemExit) as e:
            heldout.verify("test-set", edited, manifest())
        self.assertIn("committed hash", str(e.exception))

    def test_verify_refuses_a_set_that_was_never_registered(self):
        with self.assertRaises(SystemExit):
            heldout.verify("never-registered", QUERIES, manifest())

    def test_two_active_sets_is_an_error(self):
        # "The held-out score" has to name one thing.
        m = manifest()
        m["sets"].append(dict(m["sets"][0], id="second-set"))
        with self.assertRaises(SystemExit):
            heldout.active(m)

    def test_public_view_carries_no_question_text(self):
        blob = json.dumps(heldout.public_view(manifest()))
        for q in QUERIES:
            self.assertNotIn(q["text"], blob)
        self.assertIn(heldout.digest(QUERIES), blob)


class TestLeakGuard(unittest.TestCase):
    """`assert_heldout_withheld` is the only thing that makes the withholding
    checkable rather than asserted. It has to fire on every published file
    type, and it has to be silent when there is nothing to check."""

    def setUp(self):
        self.site = Path(tempfile.mkdtemp())
        (self.site / "data").mkdir()
        (self.site / "export").mkdir()
        # The active set's text, where the guard looks for it.
        self.local = Path(tempfile.mkdtemp()) / "test-set.json"
        self.local.write_text(json.dumps({"queries": QUERIES}))
        self._orig = heldout.LOCAL_DIR
        heldout.LOCAL_DIR = self.local.parent

    def tearDown(self):
        heldout.LOCAL_DIR = self._orig

    def test_clean_site_passes_and_reports_what_it_checked(self):
        (self.site / "data" / "bundle.js").write_text("window.SB_DATA = {};")
        self.assertEqual(
            export.assert_heldout_withheld(self.site, manifest()), len(QUERIES))

    def test_a_leaked_question_fails_the_build(self):
        (self.site / "data" / "bundle.js").write_text(
            'window.SB_DATA = {"q": "a withheld question"};')
        with self.assertRaises(AssertionError) as e:
            export.assert_heldout_withheld(self.site, manifest())
        self.assertIn("leaked", str(e.exception))

    def test_a_leaked_gold_answer_fails_too(self):
        # Half the leak surface. A gold answer names the question as clearly as
        # the question does, and it is the easier one to forget.
        (self.site / "export" / "judge-scores.csv").write_text(
            "week,answer\n2099-W01,a withheld answer\n")
        with self.assertRaises(AssertionError):
            export.assert_heldout_withheld(self.site, manifest())

    def test_a_leak_in_a_page_is_caught(self):
        (self.site / "methodology.html").write_text(
            "<p>For example: another withheld question</p>")
        with self.assertRaises(AssertionError):
            export.assert_heldout_withheld(self.site, manifest())

    def test_no_registered_set_checks_nothing(self):
        self.assertEqual(
            export.assert_heldout_withheld(self.site, {"sets": []}), 0)

    def test_absent_text_checks_nothing_rather_than_failing(self):
        # The ordinary case for anyone who is not the maintainer. The export
        # has to work for them; it cannot leak what it does not hold.
        heldout.LOCAL_DIR = Path(tempfile.mkdtemp())
        self.assertEqual(
            export.assert_heldout_withheld(self.site, manifest()), 0)

    def test_a_retired_set_is_not_checked(self):
        # Publishing it is the point by then, and the export writes it out
        # itself — a guard that fired here would forbid the disclosure.
        (self.site / "export" / "queries-heldout-retired.csv").write_text(
            "text\na withheld question\n")
        export.assert_heldout_withheld(
            self.site, manifest(retired_week="2099-W05", file="retired/test-set.json"))


class TestPublicationSplit(unittest.TestCase):
    """A published cell must be reproducible from the published questions."""

    def rows(self):
        def r(qid, vendor, cat, med, held):
            return {"vendor": vendor, "category": cat, "median": med,
                    "latency_ms": 100, "cost_usd": 0.001, "error": None,
                    "complete": True, "query_id": qid, "judges": {},
                    "held_out": held, "response_id": "x",
                    "response_mode": "ranked_results", "n_results": 10}
        return (
            [r(f"p{i}", "alpha", "general_facts", 8.0, False) for i in range(5)]
            + [r(f"h{i}", "alpha", "general_facts", 4.0, True) for i in range(5)]
        )

    def test_cells_built_from_public_rows_ignore_the_withheld_ones(self):
        public = [r for r in self.rows() if not r["held_out"]]
        cells = export.build_cells(public)
        self.assertEqual(len(cells), 1)
        # 8.0, not the 6.0 that pooling the two sets would produce.
        self.assertEqual(cells[0]["score"], 8.0)
        self.assertEqual(cells[0]["n_queries"], 5)

    def test_gap_is_measured_per_category_and_signed_public_minus_heldout(self):
        h = export.build_heldout(self.rows(), {"heldout_set": "test-set"}, manifest())
        self.assertEqual(h["vendors"][0]["public"], 8.0)
        self.assertEqual(h["vendors"][0]["heldout"], 4.0)
        # Positive means better on the published questions — the direction that
        # would indicate hill-climbing. Getting this sign backwards would
        # publish an accusation reversed.
        self.assertEqual(h["vendors"][0]["gap"], 4.0)

    def test_no_withheld_rows_means_no_heldout_block_at_all(self):
        public = [r for r in self.rows() if not r["held_out"]]
        self.assertIsNone(
            export.build_heldout(public, {"heldout_set": None}, manifest()))

    def test_the_set_metadata_is_the_committed_one(self):
        h = export.build_heldout(self.rows(), {"heldout_set": "test-set"}, manifest())
        self.assertEqual(h["set"]["sha256"], heldout.digest(QUERIES))
        self.assertFalse(h["set"]["published"])


class TestDisagreementRates(unittest.TestCase):
    """Rates, not just a mean. The mean is what hides a bimodal ensemble."""

    def rows(self, spreads):
        out = []
        for i, s in enumerate(spreads):
            out.append({
                "vendor": "alpha", "category": "general_facts", "median": 7.0,
                "latency_ms": 1, "cost_usd": 0.0, "error": None, "complete": True,
                "query_id": f"q{i}", "held_out": False, "response_id": f"r{i}",
                "response_mode": "ranked_results", "n_results": 10,
                "judges": {
                    "anthropic": {"overall": 5.0, "judge_model": "a"},
                    "openai": {"overall": 5.0 + s, "judge_model": "o"},
                    "google": {"overall": 5.0, "judge_model": "g"},
                },
            })
        return out

    def test_rates_count_responses_over_each_threshold(self):
        stats = export.build_judge_stats(self.rows([0, 0, 1.5, 2.5, 4.0]))
        d = stats["disagreement_rates"]
        self.assertEqual(d["unanimous"], 0.4)
        self.assertEqual(d["over_1pt"], 0.6)
        self.assertEqual(d["over_2pt"], 0.4)
        self.assertEqual(d["over_3pt"], 0.2)

    def test_a_bimodal_ensemble_is_visible_in_the_rates(self):
        # The exact case the mean cannot express: nine responses in perfect
        # agreement and one split by five points reads as a mean of 0.5, which
        # sounds like consensus. The rate says one in ten split hard.
        stats = export.build_judge_stats(self.rows([0] * 9 + [5.0]))
        self.assertAlmostEqual(stats["mean_disagreement"], 0.5)
        self.assertEqual(stats["disagreement_rates"]["over_3pt"], 0.1)

    def test_pairs_name_which_two_families_disagree(self):
        stats = export.build_judge_stats(self.rows([2.0]))
        pairs = {p["pair"]: p["mean_abs_diff"] for p in stats["family_pairs"]}
        self.assertEqual(pairs["anthropic/google"], 0.0)
        self.assertEqual(pairs["anthropic/openai"], 2.0)

    def test_empty_input_reports_nothing_rather_than_zero(self):
        # A rate of 0% and no data at all are different claims, and the second
        # must not render as the first on a page.
        d = export.build_judge_stats([])["disagreement_rates"]
        self.assertIsNone(d["over_2pt"])
        self.assertIsNone(d["unanimous"])


class TestInstallRequire(unittest.TestCase):
    """The install step's exit code has to mean something.

    2026-W33 and W34 both published `n_heldout_queries: 0` because `install`
    printed a line and returned 0 when the secret was unset. Every later step
    then succeeded and the week looked healthy, which is why nobody caught it.
    These tests pin both halves: a fork with no secret still degrades, and the
    scheduled run asking for `--require` stops.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        # Patch at load_manifest, not at active(): cmd_install also calls
        # verify(), which reads the manifest independently, and a test set that
        # is active but unregistered would fail for the wrong reason.
        real = heldout.load_manifest
        heldout.load_manifest = lambda path=None: manifest()
        self.addCleanup(setattr, heldout, "load_manifest", real)
        self.env = "SB_HELDOUT_JSON_TEST"
        os.environ.pop(self.env, None)
        self.addCleanup(os.environ.pop, self.env, None)
        os.environ["SB_HELDOUT_FILE"] = str(self.dir / "set.json")
        self.addCleanup(os.environ.pop, "SB_HELDOUT_FILE", None)

    def args(self, require: bool):
        return argparse.Namespace(env=self.env, require=require)

    def test_absent_secret_without_require_still_degrades(self):
        # A fork has no secret and must not have its CI broken by ours.
        self.assertEqual(heldout.cmd_install(self.args(require=False)), 0)

    def test_absent_secret_with_require_stops(self):
        with self.assertRaises(SystemExit) as e:
            heldout.cmd_install(self.args(require=True))
        self.assertIn(self.env, str(e.exception))

    def test_whitespace_only_secret_with_require_stops(self):
        # An empty Actions secret arrives as "", but a mangled one can arrive
        # as a newline. Both are "the set did not get here".
        os.environ[self.env] = "\n  \n"
        with self.assertRaises(SystemExit):
            heldout.cmd_install(self.args(require=True))

    def test_a_present_secret_installs_under_require(self):
        os.environ[self.env] = json.dumps({"queries": QUERIES})
        self.assertEqual(heldout.cmd_install(self.args(require=True)), 0)
        written = json.loads((self.dir / "set.json").read_text())["queries"]
        self.assertEqual(heldout.digest(written), heldout.digest(QUERIES))

    def test_require_does_not_weaken_the_hash_check(self):
        # --require must not become a reason to accept whatever showed up.
        os.environ[self.env] = json.dumps(
            {"queries": [dict(QUERIES[0], text="an easier question"), QUERIES[1]]})
        with self.assertRaises(SystemExit) as e:
            heldout.cmd_install(self.args(require=True))
        self.assertIn("committed hash", str(e.exception))


class TestWeeklyWorkflowRequires(unittest.TestCase):
    """The flag is worthless if the scheduled run does not pass it."""

    def test_the_scheduled_run_passes_require(self):
        wf = (ROOT / ".github" / "workflows" / "weekly.yml").read_text()
        self.assertIn("heldout install --require", wf)


if __name__ == "__main__":
    unittest.main()
