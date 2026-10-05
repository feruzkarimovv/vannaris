# CLAUDE.md — current development guide

Read [CURRENT-STATE.md](CURRENT-STATE.md) first for the implemented product and measured evidence, then [README.md](README.md), [AUTONOMY.md](AUTONOMY.md), and the [engineering case study](docs/18-engineering-case-study.md). [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) distinguishes this engineering release from deferred human studies and commercial plans.

## What to build and protect

Vannaris is a Python/SQLite evaluation pipeline with five search adapters, three judge families, versioned derived analysis, and a static evidence explorer. Its portfolio focus is backend and AI evaluation engineering. A paid router, hosted classifier/feed, customer portal, and proxy are not shipped products or the current release goal.

The committed measurement archive contains four published weeks, two scheduler-delivered weeks, one limited human pairwise calibration, and a W35 heldout run. The latest retrieval is August 24, 2026. Neither a configured cron nor updated code proves current weekly operation. This release changes code and derived analysis; it creates no new measured live data or human labels.

## Development workflow

The cloud task already has an isolated checkout. Use it; do not create a Git worktree unless explicitly requested.

```bash
make setup
make check
make demo
```

The demo serves http://127.0.0.1:8000/demo.html and writes only synthetic artifacts under `.demo/`. `make serve` serves the measured archive on the same port in a separate session. For full local browser validation, install the supported browser with `make setup-browser`, then run `make verify`.

Python 3.13 and Node 22 are the supported runtimes. Use the committed dependency locks and canonical Make targets. Do not use ad hoc installs or relax validation because a tool is missing. Read the current Makefile before depending on a command.

## Implementation invariants

- Run identity includes recorded inputs, week, trigger, retrieval time, prices, and vendor participation. New runs snapshot their queries; explicitly identified legacy fallbacks must not masquerade as immutable historical snapshots.
- Persist each retrieval before judging and checkpoint each accepted judge result. `--rejudge RUN_ID` reuses stored responses and retries missing families/models. `--resume RUN_ID` can retrieve missing query/vendor pairs only on the original UTC retrieval date; it must not backfill past days or weeks.
- Recovery preserves original run identity and metadata. Accepted scores remain append-only; failures remain recorded as attempts. Do not overwrite evidence to make a recovery appear successful.
- The exporter is the publication boundary. Incomplete category coverage cannot quietly change the category weights of an overall result.
- Public quality is conditional on API success. Availability, judge missingness, full-panel disagreement, and inference eligibility remain separate evidence.
- Derived statistics have their own revision and input hashes. Correcting analysis does not change retrieval dates, run triggers, query identity, or the original released observations.
- Bootstrap intervals, paired tests, and corrected comparisons have assumptions. Unresolved tiers are not equivalence, and a heldout gap is not proof of overfitting.
- The selected archived run controls its evidence and downloads. Never substitute latest detail for an old run; show an unavailable state instead.
- All published figures are generated. Synthetic demo data stay separate and clearly labelled. No invented measurements, human labels, usage, or savings.

## External operations and sensitive data

No paid vendor/judge calls, dispatching the weekly workflow, deployment, posting, or messages to others without explicit authorization. Ordinary setup and checks use mock transports or fixtures, not real keys.

Read `docs/03-legal-and-vendor-terms.md` and later verification notes before any vendor participation change. API-key availability is not benchmarking permission. Preserve the full-panel ensemble, bias mitigations, completeness floors, and registered withheld commitment; methodology changes need a documented revision and review.

Never read, print, stage, or publish credential values. Raw databases, calibration tasks containing retrieved content, and active withheld question text stay outside Git and public downloads. Workflow artifacts use sanitized status; optional encrypted recovery requires the owner's public X.509 recipient certificate. No private recovery key belongs in Actions. This release does not audit or remove historical remote artifacts.

Existing dated `docs/`, `applications/`, audits, plans, and handoffs remain research records. Correct them with a dated addition or a new document, not an in-place rewrite. The old guide below is preserved for historical context; its state descriptions and intended products are superseded by the current entry points above.

## Validation and landing

`make check` runs the strict offline gate. `make verify` adds real-browser checks and the mock demo. Verify behavior through relevant invariants, not a test count alone. Name what passed and what was not checked. If a gate appears wrong, investigate rather than weakening it to make the diff pass.

One coherent PR against `main`; no direct push or deployment unless authorized. Human-labelled research, vendor permission, withheld registration, live budgets, and publishing remain owner decisions. A study plan is not a completed study.

---

## Archived build guide — state recorded through August 14, 2026

The following text is preserved history. It is not current setup or product-status guidance. Its dated assumptions about cadence, labelling, heldout operation, commercial scope, and available local data are superseded by [CURRENT-STATE.md](CURRENT-STATE.md).

### Original August build guide

This file is written for whichever instance of Claude Code picks up this project. Read this file first, always — it's the entry point and the thing that tells you which other file to open for what. The `docs/` folder is the full research record this project is built on; treat it as authoritative unless the founder tells you otherwise, and treat anything marked UNVERIFIED inside it as still open, not resolved.

#### What this project is, in one paragraph

Vannaris is a free, public, continuously-updated benchmark of web-search/retrieval APIs used by AI agents (Tavily, Exa, Brave, Serper, You.com, Perplexity, Linkup, and others — see `docs/03-legal-and-vendor-terms.md` for exactly which ones are cleared to start with), scored weekly across a query taxonomy by an LLM-judge ensemble, published as a public dashboard with an open data export. The benchmark is the trust engine. **The business was restructured on 2026-08-04 and the old one-line summary — "the router is the business" — is no longer accurate.** What is sold is (1) private evaluations: the same harness run against a customer's own production queries, producing a custom routing table nobody can copy out of the free data; (2) a live score feed and hosted query classifier, sold alongside a routing client that is free and open source, because free OSS routers already exist and the client is not the defensible part; (3) BYOK routing whose recurring value is reliability — failover, latency-aware selection, caching, spend caps, query logs — with score-based routing as the differentiator on top rather than the whole product. Pricing is metered on volume with a savings-share option, not flat tiers. Full detail in `docs/01-product-spec.md`, `docs/05-architecture.md` and `docs/06-business-model.md`.

#### Read this before doing anything else

`docs/01-product-spec.md` — what to build and why, v1 scope, the naming caveat.
`docs/02-competitive-landscape.md` — who else exists in this space and what's actually differentiated.
`docs/03-legal-and-vendor-terms.md` — **read this before writing any code that calls a vendor API or stores/publishes vendor results.** It contains the vendor scope for v1 and the reasons two vendors are excluded by default.
`docs/04-benchmark-methodology.md` — the query taxonomy, judge design, and bias mitigations to build into the harness from day one, not retrofit.
`docs/05-architecture.md` — recommended system design, stack, and build order.
`docs/06-business-model.md` — pricing model and unit economics, relevant once the router SDK is being built.
`docs/07-build-plan.md` — the week-by-week plan and the program-application timeline this project is racing against.
`docs/08-risks-and-open-questions.md` — read this whenever something in the other docs seems too clean; it's the honest counterweight.
`docs/09-sources.md` — every citation, organized by document, with primary/secondary sourcing flagged.
`docs/13-conflict-of-interest.md` — **read before writing anything about how this project makes money, and before changing pricing.** It names the one pricing model that creates a real conflict, the commitments that constrain it, and the public disclosure register.

`AUDIT-2026-08-13.md` — the current honest statement of where the project stands, commissioned brutally and sourced throughout. It supersedes the more optimistic readings in `docs/01`, `docs/02` and `docs/06` wherever they disagree, and its §4 is the one to read before believing anything about how well the instrument discriminates. `PLAN-2026-08-13.md` is the ordered response to it, with owners and gates.

#### Working unattended

`AUTONOMY.md` is the contract for long sessions with no human in the loop: the
single gate that defines "did that work" (`scripts/check-all.sh`), the eight
things an agent may never do alone, and how work lands. Read it before starting
any autonomous run. The constraints below are the reasoning behind it.

#### Non-negotiable constraints (do not silently violate these)

**BYOK only, always.** Every vendor's terms of service prohibits reselling or sublicensing access. The router must never hold, proxy-resell, or take a markup on vendor API keys or vendor query costs — it orchestrates using the end user's own credentials. If you find yourself designing a feature where Vannaris sits between the user and the vendor as a resold/proxied service, stop and re-read `docs/03-legal-and-vendor-terms.md` — that design is not viable under the vendor terms as currently understood.

**Vendor scope for the public benchmark is not "add every vendor you can find an API key for."** Two vendors (Seltz, Search Router) have explicit contractual clauses prohibiting exactly what this benchmark does, without written consent. Do not add them to the public, published benchmark without the founder confirming that consent has actually been obtained. If you're asked to "add a new vendor," check `docs/03-legal-and-vendor-terms.md`'s per-vendor table first — if the vendor isn't in that table yet, its terms haven't been reviewed and shouldn't be assumed clear.

**The naming question is open, not settled.** This codebase and these docs use "Vannaris" as the working name because that's what the research was scoped under, not because the name has been cleared. Don't buy a domain, file a trademark, or treat the name as final on your own initiative — that's the founder's call, informed by the naming section of `docs/03-legal-and-vendor-terms.md`.

**Evidence discipline carries forward into the product itself.** The whole pitch is "the neutral benchmark nobody can dismiss as marketing." That only holds if the methodology is genuinely public, genuinely reproducible, and genuinely free of vendor influence. When implementing the judge pipeline, don't quietly simplify away the bias mitigations in `docs/04-benchmark-methodology.md` (cross-family ensemble, position-swap checks, length normalization) for the sake of shipping faster — those mitigations are the product's credibility, not nice-to-haves.

**Don't claim "continuously run" before it's true.** The dashboard and any marketing copy should only describe the benchmark as continuously/weekly run once there's an actual multi-week history to back that claim. A one-time run described as continuous is exactly the kind of vendor-marketing move this project exists to be better than. This is now enforced in code rather than left to discipline: every run records whether a scheduler or a person invoked it (`runs.trigger`), `src/export.py` computes `track_record.weeks_published` and `track_record.schedule_started` from that, and every cadence sentence on the site is derived from those two values. Don't hand-write a cadence claim into a page — in either direction. Copy saying the schedule *hasn't* started is the same failure once it has.

**The withheld set is withheld, not hidden, and its commitment is not yours to change.** `src/heldout.py` implements a rotating private question set whose SHA-256 is committed to git *before* it runs and whose questions are published in full when it retires. Never move an active set's question text into the repository, never edit `src/queries/heldout/manifest.json`, and never register or retire a set on your own initiative — the pre-registration is the entire reason a private score is worth anything here, and regenerating it silently converts this benchmark into the kind of thing it exists to be an alternative to. `src/export.py` fails the build if an active question's text reaches any published file. Published cells are computed from public questions only, so the table stays reproducible from the published query set.

**Publish the disagreement, including the parts that undercut the numbers.** Judge-disagreement rates ship per run and per category (`build_judge_stats`), and 13% of the first run's responses split the judges by more than three points. Do not remove those figures, do not replace the rates with the mean, and do not stop breaking them out by category — `docs/13-conflict-of-interest.md` names each of those as a signal that should make a reader distrust the project.

**No figure on the public site is typed by hand.** Every number, including the ones inside sentences, is filled at load from the generated export via `data-val` attributes, and `scripts/check-site.mjs` fails the build on any that doesn't resolve. If you find yourself typing a number into HTML, that's the signal it needs to come out of `src/export.py` instead — otherwise the front page and the table it summarises will eventually disagree, which is exactly the failure this project cannot afford.

#### Current phase and priority order

Per `docs/07-build-plan.md`, the build order is: (1) benchmark runner + judge pipeline against the cleared v1 vendor set, running weekly, even before the dashboard exists — get real data accumulating in public as early as possible; (2) public dashboard, once there are a few real weeks of data to show; (3) router SDK, BYOK, schema-compatible with LiteLLM's `/v1/search` endpoint per `docs/05-architecture.md`. Don't reorder this without a clear reason — the elapsed public track record is the core credibility claim and front-loading dashboard polish over runner correctness works against that.

**Step 3 is contradicted by the project's own data, and that is a finding rather than a delay.** The benchmark measured the quality gain a per-category router would deliver over always calling the best single vendor: **0.000 points in 2026-W31 and 0.017 in 2026-W33.** A cost-aware policy is worth about 18% at −0.12 quality; always-Serper is 86% cheaper at −0.78. So a *quality* router has nothing to route on, on this instrument, and the honest reading is that the finding is the product and the router is not. Do not start building step 3 on the strength of the ordering above — `AUDIT-2026-08-13.md` §4 and §8 set out what replaces it, and the durable frame is an independent evals lab for the agent tool stack with search as the wedge. A harder query set (`docs/04` taxonomy v3) is the one change that could revive the routing thesis, because it would create differences large enough to route on.

**Where it actually stands (updated 2026-08-14; the previous note here was dated 2026-07-31 and is superseded).** Step 1 is built and has produced **two published weeks**, `2026-W31` and `2026-W33`. Step 2 is built and **live at vannaris.com** — `site/` is a static four-page site generated from `src/export.py`, with `scripts/check-site.mjs`, `check-structure.mjs` and `check-quality.mjs` as its gates. The repository is public. An earlier version of this paragraph said the site was complete but not published; that stopped being true in early August, and `PUBLISH-CHECKLIST.md`'s gates were resolved by the founder rather than by anything in this repository.

**Step 1's other half — the scheduled weekly run — is armed (updated 2026-08-01, superseding the "deliberately not armed" note this paragraph previously carried).** `.github/workflows/weekly.yml` runs the full set every Monday at 06:23 UTC, exports, checks the site and commits the week; the runner exits non-zero on a methodologically invalid run so a bad week stops before the commit; the exporter merges the committed per-week JSON back in so the track record accrues without ever committing the database. The eight keys went into Actions secrets on 2026-08-01 and the workflow has been hand-dispatched to rehearse it. **It now spends real money on the founder's vendor accounts every Monday** — roughly $3.40 of vendor spend per run plus judge tokens. Do not disarm it, do not change its schedule, and do not dispatch it: an unattended agent firing a run costs money and can collide with the scheduled one.

**Armed is not the same as started, and after three attempts it still has not started.** The clock starts when a run the *scheduler itself* invoked lands in the data, not when the secrets were set. As of 2026-08-14, `track_record.scheduled_weeks` is 0 and `schedule_started` is false: 2026-08-03 died on a credit preflight, 2026-08-10 spent the vendor money and then lost 336 judge calls to quota-exhaustion 429s, and `2026-W33` was published by a hand-dispatched run. **`2026-W32` is a permanent gap** — a week that did not run cannot be backfilled, and pretending otherwise is the one thing that would make the elapsed record worthless. Nothing here or on the site may describe the benchmark as weekly or continuous until a scheduled run lands, and nothing needs editing when it does: the cadence copy is derived from `runs.trigger`. Landing `scheduled_weeks ≥ 1` is worth more than any feature.

**Benchmark hardening landed 2026-08-04, and one of the three has still never run.** A rotating withheld question set with a pre-registered hash (`src/heldout.py`, `ho-2026-08`, 30 questions) — **registered, and it has produced no data**: both published weeks carry `n_heldout_queries: 0`, because the `SB_HELDOUT_JSON` Actions secret is not set and `heldout install` degrades silently when it is missing. Judge-disagreement rates per run and per category, published. A conflict-of-interest policy (`docs/13`) mirrored into a site section, published before any vendor disputed a score.

**Run-path hardening landed 2026-08-14** (`AUDIT-2026-08-13.md` §5, PRs #26–#28): vendor responses are now stored *before* judging, so a failure in the stage that actually fails leaves a re-judgeable run rather than discarding the week; quota-exhaustion 429s are told apart from rate-limit 429s and fail fast instead of stalling in a held concurrency slot; and the key preflight sends the real judge call's parameters rather than a reduced version, with a gate that compares the two bodies field by field.

The highest-value thing *an assistant* can do next is still the human-labelled calibration set from `docs/04` — judge agreement with *humans* remains unaudited, and the disagreement rates now published measure agreement between models, which is a weaker and different quantity (`docs/12` is explicit about the difference). The pairwise set that replaces the failed absolute one is drawn and registered (`96afde9bfef3`, 280 screens, 2026-08-05) and its task is rebuildable with `python -m src.calibrate render`; what is missing is a person labelling it. **The instrument is also saturating** — 70% of 2026-W33 cells score ≥9 and only one of six categories has a separable leader — so a harder query set is not polish, it is the difference between a benchmark and a participation trophy.

Before anything in `site/` goes public, read `PUBLISH-CHECKLIST.md`. It gates on the unresolved name, on an attorney reading the methodology, and on not overclaiming the cadence — all founder decisions, none of them safe to resolve by shipping.

#### Coding conventions and stack

This section used to open "no code exists yet" and recommend a stack. The code exists, and what it settled on is not what was recommended, so what follows is the convention rather than the suggestion.

Python 3.13 for the runner, judge ensemble, export and calibration (`src/`), standard library plus `httpx` — no framework. **SQLite**, not Supabase (`src/storage/schema.sql`), with the raw-response, per-judge-score and aggregated-weekly-score layers in separate tables from the start, because the raw layer is the one that must never be published. The site is **hand-written static HTML/CSS/JS**, not Next.js: every figure is filled at load from the generated export via `data-val` attributes, and `scripts/check-site.mjs` fails the build on any that does not resolve. Node is used only for the site gates. GitHub Actions runs the weekly benchmark (`weekly.yml`), the gate on every PR (`checks.yml`) and a Monday heartbeat that notices a run that never started (`heartbeat.yml`).

Two conventions worth matching rather than inferring. **Comments say why, not what** — most non-obvious code here carries the incident that produced it, with the measurement attached, and that history is the reason the next person does not undo it. **A change that cannot be validated by an existing gate needs a new gate first** (`AUTONOMY.md`); tests assert the refusals — the cases where the right answer is to decline — because nothing in this pipeline crashes when it is wrong, it publishes.

#### Things to flag back to the founder rather than deciding unilaterally

Whether to include a borderline vendor (Brave, Tavily — broad-but-not-explicit clauses) in the public benchmark before or after attempting a written-consent conversation. Any change to the final public product name. Whether to proceed with a dataset whose license is unresolved (FreshQA — see `docs/04-benchmark-methodology.md`) versus waiting for confirmation. Any point where actual implementation reveals the cost model in `docs/06-business-model.md` or `docs/04-benchmark-methodology.md` is meaningfully wrong — correct the estimate and flag it rather than quietly absorbing the difference. Whether the actual YC W27 deadline (unpublished as of this writing) has been confirmed yet if the build timeline is running close to it.

#### Definition of done for the MVP

A live, public, weekly-refreshing benchmark dashboard covering the cleared v1 vendor set (recommended starting point: Tavily, Exa, Brave, Serper, Perplexity), with a documented methodology page, a raw data export, and at least one full weekly refresh cycle completed and visible — meaning the mechanism has actually run in public, not just that the code is capable of running. This is deliberately a lower bar than a finished company; `docs/07-build-plan.md` explains why shipping this early and applying to Founders Inc immediately once it's live is the right sequencing.
