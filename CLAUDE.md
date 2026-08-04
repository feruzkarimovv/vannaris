# CLAUDE.md — Vannaris build guide

This file is written for whichever instance of Claude Code picks up this project. Read this file first, always — it's the entry point and the thing that tells you which other file to open for what. The `docs/` folder is the full research record this project is built on; treat it as authoritative unless the founder tells you otherwise, and treat anything marked UNVERIFIED inside it as still open, not resolved.

## What this project is, in one paragraph

Vannaris is a free, public, continuously-updated benchmark of web-search/retrieval APIs used by AI agents (Tavily, Exa, Brave, Serper, You.com, Perplexity, Linkup, and others — see `docs/03-legal-and-vendor-terms.md` for exactly which ones are cleared to start with), scored weekly across a query taxonomy by an LLM-judge ensemble, published as a public dashboard with an open data export. The benchmark is the trust engine. **The business was restructured on 2026-08-04 and the old one-line summary — "the router is the business" — is no longer accurate.** What is sold is (1) private evaluations: the same harness run against a customer's own production queries, producing a custom routing table nobody can copy out of the free data; (2) a live score feed and hosted query classifier, sold alongside a routing client that is free and open source, because free OSS routers already exist and the client is not the defensible part; (3) BYOK routing whose recurring value is reliability — failover, latency-aware selection, caching, spend caps, query logs — with score-based routing as the differentiator on top rather than the whole product. Pricing is metered on volume with a savings-share option, not flat tiers. Full detail in `docs/01-product-spec.md`, `docs/05-architecture.md` and `docs/06-business-model.md`.

## Read this before doing anything else

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

## Working unattended

`AUTONOMY.md` is the contract for long sessions with no human in the loop: the
single gate that defines "did that work" (`scripts/check-all.sh`), the eight
things an agent may never do alone, and how work lands. Read it before starting
any autonomous run. The constraints below are the reasoning behind it.

## Non-negotiable constraints (do not silently violate these)

**BYOK only, always.** Every vendor's terms of service prohibits reselling or sublicensing access. The router must never hold, proxy-resell, or take a markup on vendor API keys or vendor query costs — it orchestrates using the end user's own credentials. If you find yourself designing a feature where Vannaris sits between the user and the vendor as a resold/proxied service, stop and re-read `docs/03-legal-and-vendor-terms.md` — that design is not viable under the vendor terms as currently understood.

**Vendor scope for the public benchmark is not "add every vendor you can find an API key for."** Two vendors (Seltz, Search Router) have explicit contractual clauses prohibiting exactly what this benchmark does, without written consent. Do not add them to the public, published benchmark without the founder confirming that consent has actually been obtained. If you're asked to "add a new vendor," check `docs/03-legal-and-vendor-terms.md`'s per-vendor table first — if the vendor isn't in that table yet, its terms haven't been reviewed and shouldn't be assumed clear.

**The naming question is open, not settled.** This codebase and these docs use "Vannaris" as the working name because that's what the research was scoped under, not because the name has been cleared. Don't buy a domain, file a trademark, or treat the name as final on your own initiative — that's the founder's call, informed by the naming section of `docs/03-legal-and-vendor-terms.md`.

**Evidence discipline carries forward into the product itself.** The whole pitch is "the neutral benchmark nobody can dismiss as marketing." That only holds if the methodology is genuinely public, genuinely reproducible, and genuinely free of vendor influence. When implementing the judge pipeline, don't quietly simplify away the bias mitigations in `docs/04-benchmark-methodology.md` (cross-family ensemble, position-swap checks, length normalization) for the sake of shipping faster — those mitigations are the product's credibility, not nice-to-haves.

**Don't claim "continuously run" before it's true.** The dashboard and any marketing copy should only describe the benchmark as continuously/weekly run once there's an actual multi-week history to back that claim. A one-time run described as continuous is exactly the kind of vendor-marketing move this project exists to be better than. This is now enforced in code rather than left to discipline: every run records whether a scheduler or a person invoked it (`runs.trigger`), `src/export.py` computes `track_record.weeks_published` and `track_record.schedule_started` from that, and every cadence sentence on the site is derived from those two values. Don't hand-write a cadence claim into a page — in either direction. Copy saying the schedule *hasn't* started is the same failure once it has.

**The withheld set is withheld, not hidden, and its commitment is not yours to change.** `src/heldout.py` implements a rotating private question set whose SHA-256 is committed to git *before* it runs and whose questions are published in full when it retires. Never move an active set's question text into the repository, never edit `src/queries/heldout/manifest.json`, and never register or retire a set on your own initiative — the pre-registration is the entire reason a private score is worth anything here, and regenerating it silently converts this benchmark into the kind of thing it exists to be an alternative to. `src/export.py` fails the build if an active question's text reaches any published file. Published cells are computed from public questions only, so the table stays reproducible from the published query set.

**Publish the disagreement, including the parts that undercut the numbers.** Judge-disagreement rates ship per run and per category (`build_judge_stats`), and 13% of the first run's responses split the judges by more than three points. Do not remove those figures, do not replace the rates with the mean, and do not stop breaking them out by category — `docs/13-conflict-of-interest.md` names each of those as a signal that should make a reader distrust the project.

**No figure on the public site is typed by hand.** Every number, including the ones inside sentences, is filled at load from the generated export via `data-val` attributes, and `scripts/check-site.mjs` fails the build on any that doesn't resolve. If you find yourself typing a number into HTML, that's the signal it needs to come out of `src/export.py` instead — otherwise the front page and the table it summarises will eventually disagree, which is exactly the failure this project cannot afford.

## Current phase and priority order

Per `docs/07-build-plan.md`, the build order is: (1) benchmark runner + judge pipeline against the cleared v1 vendor set, running weekly, even before the dashboard exists — get real data accumulating in public as early as possible; (2) public dashboard, once there are a few real weeks of data to show; (3) router SDK, BYOK, schema-compatible with LiteLLM's `/v1/search` endpoint per `docs/05-architecture.md`. Don't reorder this without a clear reason — the elapsed public track record is the core credibility claim and front-loading dashboard polish over runner correctness works against that.

**Where it actually stands (updated 2026-07-31).** Step 1 is built and has produced one complete validated run (150 queries × 5 vendors × 3 judges, 95.6% complete ensembles) — see `searchbench-handoff-2026-08-01.md` for what that session learned. Step 2 is now built too: `site/` is a static four-page site (landing, results, methodology, data export) generated from `src/export.py`, with `scripts/check-site.mjs` as its smoke test. Building it early, against one week of data, is a deviation from the order above and was a deliberate call — it is complete but **not published**, and every page states the one-week limitation prominently rather than implying a track record that does not exist.

**Step 1's other half — the scheduled weekly run — is armed (updated 2026-08-01, superseding the "deliberately not armed" note this paragraph previously carried).** `.github/workflows/weekly.yml` runs the full set every Monday at 06:23 UTC, exports, checks the site and commits the week; the runner exits non-zero on a methodologically invalid run so a bad week stops before the commit; the exporter merges the committed per-week JSON back in so the track record accrues without ever committing the database. The eight keys went into Actions secrets on 2026-08-01 and the workflow has been hand-dispatched to rehearse it. **It now spends real money on the founder's vendor accounts every Monday** — roughly $3.40 of vendor spend per run plus judge tokens. Do not disarm it, do not change its schedule, and do not dispatch it: an unattended agent firing a run costs money and can collide with the scheduled one.

**Armed is not the same as started, and the difference is the whole claim.** The clock starts when a run the *scheduler itself* invoked lands in the data, not when the secrets were set. As of 2026-08-01 the published record is one manually-invoked week: `track_record.scheduled_weeks` is 0 and `schedule_started` is false. The first scheduled run fires Monday 2026-08-03. Nothing in this repository or on the site may describe the benchmark as weekly or continuous until that lands — and nothing needs to be edited when it does, because the site's cadence copy is derived from `runs.trigger` rather than written by hand.

**Benchmark hardening landed 2026-08-04.** Three things the founder asked for, all built and gated: a rotating withheld question set with a pre-registered hash and delayed disclosure (`src/heldout.py`, 30 questions registered, not yet run — it first runs with the next benchmark run); judge-disagreement rates published per run and per category on the methodology page; and a conflict-of-interest policy (`docs/13`) mirrored into a site section, published before any vendor has disputed a score.

The highest-value thing *an assistant* can do next is still the human-labelled calibration set from `docs/04` — judge agreement with *humans* remains unaudited, and the disagreement rates now published measure agreement between models, which is a weaker and different quantity (`docs/12` is explicit about the difference).

Before anything in `site/` goes public, read `PUBLISH-CHECKLIST.md`. It gates on the unresolved name, on an attorney reading the methodology, and on not overclaiming the cadence — all founder decisions, none of them safe to resolve by shipping.

## Coding conventions and stack

No code exists yet, so these are recommendations, not established conventions — see `docs/05-architecture.md` for the reasoning. Suggested default: TypeScript/Node or Python for the runner and router API, Next.js + Vercel for the dashboard, Supabase (Postgres) for storage, GitHub Actions on a public repo for the weekly scheduled runner (free, unlimited minutes, and a credibility feature since the harness itself becomes publicly inspectable). Keep the raw-response, per-judge-score, and aggregated-weekly-score data separated into distinct tables from the start, since the raw layer is what gets exported publicly.

## Things to flag back to the founder rather than deciding unilaterally

Whether to include a borderline vendor (Brave, Tavily — broad-but-not-explicit clauses) in the public benchmark before or after attempting a written-consent conversation. Any change to the final public product name. Whether to proceed with a dataset whose license is unresolved (FreshQA — see `docs/04-benchmark-methodology.md`) versus waiting for confirmation. Any point where actual implementation reveals the cost model in `docs/06-business-model.md` or `docs/04-benchmark-methodology.md` is meaningfully wrong — correct the estimate and flag it rather than quietly absorbing the difference. Whether the actual YC W27 deadline (unpublished as of this writing) has been confirmed yet if the build timeline is running close to it.

## Definition of done for the MVP

A live, public, weekly-refreshing benchmark dashboard covering the cleared v1 vendor set (recommended starting point: Tavily, Exa, Brave, Serper, Perplexity), with a documented methodology page, a raw data export, and at least one full weekly refresh cycle completed and visible — meaning the mechanism has actually run in public, not just that the code is capable of running. This is deliberately a lower bar than a finished company; `docs/07-build-plan.md` explains why shipping this early and applying to Founders Inc immediately once it's live is the right sequencing.
