# The Residency — answer blocks

**Status:** drafted 2026-08-01. Written house-agnostic, before seeing the real form questions.
Blocks are modular and sized so they can be cut down to whatever limits the form imposes.

Source of truth for facts: `applications/the-residency.md`. Nothing here invents a number that
isn't in that brief.

---

## 0. Before you submit — checklist

These are things the draft depends on that are not yet true or not yet verified.

- [ ] **Full run finished?** The brief says the 150-query run was *in flight*. Every block below
      says "in flight" or hedges. If it has landed, the language gets stronger and the numbers
      should be re-pulled from the completed run rather than the 20-query pilot.
- [ ] **Something public to link to.** This is the single highest-leverage thing you can do before
      submitting. The whole application rests on "it runs, and here's what it found" — but right
      now a reviewer can't check that. A public GitHub repo with the runner and a `results/`
      markdown table would take an hour and converts the strongest claim from assertion to
      evidence. It also matches the build order in CLAUDE.md (runner public early, dashboard
      later) rather than jumping ahead of it.
- [ ] **Name.** "SearchBench" is not cleared — `Talc-AI/search-bench` exists, domain and USPTO
      unchecked. Blocks below use it descriptively, never as a launched brand. Don't let the
      application be the thing that commits you to it.
- [ ] **Full-time / in-person is mandatory.** Cannot be employed or in school concurrently.
      Confirm you can actually commit before submitting.
- [ ] **Equity terms.** Third-party profiles claim the programme takes equity in companies started
      during the residency; the percentage appears nowhere official. Get it in writing before
      signing anything — not before applying.
- [ ] **Deadline.** A secondary source claims fall 2026 applications closed 2026-07-31. Not
      corroborated by any official page, and the site publishes no deadline. Worth a one-line
      email asking whether they're rolling or whether you're aiming at the next cohort.

---

## 1. One-liners

**Ultra-short (~15 words)**

> A neutral, weekly benchmark of the search APIs AI agents run on — and a router built on its scores.

**Short (~40 words)**

> Every company selling search to AI agents publishes its own benchmark, and every one of them
> wins it. I built the neutral one. It's live, it costs $60/month to run, and its first run found
> a 16× cost gap nobody publishes.

**Medium (~90 words)**

> AI agents and RAG pipelines all depend on a web-search API — Exa, Perplexity, Serper, You.com,
> Linkup. Every vendor publishes a benchmark proving it's the best, and every one of them wins its
> own benchmark. There is no neutral measurement anywhere in the category.
>
> I built it: 150 queries across six categories, run against every vendor, scored by three LLM
> judges from three different model families to cancel single-judge bias, published weekly with
> the raw data open. On top sits the business — a BYOK router that picks a vendor per query using
> the benchmark's own live scores. The benchmark is the trust engine; the router is the business.

---

## 2. What I'm building (long form, ~200 words)

Every AI agent that touches the web goes through a search API, and the category has quietly
turned into a real market — Exa, Perplexity, Serper, You.com, Linkup, and a new funded entrant
roughly every two months. Every one of them publishes a benchmark. Every one of them wins the
benchmark it publishes. The market has already decided it wants proof-by-numbers; what doesn't
exist is a number nobody can accuse of being rigged.

I'm building that: a free, public, weekly-refreshed benchmark. Queries spanning six categories
run against every vendor through one normalised envelope, scored by a three-model cross-family
LLM judge ensemble, published as a dashboard with the full raw export so anyone can re-score it
themselves and check my work. Raw responses, per-judge scores and aggregates are stored as
separate layers precisely so the raw layer can be published.

The business sits on top of the trust. LiteLLM recently shipped a unified `/v1/search` endpoint
across 12+ providers — it commoditised the plumbing, but it still makes the developer name the
vendor on every single request. There is no quality signal and no routing logic anywhere in what
shipped. That's the gap: a BYOK routing SDK that answers "which vendor for this query" using the
benchmark's own live scores.

---

## 3. What's already built — the evidence block (~160 words)

This is the block that carries the application. Lead with it wherever the form allows.

> This isn't a plan. I built and verified the whole pipeline end-to-end in a single day.
>
> Five vendor adapters running against live APIs, with verified request/response shapes. A
> normalisation layer mapping every vendor into one envelope at uniform top-10 depth. SQLite
> storage split into three layers — raw responses, per-judge scores, weekly aggregates — kept
> separate from day one because the raw layer is what gets published. A judge ensemble of three
> models, one per model family, for cross-family bias mitigation. A failure-tolerant runner doing
> fetch → judge → aggregate → report. A 150-query set, 25 in each of six categories.
>
> The pilot run — 20 queries × 5 vendors × 3 judges, 300 judgements — is complete. The full run
> is 2,250 judgements and is running now.
>
> It costs roughly $55–70 a month to operate. That's measured, not projected. Cheap enough that
> the public track record accumulates on personal runway whether or not anyone ever funds it.

**Compression to ~60 words if the form is tight:**

> Zero to a working benchmark in one day: five live vendor adapters, a normalisation layer, a
> three-model cross-family judge ensemble, three-layer storage, and a failure-tolerant runner.
> Pilot run complete at 300 judgements; the full 2,250-judgement run is going now. $55–70/month to
> operate, measured. It keeps accruing a public record with or without funding.

---

## 4. The findings — strongest material in the application (~230 words)

Use this anywhere the form asks what you've learned, what's surprising, or what proof you have.

> Three things came out of the first real run that no vendor has an incentive to publish.
>
> **A 16–21× cost-efficiency gap.** Serper scores 8.33/10 on technical queries against
> Perplexity's 9.37 — about 89% of the quality — at roughly 5% of the per-query cost, $0.0003
> against $0.0054. On general factual queries it reaches 98% of the top score. In
> points-per-dollar that's ~28 for Serper against 1.3–1.7 for every other vendor tested. Nobody
> publishes this because nobody selling search benefits from publishing it, and until now no
> neutral party was running the comparison.
>
> **Rankings genuinely reorder by category.** Exa wins or ties 10/10 general-factual queries but
> only 3/10 technical ones. Perplexity is the mirror image at 8/10 technical. Category-aware
> routing has real signal.
>
> **LLM judges carry measurable systematic bias.** Across 100 identical scoring tasks: Anthropic
> 8.75 mean, OpenAI 9.08, Google 9.39 — a 0.64-point spread produced purely by which judge you
> asked. Relative rankings survive, because every vendor faces every judge. But any *absolute*
> score claim moves materially depending on that one choice. That's direct evidence the
> cross-family ensemble is load-bearing rather than decorative, and it's publishable methodology
> on its own — it's a finding about how everyone in AI is currently evaluating everything.

**If you only get one finding:** use the 16–21× cost gap. It's concrete, it's a number, and it
immediately explains why a neutral benchmark is worth existing.

---

## 5. What I was wrong about (~110 words)

Strong answer for "tell us about a time you changed your mind" or "what's the biggest risk."
Most applicants have nothing here. You have something dated to week one.

> The first version of the thesis was "route to the highest-quality vendor." My own benchmark
> killed it. Routing perfectly by category gains about 0.2 points out of 10 — real signal, but far
> too small to build a business on. So the thesis moved: not "we pick the best vendor," but "we
> pick the cheapest vendor that clears your quality bar." That's worth up to ~95% of a team's
> search spend, and unlike a quality claim it's checkable on a billing statement.
>
> I'd rather have found that in week one, from my own data, than in month six from a customer. The
> benchmark is the thing that made finding it cheap.

---

## 6. Why now (~110 words)

> Two things opened at once. First, the category matured enough to have real vendors with real
> pricing and real benchmark marketing — five serious players, all publishing self-scored numbers,
> and two new funded entrants in the last four months. Proof-by-numbers is already the norm; the
> neutral number is the missing piece.
>
> Second, LiteLLM shipped a unified `/v1/search` endpoint across 12+ providers. That commoditised
> the integration layer — which is exactly what makes routing possible — but it deliberately left
> the developer to name the vendor on every request. No quality signal, no routing logic. The
> plumbing arrived; the intelligence didn't.
>
> And the one asset that can't be bought later is elapsed public track record. That clock only
> starts when you start it.

---

## 7. Why The Residency (~180 words)

Adapt the house name once you pick one; nothing below depends on which.

> Runway is the only binding constraint on this project. Not the roadmap, not the technical work —
> the fact that I'm paying rent and vendor API bills out of personal savings while deliberately
> building something free. The Residency removes precisely that constraint: housing and food
> covered, and compute credits that subsidise the exact line item this incurs — judge inference
> and vendor queries. It is unusually literal fit; the thing you provide is the thing I spend money
> on.
>
> The timing is just as clean. A 3–6 month cohort is almost exactly the window in which
> "continuously updated weekly benchmark" stops being a claim and becomes a demonstrated track
> record — 12 to 24 consecutive public runs. That's the one part of this a competitor cannot catch
> up on later, and it's the part that's hardest to fund, because it's free by design and generates
> no revenue while it accrues. Demo day is a hard date to have the public dashboard live against.
>
> I'd arrive with a working runner and leave with a benchmark that has been running in public long
> enough that nobody has to take my word for it.

---

## 8. What I'd do in 3–6 months (~120 words)

> **Weeks 1–4.** Weekly runs going out in public from day one, on schedule, with the raw export
> open. Public methodology page. The judge-bias finding written up properly — it's the piece most
> likely to travel beyond this category.
>
> **Weeks 5–10.** Public dashboard, once there are several real weeks behind it rather than one run
> dressed up as a series. Open the written-consent conversations with the vendors currently held
> back, so the covered set can grow honestly.
>
> **Weeks 11–24.** The router SDK: BYOK, schema-compatible with LiteLLM's `/v1/search` so adoption
> costs an import change, routing on live benchmark scores against a caller-set quality floor.
> First design partners recruited from whoever the benchmark has already attracted.
>
> Demo day target: a benchmark with a real multi-month public history, and a router with users.

---

## 9. Risks, asked and answered (~230 words)

Only use in full if the form asks. Otherwise keep it in your pocket for the interview — the risk
section is much more powerful volunteered in conversation than buried in a text box.

> **Legal exposure is the same surface as credibility.** The router is insulated by BYOK — the
> developer brings their own vendor keys, so I never resell or proxy anyone's API. But the
> *benchmark* has to call vendor APIs with my keys, store results and publish comparisons, and
> several vendors' terms name that directly. So I scoped v1 to the five vendors with no explicit
> anti-benchmarking clause, held back two better-known ones pending a written-consent conversation,
> and publish derived scores rather than vendor content. Managed, not eliminated — and I'd rather
> say that plainly than pretend it's solved.
>
> **BYOK inverts the OpenRouter analogy.** OpenRouter's whole value is one key for every model — it
> removes setup friction. A BYOK search router asks a developer to hold five vendor accounts, which
> is *more* setup than calling one vendor. The router has to be worth that friction, and the
> cost-savings framing is what makes it worth it. That's why finding %5's cost gap mattered so much.
>
> **The market is crowding.** Two new funded entrants in four months. The only durable
> differentiators are demonstrated neutrality and elapsed public track record — neither of which can
> be acquired retroactively. Which is the argument for moving now rather than the argument against
> starting.

---

## 10. Founder / background — NEEDS INPUT

The brief has almost nothing on you personally, and most residency forms have a "tell us about
yourself" or "what have you built before" question that this can't be faked for.

Send me any of the following and I'll write the block:

- Prior projects or things you've shipped — especially anything used by people who weren't you
- Technical background: what you're strongest at, where it came from (degree, self-taught, job)
- Current situation: employed / studying / free to go full-time, and from when
- Location now, and whether you can be in SF/Berkeley/NYC/Berlin
- Anything unusual or non-obvious about your path — these programmes explicitly select on
  "high-agency" and unusual paths, not on credentials
- Links: GitHub, X, personal site

What's already usable from the brief: solo, technically capable across full stack and ML/systems,
no enterprise network, no existing audience, working on personal hardware and rented compute. The
"no audience, no network" part is worth stating rather than hiding — it makes the one-day build
and the $60/month operating cost read as resourcefulness instead of luck.

---

## 11. Interview prep — questions this application invites

1. *How do you make money if the benchmark is free?* → The router. Benchmark is trust; router is
   revenue. See %6's revision — cost savings, not quality deltas.
2. *What stops Exa or Tavily from publishing your benchmark themselves?* → Nothing, and they
   already do. That's the point: their number can't be trusted, and no amount of rigour fixes
   that. Neutrality is a structural asset, not a technical one.
3. *What stops LiteLLM adding routing?* → Honest answer: nothing technical. What they'd lack is the
   score data and the neutrality to be believed. Worth having a real answer here; it's the
   sharpest question in the deck.
4. *Won't vendors just block you?* → Possible. Mitigated by scoping to vendors without
   anti-benchmarking clauses, publishing derived scores, and being useful enough to vendors who
   win categories that blocking is costly.
5. *Why hasn't anyone done this?* → Structurally nobody's incentivised: vendors can't be neutral,
   and neutral parties have no business model. The router is what makes the neutral position
   fundable.
6. *You're solo — what breaks first?* → Distribution. No audience, no network. Which is a real
   reason to want a cohort rather than a cheque.
