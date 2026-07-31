# The Residency — field-by-field answers

Drafted 2026-08-01 against the live form. Fields are in form order, labelled exactly as they
appear. Facts come from `applications/the-residency.md`; nothing here invents a number.

**Form-level constraints observed:**
- Cohort runs **September 7 – November 29, 2026** (~12 weeks, not 3–6 months).
- The header note says not to include links except where specifically asked. Every prose answer
  below is self-contained — no URLs, no "see my GitHub."
- One field is a hard **50-character** limit.
- `[NEEDS YOU]` marks fields I can't write for you. `[CONFIRM]` marks a factual claim I've drafted
  from inference that you must verify before submitting.

---

## ⚠ Resolve these two before you submit

### 1. The cohort dates collide with a Rutgers fall semester

The form is prefilled to `feruz.karimov@rutgers.edu`, your accomplishments answer references
"my first year of college," and the cohort is **Sept 7 – Nov 29** — that is a fall semester
almost exactly. The Residency requires full-time and in-person, and states residents cannot be
simultaneously employed or in school.

This isn't a reason not to apply. But you need a real answer to "what about school?" before an
interview, because they will ask, and "I'll figure it out" reads as not serious. The credible
answers are: you're graduating before September; you're taking a formal leave of absence; or
you've already decided you're leaving. Pick the true one and be ready to say it plainly.

Nothing in the form asks directly, so I haven't written it into any answer — but the
"how much has been full-time" field is where it will surface, and I've drafted that honestly.

### 2. "link to your work" is required and you have nothing public

The field accepts "n/a", but this application's entire strength is *it exists and it already found
something*. Answering "n/a" to "link to your work" while claiming a working pipeline and three
empirical findings is the one combination that reads as unverifiable.

Highest-leverage hour you can spend before submitting: push the runner to a public GitHub repo
with a `results/` markdown table of the pilot numbers. That fills **link to your work** and
**github profile**, converts your strongest claim from assertion to evidence, and matches the
build order in CLAUDE.md (public runner early, dashboard later). It does not require the
dashboard, a domain, or the name being settled.

If you'd rather not publish before the full run lands, say so and I'll rewrite the work-detail
answer to stand entirely on its own — but I'd push back on that.

---

# about you

## what are your 2-3 most important accomplishments, personally or professionally, over the past 3 years?

**[NEEDS YOU]** — the screenshot only shows item 3 ("After moving from Uzbekistan, I finished high
school in the United States. By my first year of college, I was already doing paid full stack
development work for US clients."). Paste items 1 and 2 and I'll tighten all three together.

Two notes on what's visible:

- Item 3 is genuinely strong material — moved countries, finished school in a new language,
  was billing US clients by year one. Don't undersell it. But "I was already doing paid full
  stack development work" is vague where it could be concrete. Numbers land harder: how many
  clients, what did you build, how much did you earn, how old were you. One of those turns a
  claim into a fact.
- If SearchBench isn't one of the three, consider making it one. "Built a working benchmark of
  five commercial search APIs — five live adapters, a three-model judge ensemble, 300 scored
  judgements — in a single day, and it surfaced a 16× cost gap none of the vendors publish" is
  the most recent and most relevant thing you've done, and it makes the rest of the application
  read as continuous with your history rather than a new hobby.

## what is one thing only you believe?

Your current answer:

> The best proving ground for AI agents is not Silicon Valley. It is markets like Uzbekistan,
> where data is sparse, workflows live in Telegram, and software survives only if it actually
> works. An agent that succeeds there has passed a harder test than any benchmark.

This is the best-written thing on the form. It's specific, it's yours, and nobody else in the
pile will write it. Keep the first three sentences exactly as they are.

**One problem: the last sentence argues against your own project.** You're applying with a
benchmark, and the closing line is "harder test than any benchmark." A reviewer reading the
application front-to-back hits that contradiction. Worse, it's the sentence right before they
read what you're building.

The fix is small, because the underlying belief is actually the *same* belief — you care about
tests that can't be gamed, which is exactly why you noticed every search benchmark in the market
is written by the vendor it flatters. Two options:

**Option A — keep the belief, remove the contradiction (recommended):**

> The best proving ground for AI agents is not Silicon Valley. It is markets like Uzbekistan,
> where data is sparse, workflows live in Telegram, and software survives only if it actually
> works. What I took from building there is that most software gets graded by whoever sells it.
> Real tests are the ones the seller can't set.

**Option B — keep yours verbatim, and change one word:**

> ...has passed a harder test than any vendor's benchmark.

Option A is stronger because it converts a nice line into the thesis of your whole application.
Option B is a one-word patch if you'd rather not touch it.

## what's your #1 book recommendation / favorite book?

**[NEEDS YOU]** — has to be a real answer. Only advice: pick the one you'd actually argue about
for twenty minutes, not the one that signals well. Everyone picks the signalling one.

---

# your work

## what's your ultimate vision you're building towards

Three registers — pick by how grand you want to sound next to "making life multiplanetary."

**A — infrastructure framing (recommended):**

> An independent measurement layer for AI infrastructure. Right now every component of the AI
> stack is graded by the company selling it. I want the numbers that decide what gets built on
> to come from someone with nothing to sell, starting with where agents get their facts.

**B — consequence framing:**

> AI agents are becoming how most people reach most information, and the choice of which agent
> reads what is currently made on marketing. I want that choice made on public, reproducible
> evidence — and I want the measurement to be free, so that being neutral doesn't have to be a
> luxury.

**C — short and blunt:**

> Nobody should have to take a vendor's word for how good its AI is.

## describe what you're building or investigating in 50 characters or less

Counted exactly. Pick one:

| Chars | Text |
|---|---|
| **45** | `Neutral benchmark + router for AI search APIs` |
| 43 | `Neutral scores + routing for AI search APIs` |
| 41 | `The unrigged benchmark for AI search APIs` |
| 40 | `The neutral benchmark for AI search APIs` |
| 39 | `Independent benchmark of AI search APIs` |

Take the 45. It's the only one that contains both halves of the business, and this field is the
first thing anyone reads about your work.

## add any details that we might be interested in that you couldn't fit in 50 characters

This is the most important text box on the form. Structure: what's broken → what I built → what it
found → what that changed.

> Every AI agent that touches the web goes through a search API — Exa, Perplexity, Serper,
> You.com, Linkup. Every one of those vendors publishes a benchmark, and every one of them wins
> the benchmark it publishes. The market has already decided it wants proof-by-numbers. There is
> no neutral number anywhere in the category.
>
> I built one. Five vendor adapters running against live APIs, normalised into a single response
> envelope at uniform depth. A 150-query set across six categories. Every result scored by three
> LLM judges drawn from three different model families, because a single judge is not trustworthy
> — more on that below. Raw responses, per-judge scores and aggregates stored as three separate
> layers, specifically so the raw layer can be published for anyone to re-score and check my work.
> Adapters through report ran end-to-end in one day. The pilot is 300 judgements and is complete;
> the full run is 2,250 and is going now. It costs $55–70 a month to operate, measured rather than
> projected — cheap enough that the public record accumulates on personal runway whether or not
> anyone funds it.
>
> Three things came out of the first run.
>
> Serper returns about 89% of Perplexity's quality on technical queries at roughly 5% of the cost
> — $0.0003 against $0.0054 per query — and 98% of the top score on general factual ones. In
> points per dollar that's about 28 for Serper against 1.3 to 1.7 for everyone else. A 16–21×
> efficiency gap that no vendor has any incentive to publish.
>
> Rankings genuinely reorder by category. Exa wins or ties 10 of 10 general-factual queries but
> only 3 of 10 technical ones. Perplexity is the mirror image at 8 of 10 technical.
>
> And the judges themselves are biased. Across 100 identical scoring tasks, the Anthropic judge
> averaged 8.75, OpenAI 9.08, Google 9.39 — a 0.64-point spread produced by nothing but which
> model was asked. Relative rankings survive because every vendor faces every judge, but any
> absolute claim moves depending on that one choice. That's a finding about how the entire
> industry currently evaluates everything, not just about search.
>
> The second finding is what pays for the first. A free benchmark isn't a business, so the
> business is a routing SDK that picks a vendor per query from the benchmark's live scores. It's
> bring-your-own-key — the developer supplies their own vendor credentials and I never resell or
> proxy anyone's API, which is both the only structure the vendors' terms permit and the only one
> that keeps the benchmark credibly neutral.

*(If the box is visibly short, cut the last paragraph and the category-reordering finding. Never
cut the cost gap or the judge bias — those are the two things nobody else can say.)*

## link to your work (if available, n/a if you don't have one) — REQUIRED

See the warning at the top. Strong preference: a public repo. Fallback if you truly won't publish
before submitting, since the field is required:

> n/a — the runner and results aren't public yet. I'm publishing the repo and the first full
> week's results before the benchmark goes live rather than after, so the methodology is
> inspectable from the first run.

## demo video (if available, n/a if you don't have one) — REQUIRED

`n/a` is acceptable here. But a 60-second unlisted screen recording of the runner executing and
the report printing would do more for this application than any sentence in it — it's the
cheapest possible proof that the thing runs. Consider it if you have an hour.

## github profile / linkedin / x/twitter / personal website

**[NEEDS YOU]** — LinkedIn is required, `n/a` if none.

---

# why this idea

## why did you pick this to work on? (be concise)

This one must be personal, not analytical — they're asking what drew *you*, and the market
argument belongs in the next question. Draft:

> I was putting agents in front of the web and had to pick a search API. Every number available
> was published by a company selling one of the options. So I spent a day building the
> measurement instead of picking on vibes — and found nobody else had one either.

**[CONFIRM]** — I've inferred that you actually hit this problem while building agents or
retrieval for clients. If that's not true, say so and I'll rewrite it around whatever the real
trigger was. It must not be a story you didn't live; this is exactly the kind of detail an
interviewer pulls the thread on.

## how do you know the world needs what you're making? (be concise)

> - Every vendor in the category publishes a comparison benchmark as marketing — Tavily, Seltz,
>   Search Router, Quercle, fastCRW. Buyers are asking for numbers; they're getting them from
>   interested parties.
> - LiteLLM shipped a unified search endpoint across a dozen providers, then made the developer
>   name the vendor on every request. No quality signal, no routing logic. The integration problem
>   got solved; the decision problem didn't.
> - I ran the benchmark once and it found a 16× quality-per-dollar gap between vendors marketed as
>   comparable. A measurement that valuable on day one wasn't being taken.

---

# progress

## key traction metrics, use bullet points (be concise)

Five bullets, findings first-class rather than buried. The build details (150 queries, six
categories, normalisation layer) live in the work-detail box already — repeating them here dilutes
the two numbers that actually land.

> - Zero to a working benchmark in one day — 5 live vendor adapters, 3-model cross-family judge
>   ensemble, full fetch → judge → aggregate → report pipeline
> - 300 scored judgements complete; 2,250-judgement full run in flight
> - Found a 16–21× quality-per-dollar gap between vendors marketed as equivalent — a comparison
>   no vendor has an incentive to publish
> - Measured a 0.64-point systematic bias between LLM judge families across 100 identical scoring
>   tasks — evidence that single-judge evaluation, which is what most of the industry runs, is
>   partly measuring its own choice of judge
> - $55–70/month to operate, measured not projected — runs indefinitely on personal runway

No "no users, no revenue" bullet: the form already asks both as yes/no fields immediately below,
so stating it here reads as padding rather than candour.

## how long have you been working on this, and how much has been full-time, if any?

**[CONFIRM]** — the brief dates the build to a single day (2026-08-01). If there was research or
thinking time before that, tell me and I'll adjust. Honest draft as written:

> The research and vendor-terms work came first; the code is one day old. I built the adapters,
> the normalisation layer, the storage schema, the judge ensemble and the runner on July 31st and
> completed the pilot run the same day. None of it has been full-time — it's been built around
> school, which is exactly the constraint I'm trying to remove.
>
> I'd rather show you what one focused day produced than claim months of part-time work. The
> point isn't that it's finished. The point is that the expensive part — the measurement
> infrastructure — already exists and already works, so what a full-time block buys is the one
> thing that can't be rushed, which is elapsed weeks of it running in public.

*(That last paragraph is doing real work — it reframes "one day old" from a weakness into your
central argument for the residency. Don't cut it.)*

## what are your goals for the next 6 months?

Outcomes, not a calendar. The revenue target is grounded in `docs/06-business-model.md`'s
recommended $29–49/month indie tier (modelled on Portkey and Helicone), not invented.

> - Weekly benchmark running uninterrupted in public, no missed weeks, raw data published every run
> - Public dashboard live, with an open export anyone can re-score
> - Router SDK shipped and charging by month two
> - 20 paying teams by month six, at $29–49/month
> - The cost-savings claim validated on real customer invoices

**[CONFIRM]** — "20 paying teams" is my number, not yours. It's ~$600–1,000 MRR, which is credible
for a solo founder with no audience shipping a developer tool. Raise it if you think you can
defend a bigger one; they will ask how you got there. Don't lower it — anything smaller stops
reading as a goal.

---

# similar work

## who are your main competitors?

> - The vendors themselves. Tavily, Seltz, Search Router, Quercle and fastCRW all publish
>   benchmarks against their rivals, and each one wins its own.
> - LiteLLM. Its unified search endpoint already commoditised the integration layer across a dozen
>   providers; routing on top is the natural next step and nothing technical stops it.
> - Two new funded entrants in the last four months.

## what do you understand that they don't?

The best question on the form for you, because your answers are measurements rather than opinions.

> - Everyone competes on answer quality. I measured what perfect quality-based routing is worth:
>   0.2 points out of 10.
> - The axis nobody advertises is cost — a roughly 16-fold spread in quality-per-dollar between
>   vendors positioned as equivalent.
> - My first thesis was "route to the best vendor." My own data killed it in a week. It's now
>   "route to the cheapest vendor clearing your quality bar."
> - LLM judges disagree by 0.64 points systematically across model families. Single-judge
>   evaluation — what most of the industry runs, vendors included — partly measures its own choice
>   of judge.
> - A vendor's benchmark can't be fixed with better methodology. The problem is who holds the pen.

---

# equity / past programs

Already answered on the form and all consistent — no entity, no investment, not fundraising, no
prior accelerators. **what is the planned equity breakdown among founders?** is showing as
required: you're solo, so `100% — solo founder, no entity formed yet` is the answer. If you're
seriously looking for a cofounder, `100% currently; solo and actively looking for a cofounder`
is more accurate and matches your "looking for a cofounder: yes."

---

# how you found us

## who or what inspired you to apply?

Draft built only on what's already true: you marked "twitter" as how you heard about it, you're
solo, and you're looking for a cofounder. Deliberately says nothing about cost or funding.

> Twitter. Three months of full-time focus is exactly the window that turns my benchmark from a
> working system into a public track record — and that's the part nobody can buy back later. I'm
> also solo and looking for a cofounder; living with people building hard things beats cold DMs.

**[NEEDS YOU]** — if a specific person, post, or resident actually prompted this, name them and
lead with it. A concrete "I read X's write-up of their cohort" beats any reasoning I can supply
here, because it's the one thing that proves you didn't mass-apply.

---

## Still needed from you

1. Accomplishments 1 and 2 (item 3 is visible and good)
2. Favourite book
3. Who/what inspired you to apply
4. LinkedIn, GitHub, X, website — or `n/a`
5. **[CONFIRM]** Did you actually hit the "which search API?" problem while building for clients?
6. **[CONFIRM]** Is one day the true age of the project, including research?
7. Your answer on school vs. a Sept 7 – Nov 29 full-time cohort
8. Decision on publishing the repo before submitting
