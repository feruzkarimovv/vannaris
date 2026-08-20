# 18 — Does comparative judging separate what pointwise judging cannot? (2026-08-21)

## The question

Two attempts to fix the saturation have failed. `docs/16` showed a strict anchored rubric moves the mean and separates nothing; `docs/17` showed 240 authored hard-tier queries land at median 8.50 against a target of 6.00. Both changed *what* is scored, or *how generously*. Neither changed the **protocol**.

`docs/04` chose pointwise rubric scoring over pairwise comparison, and it chose on cost — "a 4x cost multiplier" at 8–9 vendors — not on discrimination. That left the obvious lever untested while the instrument's problems compounded: `2026-W34` ties 74.0% of queries, cannot separate its own top two (exa − perplexity = +0.014, se 0.086), and inverts its ranking when either Anthropic or OpenAI is dropped from the panel.

One number said the lever was worth pulling. On the 50 pairs the absolute ensemble scored as **near-ties**, the human labeller still picked a winner on **48 of them (96%)**. The information separating those responses is present in the responses. Pointwise scoring is not extracting it.

## Method

Only the protocol changes. The `TODAY'S DATE IS` preamble, the three dimension definitions, the length-normalisation clause and the 500-character snippet cap are spliced out of `ensemble.RUBRIC` at import and asserted, so an edit to the production rubric breaks the experiment rather than silently comparing two different things. The payload renderer is asserted byte-for-byte against `build_prompt`'s published `scored_chars` for all 750 responses. The question put to the judge is the human labeller's own instruction, verbatim from `src/calibrate_pair_ui.html`.

`today` is pinned to **2026-07-31**, the run's own date, not the execution date. The responses were retrieved then; telling the judge it is three weeks later would score the delay rather than the vendor.

Both arms ran against run `50fbea16` (`2026-W31`) — the only week whose raw vendor responses survive, for the reason `docs/16` records.

- **Arm A — validation.** The exact 280 screens of calibration set `96afde9bfef3`, in the same left/right orientation the human saw, judged comparatively by all three families. Compared against that human's choices. The set's own `swapped` (50) and `repeat` (30) strata measure this judge's position bias and self-consistency under the same design used on the human.
- **Arm B — discrimination.** Exa vs Perplexity on all 150 queries, **both orders**, three families. A preference counts only where both orders agree — `docs/04`'s mandated mitigation. Order-dependent verdicts are discarded, not resolved.

1,740 judge calls. **Arm A: 0 errors, full three-family panel on all 280 screens. Arm B: 10 errors of 900 (1.1%).** No vendor calls and no vendor spend; ~$3.41 of judge tokens.

Reproduce with `experiments/pairwise_experiment.py`.

## Result

### The protocol breaks the tie problem

| | pointwise (published) | comparative |
|---|---|---|
| Tie rate, exa vs perplexity, 150 queries | **74.0%** (W34) | **0.0%** |
| Pairs separated, format held constant (n=160) | — | **160/160 (100%)** [97.7, 100] |
| Near-ties separated (n=50) | 0 by construction | **48 (96%)** [86.5, 98.9] |
| Human's rate on the same 50 | — | 96% |

On the 50 pairs pointwise scoring called near-ties, the comparative ensemble separates at **exactly the human's rate**. The saturation is a property of the pointwise protocol, not of the vendors and not of the queries. That is the opposite of what `docs/16` and `docs/17` left the project believing was achievable.

### It agrees with humans about as well, not better

| | n | concordance | 95% CI |
|---|---|---|---|
| Comparative ensemble | 149 | **86.6%** | [80.2, 91.1] |
| Pointwise ensemble (`docs/12`) | 148 | 79.1% | [71.8, 84.8] |
| — google alone | 149 | 85.2% | [78.7, 90.0] |
| — openai alone | 150 | 82.0% | [75.1, 87.3] |
| — anthropic alone | 147 | 81.6% | [74.6, 87.1] |

The intervals overlap. **This is not a demonstrated improvement in accuracy** and must not be published as one. The gain is in resolution, not in correctness. No single family carries the result.

### It has position bias the human did not

| | judge | human |
|---|---|---|
| Position bias (swapped stratum, n=49) | **12.2%** [5.7, 24.2] | 0.0% |
| Self-agreement (repeat stratum, n=30) | 100% [88.7, 100] | 100% |

Running both orders is therefore **mandatory, not optional**. In Arm B it discarded 22 of 150 queries as order-dependent. A comparative board that judged one order would be publishing its own screen layout.

### Arm B's headline is confounded and must not be published as a quality finding

Exa vs Perplexity, both orders agreeing: **Perplexity 104, Exa 21**, 0 ties, 22 order-dependent, 3 unresolved. Perplexity takes 83.2% of decided queries, CI on Exa's share [11.3, 24.3] — separated, and in the opposite direction to the published pointwise ranking, which put Exa first in W31 (+0.278, se 0.130).

It cannot be read as retrieval quality, for one structural reason:

| vendor | responses carrying a synthesized answer |
|---|---|
| perplexity | **150 / 150** |
| exa, linkup, serper, youcom | **0 / 150** |

Perplexity is the only vendor in the cleared set that returns prose. So "Perplexity vs anyone" is *perfectly* confounded with response format, and there is no subset of Arm B in which the confound is absent. Both raters show a large format preference on pairs where exactly one side returns an answer:

| chooses the answer-returning side | rate | 95% CI |
|---|---|---|
| the comparative judge | 93.2% (109/117) | [87.1, 96.5] |
| **the human** | **87.8%** (101/115) | [80.6, 92.6] |

The intervals overlap. **The judge is not doing something the human does not do.** That makes this a question about what the benchmark should measure rather than a judging defect — but a comparative board published without addressing it would rank Perplexity first for reasons substantially about response shape.

Two things cut against the pure-format reading and are recorded because they are the honest counterweight: on the 16 exa-vs-perplexity pairs in the human set the human independently preferred Perplexity 10–6, the same direction as the judge's 12–4; and the one category Exa wins is `breaking_news`, 13–5, where links beat prose.

Crucially, the discrimination result does **not** rest on the confound. Restricted to the 160 pairs where both sides return an answer or neither does, the judge still separates 160/160, and still agrees with the human 81.2% [74.5, 86.5] — consistent with its overall rate.

## What this changes

1. **The saturation is fixable, and the fix is the protocol.** Neither a harder rubric nor harder queries was the answer. This is the first intervention of the three that produced separation.
2. **`docs/04`'s pointwise choice should be revisited on discrimination, not only on cost.** It was decided before there was any evidence about what pointwise scoring could resolve, and the cost multiplier it cites is real — Arm B alone was 900 calls for one vendor pair.
3. **Nothing here licenses a published comparative ranking yet.** Position bias requires both orders; the format confound is unresolved; and the accuracy gain over pointwise is not demonstrated. Any comparative table must carry all three.
4. **The format confound is a methodology question for the founder, not an agent.** Whether a benchmark of *search retrieval* should reward a synthesized answer at all — and if so, whether vendors that return prose belong in the same column as vendors that return links — is a scoping decision `docs/04` never faced, because pointwise scoring hid it.

## What was not checked

- Whether the confound reverses if Perplexity's answer block is stripped before judging. That is the single cheapest next experiment and it was not run.
- Any vendor pair other than exa/perplexity in Arm B.
- Whether the 86.6% holds on a second human labeller. There is one, and `docs/12` is explicit about what a single labeller can establish.
- Cost at full scale. Pairwise is quadratic in vendors: five vendors is 10 pairs × 2 orders × 3 families = 60 calls per query against pointwise's 15.
