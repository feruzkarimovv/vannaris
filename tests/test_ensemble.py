"""The judge ensemble's pure functions — the bias mitigations, tested.

`AUTONOMY.md` item 1 names these as the single most damaging thing in the
repository to get wrong: the cross-family ensemble, length normalisation, and
`require_full=True`. `CLAUDE.md` calls them the product's credibility rather
than nice-to-haves. Until now not one of them had a test.

That gap has a particular shape. None of these functions crash when they are
wrong — they return a number, and the number is published. A `median_overall`
that quietly averaged two judges where it should have returned None would put a
differently-computed figure in the same column as a properly-computed one and
nothing anywhere would notice. So these tests assert the *refusals*: the cases
where the right answer is to decline rather than to produce something.

Nothing here makes a network call. Every function under test is pure.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from src.judge.ensemble import (  # noqa: E402
    JUDGES,
    JudgeScore,
    _extract,
    _retry_after,
    build_prompt,
    median_overall,
)
from src.vendors.base import ResponseMode, SearchResponse, SearchResult  # noqa: E402


def score(overall, family="anthropic"):
    return JudgeScore(judge_family=family, judge_model="m", overall=overall)


def response(**kw):
    base = {"vendor": "fixture_alpha", "query_id": "q1",
            "response_mode": ResponseMode.RANKED_RESULTS}
    return SearchResponse(**{**base, **kw})


# ------------------------------------------------------------------ salvage

class TestExtract(unittest.TestCase):
    """The truncation-tolerant parser.

    Its reason for existing is measured, not hypothetical: 32% of Google calls
    in the 150-query run truncated mid-rationale, and the strict parser that
    preceded it discarded those replies whole. Discarding them is not merely
    lossy, it is *biased* — longer vendor payloads truncate more often, so the
    responses thrown away are not a random sample of the responses.
    """

    def test_plain_json(self):
        got = _extract('{"relevance": 8, "freshness": 6, '
                       '"citation_quality": 7, "overall": 7.5, "rationale": "fine"}')
        self.assertEqual(got["overall"], 7.5)
        self.assertEqual(got["rationale"], "fine")
        self.assertNotIn("_salvaged", got)

    def test_fenced_json(self):
        got = _extract('```json\n{"overall": 9}\n```')
        self.assertEqual(got["overall"], 9)

    def test_prose_around_the_object(self):
        got = _extract('Here is my assessment:\n{"overall": 4}\nHope that helps.')
        self.assertEqual(got["overall"], 4)

    def test_truncated_mid_rationale_keeps_every_score(self):
        # The measured failure. The four numbers are emitted before the prose
        # and were complete in essentially every truncated case, so the reply is
        # worth salvaging rather than discarding.
        got = _extract('{"relevance": 8, "freshness": 5, "citation_quality": 7, '
                       '"overall": 7, "rationale": "The results are broadly rele')
        self.assertEqual(
            [got["relevance"], got["freshness"], got["citation_quality"], got["overall"]],
            [8.0, 5.0, 7.0, 7.0])
        self.assertTrue(got["_salvaged"])
        self.assertEqual(got["rationale"], "The results are broadly rele")

    def test_truncated_before_the_rationale_has_no_rationale(self):
        got = _extract('{"relevance": 3, "overall": 2')
        self.assertEqual(got["overall"], 2.0)
        self.assertNotIn("rationale", got)

    def test_salvage_recovers_only_the_fields_present(self):
        got = _extract('{"relevance": 6, "overall": 6, "rationale": "cut')
        self.assertNotIn("freshness", got)
        self.assertNotIn("citation_quality", got)

    def test_negative_and_decimal_scores_are_parsed_not_dropped(self):
        # Clamping to 0-10 belongs to score_one. If salvage silently skipped a
        # negative it would look like a missing judge instead of a bad one.
        got = _extract('{"overall": -2.5, "rationale": "x')
        self.assertEqual(got["overall"], -2.5)

    def test_a_reply_with_no_scores_raises(self):
        # Loud, because the caller records this as a judge error and a response
        # with a judge error never reaches a published median.
        with self.assertRaises(ValueError):
            _extract("I'm sorry, I can't help with that.")

    def test_empty_reply_raises(self):
        with self.assertRaises(ValueError):
            _extract("")

    def test_an_empty_rationale_string_becomes_none_not_empty(self):
        got = _extract('{"overall": 5, "rationale": "')
        self.assertIsNone(got.get("rationale"))


# ------------------------------------------------------- the completeness rule

class TestMedianOverall(unittest.TestCase):
    """`require_full=True` — the rule that a published cell is computed one way.

    AUTONOMY.md item 1 forbids relaxing this. The bias it guards is specific:
    rate limits cluster in time rather than falling randomly, so the responses
    missing a judge are not a random subset. A two-way mean sitting in the same
    column as a three-way median is worse than a hole, because it is invisible.
    """

    def test_full_ensemble_takes_the_median(self):
        self.assertEqual(median_overall([score(2), score(7), score(9)]), 7)

    def test_the_median_ignores_one_outlier_judge(self):
        # The documented reason it is a median and not a mean. The mean here
        # would be 5.67; a single disagreeing judge must not move a number.
        self.assertEqual(median_overall([score(8), score(9), score(0)]), 8)

    def test_an_incomplete_ensemble_returns_none(self):
        self.assertIsNone(median_overall([score(8), score(9)]))

    def test_a_judge_that_errored_makes_the_ensemble_incomplete(self):
        # The realistic shape: three JudgeScore rows exist, one has overall=None
        # because the call failed. It must count as missing, not as absent.
        self.assertIsNone(median_overall([score(8), score(9), score(None)]))

    def test_no_scores_at_all_returns_none(self):
        self.assertIsNone(median_overall([]))

    def test_require_full_false_averages_what_it_has(self):
        # The escape hatch exists for diagnostics. It must stay off by default —
        # the signature is keyword-only precisely so it cannot be passed by
        # accident.
        self.assertEqual(median_overall([score(6), score(8)], require_full=False), 7)

    def test_require_full_defaults_to_true(self):
        # Pinned rather than assumed. A change of default would silently alter
        # every published number and no other test would fail.
        self.assertIsNone(median_overall([score(6), score(8)]))

    def test_the_floor_tracks_the_number_of_judges(self):
        # If a fourth family were ever added, "complete" has to mean four. This
        # fails loudly if the rule is ever hard-coded to three.
        full = [score(5) for _ in JUDGES]
        self.assertIsNotNone(median_overall(full))
        self.assertIsNone(median_overall(full[:-1]))


# --------------------------------------------------------------- retry policy

class TestRetryAfter(unittest.TestCase):
    """Retries decide how many judges survive a run, so they decide coverage."""

    @staticmethod
    def exc(status, headers=None, body=""):
        request = httpx.Request("POST", "https://example.invalid/v1")
        resp = httpx.Response(status, headers=headers or {}, text=body, request=request)
        return httpx.HTTPStatusError("boom", request=request, response=resp)

    def test_a_client_error_is_not_retried(self):
        # A 400 is a bad request and will be bad again. Retrying it burns the
        # budget that a 429 needs.
        self.assertIsNone(_retry_after(self.exc(400), 0))
        self.assertIsNone(_retry_after(self.exc(404), 0))

    def test_rate_limit_honours_the_header(self):
        self.assertEqual(_retry_after(self.exc(429, {"retry-after": "12"}), 0), 12.0)

    def test_an_absurd_header_is_capped(self):
        # A judge asking for an hour would stall the whole run past the
        # workflow's timeout, taking every remaining response with it.
        self.assertEqual(_retry_after(self.exc(429, {"retry-after": "3600"}), 0), 70.0)

    def test_a_non_numeric_header_falls_back_rather_than_crashing(self):
        # Retry-After may legally be an HTTP-date. Parsing it is not worth the
        # code; crashing on it would be.
        got = _retry_after(self.exc(429, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}), 2)
        self.assertEqual(got, 4.0)

    def test_googles_delay_in_the_body_is_found(self):
        got = _retry_after(self.exc(429, body='{"error": "please retry in 12s"}'), 0)
        self.assertEqual(got, 13.0)   # +1s of headroom

    def test_server_errors_back_off_exponentially(self):
        self.assertEqual(_retry_after(self.exc(503), 0), 1.0)
        self.assertEqual(_retry_after(self.exc(503), 3), 8.0)

    def test_the_backoff_is_capped(self):
        self.assertEqual(_retry_after(self.exc(500), 20), 30.0)

    def test_anthropics_overloaded_status_is_retried(self):
        # 529 is not a standard code and would be dropped by a naive check.
        self.assertIsNotNone(_retry_after(self.exc(529), 0))


# --------------------------------------------------- prompt / length normalisation

class TestBuildPrompt(unittest.TestCase):
    """What the judge sees, and the length figure published beside its score."""

    def test_scored_chars_measures_the_payload_not_the_prompt(self):
        # It is published so verbosity outliers are auditable. If it measured
        # the whole prompt it would be dominated by the constant rubric and
        # would say nothing about the vendor.
        prompt, chars = build_prompt(
            response(results=[SearchResult(url="https://example.invalid/a", rank=0,
                                           title="T", snippet="S")]),
            "a query", None)
        self.assertLess(chars, len(prompt))
        self.assertGreater(chars, 0)

    def test_a_longer_response_has_a_larger_scored_chars(self):
        short = response(results=[SearchResult(url="https://example.invalid/a", rank=0)])
        long = response(results=[
            SearchResult(url=f"https://example.invalid/{i}", rank=i,
                         title="A title", snippet="A snippet " * 10)
            for i in range(10)])
        self.assertGreater(build_prompt(long, "q", None)[1],
                           build_prompt(short, "q", None)[1])

    def test_an_empty_response_says_so_rather_than_rendering_blank(self):
        # A judge handed an empty payload with no explanation may score it as
        # though something were there. The vendor returned nothing and the
        # prompt has to say the vendor returned nothing.
        prompt, _ = build_prompt(response(), "a query", None)
        self.assertIn("(the API returned nothing)", prompt)

    def test_a_gold_answer_is_offered_when_there_is_one(self):
        with_gold, _ = build_prompt(response(), "q", "42")
        without, _ = build_prompt(response(), "q", None)
        self.assertIn("42", with_gold)
        self.assertNotIn("Known correct answer", without)

    def test_breaking_news_style_queries_carry_no_gold_block(self):
        # These deliberately have no gold answer (src/queries/full-v1.json), and
        # inventing an empty "Known correct answer:" line would tell the judge
        # the right answer is nothing.
        prompt, _ = build_prompt(response(), "what is the latest X", None)
        self.assertNotIn("Known correct answer", prompt)

    def test_a_synthesized_answer_is_announced(self):
        prompt, _ = build_prompt(
            response(response_mode=ResponseMode.SYNTHESIZED_ANSWER, answer="Because."),
            "why", None)
        self.assertIn("synthesized prose answer", prompt)

    def test_ranked_results_are_not_announced_as_prose(self):
        prompt, _ = build_prompt(response(results=[
            SearchResult(url="https://example.invalid/a", rank=0)]), "q", None)
        self.assertNotIn("synthesized prose answer", prompt)

    def test_ranks_are_presented_one_indexed(self):
        # rank is 0-indexed internally. A judge told the top hit is "0." reads a
        # list that starts at zero, which is not how a person reads a SERP.
        prompt, _ = build_prompt(response(results=[
            SearchResult(url="https://example.invalid/a", rank=0, title="First")]),
            "q", None)
        self.assertIn("1. First", prompt)

    def test_a_very_long_snippet_is_truncated(self):
        # Verbosity must not buy prompt real estate. Without this a vendor
        # returning essays would occupy more of the judge's attention than one
        # returning summaries, which is the bias length normalisation exists to
        # remove.
        prompt, _ = build_prompt(response(results=[
            SearchResult(url="https://example.invalid/a", rank=0, snippet="x" * 5000)]),
            "q", None)
        self.assertNotIn("x" * 500, prompt)
        self.assertIn("x" * 400, prompt)

    def test_a_result_with_no_title_still_renders(self):
        prompt, _ = build_prompt(response(results=[
            SearchResult(url="https://example.invalid/a", rank=0)]), "q", None)
        self.assertIn("(no title)", prompt)


if __name__ == "__main__":
    unittest.main()
