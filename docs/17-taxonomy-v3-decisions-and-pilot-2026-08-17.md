# 17 — Taxonomy v3: the decisions, and the pilot that failed its target (2026-08-17)

## Decisions

`PLAN-2026-08-13.md` E4 proposes a hard query tier; `docs/16` established the same day that the saturation is caused by the queries and not the rubric, so the prescription is the right one. Five open questions were settled on 2026-08-17:

1. **Size: +150, 25 per category.** Standard error on a vendor-pair comparison scales as 1/√n. At 150 hard queries se ≈ 0.086, matching the standard tier's power; at 90 it is ≈0.111 and at 60 ≈0.136. `docs/16` ran at n=60 and its per-pair standard errors of 0.14–0.24 were too wide to resolve small differences — direct evidence that a smaller tier could not do the job it exists for. Vendor spend goes $4.03 → $7.39 a week, about +$175/year.
2. **Difficulty is measured, not asserted.** Author 240 candidates, score them against two vendors, promote the 150 hardest. Authoring cannot verify its own difficulty.
3. **Published, not withheld.** Every published cell stays recomputable from the published query set; overfitting remains the held-out set's job. The next held-out set can be drawn from the hard tier once it is proven.
4. **One file, a `tier` field.** Absent means tier 1, so none of the existing 150 entries are edited. The query-set hash will change, which is correct — the set changed.
5. **Two tables, never blended.** The headline stays standard-tier only and comparable back to `2026-W31`. `separation`, `routing` and `payload_effect` must be split by tier or they silently change meaning.

## The pilot

240 candidates (`src/queries/candidates-v3.json`, 40 per category) against Exa and Serper, scored by the full three-judge ensemble. Exa because it is the strongest vendor on the standard tier — a query Exa handles well is not hard whatever a weaker vendor does with it. Serper because it is architecturally least similar, so agreement between the two means more than agreement between two similar products. 480 vendor calls, 1,440 judge calls, roughly $2 of vendor spend. Nothing written to the database: a 240-query two-vendor pass would be selected as a week's canonical run by `export.canonical_run` if it ever landed in `runs`.

Baseline is the same two vendors on 60 standard-tier questions from `2026-W31`, re-scored the same day in `docs/16`'s control arm — so the comparison crosses no model revision and no settings change.

## Result: the target was missed

| | tier 1 (n=60) | v3 all 240 | v3 kept 150 |
|---|---|---|---|
| median | 9.00 | 8.50 | **8.50** |
| mean | 8.84 | 8.50 | 8.08 |
| sd | 1.16 | 1.10 | 1.12 |
| ≥9 | 60.0% | 47.1% | 29.3% |
| ≤6 | 3.3% | 5.4% | 8.7% |
| mean per-query \|Exa − Serper\| | 0.850 | 1.092 | 1.487 |

**The target was a median near 6. The kept set lands at 8.5.** Culling the easiest 90 of 240 moved the mean from 8.50 to 8.08 and did not move the median at all.

Discrimination looks better — the mean per-query gap between the two vendors rises from 0.850 to 1.487 on the kept set — but that number should not be quoted. **The kept set was selected on low mean score, and selecting on low mean partly selects for high spread**, because a query where one vendor fails has both. The unbiased comparison is the full 240 against tier 1: 0.850 → 1.092, a difference of **+0.242 with a standard error of 0.174 (t = 1.39, 95% CI −0.100 to +0.583)**. That interval contains zero. On this evidence the candidates are not distinguishably more discriminating than the questions already in use, and the kept set's apparent advantage will regress when it runs again.

## Where the difficulty actually came from

Per-category, tier 1 (n=10 each, so indicative only) against v3 (n=40 each):

| category | spread | median |
|---|---|---|
| breaking_news | 0.50 → **1.35** | 9.50 → 8.50 |
| multi_hop | 1.30 → 1.57 | 9.00 → **9.00** |
| general_facts | 0.30 → 0.60 | 9.75 → **9.50** |
| code_technical | 0.60 → 0.78 | 9.00 → 8.50 |
| local_shopping | 1.10 → 1.05 | 8.50 → 7.50 |
| long_tail | 1.30 → 1.20 | 8.00 → **8.50** |

Three things stand out. **Freshness is where vendors genuinely differ** — `breaking_news` nearly tripled its vendor gap and was the only category to improve substantially on both measures. **`general_facts` is saturated and probably cannot be fixed by harder questions**: obscure, multi-part, well-documented facts still score 9.5, because retrieving a documented fact is a solved problem for all of these vendors. **`long_tail` got *easier*** — the authored candidates scored above the existing ones, which is an authoring failure rather than a property of the category.

## What this changes

The pilot did the job it was added for: it stopped a tier that is not hard from being promoted on the strength of the word "hard" in its name. Do not promote the kept 150 as the v3 tier on this evidence.

The finding underneath is more useful than the tier would have been. **Authoring harder questions in the same style has hit diminishing returns** — one round of deliberate effort bought a half-point of median and a spread increase indistinguishable from noise. Difficulty in the sense that matters is not obscurity; these vendors retrieve obscure documented facts about as well as common ones. It is *contestability* — questions where being wrong is possible and detectable.

Three levers remain untested, in order of expected value:

1. **False-premise questions**, deliberately excluded from this batch. A question built on a premise that is not true makes confident answering a failure, which is a kind of wrongness retrieval quality cannot paper over. It needs a rubric clause, and `docs/16` measured that rubric edits shift the score level — so it must be made and measured as its own change, not bundled with a query set.
2. **Rebalancing toward freshness and away from `general_facts`**, following where the measured spread actually is. This changes category weights and is therefore a methodology change with published consequences, not an authoring task.
3. **Comparative judging** — `docs/16`'s own open item. `docs/04` rejected pairwise on cost, not on discrimination, and an absolute scale has a ceiling that a forced comparison does not.

The 240 candidates and the pilot are kept rather than discarded: the measurement is the asset, and re-running it against a revised batch is how the next attempt gets judged.
