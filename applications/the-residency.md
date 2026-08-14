# The Residency — application brief

**Purpose of this file.** A self-contained briefing for a fresh session helping draft an
application to The Residency. It assumes no prior context. Everything factual here is
either verified against live systems on 2026-08-01 or explicitly flagged as unverified.

**Status:** written 2026-08-01. Not yet submitted.

> **Corrections, 2026-08-05.** This brief is left as written. The statements below are no longer
> true, or were never true, and must not be pasted into any form. Each is checkable against
> `site/data/latest.json` or `site/export/`.
>
> - §1 "weekly-refreshed" — `track_record.scheduled_weeks` is 0 and `schedule_started` is false.
>   One published week, person-invoked. Say "a free, neutral public benchmark".
> - §1 "the router is the business" — retired 2026-08-04 (`CLAUDE.md`). What is sold is private
>   evaluations on a customer's own queries, a live score feed and hosted classifier alongside a
>   free open-source client, and BYOK routing sold on reliability.
> - §2 "in a single day (2026-08-01)" — the published run's `ran_at` is **2026-07-31**.
> - §2 and §3 "2,250 judgements" — that is the unachieved theoretical maximum. The published
>   figure is **2,151**, across 717 complete three-judge ensembles (95.6% of 750 responses); the
>   raw export holds **2,217** individual judge scores.
> - §2 "Built, not published" — the site went live 2026-08-03 (`PUBLISH-CHECKLIST.md`).
> - §2 "Deliberately not armed" — armed 2026-08-01; it fires every Monday 06:23 UTC. No
>   scheduler-invoked run has landed yet, which is why the cadence claim above still fails.
> - §2 "roughly $55–70/month, measured rather than projected" — unsupported. Measured vendor spend
>   is **$3.38 per run, about $14.60/month** (`docs/06`). Judge tokens are published per row in the
>   export; priced at list they add roughly $2 per run, but no price table is in the repository, so
>   that half is a reconstruction and must be labelled as one.
> - "23× cheaper", "4% of the price", "16× cost-efficiency gap" — the published ratios are **7.0
>   like-for-like** and **23.3 as billed**, and 23.3 prices Serper at a top volume tier requiring a
>   commitment. 16× appears nowhere in the data. Like-for-like the price share is 14%.
> - "wins 15–23 of every 25 queries" — those are ties-or-leads, and the range is **15–22**.
>   Outright wins are **28 of 150**, because **101 of 150** queries end in a tie (67.3%).
> - "Exa ranks first in all six categories" — true as point estimates, but the lead is separated
>   from second place in only **2 of 6**; in the other four Exa is level with Perplexity. The
>   defensible claim is that a per-category routing table is worth **0.000 points**.
> - §3c "Relative rankings survive because every vendor faces every judge" — **false.**
>   `robustness.stable_under_single_family` is false, `stable_prefix_single_family` is 0, and
>   `families_that_invert_it` is `["google"]` — the Google judge alone ranks Perplexity first.
>   Dropping the OpenAI judge flips ranks four and five. The top three hold only when a family is
>   dropped (`stable_prefix_leave_one_out` is 3); under a single family alone the agreed prefix is 0.
> - "Perplexity took 2.6–5.2 seconds" — the p50 range is **2.5–5.2 s** (2,492–5,183 ms).
> - "Working name is SearchBench" — renamed to Vannaris on 2026-08-01 (`docs/10`). The name is
>   deliberately left as written here per `scripts/rename.py`; the substance still holds, because
>   the USPTO search on VANNARIS is open and no domain is registered.
>
> §5's *"exactly the window over which \"continuously run weekly benchmark\" stops being a claim
> and becomes a demonstrated track record"* is correct as written and must not be changed.

---

## 1. The project in one paragraph

A free, neutral, weekly-refreshed public benchmark of the web-search/retrieval APIs that
AI agents and RAG pipelines depend on (Exa, Perplexity, You.com, Serper, Linkup). Queries
spanning six categories are run against every vendor and scored by a three-model
cross-family LLM judge ensemble; results publish as a dashboard plus an open data export.
On top of the benchmark sits the monetisable layer: a BYOK routing SDK that selects a
vendor per query using the benchmark's own live scores. The benchmark is the trust engine;
the router is the business.

**Why it can exist now.** Every vendor in this category publishes its own benchmark as
marketing, and every one of them wins the benchmark it publishes — Tavily, Seltz, Search
Router, Quercle and fastCRW all do this. The market has already decided it wants
proof-by-numbers. What doesn't exist is a neutral one nobody can accuse of rigging.
Separately, LiteLLM shipped a unified `/v1/search` endpoint across 12+ providers, which
commoditised the plumbing but deliberately left the developer to name the vendor on every
request — there is no quality signal and no routing logic anywhere in what shipped.

---

## 2. What is actually built and working

Built and verified end-to-end **in a single day (2026-08-01)**. This is not a plan; it runs.

| Component | State |
|---|---|
| Vendor adapters (5) | Working against live APIs, verified request/response shapes |
| Normalisation layer | All vendors mapped to one envelope, uniform top-10 depth |
| Storage | SQLite, three separated layers (raw / per-judge / aggregate) |
| Judge ensemble | 3 models, one per family, cross-family bias mitigation |
| Runner | Full fetch → judge → aggregate → report pipeline, failure-tolerant |
| Query set | 150 queries, 25 in each of six categories |
| Pilot run | 20 queries × 5 vendors × 3 judges = 300 judgements, completed |
| Full run | 150 queries × 5 vendors × 3 judges = 2,250 judgements, completed — 95.6% carry a complete three-judge score |
| Public site | Four pages, every figure generated from the data export, no hand-typed numbers. Built, not published |
| Weekly runner | Scheduled GitHub Actions workflow, tested. Deliberately not armed — arming it is a decision, not a task |

**Cost to operate: roughly $55–70/month**, measured rather than projected. Cheap enough to
run indefinitely on personal runway, which means the public track record accumulates
regardless of funding.

---

## 3. The findings — this is the strongest material in the application

These came out of the first real run. They are the proof that a neutral benchmark surfaces
things vendor marketing structurally cannot.

Source: full run of 150 queries × 5 vendors × 3 judges = 2,250 judgements, 2026-08-01.
96% of responses carry a complete three-judge score. Vendor spend for the run: $3.38.

**a) A 23× cost gap with a clean quality cliff — the headline finding.**
Serper costs $0.0003 per query against Exa's $0.0070. The quality it gives up for that
splits sharply by category:

| category | Serper as % of the best vendor |
|---|---|
| general facts | 98% |
| local / shopping | 93% |
| breaking news | 93% |
| code / technical | 92% |
| multi-hop | 84% |
| long-tail research | 82% |

So on four of six categories a developer can have 92–98% of the best available quality at
4% of the price — and on the two genuinely hard retrieval problems, they cannot. That is
a concrete routing policy (default cheap, escalate on hard categories), it is worth real
money, and no vendor has any incentive to publish it.

**b) One vendor leads on quality everywhere — which kills the naive version of the pitch.**
Exa ranks first in all six categories and wins 15–23 of every 25 queries. There is no
category where a different vendor is best, so "we route to the highest-quality vendor per
category" is not a product — the answer would just be "use Exa". Worth stating plainly in
the application: this was the original thesis, the benchmark disproved it within a day, and
the product was re-aimed at the cost-escalation framing above, which the same data supports
strongly. An earlier partial run appeared to show dramatic per-category reordering; that
turned out to be an artefact of dropped judge scores and was retracted once the clean run
landed.

**c) LLM judges carry large, measurable systematic bias.**
Across 750 responses: Anthropic mean 7.69, OpenAI 8.70, Google 8.91 — a 1.22-point spread
from judge choice alone, with mean judge-to-judge disagreement of 1.77 points and 98/750
responses where judges differ by more than 3. Relative rankings survive because every
vendor faces every judge, but any absolute score claim would move materially on judge
choice. This is direct evidence the cross-family ensemble is load-bearing rather than
decorative — and it is honest about the limitation: the ensemble is noisier on hard query
categories, which makes the human-labelled monthly calibration a requirement, not a
nice-to-have.

**d) Latency separates vendors as sharply as quality.**
Exa returned breaking-news results in 298ms; Perplexity took 2.6–5.2 seconds across
categories and never ranked first anywhere. For agent pipelines making many sequential
retrieval calls, that is a first-order product concern that no vendor benchmark surfaces.

---

## 4. Founder context

- Solo, technically capable across full stack and ML/systems.
- No enterprise network, no sales motion, no existing audience.
- Hardware: personal Apple Silicon Mac, plus rented cloud compute.
- No dedicated infrastructure budget — personal runway is the binding constraint.
- Working name is "SearchBench", **not cleared**: a dormant GitHub project at
  `Talc-AI/search-bench` exists in an adjacent space, and neither domain registration nor
  USPTO trademark status has been checked yet. Do not present the name as final.

---

## 5. The Residency — what is known

Sources: livetheresidency.com, Crunchbase, LinkedIn. Fetched 2026-08-01.

- Co-living / co-working residency founded by Nick Linck and Peter D'Ambrosio.
- Locations include San Francisco, Berlin, Bangalore, NYC, Cambridge.
- Cohorts typically 3–6 months.
- Residents receive housing (private or shared), food, co-working space, compute credits,
  food discounts, free therapy. Demo day to investors.
- **Full-time and in-person are mandatory** — cannot be simultaneously employed or in school.
- Self-described target: *"inventors who want to work on hard problems"*, *"visionaries who
  think long term"*, *"founders who want to change the world"* — applicants skew toward
  founders and researchers.
- No published application deadline; appears to be rolling.

**UNVERIFIED — must be confirmed directly before signing anything.** Third-party profiles
state the programme takes equity in any company started during the residency, and mentions
cash alongside housing and food. Neither the equity percentage nor the cash amount appears
on The Residency's own site. Treat the scope of that equity clause as an open question and
get the actual terms in writing.

**Why the fit is strong:** personal runway is the binding constraint on this project, and
The Residency attacks it directly — housing and food covered, compute credits subsidising
the exact judge and vendor spend the benchmark incurs. A 3–6 month cohort is also almost
exactly the window over which "continuously run weekly benchmark" stops being a claim and
becomes a demonstrated track record. Demo day is a natural forcing function for shipping
the public dashboard.

---

## 6. The honest risks — do not hide these, they are askable

An application that pre-empts these reads as more credible than one that doesn't.

1. **Legal exposure and credibility are the same surface.** The router is insulated by BYOK
   (the developer supplies their own vendor keys), but the *benchmark* must call vendor APIs
   with its own keys, store results, and publish comparisons — which several vendors' terms
   of service name directly. Mitigation in place: the v1 vendor set was deliberately scoped
   to the five with no explicit anti-benchmarking clause, and Tavily and Brave are held back
   pending a written-consent conversation despite being better-known. Publishing derived
   scores rather than vendor content reduces exposure further. This is a real risk that has
   been managed, not eliminated.

2. **BYOK inverts the OpenRouter analogy.** OpenRouter's value is *one key, all models* — it
   removes setup friction. A BYOK search router asks the developer to hold five vendor
   accounts, which is *more* setup than calling one vendor. The router has to be worth that
   friction; the cost-savings framing is what makes it worth it.

3. **The original routing thesis was wrong, and the benchmark is what proved it.** One
   vendor leads on quality in every category (§3b), so "route to the best vendor per query
   type" has no product in it. The thesis moved to cost-escalation routing — default to the
   vendor that is 23× cheaper and 92–98% as good, escalate only on the two categories where
   that gap widens to 16–18%. Expect to be asked why the first version was wrong; the honest
   answer is the strongest one available, which is that the instrument built to test it did
   its job on day one.

4. **The market is getting crowded fast.** Two new funded entrants appeared in four months.
   The differentiator is demonstrated neutrality and elapsed public track record, neither of
   which can be caught up on later — which is the argument for moving now.

---

## 7. What the application has to accomplish

Lead with **evidence, not intention**. The single strongest asset is that there is a working
system producing real findings today, not a pitch deck. The difference between

> "I want to build a neutral benchmark of search APIs"

and

> "I built one, and it already found a 16× cost-efficiency gap that no vendor publishes"

is the entire application.

Secondary points worth landing: execution speed (zero to validated pipeline in a day),
that the benchmark accrues value every week whether or not it is funded, that the project
was scoped around real contractual constraints rather than ignoring them, and that the
product thesis has already been revised once in response to its own data — which is
evidence of how the founder handles being wrong.

---

## Note appended 2026-08-14 — do not submit this as written

*Appended, not edited (`AUTONOMY.md` item 7). Sourced from `AUDIT-2026-08-13.md` §9.*

This draft's pitch rests on two things that have since changed, and submitting it unrevised would
put a claim in front of a selector that the project's own published data contradicts.

**The router is not the business.** The benchmark measured the quality gain of routing per category
against always calling the best single vendor: 0.000 points in 2026-W31, 0.017 in 2026-W33. Routing
on cost is worth roughly 18% at −0.12 quality; routing on *quality* has nothing to route on at this
instrument's current resolution. Any answer here framed around a router is arguing against the
evidence this project published itself.

**"Benchmark plus router" is no longer an unoccupied phrase.** NativePort posted an 11-vendor
web-search-API leaderboard attached to a routing gateway on 2026-08-13 (`docs/02`, note appended the
same week as this one).

The frame that survives both is **the independent evals lab for the agent tool stack, search
first** — the harness generalises to every tool category agents depend on, and LLM Stats (YC S2025)
and speko.ai (YC S2026) are precedents investors have already funded for models and voice.

Two claims in the draft above also need checking against the live site before they are repeated
anywhere: elapsed time (no scheduled run has landed — `track_record.scheduled_weeks` is 0 after
three attempts, and 2026-W32 is a permanent gap), and any cost-spread figure, which is 7× like for
like and not 23×.

`applications/zfellows.md` §8 is the version of this story that is current, and Z Fellows is the
right first submission. This one waits for a rewrite.
