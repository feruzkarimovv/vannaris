# SearchBench — session handoff, 2026-08-01

Workspace: the repository root. Covers two sessions on 2026-08-01; the second one is marked
inline where it changed something.

## Orientation — read these first, in this order

1. `CLAUDE.md` — operating guide and non-negotiable constraints. Read before anything else.
2. `docs/01`–`docs/09` — the full research record. Authoritative; treat items marked
   UNVERIFIED as still open.
3. `applications/the-residency.md` — current project state, empirical findings, and honest
   risks, written as a self-contained brief. **This is the fastest way to get current.**
4. `README.md` — how to run it, and the two founder actions that arm the weekly schedule.
5. `PUBLISH-CHECKLIST.md` — the gate between "the site is built" and "the site is live".

Code decisions are documented in comments at the point of the decision, deliberately —
`src/vendors/base.py`, `src/vendors/adapters.py`, `src/judge/ensemble.py`,
`src/storage/schema.sql`, `src/export.py`, `.github/workflows/weekly.yml`,
`src/queries/full-v1.json`. Don't re-derive them from scratch; several encode failures that
cost a run.

## State as of end of session

Went from **zero code to a validated end-to-end benchmark in one day**, and by the end of the
second session the public site and the scheduled runner existed too. Working:

- 5 vendor adapters (Exa, Perplexity, You.com, Serper, Linkup), verified against live APIs
- Normalisation to a common envelope at uniform top-10 depth
- SQLite storage, three separated layers per `CLAUDE.md` (raw / per-judge / aggregate)
- 3-model cross-family judge ensemble with retry and truncation salvage
- Runner: fetch → judge → aggregate → report, failure-tolerant
- 150-query set, 25 in each of six taxonomy categories
- **Two complete full runs stored in `data/searchbench.db`** (the later one, 96% complete
  triples, is the valid one — see Mistakes below)
- `src/export.py` — the only code allowed to turn the database into published numbers, and
  the enforcement point for "no vendor content leaves the raw layer"
- `site/` — a static four-page site (landing, results, methodology, data export) generated
  entirely from that export, with `scripts/check-site.mjs` as its smoke test. Built early,
  against one week of data, as a deliberate deviation from the build order. **Not published.**
- `.github/workflows/weekly.yml` — the scheduled run. **Written, tested, deliberately not
  armed.** Two founder actions arm it; see Open items.

### What the second session added, and why

The theme was making the schedule safe to start rather than making the site nicer.

- **`runs.trigger`** records whether a scheduler or a person invoked each run. The site's
  cadence sentences are derived from it (`track_record.schedule_started`), so no page can
  claim a schedule that never fired — or, once it fires, keep saying it hasn't. The
  "the weekly schedule has not started" copy was hand-typed and would have silently become a
  lie on the first cron.
- **The runner exits non-zero on an unpublishable run** — a judge family that produced
  nothing, ensembles below the 60% completeness floor, every vendor call failing. Everything
  is still stored; the job just stops before the commit. `src/export.py` enforces the same
  floor when picking a week's canonical run, so the runner's claim is actually true. It
  wasn't: a collapsed run could previously still be selected and published as a table of nulls.
- **The exporter merges committed week history.** CI starts from a fresh checkout with no
  database, so the track record accumulates as per-week JSON in git and the database is never
  committed — it holds raw vendor payloads. This is why `site/data/` and `site/export/` must
  be committed for the record to survive.
- **`scripts/check_keys.py --require-all`** so a lapsed key fails preflight rather than
  publishing a table with a vendor quietly missing.

Measured operating cost ≈ **$55–70/month**, well under `docs/06`'s $225–400 projection.
That correction is flagged per `CLAUDE.md`'s instruction not to absorb cost-model deltas
silently. Vendor spend per 150-query run: $3.38.

## Findings

Full detail in `applications/the-residency.md` §3. One-line version: **Exa leads quality in
all six categories, but Serper delivers 92–98% of that quality at 4% of the cost on four of
them, dropping to 82–84% only on multi-hop and long-tail.** That cliff is the product —
cost-escalation routing, not best-vendor-per-category routing.

## Decisions made this session that aren't obvious from the code

- **v1 vendor set is the five ToS-cleared vendors, not the five in `docs/01`/`docs/07`.**
  Those docs recommend Tavily/Exa/Brave/Serper/Perplexity; `docs/03` contradicts them and
  says hold Tavily and Brave pending written consent. Founder chose the cleared set.
  `src/vendors/adapters.py::REGISTRY` is the guarded line — adding a key there is the act of
  adding a vendor to a public benchmark.
- **Top-10 normalisation across all vendors.** Vendors return 8–20 results by default;
  scoring raw output would reward verbosity. Belongs in the published methodology page.
- **`response_mode` recorded per response.** Perplexity returns prose *and* a ranked list
  (`BOTH`), so it can be scored on equal footing rather than treated as incomparable.
- **Freshness queries have no gold answers and are written in perpetually-current form.**
  A freshness query with a fixed answer decays into a general-knowledge query within weeks.
  Rationale is in the `note` field of `src/queries/full-v1.json`.
- **Judge models are pinned, and the pins are load-bearing.** A silent provider-side model
  update would invalidate week-over-week comparison. Model string is stored on every score.
- **Partial ensembles are dropped, not degraded** (`median_overall(require_full=True)`).
  Rate-limit failures cluster in time, so a mix of 3-way medians and 2-way means in one
  column is a bias mechanism, not just missing data.

## Mistakes made — do not repeat

1. **Swapped a production-proven judge model for one validated on a toy prompt.**
   `gemini-3.5-flash` passed a 4-call probe with a short prompt, then truncated its JSON on
   32% of calls under the real (much longer) judge prompt. Reverted to
   `gemini-3.1-flash-lite`, which had held 100/100 under real load. **Validate judge models
   against production-length prompts.** Comment in `ensemble.py` records why 3.5-flash must
   not be reinstated without full-run evidence.
2. **Strict JSON parsing discarded valid scores.** Judges truncate mid-`rationale`; the
   numeric scores were complete in nearly every failure. `_extract` now salvages
   field-wise. Unit-tested against the real failure strings.
3. **Piped a long background run through `tail -60`** and destroyed its own report. Recovered
   only because the DB had everything. Write full logs.
4. **Reported a finding from incomplete data and had to retract it.** A run with 56%
   complete triples appeared to show dramatic per-category vendor reordering; the clean run
   showed Exa winning everywhere. **Check triple completeness before reading any result.**
5. **`docs/04`'s recommended judge model (`gemini-2.5-flash`) is dead** — still listed in the
   models endpoint but 404s with "no longer available to new users". The listing endpoint is
   not an availability signal.

## Open items

**The one thing blocking everything else: arm the weekly workflow.** It is written and
tested; it is not armed, and nothing accrues the one asset that cannot be bought or
accelerated until it is. Two founder actions, both documented in the weekly-run section of
`README.md`:

1. Put the eight keys in GitHub Actions secrets (`gh secret set`).
2. Push, and run it once by hand with `trigger` left on `manual` before trusting the cron.

**Left undone on purpose.** Arming it starts a recurring real-money spend (~$3.40 vendor
spend per run, ~$55–70/month all in) on the founder's accounts. That is a founder decision,
not an assistant one. It is *not* gated by `PUBLISH-CHECKLIST.md` — the runner can accrue
weeks while the name and legal questions are still open, and that sequencing is the
recommended one, since weeks accrue during the wait rather than after it.

Then, roughly in order: human-labelled calibration set (`docs/04` — now a requirement, see
below, and the highest-value thing an assistant can pick up), then the router SDK. The public
dashboard is built.

**Known weaknesses to address:**
- Judge disagreement is high on the full set: mean 1.77 points, 98/750 responses differing
  by >3, and a 1.22-point systematic gap between judge families. Category rankings survive
  it; per-query numbers don't. The `docs/04` monthly human-labelled calibration is now a
  requirement, and it's the first thing a sharp reviewer will attack.
- Scores compress in the 7–10 band. Queries may be too easy to discriminate well.
- 33/750 OpenAI calls still lost to 429s at `JUDGE_CONCURRENCY = 6`.

**Still the founder's call — do not decide these unilaterally (`CLAUDE.md`):**
- Whether to approach Tavily and Brave for written consent, and when.
- The public product name. "SearchBench" is **not cleared** — a dormant
  `Talc-AI/search-bench` exists; no WHOIS check and no USPTO TESS search has been done.
  `docs/08` says do this in week one; it has not been done. Nothing public should carry the
  name until it is.
- Whether to proceed with any dataset whose licence is unresolved (FreshQA).

**In flight:** founder is applying to The Residency (livetheresidency.com). Brief written at
`applications/the-residency.md`; a paste-ready prompt for a dedicated drafting session was
provided in-conversation. The equity term is UNVERIFIED and should be confirmed in writing
before signing anything — not before applying.

## Environment

- `.venv` exists; deps in `requirements.txt`. Run as `.venv/bin/python -m src.runner`.
  Note that only `httpx` and `python-dotenv` are actually imported — the SDK entries in
  `requirements.txt` are unused.
- `.env` holds 5 vendor + 3 judge API keys, all live and verified. **Gitignored. Never read,
  echo, commit, or paste it.** `scripts/check_keys.py` verifies all eight with one cheap
  live call each and prints only pass/fail — use that instead of inspecting the file.
  `--require-all` makes an unset key a failure; that is what CI runs.
- **Git: a private GitHub repo** at `feruzkarimovv/searchbench`. `.env` and `*.db` are
  ignored and the history has been checked for key patterns. It is private, so pushing
  publishes nothing — making it public is a separate decision, gated by section 4 of
  `PUBLISH-CHECKLIST.md`, and the keys must be in Actions secrets before that happens.
- Useful: `python -m src.runner --limit N` for cheap smoke tests, and
  `node scripts/check-site.mjs [site-root]` to check a build somewhere other than `site/` —
  that is how a state the live data does not yet show (a started schedule, a second week)
  gets tested before it happens for real.

## Suggested skills

- **`claude-api`** — invoke before any work touching judge models, LLM pricing, or model
  IDs. It has already caught a stale pricing assumption and is the reason the cost
  correction is trustworthy. Do not answer model/pricing questions from memory.
- **`dataviz`** — read before writing a single line of dashboard chart code. The dashboard is
  the next major deliverable and its credibility depends on legibility.
- **`frontend-design`** — for the public dashboard build.
- **`research`** — for the open verification items: USPTO/WHOIS name clearance, Linkup's and
  Serper's full ToS text (both flagged as thin extractions in `docs/03`), FreshQA licence.
  These want primary sources captured as a repo artefact.
- **`tdd`** — the judge pipeline is where correctness bugs hide silently and skew published
  numbers rather than crashing. Worth test-first from here on.
- **`post`** — founder-voice LinkedIn/X posts. Relevant because public track record is the
  actual moat and building an audience alongside the data is close to free.
- **`grilling`** — if revisiting the router's product thesis. It has already been wrong once
  and been corrected by data; stress-test it before building on it.
