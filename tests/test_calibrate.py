"""Unit tests for the calibration arithmetic and sampling.

These are the functions where a bug is invisible: a wrong correlation or a
sampler that quietly drops a stratum still prints a confident-looking table, and
the number it prints is the one used to decide whether the judge can be trusted.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import storage
from src.calibrate import (_fisher_ci, _pearson, _pearson_ceiling, _rank, _spearman,
                           _wilson, agreement, build_pairs, cmd_export, draw,
                           draw_pairs, load_pair_set, pairwise_concordance,
                           pairwise_report, write_pair_task)


def rows(specs):
    """(id, spread) -> the minimum shape draw() needs."""
    return [{"id": i, "spread": s, "category": "c", "query_id": "q"} for i, s in specs]


class TestCorrelation(unittest.TestCase):
    def test_perfect_positive(self):
        self.assertAlmostEqual(_pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0)

    def test_perfect_negative(self):
        self.assertAlmostEqual(_pearson([1, 2, 3, 4], [8, 6, 4, 2]), -1.0)

    def test_constant_input_is_undefined_not_zero(self):
        # A judge that gave every response the same score has no correlation
        # defined at all. Reporting 0.0 would read as "uncorrelated", which is a
        # different and much more interesting claim than "cannot be computed".
        self.assertIsNone(_pearson([5, 5, 5, 5], [1, 2, 3, 4]))

    def test_too_few_points(self):
        self.assertIsNone(_pearson([1, 2], [1, 2]))

    def test_known_value(self):
        # Hand-computed: both means are 3, deviations [-2,-1,0,1,2] and
        # [-1,-2,1,0,2], so the covariance sum is 8 and each deviation norm is
        # sqrt(10) — r = 8/10.
        self.assertAlmostEqual(_pearson([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]), 0.8, places=6)


class TestRanks(unittest.TestCase):
    def test_ties_share_average_rank(self):
        self.assertEqual(_rank([10, 20, 20, 30]), [1.0, 2.5, 2.5, 4.0])

    def test_all_tied(self):
        self.assertEqual(_rank([7, 7, 7]), [2.0, 2.0, 2.0])

    def test_spearman_is_monotonic_not_linear(self):
        # The case that matters: a judge whose ordering is perfect but whose
        # scale is compressed. Pearson punishes it, Spearman does not, and the
        # site publishes an ordering.
        judge = [1, 2, 3, 4, 5]
        human = [1, 4, 9, 16, 25]
        self.assertAlmostEqual(_spearman(judge, human), 1.0)
        self.assertLess(_pearson(judge, human), 1.0)


class TestAgreement(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(agreement([]), {"n": 0})

    def test_mae_and_signed_bias(self):
        # Judge is +2, -2, +2 against the human: MAE 2, bias +0.67.
        a = agreement([(8, 6), (4, 6), (9, 7)])
        self.assertEqual(a["n"], 3)
        self.assertAlmostEqual(a["mae"], 2.0)
        self.assertAlmostEqual(a["bias"], 2 / 3)

    def test_bias_cancels_where_mae_does_not(self):
        # The reason both are reported: a judge that is wildly wrong in both
        # directions has bias 0 and looks unbiased, which it is — and useless,
        # which only MAE shows.
        a = agreement([(10, 5), (0, 5)])
        self.assertAlmostEqual(a["bias"], 0.0)
        self.assertAlmostEqual(a["mae"], 5.0)

    def test_within_1_and_off_by_3(self):
        a = agreement([(5, 5), (6, 5), (9, 5), (5, 9)])
        self.assertAlmostEqual(a["within_1"], 0.5)
        self.assertEqual(a["off_by_3"], 2)


class TestDraw(unittest.TestCase):
    def setUp(self):
        self.pool = rows([(f"r{i:03d}", i % 11) for i in range(200)])

    def test_deterministic_for_a_seed(self):
        a = [r["id"] for r in draw(self.pool, 40, 3, 0.34)]
        b = [r["id"] for r in draw(self.pool, 40, 3, 0.34)]
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        a = {r["id"] for r in draw(self.pool, 40, 1, 0.34)}
        b = {r["id"] for r in draw(self.pool, 40, 2, 0.34)}
        self.assertNotEqual(a, b)

    def test_no_response_appears_in_both_strata(self):
        picked = draw(self.pool, 60, 5, 0.34)
        ids = [r["id"] for r in picked]
        self.assertEqual(len(ids), len(set(ids)))

    def test_sizes_match_the_requested_share(self):
        picked = draw(self.pool, 100, 5, 0.30)
        n_dis = sum(1 for r in picked if r["stratum"] == "disagreement")
        self.assertEqual(n_dis, 30)
        self.assertEqual(len(picked), 100)

    def test_disagreement_stratum_takes_the_widest_spreads(self):
        picked = draw(self.pool, 40, 9, 0.5)
        dis = [r["spread"] for r in picked if r["stratum"] == "disagreement"]
        rand = [r["spread"] for r in picked if r["stratum"] == "random"]
        self.assertGreater(sum(dis) / len(dis), sum(rand) / len(rand))

    def test_smaller_pool_than_requested_does_not_overdraw(self):
        small = rows([(f"s{i}", i) for i in range(10)])
        picked = draw(small, 10, 1, 0.34)
        self.assertEqual(len(picked), 10)
        self.assertEqual(len({r["id"] for r in picked}), 10)

    def test_positions_are_dense_and_ordered(self):
        picked = draw(self.pool, 25, 4, 0.34)
        self.assertEqual([r["position"] for r in picked], list(range(25)))



class TestCategoryBalance(unittest.TestCase):
    """The random stratum must not let category mix drift with the draw."""

    def pool(self, per_cat=40):
        cats = ["a", "b", "c", "d", "e", "f"]
        return [{"id": f"{c}{i:03d}", "spread": i % 11, "category": c, "query_id": "q"}
                for c in cats for i in range(per_cat)]

    def test_small_draw_is_evenly_allocated(self):
        # The case that motivated this: a 40-item uniform draw produced 13 in one
        # category and 1 in another.
        picked = draw(self.pool(), 40, 1, 0.0)
        counts = {}
        for r in picked:
            counts[r["category"]] = counts.get(r["category"], 0) + 1
        self.assertEqual(len(picked), 40)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_still_deterministic(self):
        a = [r["id"] for r in draw(self.pool(), 30, 7, 0.0)]
        b = [r["id"] for r in draw(self.pool(), 30, 7, 0.0)]
        self.assertEqual(a, b)

    def test_thin_category_does_not_shrink_the_set(self):
        pool = self.pool() + [{"id": "z001", "spread": 3, "category": "z", "query_id": "q"}]
        picked = draw(pool, 40, 3, 0.0)
        self.assertEqual(len(picked), 40)

    def test_disagreement_stratum_still_takes_widest_spreads(self):
        picked = draw(self.pool(), 40, 4, 0.5)
        dis = [r["spread"] for r in picked if r["stratum"] == "disagreement"]
        rand = [r["spread"] for r in picked if r["stratum"] == "random"]
        self.assertGreater(sum(dis) / len(dis), sum(rand) / len(rand))

    def test_every_prefix_of_the_presentation_order_stays_balanced(self):
        # Labellers stop partway. The first pass drew 7 per category over 42
        # and the human labelled 15, which under a plain shuffle came out 4
        # multi-hop against 1 general-facts — and docs/12 then reported
        # per-category bias off n = 1 and n = 2. Balance has to survive
        # stopping early, not just finishing.
        picked = draw(self.pool(), 42, 2, 0.0)
        order = [r["category"] for r in sorted(picked, key=lambda r: r["position"])]
        for k in (6, 12, 15, 20, 30, 42):
            counts = {}
            for c in order[:k]:
                counts[c] = counts.get(c, 0) + 1
            # Every category either appears floor(k/6) or ceil(k/6) times.
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1,
                                 f"prefix of {k} is unbalanced: {counts}")

    def test_a_prefix_cannot_be_all_one_category(self):
        picked = draw(self.pool(), 36, 5, 0.0)
        order = [r["category"] for r in sorted(picked, key=lambda r: r["position"])]
        self.assertEqual(len(set(order[:6])), 6)

    def test_interleaving_is_still_deterministic(self):
        a = [r["position"] for r in draw(self.pool(), 30, 7, 0.0)]
        b = [r["position"] for r in draw(self.pool(), 30, 7, 0.0)]
        self.assertEqual(a, b)

    def test_positions_stay_dense_after_interleaving(self):
        picked = draw(self.pool(), 25, 4, 0.34)
        self.assertEqual(sorted(r["position"] for r in picked), list(range(25)))

# ---------------------------------------------------- intervals and ceilings
#
# These exist because the first calibration pass reported `r 0.10` on n = 15
# with no interval, and it was read as a finding when both signs were inside
# it. The regression guarded against is a number published without the thing
# that says how much of it is noise (docs/12).

class TestFisherCI(unittest.TestCase):
    def test_it_reproduces_the_published_first_pass_interval(self):
        # The figures docs/12 is written around. If this test fails, either the
        # transform changed or docs/12 is now wrong; both need a human.
        lo, hi = _fisher_ci(0.0972, 15)
        self.assertAlmostEqual(lo, -0.437, places=3)
        self.assertAlmostEqual(hi, +0.581, places=3)

    def test_the_interval_straddles_zero_at_this_n(self):
        lo, hi = _fisher_ci(0.10, 15)
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)

    def test_more_data_narrows_it(self):
        w = lambda n: (lambda c: c[1] - c[0])(_fisher_ci(0.5, n))   # noqa: E731
        self.assertLess(w(200), w(30))

    def test_too_few_points_is_none_not_a_crash(self):
        self.assertIsNone(_fisher_ci(0.5, 3))
        self.assertIsNone(_fisher_ci(None, 50))

    def test_a_perfect_correlation_does_not_divide_by_zero(self):
        self.assertIsNone(_fisher_ci(1.0, 20))
        self.assertIsNone(_fisher_ci(-1.0, 20))


class TestPearsonCeiling(unittest.TestCase):
    def test_it_reproduces_the_documented_ceiling(self):
        # The claim in docs/12's correction: these two distributions cannot
        # correlate above 0.935, so compression explains ~7% of the shortfall.
        human = [10, 9, 10, 7, 10, 10, 9, 10, 10, 10, 9, 5, 10, 10, 8]
        ens = [9, 10, 8, 9, 8, 10, 5, 10, 9, 8, 9, 9, 9, 10, 7]
        self.assertAlmostEqual(_pearson_ceiling(human, ens), 0.935, places=3)

    def test_a_ceiling_is_never_below_the_observed_correlation(self):
        human = [10, 9, 10, 7, 10, 10, 9, 10, 10, 10, 9, 5, 10, 10, 8]
        ens = [9, 10, 8, 9, 8, 10, 5, 10, 9, 8, 9, 9, 9, 10, 7]
        self.assertGreaterEqual(_pearson_ceiling(human, ens), _pearson(human, ens))

    def test_already_aligned_data_has_a_ceiling_of_one(self):
        self.assertAlmostEqual(_pearson_ceiling([1, 2, 3, 4], [2, 4, 6, 8]), 1.0, places=6)

    def test_it_is_reported_alongside_the_correlation(self):
        a = agreement([(9, 10), (8, 9), (7, 5), (9, 10)])
        self.assertIn("pearson_ci95", a)
        self.assertIn("pearson_max", a)


class TestWilson(unittest.TestCase):
    def test_a_half_share_straddles_a_half(self):
        lo, hi = _wilson(50, 100)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)

    def test_it_stays_inside_zero_and_one_at_the_boundary(self):
        # The reason this is Wilson and not the normal approximation.
        lo, hi = _wilson(0, 10)
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)

    def test_no_trials_is_none_not_a_crash(self):
        self.assertIsNone(_wilson(0, 0))


class TestPairwiseConcordance(unittest.TestCase):
    def test_it_reproduces_the_first_pass_ordering_figures(self):
        # 31/66 = 47.0% overall, 31/51 = 60.8% once the ensemble's 15 ties are
        # dropped. Both numbers appear in docs/12 and neither may drift silently.
        human = [10, 9, 10, 7, 10, 10, 9, 10, 10, 10, 9, 5, 10, 10, 8]
        ens = [9, 10, 8, 9, 8, 10, 5, 10, 9, 8, 9, 9, 9, 10, 7]
        p = pairwise_concordance(list(zip(ens, human)))
        self.assertEqual(p["n_pairs"], 66)
        self.assertEqual(p["agree"], 31)
        self.assertEqual(p["n_ensemble_tied"], 15)
        self.assertAlmostEqual(p["concordance_all"], 0.470, places=3)
        self.assertAlmostEqual(p["concordance_decided"], 0.608, places=3)

    def test_dropping_ties_cannot_lower_the_figure(self):
        # The whole reason both are reported: conditioning on the ensemble
        # having an opinion can only flatter it.
        human = [10, 9, 10, 7, 10, 10, 9, 10, 10, 10, 9, 5, 10, 10, 8]
        ens = [9, 10, 8, 9, 8, 10, 5, 10, 9, 8, 9, 9, 9, 10, 7]
        p = pairwise_concordance(list(zip(ens, human)))
        self.assertGreaterEqual(p["concordance_decided"], p["concordance_all"])

    def test_perfect_ordering_is_one_even_when_the_scales_differ(self):
        # The point of the pairwise reading: a labeller who uses only 9 and 10
        # still expresses orderings, and a judge on a different scale can match
        # them exactly. Pearson on this data is what the ceiling suppresses.
        p = pairwise_concordance([(2, 9), (4, 10), (6, 11), (8, 12)])
        self.assertEqual(p["concordance_all"], 1.0)
        self.assertEqual(p["n_ensemble_tied"], 0)

    def test_reversed_ordering_is_zero(self):
        p = pairwise_concordance([(8, 9), (6, 10), (4, 11), (2, 12)])
        self.assertEqual(p["agree"], 0)

    def test_pairs_the_labeller_scored_equal_are_not_counted(self):
        # No preference expressed, so there is nothing for the ensemble to
        # match. Counting them would dilute the statistic with non-questions.
        p = pairwise_concordance([(5, 7), (9, 7), (3, 7)])
        self.assertEqual(p["n_pairs"], 0)

    def test_an_all_ties_ensemble_scores_zero_not_a_division_error(self):
        p = pairwise_concordance([(7, 9), (7, 10), (7, 8)])
        self.assertEqual(p["n_pairs"], 3)
        self.assertEqual(p["n_ensemble_tied"], 3)
        self.assertEqual(p["concordance_all"], 0.0)
        self.assertIsNone(p["concordance_decided"])

    def test_too_few_items_is_empty_not_a_crash(self):
        self.assertEqual(pairwise_concordance([])["n_pairs"], 0)
        self.assertEqual(pairwise_concordance([(9, 9)])["n_pairs"], 0)


# ------------------------------------------------------- pairwise sampling
#
# The set these draw is what a person spends hours labelling, and every defect
# here is one that cannot be fixed afterwards: a leaked vendor, a side that
# always holds the better response, a repeat shown three screens after its
# original. None of it is recoverable once the labels exist.

CATS = ["general_facts", "breaking_news", "local_shopping",
        "code_technical", "multi_hop", "long_tail"]


def resp(rid, qid, cat, med, gold=True):
    return {"id": rid, "query_id": qid, "category": cat, "median": med,
            "gold_answer": "g" if gold else None, "query_text": "q",
            "response_mode": "ranked_results", "answer": None, "results": None}


def pool(n_queries=60):
    """Five vendors per query, spread so both strata are well supplied."""
    out = []
    for i in range(n_queries):
        cat = CATS[i % len(CATS)]
        for v in range(5):
            med = 5 + (v * 1.5 if i % 2 else 0.0)      # alternate wide / level
            # Gold presence varies independently of the gap: tying the two
            # would leave the stratifier nothing to balance.
            out.append(resp(f"r{i:03d}v{v}", f"q{i:03d}", cat, med, gold=(i % 4 < 2)))
    return out


class TestBuildPairs(unittest.TestCase):
    def test_pairs_never_cross_queries(self):
        # "Which of these two answers to different questions is better" is not
        # a question a person can answer.
        pairs = build_pairs(pool(6))
        for p in pairs:
            self.assertEqual(p["a"]["query_id"], p["b"]["query_id"])

    def test_every_within_query_combination_appears_once(self):
        pairs = build_pairs(pool(2))
        self.assertEqual(len(pairs), 2 * (5 * 4 // 2))
        seen = {(p["a"]["id"], p["b"]["id"]) for p in pairs}
        self.assertEqual(len(seen), len(pairs))

    def test_gap_uses_the_published_median(self):
        rows = [resp("a", "q", "general_facts", 9.0), resp("b", "q", "general_facts", 6.5)]
        self.assertAlmostEqual(build_pairs(rows)[0]["gap"], 2.5)


class TestDrawPairs(unittest.TestCase):
    def setUp(self):
        self.pairs = build_pairs(pool())

    def draw(self, **kw):
        opts = dict(n_decisive=30, n_near_tie=12, n_swapped=10, n_repeat=6)
        opts.update(kw)
        return draw_pairs(self.pairs, 3, **opts)

    def test_strata_are_the_requested_sizes(self):
        got = self.draw()
        counts = {}
        for p in got:
            counts[p["stratum"]] = counts.get(p["stratum"], 0) + 1
        self.assertEqual(counts["decisive"], 30)
        self.assertEqual(counts["near_tie"], 12)
        self.assertEqual(counts["swapped"], 10)
        self.assertEqual(counts["repeat"], 6)

    def test_decisive_and_near_tie_respect_their_thresholds(self):
        for p in self.draw():
            if p["stratum"] == "decisive":
                self.assertGreaterEqual(p["gap"], 1.0)
            elif p["stratum"] == "near_tie":
                self.assertLessEqual(p["gap"], 0.5)

    def test_gold_presence_is_stratified_not_left_to_chance(self):
        # The defect this fixes: the first sampler never read `gold_answer`, so
        # what share of the set could be judged on correctness rather than
        # plausibility was whatever the draw happened to produce.
        dec = [p for p in self.draw() if p["stratum"] == "decisive"]
        gold = sum(1 for p in dec if p["has_gold"])
        self.assertAlmostEqual(gold / len(dec), 0.5, delta=0.1)

    def test_categories_are_even_within_the_decisive_stratum(self):
        dec = [p for p in self.draw() if p["stratum"] == "decisive"]
        counts = {}
        for p in dec:
            counts[p["category"]] = counts.get(p["category"], 0) + 1
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_sides_are_not_assigned_by_score(self):
        # If the better response were always on the left, a labeller who always
        # clicks left scores 100% without reading anything.
        got = [p for p in self.draw(n_decisive=60) if p["stratum"] == "decisive"]
        left_better = sum(1 for p in got
                          if (p["b"] if p["flip"] else p["a"])["median"]
                          > (p["a"] if p["flip"] else p["b"])["median"])
        self.assertGreater(left_better, 10)
        self.assertLess(left_better, 50)

    def test_swapped_items_really_are_swapped(self):
        got = self.draw()
        by_id = {p["pair_id"]: p for p in got}
        sw = [p for p in got if p["stratum"] == "swapped"]
        self.assertTrue(sw)
        for p in sw:
            src = by_id[p["source_pair_id"]]
            self.assertEqual(p["flip"], not src["flip"])
            self.assertEqual({p["a"]["id"], p["b"]["id"]},
                             {src["a"]["id"], src["b"]["id"]})

    def test_repeats_are_identical_to_their_source(self):
        got = self.draw()
        by_id = {p["pair_id"]: p for p in got}
        for p in [p for p in got if p["stratum"] == "repeat"]:
            src = by_id[p["source_pair_id"]]
            self.assertEqual(p["flip"], src["flip"])

    def test_repeats_never_appear_before_their_source(self):
        got = self.draw()
        pos = {p["pair_id"]: p["position"] for p in got}
        for p in got:
            if p.get("source_pair_id"):
                self.assertGreater(pos[p["pair_id"]], pos[p["source_pair_id"]],
                                   "a re-presentation was shown before its original")

    def test_repeats_are_not_adjacent_to_their_source(self):
        # A pair shown twice within a few screens measures short-term memory.
        got = self.draw()
        pos = {p["pair_id"]: p["position"] for p in got}
        for p in got:
            if p.get("source_pair_id"):
                self.assertGreater(pos[p["pair_id"]] - pos[p["source_pair_id"]], 5)

    def test_positions_are_dense_and_unique(self):
        got = self.draw()
        self.assertEqual(sorted(p["position"] for p in got), list(range(len(got))))

    def test_deterministic_for_a_seed(self):
        a = [(p["pair_id"], p["position"], p["flip"]) for p in draw_pairs(self.pairs, 5)]
        b = [(p["pair_id"], p["position"], p["flip"]) for p in draw_pairs(self.pairs, 5)]
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        a = {p["a"]["id"] + p["b"]["id"] for p in draw_pairs(self.pairs, 1)}
        b = {p["a"]["id"] + p["b"]["id"] for p in draw_pairs(self.pairs, 2)}
        self.assertNotEqual(a, b)

    def test_a_thin_pool_does_not_overdraw(self):
        got = draw_pairs(build_pairs(pool(2)), 1, n_decisive=500, n_near_tie=500,
                         n_swapped=5, n_repeat=5)
        ids = [p["pair_id"] for p in got]
        self.assertEqual(len(ids), len(set(ids)))


# -------------------------------------------------------- pairwise analysis

def lab(pair_id, stratum, choice, ens, src=None, left="L", right="R"):
    return {"pair_id": pair_id, "stratum": stratum, "choice": choice,
            "ensemble_choice": ens, "source_pair_id": src,
            "shown_left": left, "shown_right": right}


class TestPairwiseReport(unittest.TestCase):
    def test_concordance_counts_only_the_decisive_stratum(self):
        # The near-tie stratum has no ensemble opinion by construction, so
        # counting it measures the labeller against a coin.
        rows = ([lab(f"d{i}", "decisive", "left", "left") for i in range(8)]
                + [lab(f"n{i}", "near_tie", "left", "tie") for i in range(20)])
        r = pairwise_report(rows)
        self.assertEqual(r["decisive"]["n_scored"], 8)
        self.assertEqual(r["decisive"]["concordance"], 1.0)

    def test_human_ties_leave_the_numerator_rather_than_counting_against(self):
        rows = [lab("a", "decisive", "left", "left"),
                lab("b", "decisive", "tie", "right")]
        r = pairwise_report(rows)
        self.assertEqual(r["decisive"]["n"], 2)
        self.assertEqual(r["decisive"]["n_human_tied"], 1)
        self.assertEqual(r["decisive"]["n_scored"], 1)

    def test_clears_chance_is_false_when_the_interval_includes_a_half(self):
        rows = [lab(f"d{i}", "decisive", "left" if i < 6 else "right", "left")
                for i in range(10)]
        r = pairwise_report(rows)
        self.assertAlmostEqual(r["decisive"]["concordance"], 0.6)
        self.assertFalse(r["decisive"]["clears_chance"])

    def test_clears_chance_is_true_on_a_strong_well_sized_result(self):
        rows = [lab(f"d{i}", "decisive", "left" if i < 120 else "right", "left")
                for i in range(150)]
        self.assertTrue(pairwise_report(rows)["decisive"]["clears_chance"])

    def test_re_presentations_never_inflate_the_concordance(self):
        # Same evidence shown twice; pooling it would narrow the interval on
        # nothing.
        base = [lab(f"d{i}", "decisive", "left", "left") for i in range(10)]
        with_extras = base + [lab(f"x{i}", "repeat", "left", "left", src=f"d{i}")
                              for i in range(10)]
        self.assertEqual(pairwise_report(base)["decisive"]["n_scored"],
                         pairwise_report(with_extras)["decisive"]["n_scored"])

    def test_position_bias_separates_same_side_from_same_response(self):
        # The labeller picked "left" both times. Because the sides were
        # swapped, that is the same SIDE and a different RESPONSE.
        rows = [lab("d0", "decisive", "left", "left", left="A", right="B"),
                lab("x0", "swapped", "left", "right", src="d0", left="B", right="A")]
        pb = pairwise_report(rows)["position_bias"]
        self.assertEqual(pb["n"], 1)
        self.assertEqual(pb["picked_same_side"], 1)
        self.assertEqual(pb["picked_same_response"], 0)

    def test_a_consistent_labeller_scores_same_response_not_same_side(self):
        rows = [lab("d0", "decisive", "left", "left", left="A", right="B"),
                lab("x0", "swapped", "right", "left", src="d0", left="B", right="A")]
        pb = pairwise_report(rows)["position_bias"]
        self.assertEqual(pb["picked_same_side"], 0)
        self.assertEqual(pb["picked_same_response"], 1)

    def test_self_agreement_reads_the_repeat_stratum(self):
        rows = [lab("d0", "decisive", "left", "left"),
                lab("d1", "decisive", "right", "right"),
                lab("x0", "repeat", "left", "left", src="d0"),
                lab("x1", "repeat", "left", "right", src="d1")]
        sa = pairwise_report(rows)["self_agreement"]
        self.assertEqual(sa["n"], 2)
        self.assertEqual(sa["agree"], 1)
        self.assertAlmostEqual(sa["rate"], 0.5)

    def test_an_orphaned_re_presentation_is_ignored_not_counted(self):
        rows = [lab("x0", "repeat", "left", "left", src="missing")]
        self.assertEqual(pairwise_report(rows)["self_agreement"]["n"], 0)

    def test_no_labels_at_all_is_empty_not_a_crash(self):
        r = pairwise_report([])
        self.assertEqual(r["decisive"]["n"], 0)
        self.assertIsNone(r["decisive"]["concordance"])
        self.assertFalse(r["decisive"]["clears_chance"])


# ------------------------------------------- recovering a set without redrawing

class TestLoadPairSet(unittest.TestCase):
    """Rebuilding a drawn set must restore it, never re-draw it.

    A pairwise set lives in two places: the rows recording what was drawn, in
    the database, and the task the labeller opens, on disk outside git because
    it shows vendor-retrieved content. The second is the half that goes missing,
    and the only previous way to get it back was `sample-pairs` — which draws a
    *new* sample. Doing that to set `96afde9bfef3`, registered 2026-08-05 with
    280 screens, would have replaced a sample drawn before anyone saw the scores
    with one drawn after. These tests are about that distinction.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = storage.connect(Path(self._tmp.name) / "c.db")
        self.conn.row_factory = sqlite3.Row
        c = self.conn
        c.execute("INSERT INTO runs (id, started_at, week, query_set_hash) "
                  "VALUES ('r1','2099-01-01T00:00:00+00:00','2099-W01','h')")
        c.execute("INSERT INTO queries (id, category, text, gold_answer) "
                  "VALUES ('q1','general_facts','how tall is the tower','330 m')")
        for rid, answer in (("A", "answer A"), ("B", "answer B")):
            c.execute(
                "INSERT INTO raw_responses (id, run_id, query_id, vendor, "
                "response_mode, answer, results, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, "r1", "q1", f"fixture_{rid}", "ranked_results", answer,
                 json.dumps([{"rank": 0, "title": f"t{rid}", "url": "https://e.invalid",
                              "snippet": "s"}]), "2099-01-01T00:00:00+00:00"))
        c.execute("INSERT INTO calibration_sets (id, run_id, created_at, seed, "
                  "n_target, disagreement_share, blinding, kind) "
                  "VALUES ('set1','r1','2099-01-01T00:00:00+00:00',7,2,0.0,'b','pairwise')")
        # Deliberately inserted out of order, with the second screen showing the
        # same two responses the other way round — the `swapped` stratum.
        c.executemany(
            "INSERT INTO calibration_pairs (set_id, pair_id, left_response_id, "
            "right_response_id, stratum, position, source_pair_id, ensemble_gap) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [("set1", "p2", "B", "A", "swapped", 1, "p1", 2.0),
             ("set1", "p1", "A", "B", "decisive", 0, None, 2.0)])
        c.commit()

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_the_screens_come_back_in_the_order_they_were_drawn(self):
        got = load_pair_set(self.conn, "set1")
        self.assertEqual([p["pair_id"] for p in got], ["p1", "p2"])
        self.assertEqual([p["position"] for p in got], [0, 1])

    def test_the_recorded_side_order_is_not_re_randomised(self):
        # The whole measurement of position bias depends on this. `sample-pairs`
        # applies the flip before writing the rows, so left in the database is
        # left on the screen; re-shuffling here would silently destroy the
        # swapped stratum by making it identical to the decisive one.
        got = {p["pair_id"]: p for p in load_pair_set(self.conn, "set1")}
        self.assertEqual(got["p1"]["a"]["answer"], "answer A")
        self.assertEqual(got["p1"]["b"]["answer"], "answer B")
        self.assertEqual(got["p2"]["a"]["answer"], "answer B")
        self.assertEqual(got["p2"]["b"]["answer"], "answer A")
        self.assertTrue(all(p["flip"] is False for p in got.values()))

    def test_rebuilding_twice_gives_the_same_task(self):
        self.assertEqual(load_pair_set(self.conn, "set1"),
                         load_pair_set(self.conn, "set1"))

    def test_registered_task_uses_run_snapshot_after_global_query_edits(self):
        self.conn.execute(
            "INSERT INTO run_queries (run_id,query_id,category,text,gold_answer) "
            "SELECT 'r1',id,category,text,gold_answer FROM queries WHERE id='q1'")
        before = load_pair_set(self.conn, "set1")
        self.conn.execute("UPDATE queries SET category='long_tail',text='different question',"
                          "gold_answer='different answer' WHERE id='q1'")
        self.conn.commit()
        self.assertEqual(load_pair_set(self.conn, "set1"), before)

    def test_the_question_and_reference_answer_travel_with_each_side(self):
        p = load_pair_set(self.conn, "set1")[0]
        self.assertEqual(p["category"], "general_facts")
        for side in ("a", "b"):
            self.assertEqual(p[side]["query_text"], "how tall is the tower")
            self.assertEqual(p[side]["gold_answer"], "330 m")

    def test_the_task_carries_no_stratum_or_margin(self):
        # Read straight out of what write_pair_task will be handed: a labeller
        # who can see that a screen is a repeat is answering a different
        # question, and the analysis rejoins all of this from the database.
        for p in load_pair_set(self.conn, "set1"):
            for leak in ("stratum", "ensemble_gap", "source_pair_id"):
                self.assertNotIn(leak, p)

    def test_a_set_with_no_pairs_says_so_rather_than_returning_nothing(self):
        self.conn.execute(
            "INSERT INTO calibration_sets (id, run_id, created_at, seed, n_target, "
            "disagreement_share, blinding) "
            "VALUES ('abs1','r1','2099-01-01T00:00:00+00:00',1,10,0.3,'b')")
        with self.assertRaises(SystemExit):
            load_pair_set(self.conn, "abs1")

    def test_an_unknown_set_raises(self):
        with self.assertRaises(SystemExit):
            load_pair_set(self.conn, "nope")

    def test_the_written_task_is_stamped_with_the_draw_date(self):
        # Not the rebuild date. A set recovered on a later machine that claimed
        # to have been created that day would misdate the one thing the design
        # rests on — that the sample predates anyone seeing the scores.
        out = Path(self._tmp.name) / "task"
        write_pair_task("set1", load_pair_set(self.conn, "set1"), out,
                        created_at="2099-01-01T00:00:00+00:00")
        # Anchored on the trailing `;\n` rather than split on ";", which the
        # vendor content is full of.
        body = re.search(r"window\.VN_TASK = (.*);\n\Z",
                         (out / "task.js").read_text(), re.S).group(1)
        payload = json.loads(body)
        self.assertEqual(payload["created_at"], "2099-01-01T00:00:00+00:00")
        self.assertEqual(payload["kind"], "pairwise")
        self.assertEqual([i["pair_id"] for i in payload["items"]], ["p1", "p2"])


class TestExport(unittest.TestCase):
    """The export is the only copy of a label that survives the laptop.

    `export` read `human_labels` and nothing else, so pointing it at the
    pairwise set `96afde9bfef3` on 2026-08-16 — 280 screens, four hours of
    labelling — found zero rows, wrote an empty file over the export, and said
    "wrote ... 0 label(s)" on the way out. Nothing crashed. These tests are the
    gate on both halves of that: read the right table, and never write an empty
    export no matter which table was wrong.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "labels"
        self.db = Path(self._tmp.name) / "c.db"
        c = storage.connect(self.db)
        c.execute("INSERT INTO runs (id, started_at, week, query_set_hash) "
                  "VALUES ('r1','2099-01-01T00:00:00+00:00','2099-W01','h')")
        c.execute("INSERT INTO queries (id, category, text, gold_answer) "
                  "VALUES ('q1','general_facts','q','a')")
        for rid in ("A", "B"):
            c.execute(
                "INSERT INTO raw_responses (id, run_id, query_id, vendor, "
                "response_mode, answer, results, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, "r1", "q1", f"fixture_{rid}", "ranked_results", "x",
                 "[]", "2099-01-01T00:00:00+00:00"))
        # A scores 8, B scores 5 — the ensemble picks left on p1.
        for jid, (rid, model, score) in enumerate(
                [("A", "m1", 8.0), ("A", "m2", 8.0),
                 ("B", "m1", 5.0), ("B", "m2", 5.0)]):
            c.execute("INSERT INTO judge_scores (id, response_id, judge_model, "
                      "judge_family, overall, created_at) VALUES (?,?,?,?,?,?)",
                      (f"j{jid}", rid, model, model, score,
                       "2099-01-01T00:00:00+00:00"))
        c.execute("INSERT INTO calibration_sets (id, run_id, created_at, seed, "
                  "n_target, disagreement_share, blinding, kind) "
                  "VALUES ('set1','r1','2099-01-01T00:00:00+00:00',7,1,0.0,'b','pairwise')")
        c.execute("INSERT INTO calibration_pairs (set_id, pair_id, "
                  "left_response_id, right_response_id, stratum, position, "
                  "source_pair_id, ensemble_gap) "
                  "VALUES ('set1','p1','A','B','decisive',0,NULL,3.0)")
        c.commit()
        c.close()

    def tearDown(self):
        self._tmp.cleanup()

    def _label(self):
        c = storage.connect(self.db)
        c.execute("INSERT INTO pair_labels (id, set_id, pair_id, labeller, "
                  "labeller_kind, choice, note, seconds, labelled_at) "
                  "VALUES ('l1','set1','p1','feruz','human','left','n',55,"
                  "'2099-01-01T00:00:00+00:00')")
        c.commit()
        c.close()

    def _run(self):
        return cmd_export(argparse.Namespace(
            db=str(self.db), set="set1", out=str(self.out)))

    def test_a_pairwise_set_exports_its_labels(self):
        self._label()
        self._run()
        got = json.loads((self.out / "set1.json").read_text())
        self.assertEqual(got["kind"], "pairwise")
        self.assertEqual(len(got["labels"]), 1)
        self.assertEqual(got["labels"][0]["choice"], "left")
        self.assertEqual(got["labels"][0]["labeller_kind"], "human")

    def test_the_ensemble_choice_travels_with_the_human_choice(self):
        # Without this the file records an opinion with nothing to compare it
        # against: judge_scores lives in the database, which is never committed,
        # so agreement could never be recomputed from the export alone.
        self._label()
        self._run()
        got = json.loads((self.out / "set1.json").read_text())
        self.assertEqual(got["labels"][0]["ensemble_choice"], "left")
        self.assertEqual(got["labels"][0]["stratum"], "decisive")

    def test_a_model_only_pass_never_reports_clearing_chance(self):
        # check-all.sh unlatches the site copy on cleared_chance + a
        # labeller_kinds of exactly ["human"]. Agreement between models is a
        # different measurement (docs/12); letting it set this field would
        # publish "the judges track humans" off the judges marking themselves.
        c = storage.connect(self.db)
        c.execute("INSERT INTO pair_labels (id, set_id, pair_id, labeller, "
                  "labeller_kind, choice, note, seconds, labelled_at) "
                  "VALUES ('l1','set1','p1','gpt','model','left',NULL,NULL,"
                  "'2099-01-01T00:00:00+00:00')")
        c.commit()
        c.close()
        self._run()
        got = json.loads((self.out / "set1.json").read_text())
        self.assertFalse(got["cleared_chance"])
        self.assertEqual(got["labeller_kinds"], ["model"])

    def test_one_agreeing_pair_is_not_enough_to_clear_chance(self):
        # The field is a statistical claim, not a tally: a single decisive pair
        # agrees 1/1 = 100% and still cannot exclude 50%.
        self._label()
        self._run()
        got = json.loads((self.out / "set1.json").read_text())
        self.assertEqual(got["decisive"]["agree"], 1)
        self.assertFalse(got["cleared_chance"])

    def test_it_refuses_to_write_an_empty_export(self):
        with self.assertRaises(SystemExit):
            self._run()
        self.assertFalse((self.out / "set1.json").exists())

    def test_an_empty_read_never_overwrites_a_good_export(self):
        # The failure that made this expensive: the file already existed and was
        # replaced with nothing.
        self._label()
        self._run()
        before = (self.out / "set1.json").read_text()
        c = storage.connect(self.db)
        c.execute("DELETE FROM pair_labels")
        c.commit()
        c.close()
        with self.assertRaises(SystemExit):
            self._run()
        self.assertEqual((self.out / "set1.json").read_text(), before)


if __name__ == "__main__":
    unittest.main()
