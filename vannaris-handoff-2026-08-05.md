# Vannaris — session handoff, 2026-08-05

Read `CLAUDE.md` first, then this. The previous handoff
(`searchbench-handoff-2026-08-01.md`) is still accurate about how the harness works;
this one supersedes it on *state* and on several published numbers that turned out
to be wrong.

## What happened this session

A full audit ran against the repository — 44 agents across ten dimensions
(statistics, judge pipeline, vendor fairness, query set, data integrity,
governance, monetization, market, legal, product), with every high-severity
finding handed to an adversarial verifier instructed to refute it. Fifteen
findings survived, fifteen were refuted. Seven were then re-run by hand against
`data/vannaris.db` and `site/export/` before being accepted.

Report: <https://claude.ai/code/artifact/930f830e-ae78-447e-997b-ec17a775bda8>
Remediation plan: `~/.claude/plans/now-you-have-everything-serialized-spindle.md`

The headline: **the measurement plumbing was sound and the published resolution
was not.** All 30 cells recomputed exactly from the published CSVs — but one
published column was provably wrong, the site asserted a robustness property its
own CSV falsified, and no uncertainty was published anywhere.

## State: everything is on a branch, nothing is merged

Branch `audit-remediation`, 8 commits, 62 files, all 10 gates green
(`scripts/check-all.sh`).

```
2c35310 Publish the repository, and gate the claims that depend on it
10e79da Level the payload every judge sees, and publish the tier policy
39e6f41 Make the harness reproducible, date-aware, and honest about cost basis
494ed5f Publish what the ranking can and cannot resolve
a046009 Count ties as ties, and stop claiming the ranking survives judge choice
f853315 Gate the held-out commit order, and alarm on a missed Monday
53ab14f Install the withheld set in CI, after its manifest is committed
fe9ba8e Register the withheld set, publish judge disagreement, and add the COI policy
```

The first two commits are the founder's own previously-uncommitted withheld-set
work, split so the manifest lands *before* the workflow step that installs it.
That ordering is load-bearing — see Open items.

## What changed, by stage

**0 — schedule.** The withheld set, COI policy and disagreement publishing were
all sitting uncommitted. Now committed in the right order. New `held-out set
committed` gate in `check-all.sh` asserts the manifest and the workflow step are
both tracked or neither is. New `.github/workflows/heartbeat.yml` fails every
Monday afternoon that the published week is behind the calendar — it exits 1 as
things stand, correctly.

**1 — the wrong numbers.** `wins` was decided by `REGISTRY` dict order on the
67.3% of queries that tie. Replaced by `outright_wins` + `shared_best`:

| | exa | perplexity | serper | youcom | linkup |
|---|---|---|---|---|---|
| was published | 70 | 18 | **55** | 4 | 3 |
| outright | 28 | 17 | **1** | 2 | 1 |
| shared best | 115 | 95 | 56 | 54 | 35 |

Six sentences claiming the ranking survives judge choice were false and are gone.
The rotation sentence on the methodology page described a mechanism that does not
exist (`rotates` is written and exported; nothing reads it) and is gone. Social
cards regenerated — they had the wrong number baked in.

**2 — uncertainty.** Cells carry `sd`/`se`. Vendor comparisons are paired on
common queries. `separation.overall_tiers` drives rank badges, so serper and
youcom now share `03=`. Four of six category leaders are not separable from
second place, and each cell says so.

**3 — harness.** `temperature=0` + OpenAI seed + `judge_model_returned`; run date
in the rubric; `--rejudge RUN_ID` so a judge-stage failure never re-buys vendor
calls; `cost_source` persisted, exported, and backfilled from stored payloads.

**4 — vendor fairness.** Judge snippet cap 400 → 500 (`SNIPPET_CHARS`), which was
binding on two vendors and none of the others. Blinding leak removed. Perplexity's
harness-imposed `max_tokens` 512 → 2048. Per-vendor tier policy published.

**5 — repo is public.** <https://github.com/feruzkarimovv/vannaris>. `REPO_URL`
set; `check-quality.mjs` now fails if a page claims the source is readable while
`repo_url` is null.

## Methodology v2 — comparability break

Stages 3 and 4 both change what a judge sees, so they are one versioned entry in
the methodology changelog with the break stated. **Scores from the next run are
not comparable with 2026-W31.** This was done deliberately now, against a single
published week, because it is the cheapest moment it will ever be. The W31 table
stands as published and is *not* rescored.

## Where the audit was wrong — do not re-litigate these

The audit is good but not infallible. Three of its recommendations were rejected
after checking, and a fresh session should not undo that work:

1. **"Leave-one-out is stable in all three cases"** — false. Dropping OpenAI flips
   ranks 4/5. Shipping that replacement copy would have put a *second* wrong
   sentence on the site. What is published instead is the measured depth of
   agreement: `stable_prefix_leave_one_out` = 3 of 5, `stable_prefix_single_family`
   = 0.

2. **"Rename ~50 SearchBench references in `docs/` and `applications/`"** — wrong.
   `docs/10` records the 2026-08-01 rename decision and states those directories
   keep the old name because they are a dated record; `scripts/rename.py` has
   `SKIP_TREES = {"docs", "applications"}` with the reasoning in a comment.
   Rewriting a record to match a later decision is the habit this project exists
   to avoid. A README paragraph explains it instead.

3. **"Payload spread is 3.9×, mean 4,977 chars for Exa"** — recomputed from
   `judge_scores.scored_chars` it is 2.1× and 5,491. The conclusion survives
   (Linkup has Exa's payload size and the lowest score); the numbers did not.

Also refuted during the audit itself, and worth knowing because acting on them
would damage the benchmark: **do not retire `general_facts`** (highest paired t in
the set, 6.39, documented in `pilot.json` as a control condition) and **do not drop
query `mh-021`** (the low score is a genuine Perplexity hallucination the judges
correctly caught).

## Open items — in priority order

**1. Anthropic credit balance — founder only, blocking.** The 2026-08-03 scheduled
run died on a credit preflight, so `track_record.scheduled_weeks` is still 0. Next
chance is Monday 2026-08-10. A missed week cannot be backfilled and it is the only
asset in the project with no recovery path.

**2. Merge `audit-remediation` into `main` before Monday.** The weekly workflow
runs off `main`, and the working-tree `weekly.yml` calls `python -m src.heldout
install`. If the workflow reaches `main` without `src/queries/heldout/manifest.json`,
the Monday job raises `SystemExit` at step 4 — before spending anything, so it
fails silently as a missing week. The two commits are already ordered correctly;
they just need to land.

**3. Stage 6 — gates and pitch surfaces (~1 hour).** Not started.
   - `scripts/check-all.sh:147` greps for forbidden cadence claims across only
     `site/*.html README.md`. Extend to `site/**/*.html applications/*.md docs/*.md`
     and add "weekly-refreshed", "refreshed weekly", "published weekly"; drop
     `when ` from the exemption list.
   - Then fix what that will catch. `applications/the-residency.md`: line 13
     "weekly-refreshed" (scheduled_weeks is 0), :46 "Deliberately not armed" (armed
     2026-08-01), :19 "the router is the business" (retired 2026-08-04), :40 "2,250
     judgements" (published 2,151; CSV holds 2,217), :30 "verified in a single day
     (2026-08-01)" (the run's `ran_at` is 2026-07-31). Also
     `the-residency-draft.md:42,57,59,71,199`. `applications/zfellows.md` already
     uses the right framing — use it as the template.
   - Reconcile `docs/01:5` and `:48`, which name a v1 vendor set (Tavily, Brave)
     that is not the set actually running (You.com, Linkup).
   - Put `README.md:72` on the site — *"One vendor (Exa) leads on quality in every
     single category. 'Route to the best vendor per query type' is therefore not a
     product."* The benchmark disproved its own thesis and it is published nowhere
     a visitor can see it. It is the most credible sentence in the project.

**4. Stage 7 — calibration rebuild (~half day).** Not started.
   - `docs/12` reason 1 (ceiling compression) is arithmetically wrong: given the
     observed marginals the maximum attainable Pearson r is 0.935, so compression
     explains at most 0.065 of the shortfall. Reasons 2 and 3 hold. Delete reason 1,
     state the max-attainable figure, and add both Fisher CI bounds — noting the
     upper bound (+0.581) already excludes the level of agreement a published
     ranking needs.
   - Switch to blinded pairwise: 150 (query, vendorA, vendorB) triples, stratified
     75 decisive (ensemble gap ≥ 1.0) / 50 near-tie (≤ 0.5) / 25 order-swapped.
     The existing 15 absolute labels already yield 51 ordered pairs at 60.8%
     concordance — 4× the information from the same effort and immune to the 9–10
     ceiling that destroyed the first attempt.
   - Fix four labelling-tool defects first: rubric visible with worked 3/6/9 anchors
     (currently only a `title` tooltip), stratify on gold presence, random draw
     instead of a presentation-order prefix, 15–20% duplicates for intra-rater
     reliability.
   - **Nothing from this goes on the site until the decisive-stratum CI supports
     it.** The "judges are unaudited" copy stays up until then.

## Things worth knowing that are not in the code

- **Judge-vs-human agreement is still the largest open caveat**, and it is not
  fixed by anything this session did. r = 0.10 on n = 15, 95% CI [−0.437, +0.581].
  Stage 7 is the work that would settle it.
- **Per-category routing gain is measured at 0.000** — Exa leads all six
  categories, so a per-category oracle is identical to hardcoding Exa. This is the
  strongest strategic fact in the repository and it argues against the router
  product as specced. `docs/01` and `docs/06` have not been updated for it.
- **Operating cost is ~$24/month** (judge spend $2.07/run, vendor spend $3.38),
  against `docs/04`'s $150–250 estimate. Worth correcting in the founder's favour:
  the track record accrues regardless of any funding outcome.
- **`gh` is authenticated** as `feruzkarimovv`; the repo is `feruzkarimovv/vannaris`
  and is now public.
- `scripts/check-all.sh` is fully offline and safe to run. **Do not** run
  `src.runner` without `--rejudge`, and **do not** dispatch the weekly workflow —
  both spend real money, and a dispatch can collide with Monday's scheduled run.
