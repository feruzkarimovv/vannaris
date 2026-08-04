"""Concrete adapters for the ToS-cleared v1 vendor set.

Every request/response shape here was verified against a live call on
2026-08-01 rather than inferred from documentation — several would have been
wrong otherwise (You.com's host, Linkup's `name` field, Perplexity returning a
full result list alongside its prose answer).

Deliberately absent: Tavily and Brave. Both have ToS language broad enough to
cover this benchmark and are held back pending written consent. Do not add an
adapter for either without confirming that consent was actually obtained
(CLAUDE.md, non-negotiable constraints).
"""

from __future__ import annotations

from typing import Any

import httpx

from .base import ResponseMode, SearchResponse, SearchResult, VendorAdapter

# Vendors return anywhere from 8 to 20 results by default. Scoring whatever
# each hands back would give the most verbose vendor a structural advantage on
# relevance, so every adapter is normalized to the same depth.
TOP_K = 10


class SerperAdapter(VendorAdapter):
    name = "serper"
    response_mode = ResponseMode.RANKED_RESULTS
    cost_per_query_usd = 0.0003  # cheapest tier, docs/06 — re-verify live

    async def _request(self, client: httpx.AsyncClient, query: str) -> dict[str, Any]:
        r = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
            json={"q": query, "num": TOP_K},
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def _parse(self, payload: dict[str, Any], query_id: str) -> SearchResponse:
        results = [
            SearchResult(
                url=item.get("link", ""),
                rank=i,
                title=item.get("title"),
                snippet=item.get("snippet"),
                published_at=item.get("date"),  # present only on some results
            )
            for i, item in enumerate(payload.get("organic", [])[:TOP_K])
        ]
        return SearchResponse(
            vendor=self.name,
            query_id=query_id,
            response_mode=self.response_mode,
            results=results,
        )


class ExaAdapter(VendorAdapter):
    name = "exa"
    response_mode = ResponseMode.RANKED_RESULTS
    cost_per_query_usd = 0.007

    async def _request(self, client: httpx.AsyncClient, query: str) -> dict[str, Any]:
        r = await client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": TOP_K,
                # Snippet text is needed for the judge to assess relevance, but
                # capped: full page text would balloon judge input tokens and
                # is not what a retrieval API is being scored on.
                "contents": {"text": {"maxCharacters": 500}},
            },
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def _parse(self, payload: dict[str, Any], query_id: str) -> SearchResponse:
        results = [
            SearchResult(
                url=item.get("url", ""),
                rank=i,
                title=item.get("title"),
                snippet=(item.get("text") or "")[:500] or None,
                published_at=item.get("publishedDate"),
            )
            for i, item in enumerate(payload.get("results", [])[:TOP_K])
        ]
        response = SearchResponse(
            vendor=self.name,
            query_id=query_id,
            response_mode=self.response_mode,
            results=results,
        )
        reported = (payload.get("costDollars") or {}).get("total")
        if reported is not None:
            response.cost_usd = float(reported)
            response.cost_source = "reported"
        return response


class LinkupAdapter(VendorAdapter):
    name = "linkup"
    response_mode = ResponseMode.RANKED_RESULTS
    cost_per_query_usd = 0.005

    async def _request(self, client: httpx.AsyncClient, query: str) -> dict[str, Any]:
        r = await client.post(
            "https://api.linkup.so/v1/search",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            # `standard` not `deep`: deep search is a different product tier and
            # would not be a like-for-like comparison against the others.
            json={"q": query, "depth": "standard", "outputType": "searchResults"},
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def _parse(self, payload: dict[str, Any], query_id: str) -> SearchResponse:
        results = [
            SearchResult(
                url=item.get("url", ""),
                rank=i,
                title=item.get("name"),  # Linkup calls it `name`, not `title`
                snippet=(item.get("content") or "")[:500] or None,
            )
            for i, item in enumerate(payload.get("results", [])[:TOP_K])
        ]
        return SearchResponse(
            vendor=self.name,
            query_id=query_id,
            response_mode=self.response_mode,
            results=results,
        )


class YouComAdapter(VendorAdapter):
    name = "youcom"
    response_mode = ResponseMode.RANKED_RESULTS
    cost_per_query_usd = 0.005

    async def _request(self, client: httpx.AsyncClient, query: str) -> dict[str, Any]:
        # api.ydc-index.io is dead — 403s on every path regardless of auth.
        r = await client.get(
            "https://api.you.com/v1/search",
            headers={"X-API-Key": self._api_key},
            params={"query": query},
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def _parse(self, payload: dict[str, Any], query_id: str) -> SearchResponse:
        web = (payload.get("results") or {}).get("web", [])
        results = [
            SearchResult(
                url=item.get("url", ""),
                rank=i,
                title=item.get("title"),
                snippet=item.get("description"),  # `description`, not `snippet`
                published_at=item.get("page_age"),
            )
            for i, item in enumerate(web[:TOP_K])
        ]
        return SearchResponse(
            vendor=self.name,
            query_id=query_id,
            response_mode=self.response_mode,
            results=results,
        )


class PerplexityAdapter(VendorAdapter):
    name = "perplexity"
    # BOTH, not SYNTHESIZED_ANSWER: Sonar returns `search_results` with URLs,
    # titles, snippets and dates alongside the prose. That means it can be
    # scored on the same ranked-list footing as the other four *and* on answer
    # quality separately — the like-for-like comparison is fairer than
    # docs/04 assumes.
    response_mode = ResponseMode.BOTH
    cost_per_query_usd = 0.008
    model = "sonar"  # NOT sonar-deep-research: 10-30x cost, different product

    async def _request(self, client: httpx.AsyncClient, query: str) -> dict[str, Any]:
        r = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": query}],
                # Was 512, which the harness imposed and the vendor did not:
                # 10 of 150 responses came back with finish_reason "length", 8
                # of them at exactly 512 tokens, and those 10 scored a median
                # 8.44 against 8.90 for the rest. A cap this benchmark chose was
                # costing one vendor half a point on the responses it cut.
                "max_tokens": 2048,
            },
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def _parse(self, payload: dict[str, Any], query_id: str) -> SearchResponse:
        choices = payload.get("choices") or []
        answer = None
        if choices:
            answer = (choices[0].get("message") or {}).get("content")

        results = [
            SearchResult(
                url=item.get("url", ""),
                rank=i,
                title=item.get("title"),
                snippet=item.get("snippet"),
                published_at=item.get("last_updated") or item.get("date"),
            )
            for i, item in enumerate(payload.get("search_results", [])[:TOP_K])
        ]

        response = SearchResponse(
            vendor=self.name,
            query_id=query_id,
            response_mode=self.response_mode,
            results=results,
            answer=answer,
            citations=list(payload.get("citations") or [])[:TOP_K],
        )
        reported = ((payload.get("usage") or {}).get("cost") or {}).get("total_cost")
        if reported is not None:
            response.cost_usd = float(reported)
            response.cost_source = "reported"
        return response


# Env var per adapter. The registry is the single place the cleared vendor set
# is defined — adding a key here is the act of adding a vendor to the public
# benchmark, so it is the line to guard.
REGISTRY: dict[str, tuple[type[VendorAdapter], str]] = {
    "serper": (SerperAdapter, "SERPER_API_KEY"),
    "exa": (ExaAdapter, "EXA_API_KEY"),
    "linkup": (LinkupAdapter, "LINKUP_API_KEY"),
    "youcom": (YouComAdapter, "YOUCOM_API_KEY"),
    "perplexity": (PerplexityAdapter, "PERPLEXITY_API_KEY"),
}


def build_all(env: dict[str, str]) -> list[VendorAdapter]:
    """Instantiate every cleared vendor whose key is present."""
    adapters: list[VendorAdapter] = []
    for name, (cls, env_var) in REGISTRY.items():
        key = (env.get(env_var) or "").strip()
        if key:
            adapters.append(cls(api_key=key))
    return adapters
