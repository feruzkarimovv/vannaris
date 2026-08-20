# 16 — Is the saturation the rubric or the queries? (2026-08-17)

## The question

The published table is bunched against its ceiling. `2026-W34`'s cell median is 8.78, 36.7% of cells score ≥9, and only one of four adjacent vendor pairs separates at 95%. `AUDIT-2026-08-13.md` §4 calls this the difference between a benchmark and a participation trophy, and `PLAN-2026-08-13.md` E4 proposes a hard query set (taxonomy v3) as the fix — days of authoring work.

That prescription assumes a cause nobody had tested. Two very different mechanisms produce the same bunching:

1. **The queries are too easy.** Every vendor genuinely does well, and the scores are correct.
2. **The rubric is lenient.** The current prompt says only *"Score each dimension from 0 to 10"* with no anchoring of what a 7 or a 9 means, and LLM judges default to the top of an unanchored scale regardless of what they are grading.

If (2) were the binding constraint, writing 150 harder questions would be the wrong work: the new questions would saturate too.

## Method

The two arms differ in exactly one thing. The strict arm inserts an anchored scale at the point where the control says "Score each dimension from 0 to 10" — explicit definitions for each band, the instruction that competent work belongs mid-scale, and the statement that 9–10 is a claim you could not describe an improvement. Every other word is byte-identical, including the `TODAY'S DATE IS` preamble and the length-normalisation clause. The insertion point is asserted in code, so a future edit that moves it fails loudly rather than silently testing nothing.

Both arms ran on **2026-08-17**, against the same pinned judge models, at the same temperature, over the **same 300 stored responses**: 60 queries (10 per category, stratified, seeded) × 5 vendors from run `50fbea16` (`2026-W31`). Paired by query, because the comparison that matters is a paired one.

Two design points worth stating:

- **The control arm was re-run rather than read from the database.** The stored `2026-W31` scores predate the temperature-0 pinning and are four judge-model-weeks old. Reading them would have confounded the rubric change with a settings change and possible model drift.
- **`2026-W31` is the only week this experiment could use.** Raw vendor responses live only in `data/vannaris.db`, which is gitignored; CI runs on a fresh database and destroys them on exit, and `responses-*.csv` publishes metadata, not result text. `2026-W33` and `2026-W34` cannot be re-judged, ever.

No vendor calls, no vendor spend. 1,800 judge calls, zero judge failures.

Reproduce with `experiments/rubric_experiment.py` then `experiments/rubric_analysis.py`.

## Result

| | control | strict |
|---|---|---|
| cell median | 9.00 | **9.00** |
| cell mean | 8.63 | 8.37 |
| spread (sd) | 1.51 | **1.51** |
| ≥9 | 69.0% | 56.3% |
| ≥8 | 89.0% | 83.3% |
| ≤6 | 6.0% | 9.3% |
| adjacent pairs separated | 1/4 | **1/4** |
| all pairs separated | 6/10 | **6/10** |
| ranking | exa, perplexity, serper, youcom, linkup | **identical** |

The strict rubric moved the *level* and nothing else. Mean fell 0.26 points and the share scoring ≥9 fell 12.7 points, so the anchors were read and acted on — this is not a null result from an ignored instruction. But the median did not move, the standard deviation did not move (1.51 → 1.51), the ranking is identical, and **the same pairs separate and the same pairs do not**. The one adjacent pair that separates under the control rubric (Perplexity vs Serper) separates under the strict one; the three that overlap still overlap.

A monotone downward shift carries no additional information. Every vendor lost roughly the same amount.

One incidental finding: the judges did not respond equally. OpenAI moved −0.49, Google −0.26, Anthropic −0.09. The families most generous under the unanchored scale were the ones the anchors disciplined most, which is the expected direction and mild evidence the intervention worked as designed.

## Verdict

**The rubric is not the binding constraint. The queries are.** `PLAN-2026-08-13.md` E4 stands as written, and the case for it is now measured rather than assumed.

## What this does not establish

It tests **one** strict variant. A stronger intervention was not tried and is not ruled out — in particular, anything that forces a comparative judgement rather than an absolute one (best-possible-response anchoring, forced ranking within a query, pairwise scoring) attacks the ceiling differently, and `docs/04` already rejects pairwise for the main loop on cost grounds rather than on discrimination grounds. If taxonomy v3 lands and the hard tier saturates too, that is the next thing to test, not more anchoring.

It also runs on 60 queries from one week. The per-pair standard errors here (0.14–0.24) are wider than the published run's (0.086 at n=146), so this experiment could not have detected a *small* separation gain. It rules out a large one, which is what the decision needed.
