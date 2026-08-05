"""Unit tests for the calibration arithmetic and sampling.

These are the functions where a bug is invisible: a wrong correlation or a
sampler that quietly drops a stratum still prints a confident-looking table, and
the number it prints is the one used to decide whether the judge can be trusted.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import unittest

from src.calibrate import (_fisher_ci, _pearson, _pearson_ceiling, _rank, _spearman,
                           _wilson, agreement, build_pairs, draw, draw_pairs,
                           pairwise_concordance, pairwise_report)


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


if __name__ == "__main__":
    unittest.main()
