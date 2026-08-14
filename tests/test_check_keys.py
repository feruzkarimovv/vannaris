"""The preflight has to fail where the run would fail, not somewhere cheaper.

On 2026-08-10 the OpenAI account went to a negative balance, `check_keys.py`
passed, and the run died fifteen minutes and $3.38 later. That hole was closed
by probing the pinned judge *model* with a real call instead of a listing. This
closes the other half of it: the probe now sends the same *parameters* as the
real judge call, so a provider that stops accepting `seed`, `temperature`,
`response_format` or a zero thinking budget is caught for a fraction of a cent
rather than after forty minutes of vendor spend.

The assertion that matters is the last one. Adding the parameters once is worth
little — the failure mode is drift, where someone changes the real call and
leaves the probe behind, which is exactly how the two got out of step in the
first place. So the two request bodies are compared field by field, and only
the token budget and the prompt are allowed to differ.

Nothing here touches the network: both call paths are driven through a stub that
records what was sent.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import httpx  # noqa: E402

import check_keys  # noqa: E402
from src.judge.ensemble import (  # noqa: E402
    _call_anthropic,
    _call_google,
    _call_openai,
)

# A judge reply that `_extract` accepts, so the real call paths run to the end
# and any body they send is the body they would send in production.
SCORES = ('{"relevance": 8, "freshness": 8, "citation_quality": 8, '
          '"overall": 8, "rationale": "fine"}')

REPLY = {
    "anthropic": {"content": [{"type": "text", "text": SCORES}],
                  "usage": {"input_tokens": 1, "output_tokens": 1}, "model": "m"},
    "openai": {"choices": [{"message": {"content": SCORES}}],
               "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "model": "m"},
    "google": {"candidates": [{"content": {"parts": [{"text": SCORES}]}}],
               "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
               "modelVersion": "m"},
}

REAL = {"anthropic": _call_anthropic, "openai": _call_openai, "google": _call_google}
PROBE = {"anthropic": check_keys.check_anthropic,
         "openai": check_keys.check_openai,
         "google": check_keys.check_google}

# The two differences the probe is allowed to have. Both are downward: this is
# meant to cost a fraction of a cent, and it is not scoring anything.
BUDGET = {"max_tokens", "max_completion_tokens", "generationConfig.maxOutputTokens"}
PROMPT = ("messages", "contents")


class Recorder:
    """Stands in for httpx.AsyncClient and remembers what was sent."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.url: str | None = None
        self.body: dict | None = None

    async def post(self, url, *, headers=None, json=None, **kw):
        self.url, self.body = url, json
        return httpx.Response(200, json=self._payload,
                              request=httpx.Request("POST", url))


def params(body: dict) -> dict:
    """Flatten a request body to {path: value}, dropping the prompt itself.

    Nested, because Google puts every parameter that matters inside
    `generationConfig` and a comparison of top-level keys would see none of them.
    """
    out: dict = {}

    def walk(d: dict, prefix: str = "") -> None:
        for k, v in d.items():
            path = prefix + k
            if path in PROMPT:
                continue
            if isinstance(v, dict):
                walk(v, path + ".")
            else:
                out[path] = v

    walk(body)
    return out


def sent(family: str, which: dict) -> tuple[str, dict]:
    """Run one call path against the stub and return (url, body)."""
    rec = Recorder(REPLY[family])
    model = check_keys.JUDGE_MODEL[family]
    if which is REAL:
        asyncio.run(REAL[family](rec, "k", model, "the rubric goes here"))
    else:
        asyncio.run(PROBE[family](rec, "k"))
    return rec.url, rec.body


class TestProbeShape(unittest.TestCase):
    def test_the_probe_names_json_because_openai_requires_it(self):
        # `response_format: json_object` is rejected outright unless the word
        # appears in the messages, so a probe without it fails against a key
        # that is in perfect health.
        self.assertIn("json", check_keys.JUDGE_PROBE.lower())

    def test_the_probe_stays_cheap(self):
        self.assertLessEqual(check_keys.PROBE_TOKENS, 64)

    def test_every_judge_is_probed_with_the_pinned_model(self):
        for family in REAL:
            _, body = sent(family, PROBE)
            blob = str(body) + (sent(family, PROBE)[0])
            self.assertIn(check_keys.JUDGE_MODEL[family], blob,
                          f"{family}: the probe does not name the pinned model")


class TestProbeMatchesTheRealCall(unittest.TestCase):
    """The drift gate. This is the point of the file."""

    def test_the_probe_hits_the_same_endpoint(self):
        for family in REAL:
            self.assertEqual(sent(family, PROBE)[0], sent(family, REAL)[0],
                             f"{family}: preflight calls a different endpoint")

    def test_the_probe_sends_every_parameter_the_real_call_sends(self):
        for family in REAL:
            real = params(sent(family, REAL)[1])
            probe = params(sent(family, PROBE)[1])
            missing = sorted(set(real) - set(probe))
            self.assertEqual(missing, [], f"{family}: preflight omits {missing} — a "
                                          f"model that rejects one would pass this "
                                          f"check and fail every judgement")

    def test_the_shared_parameters_carry_the_same_values(self):
        for family in REAL:
            real = params(sent(family, REAL)[1])
            probe = params(sent(family, PROBE)[1])
            for path, value in real.items():
                if path in BUDGET:
                    continue
                self.assertEqual(probe[path], value,
                                 f"{family}: preflight sends {path}={probe[path]!r}, "
                                 f"the run sends {value!r}")

    def test_the_gate_would_notice_a_dropped_parameter(self):
        # A gate that has only ever been observed passing is indistinguishable
        # from one that always passes (tests/test_check_vendors.py makes the
        # same argument). Drop `seed` from a copy of the probe body and confirm
        # the comparison catches it.
        real = params(sent("openai", REAL)[1])
        probe = params(sent("openai", PROBE)[1])
        self.assertIn("seed", real)
        probe.pop("seed")
        self.assertEqual(sorted(set(real) - set(probe)), ["seed"])


if __name__ == "__main__":
    unittest.main()
