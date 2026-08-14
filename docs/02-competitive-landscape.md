# 02 — Competitive Landscape

All findings below are current as of a comprehensive sweep completed 2026-07-30 across Product Hunt, YC's company directory, Hacker News (Show HN/Launch HN), GitHub, vendor blogs, and general press. Full citations in `09-sources.md`.

## Bottom line up front

No product currently combines (a) a neutral, continuously-run, cross-vendor benchmark of web-search/retrieval APIs for AI agents with (b) a monetized routing SDK/API — which is exactly SearchBench's mechanism. Everything found falls into one of four buckets: a vendor's own self-benchmark used as marketing; a generic LLM-model router with no search-API awareness; an LLM-gateway that now offers unified plumbing across search providers but zero quality-based routing; or a one-time SEO/content-marketing comparison article. The gap is real and confirmed, but it is narrowing at the infrastructure layer (LiteLLM) and getting noisier at the marketing layer (multiple vendors now publish self-benchmarks), which raises the bar for how visibly neutral SearchBench needs to be, fast.

**What the gap is not.** Added 2026-08-04, because early pitch drafts overstated this and the overstatement is easy to catch. Cross-vendor head-to-head comparisons of these APIs *do* exist, several are public, and one of them is a maintained MIT-licensed repository. Anyone evaluating this project will find them. The prior work is enumerated in the next section and should be linked directly in any launch material rather than described in the abstract — the argument is not "nobody has compared these", it is "every existing comparison is single-shot, single-judge, published by an interested party, and unaccompanied by the data that would let you re-derive it". That argument survives contact with the prior work; the stronger one does not. See `01-product-spec.md`, "The launch claim".

## Direct vendor landscape (the APIs SearchBench benchmarks)

| Vendor | What it is | Recent developments |
|---|---|---|
| **Tavily** | Search API purpose-built for LLM agents | Agreed to be acquired by Nebius for $275M (announced 2026-02-10). Maintains its own public MIT-licensed benchmark repo (`tavily-ai/tavily-search-evals`) that scores itself #1 against Perplexity, Serper/Google, Brave, and Exa on SimpleQA (93.3%) and a Document Relevance test — a textbook vendor-authored, self-ranking benchmark, published June 2025. |
| **Exa** | Semantic/neural search API, "search for AI" positioning | Powers OpenRouter's web-search tool-use feature as the backend (per Exa's own customer case study) — a real distribution relationship worth understanding, not necessarily a threat. |
| **Brave Search API** | Independent search index, API productized from Brave's consumer search engine | Requires "POWERED BY BRAVE" attribution in any product built on it. |
| **Serper** | Cheapest vendor surveyed (as low as $0.0003/query at volume) | Thin public ToS; ambiguous whether the absence of an anti-benchmarking clause reflects genuine absence or incomplete extraction (flagged in `03-legal-and-vendor-terms.md`). |
| **You.com API** | Search + "Research API" tiers | Eliminated tiered search pricing in favor of a flat $5/1,000-calls rate effective 2026-03-12. |
| **Perplexity (Sonar API)** | Search-augmented answer API, multiple reasoning tiers | ToS is unusually customer-favorable: explicitly bars Perplexity itself from training on customer content. Most expensive vendor surveyed once Deep Research mode and search-context fees are counted. |
| **Linkup** | French startup positioning itself as the "safe alternative" to scraping-based SERP APIs | Raised a $10M seed led by Gradient (~Feb 2026). Explicitly markets that it avoids the CFAA/ToS exposure that hit SerpApi because it runs its own independent crawl/index rather than scraping Google. |
| **Seltz** | New entrant, proprietary crawl/index/retrieval stack ("Web Knowledge API") | Raised a $12.5M seed (2026-06-24), founded by Antonio Mallia (ex-Amazon Alexa search, ex-Pinecone). Published a self-run "Dynamic News Search Benchmark" claiming 89% accuracy and sub-250ms latency — SiliconANGLE explicitly notes this is not an independently assessed figure. **Has an explicit contractual no-benchmarking clause — see `03-legal-and-vendor-terms.md` before including in v1.** |
| **Search Router** | Single-vendor branded search API despite the router-sounding name | Launched in India 2026-07-24 via wire-syndicated press release only (no independent tech-press coverage found across YourStory/Inc42/Entrackr). Publishes a self-run SimpleQA table ranking itself #1. Pricing undisclosed. **Also has an explicit contractual no-benchmarking clause.** No founder, funding, or legal-entity information found anywhere. |

## Prior comparisons — the work to cite, not to ignore

Every item below compares two or more of the vendors SearchBench benchmarks. Linking them is the point: it establishes that the category wants this measurement, and it lets the actual differentiator be stated as a specific difference rather than a claim of novelty. Each entry names what it does and the one property SearchBench adds.

| Prior comparison | What it is | What it does not do |
|---|---|---|
| **`tavily-ai/tavily-search-evals`** (MIT, published June 2025) | The most substantial prior work: a public, runnable evaluation repository scoring Tavily against Perplexity, Serper/Google, Brave and Exa on SimpleQA (Tavily 93.3%) and a document-relevance test. Genuinely open code | Run by the winner, run once rather than on a schedule, and no per-judge score data published — so the ranking cannot be independently recomputed, only re-run under the same design |
| **Seltz, "Dynamic News Search Benchmark"** | Self-run, claims 89% accuracy and sub-250ms latency. SiliconANGLE explicitly notes the figure is not independently assessed | Single vendor's own framing; not reproducible; Seltz also has a contractual no-benchmarking clause (`03-legal-and-vendor-terms.md`) |
| **Search Router's SimpleQA table** | Self-run table ranking Search Router #1 | No methodology published, no data, no independent coverage of the company at all |
| **Quercle and fastCRW head-to-head pages** | Marketing comparison pages against Tavily/Exa/Firecrawl; fastCRW cites a "200-query benchmark" | Self-authored, self-favouring, query sets not published |
| **Third-party comparison articles** | Recurring SEO-driven "best search API for AI agents" roundups | Snapshot-dated, usually qualitative or single-run, no judge design, no data export |

The honest summary of the prior art: at least five parties have published head-to-head numbers for these APIs, and every one of them either wins its own benchmark or is not reproducible from published data. What no one has published is a leaderboard that is **updated on a schedule with the history visible, scored by multiple judges from different labs with their disagreement disclosed, and exported as open data anyone can use to re-derive the ranking.** That is a narrower claim than "nobody has compared these" and it is the one that holds.

## Adjacent products and infrastructure (not direct competitors, but load-bearing context)

**LiteLLM (`BerriAI/litellm`)** is the single most important infrastructure development to track. As of v1.79.0-stable (2025-10-26) and v1.81.0-stable (2026-01-18), LiteLLM ships a native, unified `/v1/search` endpoint across 12+ search providers (Perplexity, Tavily, Exa, Brave, Parallel AI, Google PSE, DataForSEO, Firecrawl, SearXNG, Linkup, Serper, You.com, APISerpent) with cost tracking. This closed GitHub issue #15314 ("Universal API Proxy with Routing/Load Balancing for Agent Tools") via a cluster of PRs merged October 2025 (#15769, #15770, #15772, #15774, #15780 — the last explicitly states "fixes #15314"). What it does *not* do, confirmed by inspecting the shipped docs directly: any quality-based, benchmark-informed, or query-type-aware selection of which vendor to call. The developer still manually names the provider on every request. This is good news framed correctly: LiteLLM commoditized the plumbing SearchBench doesn't need to rebuild, and its proxy is a plausible integration point — SearchBench's router could ship as a routing-policy plug-in on top of LiteLLM's now-standard schema rather than reinventing per-vendor request/response mapping.

**OpenRouter** is the closest technical analogy for the router product, just for LLM models instead of search vendors. Its architecture — uptime filtering, inverse-square cost-weighted load distribution among stable providers, and a quality-tier system for tool-calling reliability — is a legitimate blueprint for SearchBench's own routing logic (detail in `05-architecture.md`). OpenRouter has no search-vendor-routing ambitions as far as could be determined; its own "web search" feature is a single-vendor (Exa) bolt-on for LLM tool-use, not a multi-vendor router.

**Portkey, Helicone** — AI gateways with logging/observability integrations for individual vendors (e.g., Portkey's Tavily plugin) but no evidence of a cross-search-vendor routing or benchmarking roadmap.

**Not Diamond, Martian** — LLM-model routers, not search-API routers, but directly relevant as pricing-model precedent (`06-business-model.md`).

**Free open-source routing clients.** Added 2026-08-04 as a correction to this document's earlier framing. LiteLLM's `/v1/search` is itself a free, open-source, multi-vendor search client, and it is the one most likely to be already installed wherever this product would be sold. Treating "a client that calls several search APIs behind one interface" as the differentiated asset is a mistake: that layer is commoditised, and a paid version of it competes against something free, maintained, and better distributed. This is the reasoning behind the open-source-client decision in `05-architecture.md` and the pricing split in `06-business-model.md` — give the client away, sell the live score feed, the hosted classifier and the private evaluations, which are the parts a fork cannot reproduce because they depend on continuously running the benchmark. What LiteLLM still does not have, confirmed against its shipped docs, is any quality signal or automatic per-query vendor selection; that gap is real, but it is a gap in *decision quality*, not in plumbing, and the plumbing should not be re-sold.

**Agentset.ai leaderboard** — covers embeddings, rerankers, LLMs, and vector databases; confirmed zero overlap with web-search/retrieval API benchmarking.

**Openbenchmarks.com** — validates the underlying mechanism almost exactly ("one input in, structured provider output out, methodology public on GitHub") but scoped to company-funding-data APIs, not web search. Evidence the neutral-benchmark-plus-monetization playbook is being replicated across verticals in 2026 — which raises urgency to move in the web-search vertical specifically, not evidence of a direct competitor.

**Rhumb / "AN Score"** (rhumb.dev) — an independent, third-party API-readiness scoring framework covering 645+ APIs including a search-specific comparison post. This is the closest thing found to a genuinely neutral evaluator already active in adjacent territory, but its metric set is generic "agent-readiness" (auth, error handling, reliability) rather than search-quality dimensions (relevance, freshness, citation quality), and it has no routing SDK attached. Worth monitoring, not yet a competitor.

**Quercle, fastCRW** — single-vendor search products that publish self-authored, self-favoring comparison pages against Tavily/Exa/Firecrawl. Reinforce the pattern that vendor self-benchmarking is now a normal marketing move in this category (at least five vendors — Tavily, Seltz, Search Router, Quercle, fastCRW — now do this), which is the exact gap SearchBench is built to fill.

## Confirmed non-competitors (false leads closed out)

DocsRouter.com is an OCR-API aggregator, unrelated to web search. Eden AI has no dedicated web-search-API comparison page found after repeated targeted searches (UNVERIFIED as absent, not confirmed). OmniRoute is an LLM-provider router only, explicitly does not route search APIs.

## YC and Product Hunt sweep

Reviewing YC's Search and Infrastructure industry directories directly turned up no YC-backed company doing cross-vendor web-search-API benchmarking or routing, across the S2025/W2026/S2026 batches checked. The closest adjacent YC company is **LLM Stats** (YC S2025), an "Independent AI evaluations lab" for LLM *model* benchmarks — a strong structural precedent that YC will fund exactly this business model (independent benchmarking-as-a-company), just not yet applied to search APIs. Product Hunt's current Search category (Perplexity, Cortex, Limitless, Klu, Fabric, Typesense, Algolia, Consensus, Meilisearch, DuckDuckGo, Globe Explorer, Tool Finder) contains no benchmarking or cross-vendor-routing product. Hacker News Show/Launch HN sweeps found single-vendor launches (Seltz, Quercle) and adjacent-but-different launches (Airweave — internal app search, not web search; Tokenless — automatic LLM model switching, not search) but no post matching SearchBench's specific mechanism.

## What this means for sequencing

Two new, real, funded entrants (Seltz, Search Router) appeared in the four months between the prior research round and this one — this space is moving quickly and getting more crowded at the single-vendor-with-self-benchmark layer, which is exactly the noise SearchBench needs to cut through by being visibly, verifiably neutral (public methodology, no vendor stake, third-party-auditable data) rather than by being first. The whitespace is specifically the *neutral, ongoing, cross-vendor* combination — not "a search benchmark exists," which is now common, but "a search benchmark nobody can dismiss as marketing" plus "a router that acts on it," which nobody has shipped.

---

## Note appended 2026-08-14 — the load-bearing sentence above has expired

*Appended rather than edited, per `AUTONOMY.md` item 7: this document is a record of what was
found on the date it was written, and the reason it is worth keeping is that it can be checked
against what happened next. Sourced from `AUDIT-2026-08-13.md` §3.*

**The claim this document ends on — that nobody has shipped "a benchmark nobody can dismiss as
marketing" plus "a router that acts on it" — stopped being safely true on 2026-08-13.** NativePort
(nativeport.ai) posted a "Web Search API Leaderboard: Quality, Latency, and Cost per Useful Result"
to Hacker News that morning: 11 vendors, measurement dated 2026-08-05, covering all five vendors
this benchmark runs plus Tavily, Brave, Parallel, Jina, SerpApi and DataForSEO. NativePort is itself
a metered gateway routing agents across roughly 32 APIs — benchmark and router in one product.

What survives is narrower and still real: NativePort sells the routing it benchmarks, so it is not
neutral; it is apparently not BYOK; and its methodology and reproducibility are unverified. The
differentiation that remains is **neutral, open-data, multi-judge, disclosure-first** — not
"first to combine the two". What does not survive is the assumption that there is time.

**Two further corrections to the sequencing section above.** First, the valuations recorded earlier
in this document are badly low: Exa raised $250M at **$2.2B** (Bloomberg, 2026-05-20), Parallel is
at **$2B** (TechCrunch, 2026-04-29), and the Tavily/Nebius deal is reported at up to **$400M**. The
market-size objection to this space is weaker than this document assumes. Second, Keiro launched at
$0.10/1K queries with a self-published benchmark (HN, 2026-07-24), and LiteLLM shipped Auto-Router
v2 on 2026-07-28 — still LLM-model routing with no search-quality signal, so that specific gap
remains open.

**And the router half of the framing is contradicted by this project's own data.** The measured
quality gain of a per-category router over always calling the best single vendor is 0.000 points
(2026-W31) and 0.017 (2026-W33). The durable frame is therefore not "benchmark plus router" — a
phrase NativePort now occupies and the data does not support — but **the independent evals lab for
the agent tool stack, with search as the wedge**. The precedent this document already identifies,
LLM Stats (YC S2025), is the right one; it is just the whole business rather than an adjacent
comparison. speko.ai (YC S2026) is the same pattern applied to voice.
