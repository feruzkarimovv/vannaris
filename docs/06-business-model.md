# 06 — Business Model

## The constraint that shapes everything here

`03-legal-and-vendor-terms.md` establishes that every vendor's terms of service bars reselling, sublicensing, or proxying access to their API. That forecloses the simplest possible monetization model (buy vendor access wholesale, mark it up, resell to developers) entirely. Every viable path here is BYOK: the developer holds their own vendor relationship and API keys; SearchBench monetizes the routing/orchestration decision layered on top, never the underlying query itself. This is not a limitation unique to SearchBench — it's exactly the model every comparable BYOK-orchestration company below has already been forced into, which is useful, because it means there are real, working pricing precedents to copy rather than needing to invent one from scratch.

## Underlying vendor pricing (what SearchBench's users are already paying, directly)

| Vendor | Free tier | Basic paid rate | Effective cost per query |
|---|---|---|---|
| Tavily | 1,000 credits/mo free | $30/mo for 4,000 credits ($0.0075/credit) up to $500/mo for 100,000 ($0.005/credit); pay-as-you-go $0.008/credit | ~$0.005-0.008 |
| Exa | $20 signup credit + $10/mo ongoing | $7/1,000 requests (search only) | ~$0.007 |
| Brave Search API | $5/mo free credit | $5/1,000 requests, 50 QPS | ~$0.005 |
| Serper | 2,500 free queries | As low as $0.30/1,000 at the top volume tier | ~$0.0003-0.001 (cheapest vendor surveyed) |
| You.com API | $100 free credit | Flat $5/1,000 calls (content included), effective since 2026-03-12 | ~$0.005 |
| Perplexity (Sonar) | none disclosed | $1-3/M tokens plus a $5-14 per-1,000-request context fee depending on tier/mode | ~$0.008-0.02 basic, $0.05-0.25+ for Deep Research (most expensive vendor surveyed) |
| Linkup | 4,000 free queries | ~$5-6/1,000 requests | ~$0.005-0.006 |
| Seltz | $20 free credit | $5/1,000 requests | ~$0.005 |
| Search Router | 2,000 free credits | Undisclosed | UNVERIFIED |

Across the eight vendors with disclosed pricing, basic single-call queries cluster tightly at $0.005-0.008/query, with Serper a clear outlier cheap and Perplexity's Sonar (especially Deep Research mode) a clear outlier expensive — roughly a 15-20x spread between cheapest and priciest per-query cost.

**Measured, 2026-07-31, first full run** (150 queries × 5 cleared vendors, billed at list): the spread is **23.3×** — Serper at $0.000300/query against Exa at $0.007000/query — and Serper reaches 90% or better of the leading score in four of the six categories. The table-price estimate above was directionally right and understated the gap. This is the number the pricing model below is built on, and it is the strongest single argument in the whole document: the economic value of a cost-aware router is not a projection here, it is a measurement, and it is larger than the vendors' own price lists suggest.

## Pricing-model precedent (BYOK-orchestration and AI-gateway comparables)

Two clean archetypes recur across every comparable company surveyed, and neither charges a resale markup on the underlying provider's per-token/per-request cost as its primary model — consistent with the BYOK constraint SearchBench is also bound by.

**Flat usage-based metering, no subscription**: OpenRouter charges roughly a 5% fee on top of routed inference spend (5.5% with an $0.80 minimum on card top-ups specifically; 5% on crypto top-ups; no markup on the per-token inference rate itself; the first 1,000,000 BYOK requests/month are free, then 5% of the equivalent OpenRouter-hosted price). OpenRouter's growth trajectory under this model is the strongest available proof-of-concept for the whole category: revenue run-rate reportedly grew from roughly $400K/month (May 2025) to ~$19M annualized (end of 2025) to ~$50M annualized (March 2026), on total funding of $40.5M since a 2023 founding (seed $12.5M led by a16z, Series A $28M led by Menlo Ventures at a $500M valuation) — figures come from a paid research aggregator (Sacra), not OpenRouter's own disclosure, and should be treated as widely-reported-and-plausible rather than confirmed. Not Diamond charges a flat $0.05 per million tokens routed, pay-as-you-go, no free tier. Martian charges free for the first 2,500 requests, then $20 per 5,000 requests (an effective $0.004/request).

**Freemium log-volume SaaS subscription**: Portkey's tiers run free (10,000 logs/month) to $49/month (100,000 logs/month, then $9 per additional 100,000 up to 3M) to custom enterprise; Portkey raised a $15M Series A led by Elevation Capital (~Feb 2026). Helicone's tiers run free (10,000 requests/month) to $79/month (Pro) to $799/month (Team, 5 orgs) to custom enterprise — its disclosed funding figures ($5M seed at a $25M valuation, plus an earlier $125K pre-seed) rest only on funding-aggregator sites, not a Helicone press release, and should be treated as unverified.

## Recommended pricing shape — revised 2026-08-04

**What changed and why.** The previous version of this section recommended flat subscription tiers: $29-49/month for 50-100K routing decisions, $199-299/month for 500K-1M. That was modelled on Portkey and Helicone, and it has one structural flaw that the first real run made concrete. A flat cap prices by *logs stored*, which is a cost proxy, while the value delivered scales with *spend routed*. Those diverge violently here: the first run measured a **23× per-query cost spread** between the cheapest and most expensive cleared vendor (Serper at $0.0003/query, Exa at $0.0070/query, measured not quoted), with Serper reaching 90% of the leading score in four of six categories. A customer routing ten million queries a month across that spread has five figures a month at stake. Charging them $299 is not a discount, it is a failure to participate in the value created — and it is worst precisely for the customers who benefit most, which is exactly backwards.

The revised model prices on volume, with a savings-share option where the savings are genuinely attributable.

| Tier | Price | Shape |
|---|---|---|
| **Free** | $0, no card | ~1,000 routing decisions/month, full open-source client, weekly score snapshot (not the live feed) |
| **Metered** | $0.001/decision, falling to $0.0007 above 500K and $0.0004 above 5M | Live score feed, hosted classifier, spend caps, query log retention |
| **Private eval** | $2,000-5,000 per run | The benchmark on the customer's own queries: scored table, recommended routing policy, modelled spend under it. The first thing sold, and the thing nothing free can substitute for |
| **Managed routing** | Floor + a share of measured savings, capped | For customers above roughly $5K/month of vendor spend, where a private eval has established a baseline to measure against |

**Why per-decision metering is the default self-serve tier.** It scales with usage rather than capping on the heaviest users, it is trivially comparable to what a developer already pays (Martian's effective $0.004/request; OpenRouter's ~5% take rate, which on a ~$0.007 blended vendor query cost is roughly $0.00035/query), and — the reason it should stay the default even as other tiers appear — it pays the same whichever vendor is chosen. A pricing model that is neutral by construction is worth a great deal to a company whose product is neutrality (`13-conflict-of-interest.md`).

**The savings-share tier, and its honest cost.** Charging a percentage of measured spend reduction aligns revenue with the 23× spread the benchmark exists to surface, and it is the only model where a customer saving $40K/month pays proportionately. It also creates the one conflict of interest in this document that cannot be mitigated away: under it, Vannaris earns more when traffic moves to cheaper vendors, while also publishing the ranking that says which vendors are good enough to move to. That conflict is disclosed in `13-conflict-of-interest.md`, must be stated on the pricing page itself rather than only in a policy document, and is the reason the metered tier — not this one — should remain the default. Mechanically it needs: a baseline established by a private eval before routing starts, a floor so small accounts still pay something, a cap so the price cannot exceed what the metered tier would have cost, and a measurement window both sides agree on in advance. Without all four it is unsellable, and with them it is still the tier to revisit if the disclosure ever starts feeling uncomfortable to write.

**What is deliberately not priced.** The open-source client itself, forever. It is the distribution channel, and the thing being sold is the feed that keeps it current, the classifier that makes its routing accurate, and the evals that tell a customer what their own traffic is worth. Free open-source routers already exist; the winning position is to be the one everyone installs, not to be a paid alternative to one.

## Cost to run SearchBench itself

**Vendor API spend** (the benchmark's own query cost, running the harness against 200 queries × 8.5 vendors weekly): roughly **$47-94/month**, driven mostly by how many queries get routed through the pricier modes (Perplexity's high-context/Deep Research tiers, Exa's Deep Search). **Measured at the actual v1 scale** (150 public queries × 5 cleared vendors): **$3.38 per run**, about **$14.60/month** — well under the estimate, because the estimate assumed 8.5 vendors including the two most expensive and none of the queries use Deep Research modes. Adding the 30-question withheld set (`04-benchmark-methodology.md`) takes it to roughly **$4.06 per run, $17.60/month**. The estimate above is left in place as the planning figure for a larger vendor set; the measured figure is what the operation actually costs today. **LLM-judge grading** (per `04-benchmark-methodology.md`'s 3-judge cross-family ensemble design): roughly **$150-250/month**. **Compute/hosting**: effectively **$0/month** at the leanest (GitHub Actions on a public repo is free and unlimited for the weekly runner; Supabase and Vercel free tiers cover early dashboard traffic) up to roughly **$55-100/month** once the dashboard has real traffic and warrants Supabase Pro ($25/month) plus Vercel Pro ($20/user/month) plus a few dollars of object storage for data exports.

| Cost line | Lean/bootstrap | Comfortable/production |
|---|---|---|
| Vendor API spend | ~$50/mo | ~$100-150/mo |
| LLM-judge grading | ~$10-25/mo (single cheap judge, no redundancy) | ~$50-150/mo (full 3-judge ensemble) |
| Compute/hosting/DB/dashboard | ~$0/mo (all free tiers + GitHub Actions) | ~$55-100/mo |
| **Total** | **~$75-125/month** | **~$225-400/month** |

This is consistent with a solo founder's stated resources (personal Mac plus rented cloud compute, no dedicated infra budget) — running the entire benchmark operation is a low-hundreds-of-dollars-per-month cost structure even at the comfortable end, not a capital-intensive undertaking, and well within what an f.inc first check ($100K-$250K) would cover for a very long runway. The two biggest cost-control levers are using GitHub Actions on a public repo instead of an always-on VM for the weekly runner, and choosing a cheap judge model for routine grading (reserving a pricier frontier judge only for spot-checks or disputed gradings).

## Open gaps in this analysis

Serper's exact live tier table could not be pulled directly from its own pricing page (returned a 404 on fetch) and was corroborated instead via a dated third-party tracker plus Serper's own homepage headline numbers — re-verify against Serper's live pricing page before treating the intermediate tier breakdown as vendor-confirmed. Search Router's actual pricing is undisclosed anywhere found beyond "2,000 free requests," and whether it's a single-vendor product or a multi-vendor aggregator is genuinely ambiguous between how prior research characterized it and how its own launch press release describes itself ("integrates with existing web-search services") — that press coverage is one wire release syndicated across five outlets, not five independent confirmations, and is worth a direct follow-up against Search Router's own site/docs. Helicone's and OpenRouter's funding/revenue figures rest on funding-aggregator sites or a paid research aggregator rather than each company's own primary disclosure — treat as plausible-but-unconfirmed. The overall unit-economics sketch above is a first-principles estimate built from verified per-unit prices, not an observed real-world bill from anyone actually running a benchmark at this exact scale — validate it empirically in the first month of real runs rather than trusting it as a guarantee.
