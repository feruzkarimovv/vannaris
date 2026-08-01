# 09 — Sources

All sources below were fetched or searched on 2026-07-30 unless otherwise dated. Each entry notes whether it's a primary source (the vendor's/entity's own page or filing) or a secondary source (press coverage, aggregator, or third-party analysis). Where a claim rests only on a secondary or aggregator source, that is flagged explicitly in the relevant doc — treat those as "widely reported, plausible" rather than confirmed, per this directory's evidence-discipline standard.

## Legal, vendor terms, and naming (`03-legal-and-vendor-terms.md`)

- Tavily: [tavily.com/terms](https://www.tavily.com/terms), [tavily.com/acceptable-use-policy](https://www.tavily.com/acceptable-use-policy), [help.tavily.com/articles/3240802908-rate-limits](https://help.tavily.com/articles/3240802908-rate-limits), [github.com/tavily-ai/tavily-search-evals](https://github.com/tavily-ai/tavily-search-evals) — primary
- Exa: [exa.ai/assets/Exa_Labs_Terms_of_Service.pdf](https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf), [exa.ai/docs/reference/pricing](https://exa.ai/docs/reference/pricing) — primary
- Brave: [api.search.brave.com/.../terms-of-service](https://api.search.brave.com/app/documentation/general/terms-of-service), [brave.com/search/api](https://brave.com/search/api/) — primary
- Serper: [serper.dev/terms](https://serper.dev/terms), [serper.dev](https://serper.dev/) — primary (thin extraction, flagged as possibly incomplete)
- You.com: [you.com/terms](https://you.com/terms), [you.com/pricing](https://you.com/pricing) — primary
- Perplexity: [perplexity.ai/hub/legal/perplexity-api-terms-of-service](https://www.perplexity.ai/hub/legal/perplexity-api-terms-of-service), [docs.perplexity.ai/getting-started/pricing](https://docs.perplexity.ai/getting-started/pricing) — primary
- Linkup: [linkup.so/terms-of-use](https://www.linkup.so/terms-of-use) (partially loaded — secondary fragments used), [linkup.so/privacy-policy](https://www.linkup.so/privacy-policy), [linkup.so/blog/linkup-safe-alternative-serpapi](https://www.linkup.so/blog/linkup-safe-alternative-serpapi) — primary/secondary mixed; funding via [theaiinsider.tech, 2026-02-10](https://theaiinsider.tech/2026/02/10/linkup-raises-10m-seed-round-led-by-gradient-to-build-web-search-for-ai/) — secondary
- Seltz: [seltz.ai/terms](https://seltz.ai/terms), [seltz.ai/pricing](https://seltz.ai/pricing), [seltz.ai/blog/why-we-built-seltz](https://seltz.ai/blog/why-we-built-seltz), [seltz.ai/blog/seed-round-announcement](https://seltz.ai/blog/seed-round-announcement) — primary; funding via [fortune.com, 2026-06-24](https://fortune.com/2026/06/24/exclusive-seltz-a-startup-rebuilding-web-search-for-ai-agents-raises-12-5-million-in-seed-funding/) and [siliconangle.com, 2026-06-24](https://siliconangle.com/2026/06/24/agentic-infrastructure-startup-seltz-raises-12-5m-help-ai-agents-search-web-answers/) — secondary
- Search Router: [search-router.com/terms](https://search-router.com/terms) — primary; launch coverage via [business-standard.com, 2026-07-24](https://www.business-standard.com/content/press-releases-ani/search-router-launches-search-api-in-india-to-help-ai-agents-access-real-time-web-information-126072400613_1.html) (wire/advertorial syndication, one source distributed across multiple outlets) — secondary
- Tavily/Nebius acquisition: [bloomberg.com, 2026-02-10](https://www.bloomberg.com/news/articles/2026-02-10/nebius-agrees-to-buy-ai-agent-search-company-tavily-for-275-million) — secondary
- Google LLC v. SerpApi, LLC, No. 4:25-cv-10826 (N.D. Cal.): [courtlistener.com/docket/72059948](https://www.courtlistener.com/docket/72059948/google-llc-v-serpapi-llc/), complaint filed 2025-12-19; ruling coverage: [techdirt.com, 2026-07-27](https://www.techdirt.com/2026/07/27/judge-rejects-googles-attempt-to-dmca-its-way-out-of-being-scraped/), [searchengineland.com](https://searchengineland.com/google-loses-key-dmca-claims-against-serpapi-in-scraping-lawsuit-483185), [theregister.com, 2026-02-21](https://www.theregister.com/2026/02/21/serpapi_google_scraping_lawsuit/) — secondary
- Naming conflicts: [github.com/Talc-AI/search-bench](https://github.com/Talc-AI/search-bench) (last updated 2024-08-30), [drupal.org/project/searchbench](https://www.drupal.org/project/searchbench), [huggingface.co/datasets/NasimBrz/SearchBench](https://huggingface.co/datasets/NasimBrz/SearchBench), [querybench.com](https://querybench.com) — primary
- LMArena Search Arena (naming conflict — reject "SearchArena"): [github.com/lmarena/search-arena](https://github.com/lmarena/search-arena), [news.lmarena.ai/search-arena](https://news.lmarena.ai/search-arena) — primary

## Competitive landscape (`02-competitive-landscape.md`)

- LiteLLM: [docs.litellm.ai/docs/search](https://docs.litellm.ai/docs/search/), [v1.79.0-stable release notes](https://docs.litellm.ai/release_notes/v1.79.0-stable/v1-79-0), [v1.81.0 release notes](https://docs.litellm.ai/release_notes/v1.81.0/v1-81-0), [github.com/BerriAI/litellm/issues/15314](https://github.com/BerriAI/litellm/issues/15314), [issues/16169](https://github.com/BerriAI/litellm/issues/16169), [pull/15770](https://github.com/BerriAI/litellm/pull/15770), [pull/15774](https://github.com/BerriAI/litellm/pull/15774), [pull/15780](https://github.com/BerriAI/litellm/pull/15780) — primary
- OpenRouter: [openrouter.ai/blog/insights/model-routing](https://openrouter.ai/blog/insights/model-routing/), [openrouter.ai/docs/.../web-search](https://openrouter.ai/docs/api_reference/responses/web-search), [exa.ai/customers/openrouter](https://exa.ai/customers/openrouter) — primary
- Portkey: [portkey.ai/docs/integrations/plugins/tavily](https://portkey.ai/docs/integrations/plugins/tavily) — primary
- OmniRoute: [github.com/diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute/blob/main/README.md) — primary
- Agentset.ai: [agentset.ai/leaderboard](https://agentset.ai/leaderboard), [agentset.ai/rerankers](https://agentset.ai/rerankers) — primary
- DocsRouter: [docsrouter.com](https://docsrouter.com/) — primary
- Quercle: [quercle.dev/comparison](https://quercle.dev/comparison), [Show HN](https://news.ycombinator.com/item?id=46311753) — primary
- fastCRW: [fastcrw.com/blog/search-api-for-ai-agents](https://fastcrw.com/blog/search-api-for-ai-agents) (published 2026-04-05, updated 2026-06-13) — primary
- Rhumb / AN Score: [dev.to/supertrained/... comparison](https://dev.to/supertrained/exa-vs-tavily-vs-serper-vs-brave-search-for-ai-agents-an-score-comparison-2l1g) (2026-03-30/04-01), [rhumb.dev](https://rhumb.dev) — secondary/primary mixed
- Openbenchmarks.com: [openbenchmarks.com/company-funding/...](https://openbenchmarks.com/company-funding/best-company-funding-data-api) — primary
- YC directory: [ycombinator.com/companies/industry/search](https://www.ycombinator.com/companies/industry/search), [.../industry/infrastructure](https://www.ycombinator.com/companies/industry/infrastructure) — primary
- Product Hunt Search category: [producthunt.com/categories/search](https://www.producthunt.com/categories/search) — primary
- HN threads: [Airweave, Launch HN](https://news.ycombinator.com/item?id=45427482), [Tokenless, Launch HN](https://news.ycombinator.com/item?id=49099143), [cheapest-model router, Show HN](https://news.ycombinator.com/item?id=47036011) — primary
- Tavily self-benchmark blog post: [tavily.com/blog/tavily-evaluation-part-1-...](https://www.tavily.com/blog/tavily-evaluation-part-1-tavily-achieves-sota-on-simpleqa-benchmark) (2025-06-18) — primary
- Speko.ai reference: [x.com/bosmeny/status/2082567320594235489](https://x.com/bosmeny/status/2082567320594235489) — secondary

## Benchmark methodology (`04-benchmark-methodology.md`)

- RAGAS: [docs.ragas.io/.../align-llm-as-judge](https://docs.ragas.io/en/stable/howtos/applications/align-llm-as-judge/), [docs.ragas.io/.../available_metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) — primary
- TruLens: [qaskills.sh/blog/trulens-rag-triad-...](https://qaskills.sh/blog/trulens-rag-triad-groundedness-context-relevance-2026), [Databricks TruLens docs](https://docs.databricks.com/gcp/en/mlflow3/genai/eval-monitor/third-party-scorers/trulens) — secondary/primary mixed
- DeepEval: [deepeval.com/docs/metrics-llm-evals](https://deepeval.com/docs/metrics-llm-evals), [deepeval.com/docs/metrics-introduction](https://deepeval.com/docs/metrics-introduction) — primary
- Braintrust/autoevals: [braintrust.dev/articles/what-is-llm-as-a-judge](https://www.braintrust.dev/articles/what-is-llm-as-a-judge), [github.com/braintrustdata/autoevals](https://github.com/braintrustdata/autoevals), [llm-as-a-judge-vs-human-in-the-loop](https://www.braintrust.dev/articles/llm-as-a-judge-vs-human-in-the-loop-evals) — primary
- LangSmith: [langchain.com/blog/aligning-llm-as-a-judge-...](https://www.langchain.com/blog/aligning-llm-as-a-judge-with-human-preferences), [docs.langchain.com/langsmith/llm-as-judge](https://docs.langchain.com/langsmith/llm-as-judge) — primary
- Positional bias: [mbrenndoerfer.com/writing/position-bias-in-llm-judges](https://mbrenndoerfer.com/writing/position-bias-in-llm-judges) — secondary
- Self-preference bias study: [arxiv.org/html/2410.21819v1](https://arxiv.org/html/2410.21819v1) (Chatbot Arena dataset, 33,000 human-labeled comparisons, 8 LLM judges) — primary (peer-reviewed/preprint academic source)
- FreshQA: [github.com/freshllms/freshqa](https://github.com/freshllms/freshqa/blob/main/README.md), [arxiv.org/abs/2310.03214](https://arxiv.org/abs/2310.03214) — primary
- SimpleQA: [huggingface.co/datasets/basicv8vc/SimpleQA](https://huggingface.co/datasets/basicv8vc/SimpleQA), [openai.com/index/introducing-simpleqa](https://openai.com/index/introducing-simpleqa/) — primary
- HotpotQA: [huggingface.co/datasets/hotpotqa/hotpot_qa](https://huggingface.co/datasets/hotpotqa/hotpot_qa/blob/main/README.md) — primary
- 2WikiMultihopQA: [github.com/Alab-NII/2wikimultihop](https://github.com/Alab-NII/2wikimultihop) — primary
- BEIR: [github.com/beir-cellar/beir/wiki/Datasets-available](https://github.com/beir-cellar/beir/wiki/Datasets-available) — primary
- Natural Questions: [huggingface.co/datasets/google-research-datasets/natural_questions](https://huggingface.co/datasets/google-research-datasets/natural_questions), [LICENSE](https://github.com/google-research-datasets/natural-questions/blob/master/LICENSE) — primary
- TriviaQA: [github.com/mandarjoshi90/triviaqa](https://github.com/mandarjoshi90/triviaqa) — primary
- LegalBench-RAG: [github.com/zeroentropy-ai/legalbenchrag](https://github.com/zeroentropy-ai/legalbenchrag), [arxiv.org/abs/2408.10343](https://arxiv.org/abs/2408.10343) — primary
- FinanceBench: [huggingface.co/datasets/PatronusAI/financebench](https://huggingface.co/datasets/PatronusAI/financebench/blob/main/README.md), [arxiv.org/abs/2311.11944](https://arxiv.org/abs/2311.11944) — primary
- Amazon ESCI: [github.com/amazon-science/esci-data](https://github.com/amazon-science/esci-data/blob/main/LICENSE), [arxiv.org/abs/2206.06588](https://arxiv.org/abs/2206.06588) — primary
- CodeRAG-Bench: [github.com/code-rag-bench/code-rag-bench](https://github.com/code-rag-bench/code-rag-bench), [arxiv.org/abs/2406.14497](https://arxiv.org/abs/2406.14497) — primary
- Judge model pricing (July 2026 snapshot): [benchlm.ai/anthropic/api-pricing](https://benchlm.ai/anthropic/api-pricing), [benchlm.ai/google/api-pricing](https://benchlm.ai/google/api-pricing), [benchlm.ai/openai/api-pricing](https://benchlm.ai/openai/api-pricing), [anthropic.com/claude/haiku](https://www.anthropic.com/claude/haiku), [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) — secondary/primary mixed

## Business model (`06-business-model.md`)

- Tavily pricing: [docs.tavily.com/documentation/api-credits](https://docs.tavily.com/documentation/api-credits) — primary
- Exa pricing: [exa.ai/docs/reference/pricing](https://exa.ai/docs/reference/pricing) — primary
- Brave pricing: [brave.com/search/api](https://brave.com/search/api/) — primary
- Serper pricing: [serper.dev](https://serper.dev/) (headline figures primary); tier breakdown cross-checked via [coldiq.com/blog/serper-pricing](https://coldiq.com/blog/serper-pricing) (dated ~2026-07-05) — secondary
- You.com pricing: [you.com/resources/lower-search-api-cost](https://you.com/resources/lower-search-api-cost) — primary
- Perplexity pricing: [docs.perplexity.ai/getting-started/pricing](https://docs.perplexity.ai/getting-started/pricing) — primary
- Linkup pricing: [linkup.so/pricing](https://www.linkup.so/pricing) — primary
- Seltz pricing: [seltz.ai/pricing](https://seltz.ai/pricing) — primary
- OpenRouter revenue/funding: [sacra.com/c/openrouter](https://sacra.com/c/openrouter/) — secondary (paid research aggregator, not OpenRouter's own disclosure)
- Portkey: [portkey.ai/pricing](https://portkey.ai/pricing) — primary; funding via [inc42.com](https://inc42.com/buzz/portkey-bags-15-mn-to-help-enterprises-manage-ai-spending/), [yourstory.com](https://yourstory.com/2026/02/ai-application-infra-startup-portkey-raises-series-a-round-elevation-capital) — secondary
- Helicone: [helicone.ai/pricing](https://helicone.ai/pricing) — primary; funding via [salestools.io](https://salestools.io/en/report/helicone-5m-seed), [trysignalbase.com](https://www.trysignalbase.com/news/funding/helicone-secures-125k-seed-round-...) — UNVERIFIED, aggregator-only
- Not Diamond: [notdiamond.ai/pricing](https://www.notdiamond.ai/pricing) — primary; funding via [finsmes.com, 2024-07](https://www.finsmes.com/2024/07/not-diamond-raises-2-3m-in-funding.html) — secondary
- Martian: [route.withmartian.com/pricing](https://route.withmartian.com/pricing) — primary; funding via [thesaasnews.com](https://www.thesaasnews.com/news/martian-raises-9-million-in-seed-round), [Accenture newsroom](https://newsroom.accenture.com/news/2024/accenture-invests-in-martian-...) — secondary
- Infra pricing: [GitHub Actions billing docs](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions), [supabase.com/pricing](https://supabase.com/pricing), [vercel.com/pricing](https://vercel.com/pricing) — primary

## Programs — Founders Inc and YC (`07-build-plan.md`)

- Founders Inc: [f.inc](https://f.inc/), [f.inc/about](https://f.inc/about), [f.inc/apply](https://f.inc/apply), [f.inc/portfolio](https://f.inc/portfolio), [f.inc/ai-hardware-residency](https://f.inc/ai-hardware-residency) — primary
- YC application timeline: [ycombinator.com/apply](https://www.ycombinator.com/apply) — primary
- YC W27 deadline projection (explicitly labeled estimate, not official): [roundfunded.com/.../yc-application-deadlines-2026-2027](https://www.roundfunded.com/en/blogs/yc-application-deadlines-2026-2027) (2026-07-05) — secondary, UNVERIFIED
- YC blog (checked for W27 announcement, none found as of this research): [ycombinator.com/blog](https://www.ycombinator.com/blog) — primary
- YC Requests for Startups: [ycombinator.com/rfs](https://www.ycombinator.com/rfs) — primary; cycle-dating cross-check via [startup.whatfinger.com, 2026-07-26](https://startup.whatfinger.com/2026/07/26/self-maintaining-apis/) — secondary
- YC Early Decision (ruled out as not applicable): [techcrunch.com, 2025-09-24](https://techcrunch.com/2025/09/24/y-combinator-launches-early-decision-for-students-who-want-to-graduate-first-build-later/) — secondary
- LLM Stats (YC S2025 portfolio precedent): [ycombinator.com/companies/llm-stats](https://www.ycombinator.com/companies/llm-stats) — primary

## Name clearance, checked 2026-08-01 (`10-name-clearance-2026-08-01.md`)

- Domain registration status: registry RDAP records for `searchbench`, `searchref` and
  `retrievalreferee` across `.com` / `.ai` / `.dev` / `.io`, reached through the IANA RDAP bootstrap
  at [rdap.org](https://rdap.org/) — primary (the registry's own record, not a reseller widget).
  Registrar, creation and expiry dates as returned by Verisign, Identity Digital, Google Registry and
  the `.ai` registry on 2026-08-01.
- Repository collisions and `Talc-AI/search-bench`'s licence/activity: [GitHub REST API](https://docs.github.com/rest)
  (`repos/{owner}/{repo}` and repository search) — primary
- Package namespace availability: [pypi.org](https://pypi.org/) JSON API and
  [registry.npmjs.org](https://registry.npmjs.org/) — primary
- Name selection sweep (§6, ~250 candidates over twelve passes): the same four registries as above —
  Verisign RDAP for `.com`, `whois.nic.ai` for `.ai`, Google Registry RDAP
  (`pubapi.registry.google`) for `.dev`, Identity Digital RDAP for `.io` — plus the PyPI, npm,
  GitHub and [Hugging Face](https://huggingface.co/docs/hub/api) APIs, and open web search for
  residual brand presence — primary
- USPTO federal register: **NOT SOURCED — the check was not completed.**
  [tmsearch.uspto.gov](https://tmsearch.uspto.gov/) is behind an AWS WAF challenge,
  [api.uspto.gov](https://api.uspto.gov/) requires an interactively-obtained API key,
  `assignment-api.uspto.gov` no longer resolves, and [tmview](https://www.tmdn.org/tmview/) resets
  its search API. No trademark claim in `docs/10` rests on a source, because there is none.

## Carried forward from earlier research rounds (rounds 9-10 and the Speko/YC correction)

The founder idea search that preceded this gap-closing pass — including the original 27-idea, 8-round search; round 9's 20-idea generate/kill-test pass; round 10's benchmark-focused generalization of the Speko.ai mechanism; and the correction confirming Speko.ai as a real Y Combinator Summer 2026 company (via [ycombinator.com/companies/speko](https://www.ycombinator.com/companies/speko)) — is preserved in full in `founder-idea-search-round9.md`, delivered separately over the course of this project. That file is the complete provenance record for how SearchBench was selected over the other 31+ ideas considered; it is not duplicated here, but should be treated as part of this project's source record.
