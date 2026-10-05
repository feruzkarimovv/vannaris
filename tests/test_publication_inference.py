"""Publication inference tests use hand-checkable paired designs, never APIs."""

from __future__ import annotations

import unittest

from src import export, inference


def observation(qid, vendor, category, score, *, families=3, error=None):
    return {
        "query_id": qid, "vendor": vendor, "category": category,
        "median": score if families == 3 and error is None else None,
        "complete": families == 3 and error is None, "held_out": False,
        "response_id": f"{qid}:{vendor}", "response_mode": "ranked_results",
        "latency_ms": 100, "cost_usd": 0.001, "cost_source": "estimated",
        "n_results": 10, "error": error,
        "judges": {fam: {"overall": score, "judge_model": model, "scored_chars": 100}
                   for fam, model in export.JUDGES[:families]},
    }


class TestFiniteSampleInference(unittest.TestCase):
    def test_constant_four_pair_gap_is_not_certain(self):
        # A degenerate bootstrap interval is not a valid claim of certainty.
        groups = ((1.0, 1.0, 1.0, 1.0),)
        bootstrap = inference.bootstrap_mean(groups, "constant-four", draws=100)
        self.assertEqual(bootstrap["ci95"], [1.0, 1.0])
        permutation = inference.paired_sign_flip(groups, "constant-four")
        self.assertEqual(permutation["permutations"], 16)
        self.assertEqual(permutation["p_value"], 2 / 16)
        rows = [observation(str(i), v, "general_facts", 8.0 if v == "a" else 7.0)
                for i in range(4) for v in ("a", "b")]
        cmp = export.build_comparisons(rows)[export.comparison_key("a", "b", "general_facts")]
        self.assertFalse(cmp["separated"])

    def test_a_balanced_sign_pattern_has_p_one(self):
        self.assertEqual(inference.paired_sign_flip(((1.0, -1.0),), "balanced")["p_value"], 1.0)

    def test_monte_carlo_uses_add_one_and_is_deterministic(self):
        groups = ((1.0,) * 20,)
        a = inference.paired_sign_flip(groups, "twenty", draws=99)
        b = inference.paired_sign_flip(groups, "twenty", draws=99)
        self.assertEqual(a, b)
        self.assertGreaterEqual(a["p_value"], 1 / 100)
        self.assertEqual(a["test"], "monte_carlo_paired_sign_flip")

    def test_holm_includes_the_unavailable_slot(self):
        # Hand-calculated sorted products: .001*4, .02*3, .04*2.
        adjusted = inference.holm_adjust([0.001, 0.04, 0.02, None])
        for actual, expected in zip(adjusted[:3], [0.004, 0.08, 0.06]):
            self.assertAlmostEqual(actual, expected)
        self.assertIsNone(adjusted[3])

    def test_one_observation_cannot_support_an_interval(self):
        self.assertIsNone(inference.bootstrap_mean(((8.0,),), "one", draws=100)["ci95"])

    def test_category_balancing_survives_unequal_pair_counts(self):
        rows = []
        for index, category in enumerate(export.CATEGORY_ORDER):
            for i in range(2 if index == 0 else 20):
                # +5 in the small category, -1 in each of the other five:
                # equal-category overall is zero, despite pooled mean < zero.
                a, b = (9.0, 4.0) if index == 0 else (7.0, 8.0)
                rows.extend([observation(f"{category}-{i}", "a", category, a),
                             observation(f"{category}-{i}", "b", category, b)])
        cmp = export.paired_difference(rows, "a", "b")
        self.assertEqual(cmp["mean_diff"], 0.0)
        self.assertEqual(cmp["n_common"], 102)
        self.assertEqual(cmp, export.paired_difference(list(reversed(rows)), "a", "b"))

    def test_missing_required_category_prevents_overall_comparison(self):
        rows = [observation(str(i), v, "general_facts", 8.0)
                for i in range(4) for v in ("a", "b")]
        self.assertIsNone(export.paired_difference(rows, "a", "b"))
        comparisons = export.build_comparisons(rows)
        self.assertEqual(len(comparisons), 7)
        self.assertEqual(comparisons[export.comparison_key("a", "b")]["status"], "insufficient_coverage_or_pairs")


class TestComparablePublication(unittest.TestCase):
    def test_all_required_category_means_are_required(self):
        rows = [observation(f"{cat}-{i}", v, cat, 9.0)
                for cat in export.CATEGORY_ORDER for i in range(2) for v in ("a", "b")]
        missing = [r for r in rows if r["vendor"] == "b" and r["category"] == "breaking_news"]
        for r in missing:
            r.update(median=None, complete=False, judges={})
        totals = {v["vendor"]: v for v in export.build_vendor_totals(rows, export.build_cells(rows))}
        self.assertEqual(totals["a"]["score"], 9.0)
        self.assertIsNone(totals["b"]["score"])
        self.assertEqual(totals["b"]["category_coverage"], round(5 / 6, 4))
        self.assertNotIn("breaking_news", totals["b"]["included_categories"])

    def test_two_judge_unanimity_never_enters_three_judge_rates(self):
        complete = observation("full", "a", "general_facts", 8.0)
        complete["judges"]["google"]["overall"] = 4.0
        partial = observation("partial", "a", "general_facts", 8.0, families=2)
        judged = export.build_judge_stats([complete, partial])
        self.assertEqual(judged["n_compared"], 1)
        self.assertEqual(judged["disagreement_rates"]["unanimous"], 0.0)
        self.assertEqual(judged["disagreement_rates"]["over_3pt"], 1.0)
        self.assertEqual(judged["partial_panels"]["n_compared"], 1)
        self.assertEqual(judged["panel_counts"]["2"], 1)

    def test_api_failure_and_missing_judge_are_different(self):
        rows = [observation("ok", "a", "general_facts", 9.0),
                observation("judge", "a", "general_facts", 9.0, families=2),
                observation("api", "a", "general_facts", 9.0, families=0, error="FIXTURE FAILURE")]
        availability = export.build_availability(rows)
        self.assertEqual(availability["n_vendor_success"], 2)
        self.assertEqual(availability["n_missing_judgements"], 1)
        self.assertEqual(availability["n_vendor_errors"], 1)

    def test_tiers_check_all_members_not_only_the_leader(self):
        # A~B and A~C does not make B~C. The old leader-only algorithm put
        # this known-resolved pair into one apparently homogeneous group.
        cmps = {}
        for a, b, resolved in [("a", "b", False), ("a", "c", False), ("b", "c", True)]:
            cmps[export.comparison_key(a, b)] = {
                "status": "estimated", "mean_diff": 1.0, "ci95": [0.5, 1.5], "separated": resolved}
        tiers = export.build_tiers([], ["a", "b", "c"], comparisons=cmps)
        self.assertEqual([t["vendors"] for t in tiers], [["a", "b"], ["c"]])

    def test_zero_rubric_scores_do_not_divide_by_zero(self):
        cell = export.build_cells([observation(str(i), "a", "general_facts", 0.0) for i in range(2)])[0]
        self.assertEqual(cell["score"], 0.0)
        self.assertIsNone(cell["pct_of_best"])


if __name__ == "__main__":
    unittest.main()
