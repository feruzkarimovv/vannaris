# Contributing

The value of this project is entirely in whether people believe the numbers. That makes some
ordinary contributions unusually sensitive here, so this file is mostly about which changes need
extra care rather than about code style.

## The most useful contribution

**Tell us a number is wrong, and show the recomputation.** Every published figure can be recomputed
from `site/export/*.csv` with no API keys — there is a worked example on the site's data page. An
issue that says "your multi-hop figure for vendor X disagrees with this script's output" is worth
more than a feature.

Close behind: a query that should be in the set and is not, especially one that discriminates
between vendors in the 7–10 band where scores currently cluster.

## Changes that need more than a pull request

### Adding a vendor

`src/vendors/adapters.py::REGISTRY` is a legal gate, not a config list. Adding an entry there is the
act of adding a vendor to a published comparison.

Before opening a PR:

1. Read that vendor's current terms of service and acceptable use policy in full.
2. Record what they say about benchmarking, competitive analysis, storing results, and publishing
   comparisons — in `docs/03-legal-and-vendor-terms.md`, in the same per-vendor table format.
3. If any clause could plausibly be read as covering third-party benchmarking, the vendor does not
   go into the public benchmark without written consent. Say so in the PR rather than deciding it.

Two vendors surveyed have explicit, unambiguous prohibitions. Tavily and Brave have language broad
enough to cover this. None of them are included, and PRs adding them without documented consent will
be closed with a link to this section.

### Changing the methodology

Anything that changes what a published number means: the rubric, a judge model pin, the aggregation
rules, the normalisation depth, the completeness floor.

These need a changelog entry on the methodology page in the same PR. A judge model swap changes
every score without anything changing about the vendors, and a benchmark that lets that happen
silently is not measuring vendors any more.

Judge model pins have one extra rule, learned the expensive way: **validate a candidate judge
against a production-length prompt, never a short probe.** A model that passed a four-call test with
a toy prompt truncated its JSON on roughly a third of calls under the real rubric. The comment in
`src/judge/ensemble.py` records which model and why it must not be reinstated without evidence from
a full run.

### Anything that moves the numbers in a flattering direction

Filtering out "bad" queries, dropping an outlier judge, changing an aggregation to a more favourable
statistic, raising a floor so a thin cell publishes anyway. These may all be correct changes. They
need an argument that stands on its own, made before the effect on the results is known, and the
effect stated in the PR.

The one kind of change that will not be merged is one that makes the results look better without
changing what was measured.

## Ordinary contributions

Everything else: bug fixes, adapter fixes when a vendor changes its response shape, site
accessibility and responsive fixes, documentation.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.runner --limit 5     # smoke test, a few cents of API spend
.venv/bin/python -m src.export

npm install jsdom                            # ad hoc; this is not a Node project
node scripts/check-site.mjs
```

`scripts/check-site.mjs` must pass before a site change is merged. It fails on an unresolved figure,
a chart that rendered nothing, a chart with no table equivalent, a dead link or anchor, or a missing
accessibility floor.

## House style

The comments in this repository explain **why**, at the point of the decision, and several of them
record a failure that cost a run. Don't strip them, and add one when you make a non-obvious call.
`src/judge/ensemble.py`, `src/vendors/adapters.py` and `src/export.py` are the examples to follow.

Python: standard library plus what is already in `requirements.txt`; type hints on function
signatures; no new dependency without a reason in the PR.

Site: no build step, no framework, no external requests. It has to open from disk and stay
inspectable. Data reaches the page through `site/data/bundle.js`, which is generated — never edit a
generated file, and never type a figure into the HTML.

Three site conventions that are load-bearing rather than taste:

- **Colour is referenced by role, never by raw value.** `--surface`, `--text`, `--rule`, `--accent`
  and the `--d100`…`--d700` ramp are re-declared inside `[data-field="ink"]`, which is what lets one
  attribute flip a whole band — including the charts drawn inside it, which resolve tokens from
  their own host element rather than from the document root.
- **A chart never gets a second colour scale for identity.** Quantity is the blue ramp; identity is
  carried by direct labels. The vermilion accent is emphasis only.
- **Every chart ships a table equivalent** built from the same rows the SVG is built from, so the
  two cannot disagree. `scripts/check-site.mjs` fails if one is missing.
- **Animations are additive, never gating.** The finished state is the default; the observer adds a
  flag. If you find yourself writing `opacity: 0` on something that holds content, stop — that is
  how a page ships blank to a background tab or a screenshot service. The same rule killed a
  count-up that briefly wrote `0` over four real figures and relied on frames to put them back.

## Security and keys

`.env` is gitignored and holds live API keys. Never read, echo, paste or commit it.
`scripts/check_keys.py` verifies every key with one cheap call each and prints only pass or fail.
If you think a key has leaked, rotate it first and open the issue second.
