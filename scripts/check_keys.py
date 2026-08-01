#!/usr/bin/env python3
"""Verify every API key in .env with one cheap live call each.

Run this before the first full benchmark run. Debugging five vendor auth
schemes inside a 1,700-call pipeline is miserable; debugging them here is not.

    python scripts/check_keys.py
    python scripts/check_keys.py --require-all   # a missing key is a failure

Each vendor gets one trivial query. Total cost is a fraction of a cent, and it
confirms the thing that actually matters: the key is valid, the endpoint shape
is right, and we can parse what comes back.

`--require-all` is what the weekly workflow runs. Locally an unset key means
"not working on that vendor today"; under the scheduler it means the run would
quietly publish a week with a vendor missing from the table, which is worth
sixty seconds and a fraction of a cent to catch up front.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

PROBE = "what is the capital of France"
TIMEOUT = 30.0

OK, FAIL, SKIP = "\033[32m  ok\033[0m", "\033[31mfail\033[0m", "\033[33mskip\033[0m"


async def check_serper(c: httpx.AsyncClient, key: str) -> str:
    r = await c.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        json={"q": PROBE},
    )
    r.raise_for_status()
    return f"{len(r.json().get('organic', []))} organic results"


async def check_exa(c: httpx.AsyncClient, key: str) -> str:
    r = await c.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": key, "Content-Type": "application/json"},
        json={"query": PROBE, "numResults": 3, "contents": {"text": False}},
    )
    r.raise_for_status()
    return f"{len(r.json().get('results', []))} results"


async def check_linkup(c: httpx.AsyncClient, key: str) -> str:
    r = await c.post(
        "https://api.linkup.so/v1/search",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"q": PROBE, "depth": "standard", "outputType": "searchResults"},
    )
    r.raise_for_status()
    return f"{len(r.json().get('results', []))} results"


async def check_youcom(c: httpx.AsyncClient, key: str) -> str:
    # Host note: api.ydc-index.io is dead — it 403s on every path regardless of
    # auth header. api.you.com/v1/search is the live endpoint, and results nest
    # under results.web rather than a flat `hits` array.
    r = await c.get(
        "https://api.you.com/v1/search",
        headers={"X-API-Key": key},
        params={"query": PROBE},
    )
    r.raise_for_status()
    web = r.json().get("results", {}).get("web", [])
    return f"{len(web)} web results"


async def check_perplexity(c: httpx.AsyncClient, key: str) -> str:
    r = await c.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": PROBE}],
            "max_tokens": 32,
        },
    )
    r.raise_for_status()
    body = r.json()
    n_cites = len(body.get("citations", []) or body.get("search_results", []))
    return f"answer + {n_cites} citations"


async def check_anthropic(c: httpx.AsyncClient, key: str) -> str:
    r = await c.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "Reply with: ok"}],
        },
    )
    r.raise_for_status()
    return r.json()["model"]


async def check_openai(c: httpx.AsyncClient, key: str) -> str:
    r = await c.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return f"{len(r.json().get('data', []))} models visible"


async def check_google(c: httpx.AsyncClient, key: str) -> str:
    r = await c.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": key},
    )
    r.raise_for_status()
    return f"{len(r.json().get('models', []))} models visible"


CHECKS = [
    ("vendor", "SERPER_API_KEY", check_serper),
    ("vendor", "EXA_API_KEY", check_exa),
    ("vendor", "LINKUP_API_KEY", check_linkup),
    ("vendor", "YOUCOM_API_KEY", check_youcom),
    ("vendor", "PERPLEXITY_API_KEY", check_perplexity),
    ("judge", "ANTHROPIC_API_KEY", check_anthropic),
    ("judge", "OPENAI_API_KEY", check_openai),
    ("judge", "GOOGLE_API_KEY", check_google),
]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--require-all", action="store_true",
                    help="treat an unset key as a failure (used by the weekly workflow)")
    args = ap.parse_args()

    load_dotenv()
    failures, skipped = 0, 0

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for kind, env_var, check in CHECKS:
            label = env_var.removesuffix("_API_KEY").lower()
            key = os.getenv(env_var, "").strip()

            if not key:
                print(f"  {SKIP}  {label:<12} {kind:<7} {env_var} not set")
                skipped += 1
                continue

            try:
                detail = await check(client, key)
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:120].replace("\n", " ")
                print(f"  {FAIL}  {label:<12} {kind:<7} HTTP {exc.response.status_code} — {body}")
                failures += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  {FAIL}  {label:<12} {kind:<7} {type(exc).__name__}: {exc}")
                failures += 1
            else:
                print(f"  {OK}  {label:<12} {kind:<7} {detail}")

    print()
    if failures:
        print(f"{failures} key(s) failed. Fix these before the first run.")
    if skipped:
        print(f"{skipped} key(s) not set yet."
              + (" --require-all: that is a failure." if args.require_all else ""))
    if not failures and not skipped:
        print(f"All {len(CHECKS)} keys live. Ready for the benchmark run.")
    return 1 if failures or (skipped and args.require_all) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
