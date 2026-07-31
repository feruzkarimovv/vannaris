# CLAUDE.md — SearchBench build guide

This file is written for whichever instance of Claude Code picks up this project. Read this file first, always — it's the entry point and the thing that tells you which other file to open for what. The `docs/` folder is the full research record this project is built on; treat it as authoritative unless the founder tells you otherwise, and treat anything marked UNVERIFIED inside it as still open, not resolved.

## What this project is, in one paragraph

SearchBench is a free, public, continuously-updated benchmark of web-search/retrieval APIs used by AI agents (Tavily, Exa, Brave, Serper, You.com, Perplexity, Linkup, and others — see `docs/03-legal-and-vendor-terms.md` for exactly which ones are cleared to start with), scored weekly across a query taxonomy by an LLM-judge ensemble, published as a public dashboard with an open data export. On top of the free benchmark sits a monetized BYOK routing SDK/API that picks the best vendor per query using the benchmark's own live scores. The benchmark is the trust engine; the router is the business. Full detail in `docs/01-product-spec.md`.

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

## Non-negotiable constraints (do not silently violate these)

**BYOK only, always.** Every vendor's terms of service prohibits reselling or sublicensing access. The router must never hold, proxy-resell, or take a markup on vendor API keys or vendor query costs — it orchestrates using the end user's own credentials. If you find yourself designing a feature where SearchBench sits between the user and the vendor as a resold/proxied service, stop and re-read `docs/03-legal-and-vendor-terms.md` — that design is not viable under the vendor terms as currently understood.

**Vendor scope for the public benchmark is not "add every vendor you can find an API key for."** Two vendors (Seltz, Search Router) have explicit contractual clauses prohibiting exactly what this benchmark does, without written consent. Do not add them to the public, published benchmark without the founder confirming that consent has actually been obtained. If you're asked to "add a new vendor," check `docs/03-legal-and-vendor-terms.md`'s per-vendor table first — if the vendor isn't in that table yet, its terms haven't been reviewed and shouldn't be assumed clear.

**The naming question is open, not settled.** This codebase and these docs use "SearchBench" as the working name because that's what the research was scoped under, not because the name has been cleared. Don't buy a domain, file a trademark, or treat the name as final on your own initiative — that's the founder's call, informed by the naming section of `docs/03-legal-and-vendor-terms.md`.

**Evidence discipline carries forward into the product itself.** The whole pitch is "the neutral benchmark nobody can dismiss as marketing." That only holds if the methodology is genuinely public, genuinely reproducible, and genuinely free of vendor influence. When implementing the judge pipeline, don't quietly simplify away the bias mitigations in `docs/04-benchmark-methodology.md` (cross-family ensemble, position-swap checks, length normalization) for the sake of shipping faster — those mitigations are the product's credibility, not nice-to-haves.

**Don't claim "continuously run" before it's true.** The dashboard and any marketing copy should only describe the benchmark as continuously/weekly run once there's an actual multi-week history to back that claim. A one-time run described as continuous is exactly the kind of vendor-marketing move this project exists to be better than.

## Current phase and priority order

As of this directory's creation, no code has been written yet. Per `docs/07-build-plan.md`, the build order is: (1) benchmark runner + judge pipeline against the cleared v1 vendor set, running weekly, even before the dashboard exists — get real data accumulating in public as early as possible; (2) public dashboard, once there are a few real weeks of data to show; (3) router SDK, BYOK, schema-compatible with LiteLLM's `/v1/search` endpoint per `docs/05-architecture.md`. Don't reorder this without a clear reason — the elapsed public track record is the core credibility claim and front-loading dashboard polish over runner correctness works against that.

## Coding conventions and stack

No code exists yet, so these are recommendations, not established conventions — see `docs/05-architecture.md` for the reasoning. Suggested default: TypeScript/Node or Python for the runner and router API, Next.js + Vercel for the dashboard, Supabase (Postgres) for storage, GitHub Actions on a public repo for the weekly scheduled runner (free, unlimited minutes, and a credibility feature since the harness itself becomes publicly inspectable). Keep the raw-response, per-judge-score, and aggregated-weekly-score data separated into distinct tables from the start, since the raw layer is what gets exported publicly.

## Things to flag back to the founder rather than deciding unilaterally

Whether to include a borderline vendor (Brave, Tavily — broad-but-not-explicit clauses) in the public benchmark before or after attempting a written-consent conversation. Any change to the final public product name. Whether to proceed with a dataset whose license is unresolved (FreshQA — see `docs/04-benchmark-methodology.md`) versus waiting for confirmation. Any point where actual implementation reveals the cost model in `docs/06-business-model.md` or `docs/04-benchmark-methodology.md` is meaningfully wrong — correct the estimate and flag it rather than quietly absorbing the difference. Whether the actual YC W27 deadline (unpublished as of this writing) has been confirmed yet if the build timeline is running close to it.

## Definition of done for the MVP

A live, public, weekly-refreshing benchmark dashboard covering the cleared v1 vendor set (recommended starting point: Tavily, Exa, Brave, Serper, Perplexity), with a documented methodology page, a raw data export, and at least one full weekly refresh cycle completed and visible — meaning the mechanism has actually run in public, not just that the code is capable of running. This is deliberately a lower bar than a finished company; `docs/07-build-plan.md` explains why shipping this early and applying to Founders Inc immediately once it's live is the right sequencing.
