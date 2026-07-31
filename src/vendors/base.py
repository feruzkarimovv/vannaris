"""Vendor adapter interface.

The central design problem this file solves: vendors in the v1 set return two
different shapes of thing. Serper, Exa, You.com and Linkup return a *ranked list
of results*. Perplexity Sonar returns a *synthesized answer* plus citations.
Scoring both against one rubric without acknowledging the difference is the
single easiest way for a vendor to dismiss the benchmark as unfair.

So every adapter normalizes into the same envelope, and records which shape it
actually produced. The judge then scores the shapes it was given rather than
pretending they are the same, and `response_mode` is published alongside every
score so the asymmetry is visible to anyone reading the methodology.

Adapters are also the only place vendor-specific request logic lives. Everything
downstream — runner, judge, storage — sees `SearchResponse` and nothing else.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx


class ResponseMode(str, Enum):
    """What kind of thing the vendor actually returned.

    Recorded per response, not per vendor: some vendors can return either shape
    depending on endpoint or query, and the benchmark should reflect what
    happened on this call rather than what the vendor usually does.
    """

    RANKED_RESULTS = "ranked_results"  # a SERP-like list; no synthesis
    SYNTHESIZED_ANSWER = "synthesized_answer"  # prose answer, citations attached
    BOTH = "both"  # answer *and* an independently useful result list


@dataclass(frozen=True)
class SearchResult:
    """One retrieved document. `rank` is 0-indexed, in vendor-returned order."""

    url: str
    rank: int
    title: str | None = None
    snippet: str | None = None
    published_at: str | None = None  # ISO-8601 when the vendor supplies it


@dataclass
class SearchResponse:
    """Normalized result of one (query, vendor) call.

    `raw` holds the untouched vendor payload. It is written to the raw storage
    layer for reproducibility and is deliberately *not* part of the public
    export — docs/03 recommends publishing derived scores rather than
    republishing vendor content, and Brave's storage clause is a live example of
    why that distinction matters even for vendors not yet in the set.
    """

    vendor: str
    query_id: str
    response_mode: ResponseMode
    results: list[SearchResult] = field(default_factory=list)
    answer: str | None = None
    citations: list[str] = field(default_factory=list)

    latency_ms: int | None = None
    cost_usd: float | None = None
    # Exa and Perplexity return the true billed cost on every call; the others
    # do not, so their cost is derived from published pricing. Tracking which is
    # which matters because docs/06's unit economics are a projection, and the
    # reported figures are the empirical correction to it.
    cost_source: str = "estimated"  # "reported" | "estimated"
    raw: dict[str, Any] | None = None

    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def result_urls(self) -> list[str]:
        return [r.url for r in self.results]


class VendorAdapter(ABC):
    """Base class for a single search vendor.

    Subclasses implement `_request` (the HTTP call) and `_parse` (payload ->
    normalized envelope). `search` wraps both with timing and error capture so a
    single vendor failing never aborts a weekly run — a failed call is recorded
    as a failed call, which is itself a data point about reliability.
    """

    name: str
    response_mode: ResponseMode
    # Published per-query price, used for the cost column on the dashboard.
    # Sourced from docs/06-business-model.md; re-verify against live pricing
    # pages before publishing, since two of these were flagged as stale there.
    cost_per_query_usd: float

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError(f"{self.name}: missing API key")
        self._api_key = api_key
        self._timeout = timeout

    @abstractmethod
    async def _request(self, client: httpx.AsyncClient, query: str) -> dict[str, Any]:
        """Issue the vendor call and return the decoded JSON payload."""

    @abstractmethod
    def _parse(self, payload: dict[str, Any], query_id: str) -> SearchResponse:
        """Map a vendor payload onto the normalized envelope."""

    async def search(
        self, client: httpx.AsyncClient, query: str, query_id: str
    ) -> SearchResponse:
        started = time.perf_counter()
        try:
            payload = await self._request(client, query)
        except Exception as exc:  # noqa: BLE001 - a failed vendor call is data
            return SearchResponse(
                vendor=self.name,
                query_id=query_id,
                response_mode=self.response_mode,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        response = self._parse(payload, query_id)
        response.latency_ms = latency_ms
        response.raw = payload
        # _parse sets cost_usd itself when the vendor reports a real figure;
        # only fall back to the published estimate when it didn't.
        if response.cost_usd is None:
            response.cost_usd = self.cost_per_query_usd
            response.cost_source = "estimated"
        return response
