"""Vendor adapters: the normalisation that makes the comparison a comparison.

Five vendors return five different payload shapes, and `_parse` is what turns
them into one envelope. Nothing here had a test, and the failure mode is the
worst kind this repository has: a mapping bug does not raise, it produces
*fewer or emptier results for one vendor*, which the judge then scores lower,
which the site then publishes as that vendor being worse. The benchmark would
be measuring the adapter and calling it the vendor.

Two properties carry most of the weight:

  * **TOP_K.** Vendors return 8 to 20 results by default. Scoring whatever each
    hands back would give the most verbose vendor a structural advantage on
    relevance, so every adapter truncates to the same depth. That is a fairness
    guarantee, not a formatting detail.
  * **cost_source.** Exa and Perplexity report a real billed figure; the other
    three are estimated from published pricing. `docs/06`'s unit economics are a
    projection and the reported figures are the empirical correction to it, so
    mislabelling an estimate as reported would quietly launder a guess into
    evidence.

The payloads below are invented, and shaped after the field names recorded in
`adapters.py` — several of which the module docstring says would have been
wrong if taken from documentation rather than a live call. No network, no keys,
no spend.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.vendors.adapters import (  # noqa: E402
    REGISTRY,
    TOP_K,
    ExaAdapter,
    LinkupAdapter,
    PerplexityAdapter,
    SerperAdapter,
    YouComAdapter,
    build_all,
)
from src.vendors.base import ResponseMode  # noqa: E402

KEY = "fixture-key-not-a-real-credential"


def many(n, **item):
    return [{**item, "i": i} for i in range(n)]


# Each adapter, with a payload in its own shape and where its results live.
# Written as data so the shared guarantees below are asserted against all five
# rather than against whichever one someone remembered.
CASES = {
    "serper": (
        SerperAdapter,
        lambda rows: {"organic": rows},
        lambda i: {"link": f"https://example.invalid/{i}", "title": f"T{i}",
                   "snippet": f"S{i}", "date": "2026-07-01"},
    ),
    "exa": (
        ExaAdapter,
        lambda rows: {"results": rows},
        lambda i: {"url": f"https://example.invalid/{i}", "title": f"T{i}",
                   "text": f"S{i}", "publishedDate": "2026-07-01"},
    ),
    "linkup": (
        LinkupAdapter,
        lambda rows: {"results": rows},
        lambda i: {"url": f"https://example.invalid/{i}", "name": f"T{i}",
                   "content": f"S{i}"},
    ),
    "youcom": (
        YouComAdapter,
        lambda rows: {"results": {"web": rows}},
        lambda i: {"url": f"https://example.invalid/{i}", "title": f"T{i}",
                   "description": f"S{i}", "page_age": "2026-07-01"},
    ),
    "perplexity": (
        PerplexityAdapter,
        lambda rows: {"search_results": rows,
                      "choices": [{"message": {"content": "An answer."}}]},
        lambda i: {"url": f"https://example.invalid/{i}", "title": f"T{i}",
                   "snippet": f"S{i}", "last_updated": "2026-07-01"},
    ),
}


def parsed(vendor, n_results):
    cls, wrap, row = CASES[vendor]
    payload = wrap([row(i) for i in range(n_results)])
    return cls(api_key=KEY)._parse(payload, "q1")


class TestSharedGuarantees(unittest.TestCase):
    """Asserted for every adapter, not for whichever one comes to mind."""

    def test_every_adapter_truncates_to_top_k(self):
        # The fairness guarantee. A vendor returning 20 results must not be
        # scored on 20 while another is scored on 10.
        for vendor in CASES:
            with self.subTest(vendor=vendor):
                self.assertEqual(len(parsed(vendor, 25).results), TOP_K)

    def test_a_vendor_returning_fewer_than_top_k_is_not_padded(self):
        # Returning three results is a fact about the vendor. Padding would
        # hide it; the count is published precisely so it is visible.
        for vendor in CASES:
            with self.subTest(vendor=vendor):
                self.assertEqual(len(parsed(vendor, 3).results), 3)

    def test_ranks_are_zero_indexed_and_in_vendor_order(self):
        for vendor in CASES:
            with self.subTest(vendor=vendor):
                ranks = [r.rank for r in parsed(vendor, 5).results]
                self.assertEqual(ranks, [0, 1, 2, 3, 4])

    def test_every_adapter_maps_url_title_and_snippet(self):
        # The field names differ per vendor and several are counter-intuitive —
        # Linkup's `name`, You.com's `description`, Serper's `link`. A mapping
        # that silently produced None would hand the judge a blank result and
        # score the vendor down for the adapter's mistake.
        for vendor in CASES:
            with self.subTest(vendor=vendor):
                first = parsed(vendor, 3).results[0]
                self.assertEqual(first.url, "https://example.invalid/0")
                self.assertEqual(first.title, "T0")
                self.assertEqual(first.snippet, "S0")

    def test_an_empty_payload_yields_no_results_rather_than_raising(self):
        # "The vendor returned nothing" and "the call failed" are different
        # data. If _parse raised, search() would record the second for the
        # first, and a vendor's reliability figure would be wrong.
        for vendor, (cls, _, _) in CASES.items():
            with self.subTest(vendor=vendor):
                response = cls(api_key=KEY)._parse({}, "q1")
                self.assertEqual(response.results, [])
                self.assertIsNone(response.error)

    def test_the_query_id_and_vendor_are_carried_through(self):
        for vendor in CASES:
            with self.subTest(vendor=vendor):
                response = parsed(vendor, 1)
                self.assertEqual(response.query_id, "q1")
                self.assertEqual(response.vendor, vendor)

    def test_an_api_key_is_required(self):
        for vendor, (cls, _, _) in CASES.items():
            with self.subTest(vendor=vendor):
                with self.assertRaises(ValueError):
                    cls(api_key="")


class TestPerVendorQuirks(unittest.TestCase):
    """The mappings adapters.py says would have been wrong from the docs."""

    def test_linkup_reads_name_not_title(self):
        response = LinkupAdapter(api_key=KEY)._parse(
            {"results": [{"url": "https://example.invalid/a", "name": "The name",
                          "title": "WRONG"}]}, "q1")
        self.assertEqual(response.results[0].title, "The name")

    def test_youcom_results_are_nested_under_web(self):
        # A flat `results` list would silently yield zero results for You.com,
        # and zero results scores as a bad vendor rather than a broken adapter.
        response = YouComAdapter(api_key=KEY)._parse(
            {"results": {"web": [{"url": "https://example.invalid/a"}]}}, "q1")
        self.assertEqual(len(response.results), 1)

    def test_youcom_reads_description_not_snippet(self):
        response = YouComAdapter(api_key=KEY)._parse(
            {"results": {"web": [{"url": "https://example.invalid/a",
                                  "description": "D", "snippet": "WRONG"}]}}, "q1")
        self.assertEqual(response.results[0].snippet, "D")

    def test_serper_reads_link_not_url(self):
        response = SerperAdapter(api_key=KEY)._parse(
            {"organic": [{"link": "https://example.invalid/a"}]}, "q1")
        self.assertEqual(response.results[0].url, "https://example.invalid/a")

    def test_exa_caps_snippet_length(self):
        # Judge input tokens, and length normalisation: a vendor is scored on
        # retrieval, not on how much page text it will hand over.
        response = ExaAdapter(api_key=KEY)._parse(
            {"results": [{"url": "https://example.invalid/a", "text": "x" * 5000}]}, "q1")
        self.assertEqual(len(response.results[0].snippet), 500)

    def test_an_empty_snippet_becomes_none_not_empty_string(self):
        # None means "the vendor gave no snippet"; "" would render as a blank
        # line in the judge prompt and read as an empty result.
        response = ExaAdapter(api_key=KEY)._parse(
            {"results": [{"url": "https://example.invalid/a", "text": ""}]}, "q1")
        self.assertIsNone(response.results[0].snippet)

    def test_perplexity_is_scored_as_both_not_prose_only(self):
        # The reason it is BOTH: Sonar returns a real ranked list alongside its
        # answer, so it can be compared like for like with the other four. If
        # this regressed to SYNTHESIZED_ANSWER the comparison would change
        # shape without any number visibly moving.
        self.assertEqual(PerplexityAdapter.response_mode, ResponseMode.BOTH)
        response = parsed("perplexity", 5)
        self.assertEqual(len(response.results), 5)
        self.assertEqual(response.answer, "An answer.")

    def test_perplexity_survives_a_missing_answer(self):
        response = PerplexityAdapter(api_key=KEY)._parse({"search_results": []}, "q1")
        self.assertIsNone(response.answer)

    def test_perplexity_caps_citations_at_top_k(self):
        response = PerplexityAdapter(api_key=KEY)._parse(
            {"citations": [f"https://example.invalid/{i}" for i in range(30)]}, "q1")
        self.assertEqual(len(response.citations), TOP_K)

    def test_the_other_four_are_ranked_results(self):
        for cls in (SerperAdapter, ExaAdapter, LinkupAdapter, YouComAdapter):
            with self.subTest(vendor=cls.name):
                self.assertEqual(cls.response_mode, ResponseMode.RANKED_RESULTS)


class TestCostProvenance(unittest.TestCase):
    """Reported vs estimated. docs/06's economics are a projection; this is the
    line between the projection and the measurement of it."""

    def test_exa_uses_the_billed_figure_when_it_reports_one(self):
        response = ExaAdapter(api_key=KEY)._parse(
            {"results": [], "costDollars": {"total": 0.0123}}, "q1")
        self.assertEqual(response.cost_usd, 0.0123)
        self.assertEqual(response.cost_source, "reported")

    def test_perplexity_uses_the_billed_figure_when_it_reports_one(self):
        response = PerplexityAdapter(api_key=KEY)._parse(
            {"usage": {"cost": {"total_cost": 0.0091}}}, "q1")
        self.assertEqual(response.cost_usd, 0.0091)
        self.assertEqual(response.cost_source, "reported")

    def test_a_missing_cost_block_is_left_for_the_estimate(self):
        # _parse leaves cost_usd None; search() fills the published estimate and
        # labels it estimated. If _parse guessed here, the two would be
        # indistinguishable afterwards.
        for cls, payload in ((ExaAdapter, {"results": []}),
                             (PerplexityAdapter, {"search_results": []})):
            with self.subTest(vendor=cls.name):
                self.assertIsNone(cls(api_key=KEY)._parse(payload, "q1").cost_usd)

    def test_the_three_estimating_vendors_never_claim_to_report(self):
        for vendor in ("serper", "linkup", "youcom"):
            with self.subTest(vendor=vendor):
                response = parsed(vendor, 2)
                self.assertIsNone(response.cost_usd)
                self.assertEqual(response.cost_source, "estimated")

    def test_every_adapter_publishes_a_price(self):
        for cls, _, _ in CASES.values():
            with self.subTest(vendor=cls.name):
                self.assertGreater(cls.cost_per_query_usd, 0)


class TestRegistry(unittest.TestCase):
    """REGISTRY is the line AUTONOMY.md item 2 guards."""

    def test_the_registry_is_exactly_the_cleared_set(self):
        # docs/03 cleared five. Tavily and Brave are deliberately absent pending
        # written consent, and this is the test that notices a sixth arriving.
        self.assertEqual(set(REGISTRY),
                         {"serper", "exa", "linkup", "youcom", "perplexity"})

    def test_neither_held_back_vendor_is_present(self):
        # Named explicitly rather than left to the set comparison above, so the
        # failure message says which contract is being broken.
        for vendor in ("tavily", "brave", "seltz", "search_router"):
            with self.subTest(vendor=vendor):
                self.assertNotIn(vendor, REGISTRY)

    def test_each_entry_names_its_own_env_var(self):
        for name, (cls, env_var) in REGISTRY.items():
            with self.subTest(vendor=name):
                self.assertEqual(cls.name, name)
                self.assertTrue(env_var.endswith("_API_KEY"), env_var)

    def test_build_all_skips_vendors_with_no_key(self):
        built = build_all({"EXA_API_KEY": KEY, "SERPER_API_KEY": KEY})
        self.assertEqual({a.name for a in built}, {"exa", "serper"})

    def test_build_all_treats_a_blank_key_as_absent(self):
        # A secret set to an empty string is the shape a mis-configured CI
        # takes. Building the adapter anyway would produce a full column of
        # auth failures that looks like a vendor outage.
        built = build_all({"EXA_API_KEY": "   ", "SERPER_API_KEY": KEY})
        self.assertEqual({a.name for a in built}, {"serper"})
        self.assertEqual(build_all({"EXA_API_KEY": "  "}), [])

    def test_build_all_with_no_keys_builds_nothing(self):
        self.assertEqual(build_all({}), [])


class TestSearchWrapper(unittest.IsolatedAsyncioTestCase):
    """search() is what makes a vendor outage data rather than a crash."""

    class Stub(SerperAdapter):
        def __init__(self, payload=None, raises=None):
            super().__init__(api_key=KEY)
            self._payload, self._raises = payload, raises

        async def _request(self, client, query):
            if self._raises:
                raise self._raises
            return self._payload

    async def test_a_successful_call_records_latency_and_the_raw_payload(self):
        payload = {"organic": [{"link": "https://example.invalid/a"}]}
        response = await self.Stub(payload).search(None, "a query", "q1")
        self.assertTrue(response.ok)
        self.assertIsNotNone(response.latency_ms)
        self.assertEqual(response.raw, payload)

    async def test_the_published_estimate_fills_in_when_the_vendor_is_silent(self):
        response = await self.Stub({"organic": []}).search(None, "q", "q1")
        self.assertEqual(response.cost_usd, SerperAdapter.cost_per_query_usd)
        self.assertEqual(response.cost_source, "estimated")

    async def test_a_failing_vendor_is_recorded_not_raised(self):
        # The whole failure-tolerance design: one vendor going down must not
        # abort a weekly run, and the failure is itself evidence about that
        # vendor's reliability.
        response = await self.Stub(raises=RuntimeError("connection reset")).search(
            None, "q", "q1")
        self.assertFalse(response.ok)
        self.assertIn("RuntimeError", response.error)
        self.assertNotIn("connection reset", response.error)

    async def test_a_failed_call_still_reports_how_long_it_took(self):
        # A timeout that took 30 seconds and one that failed instantly are
        # different facts about a vendor.
        response = await self.Stub(raises=RuntimeError("x")).search(None, "q", "q1")
        self.assertIsNotNone(response.latency_ms)

    async def test_a_failed_call_carries_no_results_and_no_raw(self):
        response = await self.Stub(raises=RuntimeError("x")).search(None, "q", "q1")
        self.assertEqual(response.results, [])
        self.assertIsNone(response.raw)


class TestMalformedHTTPResponses(unittest.IsolatedAsyncioTestCase):
    """A successful HTTP status is not evidence of a usable search response."""

    async def search(self, cls, payload):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )) as client:
            return await cls(api_key=KEY).search(client, "private query", "q1")

    async def test_null_result_lists_are_recorded_with_the_raw_reply(self):
        for vendor, (cls, wrap, _) in CASES.items():
            with self.subTest(vendor=vendor):
                payload = wrap(None)
                response = await self.search(cls, payload)
                self.assertFalse(response.ok)
                self.assertEqual(response.results, [])
                self.assertEqual(response.raw, payload)
                self.assertEqual(response.vendor, vendor)
                self.assertEqual(response.query_id, "q1")
                self.assertIsNotNone(response.latency_ms)
                self.assertIn("invalid response", response.error)

    async def test_non_object_replies_remain_available_as_raw_evidence(self):
        for payload in (None, [], "bad reply", 42):
            with self.subTest(payload=payload):
                response = await self.search(SerperAdapter, payload)
                self.assertFalse(response.ok)
                self.assertEqual(response.raw, payload)

    async def test_an_error_body_with_http_success_is_not_an_empty_success(self):
        payload = {"error": {"message": "private failure"}}
        response = await self.search(SerperAdapter, payload)
        self.assertFalse(response.ok)
        self.assertEqual(response.raw, payload)
        self.assertNotIn("private", response.error)

    async def test_invalid_result_fields_never_reach_prompt_rendering(self):
        for item in (None, "bad result", {"link": []},
                     {"link": "https://example.invalid", "snippet": ["secret"]},
                     {"link": "https://example.invalid", "title": {"private": "text"}}):
            with self.subTest(item=item):
                payload = {"organic": [item]}
                response = await self.search(SerperAdapter, payload)
                self.assertFalse(response.ok)
                self.assertEqual(response.raw, payload)
                self.assertNotIn("secret", response.error)
                self.assertNotIn("private", response.error)

    async def test_non_text_answers_and_citations_are_failures(self):
        for payload in (
            {"choices": [{"message": {"content": ["answer"]}}]},
            {"citations": [{"url": "https://example.invalid"}]},
        ):
            with self.subTest(payload=payload):
                response = await self.search(PerplexityAdapter, payload)
                self.assertFalse(response.ok)
                self.assertEqual(response.raw, payload)

    async def test_nonfinite_and_negative_billed_costs_are_failures(self):
        # Strings are what these providers can legitimately use for costs;
        # converting a string to float must not accept nonfinite accounting.
        for cost in ("NaN", "Infinity", "-0.1"):
            with self.subTest(cost=cost):
                payload = {"results": [], "costDollars": {"total": cost}}
                response = await self.search(ExaAdapter, payload)
                self.assertFalse(response.ok)
                self.assertEqual(response.raw, payload)

    async def test_a_malformed_vendor_does_not_cancel_a_concurrent_success(self):
        def reply(request):
            if request.url.host == "google.serper.dev":
                return httpx.Response(200, json={"organic": None})
            return httpx.Response(200, json={"results": [{"url": "https://example.invalid/a"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
            bad, good = await asyncio.gather(
                SerperAdapter(KEY).search(client, "q", "q1"),
                ExaAdapter(KEY).search(client, "q", "q1"),
            )
        self.assertFalse(bad.ok)
        self.assertTrue(good.ok)
        self.assertEqual(good.result_urls(), ["https://example.invalid/a"])

    async def test_http_errors_keep_status_without_echoing_sensitive_content(self):
        payload = {"error": "private query and " + KEY}
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json=payload)
        )) as client:
            response = await YouComAdapter(KEY).search(client, "private query", "q1")
        self.assertIn("HTTP 401", response.error)
        self.assertNotIn("private", response.error)
        self.assertNotIn(KEY, response.error)
        self.assertEqual(response.raw, payload)

    async def test_invalid_json_is_a_failure_not_an_exception(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not JSON: private query")
        )) as client:
            response = await SerperAdapter(KEY).search(client, "q", "q1")
        self.assertFalse(response.ok)
        self.assertIn("JSONDecodeError", response.error)
        self.assertNotIn("private", response.error)

    async def test_a_genuine_empty_result_still_counts_as_a_success(self):
        response = await self.search(SerperAdapter, {"organic": []})
        self.assertTrue(response.ok)
        self.assertEqual(response.results, [])
        self.assertEqual(response.cost_usd, SerperAdapter.cost_per_query_usd)


if __name__ == "__main__":
    unittest.main()
