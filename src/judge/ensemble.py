"""Three-judge cross-family ensemble.

Why three families and not one good model: a quantitative study on 33,000
human-labelled Chatbot Arena comparisons found self-preference bias is real and
is driven by a preference for low-perplexity, "model-like" text — not literal
self-recognition. It therefore fires even on text the judge did not write, as
long as it reads like the judge's own house style. Since vendor answer
synthesis is itself often GPT/Claude/Gemini-class output, a single judge is
structurally unsafe here (docs/04).

Judge versions are pinned, not floating. A silent provider-side model update
would change scores without changing anything about the vendors, which would
quietly invalidate every week-over-week comparison the benchmark exists to
make. The exact model string is stored on every score row so a change is
visible in the data rather than inferred.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from ..vendors.base import ResponseMode, SearchResponse

# Pinned. Bumping any of these is a methodology change and belongs in the
# published changelog, not a silent commit.
JUDGES: list[tuple[str, str]] = [
    ("anthropic", "claude-haiku-4-5"),
    ("openai", "gpt-5.4-mini-2026-03-17"),
    # NOT gemini-2.5-flash, which docs/04 recommends: it still appears in the
    # /models listing but 404s on generateContent with "no longer available to
    # new users". The listing endpoint is not an availability signal — verify a
    # judge model with a real call before pinning it.
    #
    # 3.1-flash-lite, NOT 3.5-flash. 3.5 passed a 4-call probe with a short
    # prompt and then truncated its JSON on 32% of calls under the real judge
    # prompt, which is many times longer. 3.1-flash-lite has held 100/100 under
    # real load. Lesson worth keeping: validate a judge model against a
    # production-length prompt, never a toy one. Revisit only with evidence from
    # a full run, and validate against the human-labelled gold set per docs/04.
    ("google", "gemini-3.1-flash-lite"),
]

# Sampling is pinned as well as the model. Pinning a model version buys nothing
# for reproducibility if the call is still a temperature-1 sample: across the two
# runs in the first week's database, on 297 (query, vendor) pairs whose vendor
# payload was byte-identical, the ensemble median came out the same only 69.4% of
# the time — Google alone agreed with itself 55.2%. Every judge call now runs at
# temperature 0, and OpenAI, which exposes one, gets a fixed seed.
#
# The number itself is arbitrary and only has to stay constant; changing it is a
# methodology change like any other.
JUDGE_SEED = 20260731

# How much of each snippet the judge sees. Must be at least the largest amount
# any adapter asks a vendor for, or the cap becomes a per-vendor handicap rather
# than a normalisation: at 400 it discarded 19.8% of Exa's text and 19.6% of
# Linkup's while never binding on Serper, You.com or Perplexity, which return
# shorter snippets. Vendors are already normalised to the same result count
# (adapters.TOP_K); this is the same idea applied to snippet length.
SNIPPET_CHARS = 500

RUBRIC = """You are grading how well a web-search API answered a query. You are \
grading the SEARCH RESULTS, not writing an answer yourself.

TODAY'S DATE IS {today}. This is later than your training cutoff. Results \
describing events, versions or people you do not recognise, and results dated \
after your cutoff, are the expected output of a working search engine — they \
are NOT evidence of fabrication, error or a corrupted result set. Do not \
penalise a result for being newer than your knowledge. If you cannot verify a \
current fact from your own memory, judge whether the RESULTS are internally \
consistent, recent, and from sources that would know.

Query: {query}
{gold_block}
The API returned {n_results} result(s){answer_note}.

{payload}

Score each dimension from 0 to 10.

relevance — Do the returned results actually address the query? Judge whether a \
competent person could answer the query from these results. Reward results that \
directly answer it; penalise topically-adjacent filler.

freshness — Are these results current enough for this specific query? Some \
queries are timeless and any date is fine: score those high unless results are \
actively outdated. Version-specific technical queries need current sources. \
IMPORTANT: many vendors return no date metadata at all. Judge freshness from the \
CONTENT, and do not penalise a result merely for having no date attached — doing \
so would score the vendor's metadata format rather than its retrieval quality.

citation_quality — Are the sources authoritative and appropriate? Official docs, \
primary sources and reputable publications rank above content farms, SEO spam \
and scraped aggregators.

overall — Holistic judgement of whether this response serves the user well.

LENGTH NORMALISATION: judge substance, not volume. A response with three \
excellent results must not score below one with ten mediocre ones. Longer \
snippets are not better snippets. Do not reward verbosity.

Return ONLY a JSON object, no prose, no markdown fence:
{{"relevance": <0-10>, "freshness": <0-10>, "citation_quality": <0-10>, \
"overall": <0-10>, "rationale": "<one short sentence, max 25 words>"}}"""


@dataclass
class JudgeScore:
    judge_family: str
    judge_model: str
    relevance: float | None = None
    freshness: float | None = None
    citation_quality: float | None = None
    overall: float | None = None
    rationale: str | None = None
    scored_chars: int = 0
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    # What the provider actually served, as opposed to what was asked for. Two
    # of the three pins are aliases that a provider can repoint without notice,
    # and a silent model swap would move every score without moving anything
    # about the vendors. Recorded per row so it is visible in the data.
    judge_model_returned: str | None = None
    error: str | None = None


def build_prompt(response: SearchResponse, query_text: str, gold: str | None,
                 today: str) -> tuple[str, int]:
    """Render the rubric for one vendor response. Returns (prompt, scored_chars).

    scored_chars is the size of the vendor payload the judge saw — published
    alongside scores so verbosity outliers are visible to anyone auditing.

    `today` is interpolated because omitting it was not neutral. On the first
    run the Anthropic judge read post-cutoff dates in breaking-news payloads as
    evidence of fabrication and collapsed the score while its own rationale
    credited the results with answering the query: 20.0% of its breaking_news
    rationales carried fabrication language against OpenAI's 1.6%, and its mean
    in that category was 6.664 against 8.869 and 9.072. Freshness is the column
    that behaviour most distorts, and it distorts it against vendors returning
    genuinely current information — the opposite of what the column measures.
    """
    lines: list[str] = []

    if response.answer:
        lines.append("SYNTHESIZED ANSWER:")
        lines.append(response.answer.strip())
        lines.append("")

    if response.results:
        lines.append("RESULTS:")
        for r in response.results:
            date = f" [{r.published_at}]" if r.published_at else ""
            title = r.title or "(no title)"
            lines.append(f"{r.rank + 1}. {title}{date}")
            lines.append(f"   {r.url}")
            if r.snippet:
                lines.append(f"   {r.snippet.strip()[:SNIPPET_CHARS]}")

    payload = "\n".join(lines) if lines else "(the API returned nothing)"

    # No shape hint. This used to append " plus a synthesized prose answer" for
    # the vendors that return prose and nothing for the rest, which told the
    # judge which vendor it was looking at for exactly one vendor in the set —
    # a blinding hole that no amount of rubric wording compensates for. The
    # answer is already visible in the payload under its own heading; naming it
    # in the preamble added nothing except the tell.
    answer_note = ""

    gold_block = f"Known correct answer (for your reference): {gold}\n" if gold else ""

    prompt = RUBRIC.format(
        today=today,
        query=query_text,
        gold_block=gold_block,
        n_results=len(response.results),
        answer_note=answer_note,
        payload=payload,
    )
    return prompt, len(payload)


_NUM_FIELDS = ("relevance", "freshness", "citation_quality", "overall")


def _extract(text: str) -> dict[str, Any]:
    """Pull the scores out of a judge reply, tolerating truncation.

    Judges truncate mid-`rationale` often enough to matter — a full 32% of
    Google calls in the 150-query run — and the earlier strict parser discarded
    those replies wholesale. But the numeric scores are emitted *before* the
    rationale and were complete in essentially every truncated case. Throwing
    away four valid scores because an optional prose field got cut is the
    expensive kind of correctness: it silently shrinks the sample, and it does
    so non-randomly (longer vendor payloads truncate more), which biases the
    result rather than merely thinning it.

    So: try strict JSON first, and fall back to field-wise salvage. A salvaged
    reply keeps its scores and loses only its rationale.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass  # fall through to salvage

    salvaged: dict[str, Any] = {}
    for field in _NUM_FIELDS:
        m = re.search(rf'"{field}"\s*:\s*(-?\d+(?:\.\d+)?)', text)
        if m:
            salvaged[field] = float(m.group(1))
    if not salvaged:
        raise ValueError(f"no scores in judge reply: {text[:160]!r}")

    m = re.search(r'"rationale"\s*:\s*"([^"]*)', text)
    if m:
        salvaged["rationale"] = m.group(1).strip() or None
    salvaged["_salvaged"] = True
    return salvaged


async def _call_anthropic(c: httpx.AsyncClient, key: str, model: str, prompt: str) -> tuple[dict, int, int]:
    r = await c.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": 400, "temperature": 0,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=90.0,
    )
    r.raise_for_status()
    b = r.json()
    text = "".join(blk.get("text", "") for blk in b.get("content", []) if blk.get("type") == "text")
    u = b.get("usage", {})
    return (_extract(text), u.get("input_tokens", 0), u.get("output_tokens", 0),
            b.get("model"))


async def _call_openai(c: httpx.AsyncClient, key: str, model: str, prompt: str) -> tuple[dict, int, int]:
    r = await c.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "seed": JUDGE_SEED,
        },
        timeout=90.0,
    )
    r.raise_for_status()
    b = r.json()
    text = b["choices"][0]["message"]["content"]
    u = b.get("usage", {})
    return (_extract(text), u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
            b.get("model"))


async def _call_google(c: httpx.AsyncClient, key: str, model: str, prompt: str) -> tuple[dict, int, int]:
    r = await c.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 2048,
                "temperature": 0,
                # Gemini 3.x thinks by default and the thinking spends the same
                # output budget as the answer — which silently truncated the
                # JSON mid-string rather than erroring. A judge returning a
                # rubric score has nothing to gain from chain-of-thought here.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        },
        timeout=90.0,
    )
    r.raise_for_status()
    b = r.json()
    text = b["candidates"][0]["content"]["parts"][0]["text"]
    u = b.get("usageMetadata", {})
    return (_extract(text), u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0),
            b.get("modelVersion"))


_DISPATCH = {"anthropic": _call_anthropic, "openai": _call_openai, "google": _call_google}

# Rate limits are the normal case, not the exception: Google's free tier allows
# 5 requests/minute, and every provider throttles under burst. A judge call
# dropped to a 429 is a hole in a published score, so retry rather than lose it.
MAX_RETRIES = 4


def _retry_after(exc: httpx.HTTPStatusError, attempt: int) -> float | None:
    """Seconds to wait, or None if this error is not worth retrying."""
    status = exc.response.status_code
    if status not in (429, 500, 502, 503, 529):
        return None
    header = exc.response.headers.get("retry-after")
    if header:
        try:
            return min(float(header), 70.0)
        except ValueError:
            pass
    # Google embeds the delay in the message body rather than a header.
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", exc.response.text)
    if match:
        return min(float(match.group(1)) + 1.0, 70.0)
    return min(2.0**attempt, 30.0)


async def _call_with_retry(family: str, client, key: str, model: str, prompt: str):
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await _DISPATCH[family](client, key, model, prompt)
        except httpx.HTTPStatusError as exc:
            delay = _retry_after(exc, attempt)
            if delay is None or attempt == MAX_RETRIES - 1:
                raise
            last = exc
            await asyncio.sleep(delay)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            last = exc
            await asyncio.sleep(min(2.0**attempt, 30.0))
    raise last  # unreachable, but keeps the type checker honest


async def score_one(
    client: httpx.AsyncClient,
    keys: dict[str, str],
    family: str,
    model: str,
    prompt: str,
    scored_chars: int,
) -> JudgeScore:
    score = JudgeScore(judge_family=family, judge_model=model, scored_chars=scored_chars)
    try:
        data, pt, ot, served = await _call_with_retry(family, client, keys[family], model, prompt)
    except Exception as exc:  # noqa: BLE001 — a judge failing is data, not a crash
        score.error = f"{type(exc).__name__}: {exc}"[:300]
        return score

    def num(field: str) -> float | None:
        v = data.get(field)
        if isinstance(v, (int, float)):
            return max(0.0, min(10.0, float(v)))
        return None

    score.relevance = num("relevance")
    score.freshness = num("freshness")
    score.citation_quality = num("citation_quality")
    score.overall = num("overall")
    score.rationale = str(data.get("rationale", ""))[:500] or None
    score.prompt_tokens, score.output_tokens = pt, ot
    score.judge_model_returned = served
    return score


async def score_response(
    client: httpx.AsyncClient,
    keys: dict[str, str],
    response: SearchResponse,
    query_text: str,
    gold: str | None,
    today: str,
) -> list[JudgeScore]:
    """Run all three judges concurrently over one vendor response."""
    prompt, chars = build_prompt(response, query_text, gold, today)
    return list(
        await asyncio.gather(
            *(score_one(client, keys, fam, mdl, prompt, chars) for fam, mdl in JUDGES)
        )
    )


def median_overall(scores: list[JudgeScore], *, require_full: bool = True) -> float | None:
    """Median, not mean — one outlier judge must not move a published number.

    `require_full` guards a subtle bias: if a judge is missing on some rows but
    not others (rate limits cluster in time, they are not randomly distributed),
    then a 3-way median and a 2-way mean end up side by side in the same
    published column, computed by different methods. Rows without the complete
    ensemble are dropped rather than silently degraded — a missing datapoint is
    honest, a differently-computed one is not.
    """
    vals = sorted(s.overall for s in scores if s.overall is not None)
    if not vals:
        return None
    if require_full and len(vals) < len(JUDGES):
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
