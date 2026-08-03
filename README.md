# Vannaris

An independent benchmark of the web-search APIs that AI agents and RAG pipelines depend on.

Every vendor in this space publishes a benchmark, and every one of them wins the benchmark it
publishes. This is an attempt at the other kind: the same queries against every API, scored by a
three-model cross-family LLM judge ensemble, with the methodology, the individual judge scores and
the gaps in the data all published — including the parts that make the results look worse.

> **Working name.** "Vannaris" has **not** been cleared for trademark or domain use, and a
> dormant project with a near-identical name exists in an adjacent space. Nothing here should be
> published under this name until [`PUBLISH-CHECKLIST.md`](PUBLISH-CHECKLIST.md) is satisfied.
> `python scripts/rename.py <NewName>` renames the whole repo in one pass.

## Status

**As of 2026-08-01: one complete week of data, from a run a person invoked. The first scheduled
run fires 2026-08-03.**

Every figure below is a dated snapshot, not a live reading. This file is markdown and can derive
nothing, so it states what was true and when, and points at the generated export for what is true
now — [`site/data/latest.json`](site/data/latest.json), written by `src/export.py`. Where the two
disagree, the export is right and this file is stale.

**First published week, `2026-W31`, run 2026-07-31:**

| | |
|---|---|
| Queries | 150, across 6 categories |
| Vendors | 5 (Exa, Perplexity, Serper, You.com, Linkup) |
| Judges | 3, one each from Anthropic, OpenAI and Google |
| Judgements | 2,151 across 717 fully-scored responses (95.6% of 750) |
| Vendor spend | $3.38 |

The whole premise of this project is elapsed public running time. The clock it measures counts
weeks the *scheduler* delivered — `track_record.scheduled_weeks` in the export — and nothing here
or on the site describes the benchmark as recurring until that number moves. That restraint is the
point, not modesty, and it is enforced in code rather than left to discipline: each run records
whether a scheduler or a person invoked it, and the site's cadence copy is derived from that, so no
page can claim a schedule that never fired. This file is the one place that cannot derive its
claims, which is why it dates them instead.

The workflow that starts that clock was **armed on 2026-08-01**, and has not yet delivered a week:
the first scheduled run fires Monday 2026-08-03 at 06:23 UTC. Everything published so far comes
from a run a person invoked, which is why the track record reads one week and
`schedule_started` is still false. Armed is not started — see [the weekly run](#the-weekly-run).

## What the first run found — `2026-W31`

These are that week's numbers and they stay that week's numbers: a later week does not revise them,
and it does not update this section either. For the current figures, read the site or
`site/data/latest.json`.

The cheapest API in the set costs **23× less per query** than the highest-scoring one, and what you
give up for that depends entirely on the category:

| Category | Serper as % of the best vendor |
|---|---|
| General facts | 98% |
| Local & shopping | 93% |
| Breaking news | 93% |
| Code & technical | 92% |
| **Multi-hop** | **84%** |
| **Long-tail research** | **82%** |

Four of six categories give you 92–98% of the best available quality at 4% of the price. The two
genuinely hard retrieval problems do not. That is a concrete routing policy — default cheap,
escalate on hard categories — and no vendor has any incentive to publish it.

Two findings that cut the other way, and are published just as prominently:

- **One vendor (Exa) leads on quality in every single category.** "Route to the best vendor per
  query type" is therefore not a product; the answer would just be "use Exa". The original thesis
  was wrong and the benchmark is what proved it.
- **The judge families disagree by 1.22 points on the same responses**, with mean judge-to-judge
  disagreement of 1.77 points. Rankings survive that, because every vendor faces every judge.
  Absolute scores do not.

## Repository layout

```
.github/workflows/
  weekly.yml           the scheduled run: verify keys → run → export → commit the week
src/
  runner.py            fetch → judge → aggregate → report, failure-tolerant
  export.py            the only code allowed to turn the database into published numbers
  vendors/             one adapter per API, normalised to a common envelope
  judge/ensemble.py    the three-model ensemble, the rubric, and the pins
  queries/full-v1.json the 150-query set, authored in-house
  storage/schema.sql   three separated layers: raw / per-judge / aggregate
site/                  the public site; data/ and export/ are generated, everything else is source
scripts/               key checks, site smoke test, rename
docs/                  the research record this project was built on (01–09)
```

The database itself is **not** committed. It holds raw vendor responses, and publishing vendor
content rather than derived scores is exactly what this project's legal scoping avoids. The
generated export in `site/export/` is the published artefact, and it is enough to recompute every
number on the site.

## Run it

Needs your own keys: five vendor APIs and three judge models.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                          # add your keys
.venv/bin/python scripts/check_keys.py        # verifies all eight, one cheap call each
.venv/bin/python -m src.runner --limit 5      # smoke test, a few cents
.venv/bin/python -m src.runner --queries src/queries/full-v1.json
.venv/bin/python -m src.export                # rebuild site/data and site/export
```

`--limit` runs are smoke tests and are structurally prevented from reaching the published tables:
the exporter only publishes a run that covers at least 10 queries in every category, carries a
complete three-judge ensemble on at least 60% of its responses, and aggregation refuses to
overwrite a cell computed from more queries than the run writing it.

The runner exits non-zero when a run is not fit to publish — a judge family that produced nothing,
ensembles below the completeness floor, every vendor call failing. Everything is still stored,
because a failed run is real evidence about vendor and judge reliability; it just does not get a
row on the site.

## The weekly run

`.github/workflows/weekly.yml` runs the benchmark every Monday at 06:23 UTC: verify all eight keys
with one cheap call each, run the full 150-query set, build the export, check the site, and commit
the week. A run that fails any of those steps stops before the commit, and its log and database are
uploaded as an artifact regardless — the failed runs are the ones most worth keeping.

**It was armed on 2026-08-01.** The eight secrets are set and the workflow has been rehearsed by
hand; the first *scheduled* run fires Monday 2026-08-03 at 06:23 UTC. It was armed by these two
steps, kept here because they are also how it would be re-armed after a secret rotates or after
GitHub disables the schedule for repository inactivity:

```bash
# 1. Give Actions the keys. Eight secrets, same names as .env.
for k in EXA PERPLEXITY YOUCOM SERPER LINKUP ANTHROPIC OPENAI GOOGLE; do
  gh secret set "${k}_API_KEY"     # paste the value when prompted
done

# 2. Push. The cron only fires from the default branch of the remote.
git push origin main
```

Rehearse it by hand — `gh workflow run "Weekly benchmark"` — before trusting the cron, and leave
the `trigger` input on `manual`: `scheduled` is what the site's track record counts, and a
hand-fired test is not a week the schedule delivered. Use the `limit` input to cap the query count
so a rehearsal costs cents rather than dollars; the canonical-selection floor will correctly refuse
to publish it.

**Armed is not started.** The clock this project runs on measures weeks the *scheduler* delivered,
so nothing here or on the site describes the benchmark as weekly or continuous until
`track_record.scheduled_weeks` is above zero. That is derived from `runs.trigger` rather than
asserted, so no copy anywhere needs editing on the day it changes.

Worth knowing now that it is armed:

- **It spends real money on a schedule, starting now.** About $3.40 of vendor spend per run plus
  judge tokens; roughly $55–70/month all in, measured rather than estimated.
- **The database is never committed** — it holds raw vendor payloads. What gets committed is
  `site/data/` and `site/export/`, which the exporter guarantees carry no vendor-written text. The
  track record therefore accumulates as per-week JSON in git, and each run merges that history
  back in. This is why the export must be committed for the record to survive.
- **This does not publish the site.** Arming the runner starts the clock; putting the site on a
  domain is gated separately by `PUBLISH-CHECKLIST.md`, and the unresolved name blocks that. The
  sequencing is deliberate: weeks of data accrue while the naming and legal questions are settled,
  rather than after.
- **A missed week stays missed.** GitHub queues scheduled jobs and drops them under load, and
  disables scheduled workflows after a stretch of repository inactivity. Backfilling a skipped week
  by running it late would put a week's label on data collected at a different time, which is the
  one thing this benchmark cannot do.

## View the site

`site/` is static, has no build step, and makes no network requests — the two typefaces
(Archivo and Martian Mono, both OFL, both variable, subset to latin at 111KB for the pair) are
self-hosted in `site/assets/fonts/`. Open `site/index.html` directly, or serve it:

```bash
python -m http.server -d site 8000
```

Nothing on the site is hand-entered. Every figure, including the ones inside sentences, is filled
at load from `site/data/bundle.js`, which `src/export.py` generates from the database. The smoke
test enforces it:

```bash
npm install jsdom      # ad hoc; this is not a Node project
node scripts/check-site.mjs
```

It fails the build on an unresolved figure, a chart that rendered nothing, a chart with no table
equivalent, a dead link or anchor, or a missing accessibility floor.

Design notes worth knowing before editing it. The ground is warm off-white rather than white, so
cards sit on it in true white and read as cards without a heavy border; dark is available through
the toggle and is declared in the same role tokens, which is why one attribute on `<html>` repaints
the page and the charts inside it. Two colour systems, kept apart on purpose: one orange accent
marks the live thing on a page — the ping dot, the primary action, the single figure a section is
about — and one blue sequential ramp carries every quantity. The accent never means "series 2" and
the ramp never means "click here", so a chart cannot be mistaken for a call to action.

**The motion contract.** Every entrance animation is additive: the finished state is the default and
the observer only adds a flag. Nothing on this site is ever hidden waiting for an animation that
might not run. Reveals are also differentiated by what they reveal — headings rise in reading order,
single figures settle, chart marks count in one at a time — because one identical fade applied to
every section is the tell this project is trying not to be. Hover states are mechanisms rather than
light sources: a sheen crosses a button, a card lifts a pixel or two, nothing glows. A `data-done`
stamp removes each animation a few seconds after entry, so a
paused frame loop leaves plain finished markup rather than a half-drawn page.

**Generated pages.** `site/vendors/<id>.html` is one page per vendor in the published run, written by
`python scripts/make_vendor_pages.py`. They exist because the question people actually arrive with is
about one vendor, and because a per-vendor URL is what a vendor links to when it cites this
benchmark. No number is baked into them: they carry the vendor's id and fill every figure from
`site/data/bundle.js` at load, exactly like the hand-written pages, so they cannot go stale between
runs. `scripts/check-site.mjs` asserts that the set of pages matches the vendors in the export, so a
vendor added or dropped without regenerating is a failed gate rather than a missing page — and the
weekly workflow regenerates them anyway.

The share cards at `site/assets/og.png` and `site/assets/og-<vendor>.png` are generated from the same
export (`python scripts/make_og_image.py`), so a link preview cannot show a result the site no longer
reports. Both generators take `--site <root>`, matching `python -m src.export --out`, which is how
the whole publish pipeline gets exercised against a generated fixture without touching `site/`.

## Data

Everything under `site/export/` is **CC BY 4.0**: every individual judge score, per-response timing
and cost, the aggregate table, and the full query set.

Deliberately **not** published: retrieved URLs, titles, snippets, and synthesized answers. Publishing
derived scores rather than vendor content reduces copyright and terms-of-service exposure at the
same time, and `src/export.py` fails the build if a field carrying vendor content ever reaches the
export.

## Methodology, in short

Full version on the site's methodology page; the reasoning behind it is in `docs/04`.

- **Uniform depth.** Vendors return 8–20 results; all are truncated to the top 10 before judging, so
  verbosity is not rewarded.
- **Three judge families.** LLM judges prefer text that reads like their own output, and search APIs
  increasingly synthesize with the same class of model, so a single judge is structurally unsafe.
- **Median, and only when complete.** A response missing any judge is dropped, not averaged over the
  survivors: rate-limit failures cluster in time, so mixing three-way medians with two-way means in
  one column introduces bias rather than just thinning the sample.
- **Pinned judge models.** A silent provider-side model update would change scores without anything
  changing about the vendors. Pins are recorded on every score row and changes go in a changelog.
- **One canonical run per week**, chosen by coverage rather than by being most recent.

## Vendor scope

The five vendors here were chosen because none of them contractually prohibit third-party
benchmarking — not because they are the five best known.

**Tavily and Brave are deliberately absent.** Both have terms broad enough to be read as covering
this, and no written consent has been sought. Two further vendors surveyed have explicit,
unambiguous bars on benchmarking without prior written consent and will not appear without it.
`src/vendors/adapters.py::REGISTRY` is the single gate: adding an entry there is the act of adding a
vendor to a published comparison. See `docs/03` before touching it.

This is a cautious reading of published terms, not legal clearance, and it is not a substitute for
an attorney reviewing the methodology before a public launch.

## Known limitations

Restating what the site says, because a repository that only advertises its strengths is marketing.
Written 2026-08-01; the site states its own limitations from the data rather than from this list,
so where the two disagree the site is current and this is not:

- **No human calibration *yet*.** The methodology calls for a hand-labelled gold set scored monthly
  against the ensemble. The tooling exists and a set is drawn; **no human has labelled it**, so the
  judges remain unaudited and this is still the first thing a sharp reviewer should attack. See
  "Calibrating the judges" below.
- **One week of data** at the time of writing, so no trend, no week-over-week movement, no track
  record. This is the limitation that fixes itself, and only by elapsed time.
- **Scores cluster between 7 and 10**, which suggests the query set is not hard enough to
  discriminate cleanly at the top.
- **Single geography, single point in time.** Search results vary by region and by hour; this
  measures neither.
- **The query set is authored in-house**, which avoids dataset-licence problems and makes the set
  easier to accuse of being unrepresentative. The whole set is published, so the accusation is
  checkable.

## Calibrating the judges

An LLM judge measured against nothing is an assertion. `docs/04` calls for 100–200 expert-labelled
examples and a four-phase loop — baseline, error analysis, targeted rubric refinement, re-measure —
repeated monthly until agreement plateaus. This is that loop:

```bash
.venv/bin/python -m src.calibrate sample --n 150        # draw a set; writes calibration/<id>/
open calibration/<id>/label.html                        # label it — about 100 minutes
.venv/bin/python -m src.calibrate import calibration/<id>/labels.json --labeller YOURNAME
.venv/bin/python -m src.calibrate report
```

Four properties are deliberate, and each of them is there to stop the exercise from flattering the
judge:

- **Two strata, never pooled.** Two thirds of the set is drawn uniformly at random and is the only
  thing that may be quoted as the benchmark's agreement figure. One third is drawn from the
  responses where the three judges disagreed most — deliberately the judge's worst moments, useful
  for diagnosis and meaningless as a headline. `report` prints them separately and says which is
  which.
- **The labeller is blind.** No judge scores, no vendor names, shuffled order. Showing any of them
  turns the measurement into agreement-with-an-anchor, and a brand halo would then be baked into
  the gold standard the judge gets corrected against.
- **The draw is seeded and recorded** — run, seed, strata and blinding all go in the database, so
  the sample can be redrawn exactly. A gold set nobody can reproduce is an assertion about the
  judge, not evidence about it.
- **The task never enters the repository.** It shows the vendors' actual titles, URLs and snippets;
  `docs/03` says retrieved content is stored and not republished, so `calibration/` is gitignored.
  The labels that come back are numbers, and those are as publishable as any judge score.

Two checks guard it: `node scripts/check-labeller.mjs` exercises the labelling page — persistence,
keyboard entry, export shape, and that blinding actually holds — and
`.venv/bin/python -m unittest discover tests` covers the sampler and the agreement arithmetic.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: methodology changes need a changelog
entry, adding a vendor needs its terms read first, and a pull request that makes the results look
better without changing what was measured is the one kind that will not be merged.

## Licences

Code MIT ([`LICENSE`](LICENSE)). Data CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)).

Not affiliated with, endorsed by, or sponsored by any vendor measured here.
