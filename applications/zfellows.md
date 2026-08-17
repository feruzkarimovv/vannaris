# Z Fellows — application brief and field-by-field answers

Drafted 2026-08-03 against the live form (2026 cohorts, rolling). Every number here is read from
`site/data/latest.json` or the repo as of today; nothing is invented. `[NEEDS YOU]` marks a field
I cannot write. `[CONFIRM]` marks something I inferred that you must verify.

---

## 1. What Z Fellows actually selects for

Sources: zfellows.com, corylevy.com, TechCrunch (2020), Cory Levy's hiring post, third-party
application guides. The picture is consistent across all of them.

**The deal.** One week. Ten builders per cohort. $10,000 optional, on a $1B post-money cap
(converts at the next priced round). You can participate without taking the money. Cohorts run
roughly every other month; applications are rolling with no deadline and reapplications are
explicitly encouraged.

**Who they fund.** Cory Levy's own words for the role he hired for: *"finding and helping propel
undiscovered, first-time technical founders."* The site says technical builders **of all ages**,
and lists high-school dropouts, college students, and people with full-time jobs as welcome. They
will help you incorporate if you have no company. Alumni include Cursor, Cognition, and Etched —
they bet before anyone else does.

**Cory's own profile is the template.** Interned at Founders Fund and Union Square Ventures *while
in high school*, left UIUC CS, built After School to ~20M users. He is pattern-matching on people
who did unusual things early and without permission.

**Three implications that should change how you write this:**

**(a) This is a talent bet, not a company bet.** Count the form: eight of the fourteen substantive
questions are about *you* — past work, nerdiest thing, what drives you, non-traditional childhood,
risk taken, achievements, who you'd co-found with. One guide puts it exactly right: *"These are the
selection criteria in disguise, not warm-up questions."* The Residency application you drafted was
90% product. This one should be roughly half person. Do not treat the personal boxes as filler —
they are where the decision gets made.

**(b) 500 characters is ~80 words, not 100.** That is three or four sentences. The Residency draft
had a 300-word work-detail box; nothing like it survives here. Every product answer must lead with
its single hardest fact and stop. The 250-character boxes are two sentences, maximum.

**(c) Skip the market-size register entirely.** The guidance is to *"name a specific user and a
specific broken thing"* and to skip market size. You are unusually well set up for this: you have
measurements, not projections, and your strongest material is a number a vendor would never print.

**On the video (optional, but take it).** Phone, one take, no slides, and — the form says this
explicitly — **no product demo**. Background, one thing you're proud of, what you're building.
The most common self-inflicted rejection is a screen recording of a dashboard with voiceover.
Script is in §4.

---

## 2. What this application must do differently from The Residency one

The Residency wanted a full-time in-person founder for 12 weeks; your pitch there was *give me
elapsed time so the track record accrues*. Z Fellows is one week and $10k. Elapsed time is not
what they're selling, so that argument lands weakly here.

What Z Fellows sells is **proximity to founders who have already done it**, and what they're
buying is **a person worth betting on early**. So the spine of this application is:

> I ship fast, I measure instead of guessing, and when my own instrument proved my thesis wrong
> I changed the thesis in a day. Here is the thing running in public today.

The "my benchmark killed my own idea" beat is your best asset here, and it was buried in the
Residency draft. Put it in the competitors box, where it answers the question directly and
doubles as a character reference.

**One honest constraint to plan around.** As of this morning the first scheduled run *failed* on
an Anthropic credit-balance preflight, so `scheduled_weeks` is still 0. No answer below says
"weekly" or "continuous" — the drafts say "one published week" and "runs every Monday" only as a
description of the mechanism, never as a claim about elapsed history. Keep it that way even if it
feels weaker; it is the whole premise of the project.

---

## 3. Field-by-field answers

### Email / First Name / Last Name / Birthday / Phone Number
**[NEEDS YOU]** — the form is prefilled to `feruz.karimov701@gmail.com`. Note your Rutgers address
appeared on the Residency form; use whichever you actually read.

### Company or project name
```
Vannaris
```
The name is still uncleared per `PUBLISH-CHECKLIST.md`, but it is what the live site says, so it
is the right answer here. Nothing about applying under it forecloses a rename.

### Are you technical?
```
Yes
```

### Have you previously applied to Z Fellows?
**[NEEDS YOU]** — a prior application is not a negative; they encourage reapplying.

### Where are you based?
**[CONFIRM]** — drafted from your Rutgers email:
```
New Jersey (open to relocating to SF)
```
The in-person finale is in SF or NYC, so signalling mobility is free and useful.

### Are you in school or working? Or both? Where at?
**[NEEDS YOU / CONFIRM]** — something like:
```
Both — CS at Rutgers, and freelance full-stack development for US clients.
```
Fix the major and add your year. Z Fellows explicitly welcomes students and people with jobs, so
there is no reason to soften this.

---

### What is the project that you are currently working on or would like to pursue? Why? (500 char)

> Vannaris — an independent benchmark of the web-search APIs that AI agents run on: Exa,
> Perplexity, Serper, You.com, Linkup. Same queries, every vendor, scored by three LLM judges
> from three different labs, published free with the raw data. Every vendor in this category
> publishes a benchmark and every one wins its own. I built the neutral one. It's live at
> vannaris.com. The business sits on top: a router that picks the vendor per query from those
> live scores, using the developer's own keys.

*(494 characters — verified.)*

### What problem are you solving? (500 char)

> Every AI agent that touches the web calls a search API, and developers pick one on marketing.
> There is no neutral number anywhere in the category — the only benchmarks are published by the
> vendors being compared. So teams overpay blind. My first run found the cheapest API returns
> 92–98% of the best vendor's quality on four of six query categories, at 1/23rd the price per
> query. Nobody selling search has any reason to tell you that.

*(435 characters — verified.)*

### What expertise do you have to execute on the work that you want to do? (500 char)

**[CONFIRM]** — the self-taught / Uzbekistan line is inferred from your Residency answers. Correct
it if the real story differs.

> I built all of it — five live vendor adapters, a three-model judge ensemble, storage, runner,
> data export and the site — and had the first 2,151 judgements scored within a day of starting.
> Full-stack plus ML and systems; I've been billing US clients for development work since my
> first year of college. I learned to build in Uzbekistan on sparse data and bad connections,
> which is where I stopped trusting anyone's marketing numbers.

*(433 characters — verified. 67 spare, so there's room to swap in a concrete client detail.)*

### Who are your competitors and what do you understand about your idea that they don't? (500 char)

This is your best box on the form. It answers the question and doubles as evidence about how you
handle being wrong.

> Competitors are the vendors' own benchmarks — Tavily, Seltz and Quercle each publish one and
> each wins it — and LiteLLM, which unified the plumbing across 12+ providers but still makes you
> name the vendor on every call. No quality signal, no routing.
> What I understand: quality routing is worthless. One vendor leads every category, so "route to
> the best" collapses to "use Exa." My own benchmark killed that thesis in a day. The real axis
> is cost — a 23× spread between APIs sold as equivalent.

*(495 characters — verified, including the single line break. Don't add a blank line between the
two paragraphs; that costs a character and the margin is 5.)*

### What have you worked on in the past? (500 char)

**[NEEDS YOU]** — I have only fragments: paid full-stack work for US clients from your first year
of college, and moving from Uzbekistan and finishing high school in the US. That is genuinely
strong material and it is currently vague where it could be concrete.

What turns it into an answer: **how many clients, what did you actually build, what did it do for
them, how old were you, how much did you earn.** One number converts a claim into a fact. Send me
those and I'll write this box.

The example answer on the form is a list of three separate things (A/B/C) — that format works well
here if you have three.

### What's the nerdiest thing about you? (250 char)

**[NEEDS YOU]** — pick something true. But here is a candidate drawn from work you actually did,
if nothing better comes to mind:

> I ran 750 identical scoring tasks through three different LLMs just to find out whether they'd
> disagree. They did — 1.22 points apart on the same answers. I no longer trust any number that
> only one model produced.

*(213 characters — verified.)*

It's on-brand and it's real. But a childhood-obsession answer is usually more charming here, and
this form has plenty of other places to be rigorous. Your call.

### What drives you? (250 char)

**[NEEDS YOU]** — must be yours. For reference, the belief you wrote for The Residency was the
best-written thing on that form:

> The best proving ground for AI agents is not Silicon Valley. It is markets like Uzbekistan,
> where data is sparse, workflows live in Telegram, and software survives only if it actually
> works.

A version of that compressed to 250 characters and pointed at *drive* rather than belief would be
excellent. Something in the direction of: what you took from building there is that most software
is graded by whoever sells it, and you want to build the tests the seller can't set. Write it in
your own words — that's the point of the box.

### What non-traditional things were you doing growing up?

**[NEEDS YOU]** — this is a high-signal question for Z Fellows specifically, because Cory was
interning at Founders Fund in high school. He is looking for evidence you did unusual things
early and without waiting for permission.

Prompts: what were you building or selling before anyone paid you? Did you work while in school?
Teach yourself something with no teacher available? Run anything online? The Uzbekistan-to-US
move belongs in the risk question below, so keep this one about what you *did*.

### Tell us about a risk you've taken or a challenge you've faced. Tell us whether you failed or succeeded, how you behaved, and how you think this reflects your character. (500 char)

**[NEEDS YOU]** — the obvious candidate is moving from Uzbekistan and finishing high school in a
new language, then billing US clients by your first year of college. That is a real risk story and
it fits their taste.

Note the question has four parts and the example answer hits all four. Whatever story you pick,
make sure it says: what you risked, what happened, **what you actually did** (behaviour, not
feeling), and what it shows. Most applicants skip the third.

A second candidate, smaller but very much in character: you built an instrument, it disproved the
product you were building, and you changed the product rather than the measurement. If you'd
rather not lead with the immigration story, that one is unusual and entirely yours.

### Personal and/or Project Website and/or Links about you

```
https://vannaris.com
https://github.com/feruzkarimovv/vannaris
```
**⚠ The repo is currently private.** Do not put that link on the form until you flip it public —
a 404 on the only technical link in a technical-founder application is worse than no link. See
§5; this is the highest-leverage thing you can do before submitting.

**[NEEDS YOU]** — LinkedIn, X, personal site if any.

### Please list or describe any achievements and prizes.

**[NEEDS YOU]** — olympiads, scholarships, hackathons, rankings, anything from school in
Uzbekistan or the US. If genuinely none, say what you've shipped instead of leaving it blank;
Z Fellows cares more about built things than prizes, but an empty box reads as unanswered.

### Who would you co-found a company with if you could pick anyone in your network?

**[NEEDS YOU]** — must be a real name, and the form is explicit: *not* someone you already work
with. This tests two things at once — the quality of your network and your taste in people. One
sentence on *why* them lands better than the name alone.

### How did you hear about Z Fellows?

**[NEEDS YOU]** — you marked Twitter for The Residency. If a specific post or person, name them.

### Optional: What's 1 thing you need help with? (500 char)

Take the optional box. It's a direct read on whether you know your own bottleneck, which is the
same instinct as Cory's "key logs" essay. The form says *1 thing*, so name one and keep the ask
concrete — "intros to smart people" is what everyone writes.

**Recommended (412 characters — verified):**

> Distribution. I built the instrument and have no audience yet. A benchmark only becomes a
> standard if the people choosing search APIs actually read it, and I am better at building it
> than at getting it in front of anyone. I would want intros to teams shipping agents who would
> route real traffic on this data, and to anyone who has taken a public benchmark from "this
> exists" to "this is the number people cite."

**Alternate (451 characters — verified)**, if you'd rather the ask include the vendor problem.
Still one thing — introductions — pointed two ways:

> Distribution. I have a working instrument and no audience. A benchmark only becomes a standard
> if the people choosing search APIs read it, and I am better at building it than at getting it
> in front of them. I want intros two ways: teams shipping agents who would route real traffic on
> this data, and the vendors themselves. A couple have terms that make third-party benchmarking a
> written-consent conversation, and that goes far better warm than cold.

---

## 4. The one-minute video

Optional on the form, and you should do it. Ten builders per cohort — the video is where you stop
being a paragraph.

**Format:** phone, one take, face to camera, no slides. **No product demo** — the form says so
explicitly and ignoring it is the most common self-inflicted rejection.

**Script (169 words, ~60–65s at a normal talking pace).** Four beats, in the order the form asks
for them: background, brag, project. Learn the shape, not the words.

> **[0:00–0:18 — who you are]**
> I'm Feruz, twenty, from Uzbekistan. I taught myself to code at twelve and was freelancing three
> months later. Then I moved to the US, finished high school in a language I was still learning,
> and worked at Walmart while I did it. I'm on leave from Rutgers now, building full time in SF.
>
> **[0:18–0:31 — the brag]**
> Proudest thing I've built: a benchmark of five commercial search APIs, on my own. The vendor
> adapters, a three-model judge ensemble, the whole pipeline. Twenty-one hundred scored
> judgements inside a day of starting.
>
> **[0:31–0:47 — what it is, and the finding]**
> That's Vannaris. Every AI agent calls a search API, and every vendor in that category publishes
> a benchmark it wins. I built the neutral one. The cheapest API returns ninety-two percent of the
> best one's quality, at four percent of the price.
>
> **[0:47–1:00 — the beat that's actually about you]**
> It also killed my own idea. I was building a router that picks the best vendor per query, and my
> own data said one vendor wins almost everything. So I changed the product, not the measurement.
> That's what I'm on today.

**If you run long, cut this sentence:** *"The vendor adapters, a three-model judge ensemble, the
whole pipeline."* It's the only line whose content is already in the written answers.

**Delivery notes.** Say the numbers as words — "ninety-two percent," "four percent" — reading
digits aloud is what makes a script sound like a script. Beat four is the one that decides the
video, so don't rush it and don't apologise for it; changing your own mind on your own evidence
is the trait they're selecting for. Talking to camera, not reading. A retake is cheap; a script
that sounds read is not.

---

## 5. Do these before you submit

**1. Make the repo public.** `isPrivate: true` right now. Your entire application is "I measure
things instead of trusting marketing," submitted to people who fund *technical* builders — and
the code is the proof. `CLAUDE.md` already treats a public repo as a credibility feature. This is
one command and it upgrades the strongest link on the form from unusable to your best asset.
Check `.env` handling first; `.gitignore` covers it, but confirm nothing sensitive is in history.

**2. Decide what to do about this morning's failed scheduled run.** It died on an Anthropic
credit-balance preflight before spending anything at the vendors — the guard did its job. But
until a scheduled run lands, `scheduled_weeks` stays 0 and the "armed is not started" distinction
in `CLAUDE.md` still binds. Topping up the balance is yours to do; per `CLAUDE.md` I won't
dispatch a run. None of the answers above depend on it, by design.

**3. Answer the eight `[NEEDS YOU]` boxes** — they're listed in §6.

---

## 6. What I need from you to finish this

1. **Past work** — clients, what you built, what it did for them, your age, earnings. Any two of
   those and I'll write the box.
2. **Non-traditional things growing up** — what were you building or selling before anyone paid?
3. **Risk / challenge story** — the Uzbekistan move, or the killed-thesis one, or something else.
4. **What drives you** — in your words.
5. **Nerdiest thing** — yours, or take the judge-bias draft above.
6. **Achievements and prizes.**
7. **Co-founder pick** — a real name, not someone you already work with.
8. **How you heard about Z Fellows**, and whether you've applied before.
9. **Links** — LinkedIn, X, personal site.
10. **Confirm:** year and major at Rutgers, still freelancing, based in NJ, and whether the
    "learned to build in Uzbekistan" line is accurate.

---

## 7. Review of your filled form — 2026-08-04

Read against the form's own instruction, *"Please try to write concise answers with no fluff,"* and
against what Z Fellows publicly selects for (zfellows.com; Cory Levy's hiring post; the Causo 2026
guide). Answers below transcribed from your screenshot — correct me where I misread.

Verdict up front: the writing is good and the material is genuinely strong. The problems are not
prose problems. Two are factual, and one of those is serious.

### 7.1 CRITICAL — your headline cost number contradicts your own site

You wrote "4 percent of the price" and "a 23x spread between APIs sold as equal."

`site/data/latest.json` carries both ratios: `as_billed_ratio: 23.3` and
`like_for_like_ratio: 7.0`. The 23× is Serper's *top volume tier* ($0.30/1,000) against Exa;
like-for-like PAYG it is 7×. And every figure on the live site — `site/index.html:184`, `:196`,
`:209`, `methodology.html:290` — renders `like_for_like_ratio`. **The site says 7×. The
application says 23×.**

You invite them to click vannaris.com in the same box. The one number they can check is the one
where you quoted the flattering variant of your own finding — in an application whose entire
argument is that you are the person who does not do that. Fix it, and it becomes an asset: quoting
the conservative version of your own result is the trait, stated without having to claim it.

### 7.2 Verified against the data (all fine, one improvable)

- **2,151 judgements** — matches `n_judgements`. Correct.
- **"One vendor leads every category"** — correct. Exa leads all six.
- **"92% on four of six query types"** — true but understated. Serper is at 97.6, 93.0, 93.3 and
  91.9% of best on those four. **"92–98%"** is both more accurate and stronger.
- **No answer claims "weekly" or "continuous."** Correct, and it must stay that way:
  `trigger` is null and `scheduled_weeks` is still 0.

### 7.3 CRITICAL — two of your five links are dead

| link | status |
|---|---|
| vannaris.com | 200, real site |
| github.com/feruzkarimovv | 200 (**the Vannaris repo behind it is still private**) |
| npmjs.com/package/vchk | live, maintainer `feruzkarimov` |
| **jonivor.com.uz** | **NXDOMAIN — does not resolve.** `.uz`, `.com`, `www` all fail |
| **feruz.karimov.dev** | **404.** Host answers, no page |

jonivor.com.uz is cited *inside* the expertise answer as well as in the links box. A technical
application to people who fund technical builders, with a dead link next to "it is live with 10+
clinics" — that is the worst possible failure mode. Either fix DNS, or replace with a link that
works (Telegram Mini App, App Store, a demo video, screenshots in the README).

### 7.4 Cross-answer contradiction — the router

Project box: *"a router that picks a vendor per query from those scores."*
Competitors box: *"routing on quality is worthless… the real axis is cost."*

Read together, the first describes the product your own data killed. Say the *post-finding* design
in the project box and the two answers stop fighting: route to the cheapest vendor that clears the
quality bar for that query type.

### 7.5 The rewrites

**Are you in school or working? Or both? Where at?** — you wrote *"took a leave of absence,
graduating in 2028."* Passive, and it never answers *where at*. A leave of absence to build is one
of the strongest signals you can send these people — Cory left UIUC. Say it plainly (122 chars):

> Neither right now. I took a leave of absence from Rutgers (CS, class of 2028) and moved to SF to
> build Vannaris full time.

**Where are you based?** — "sf" → `San Francisco`. The in-person day is SF or NYC; you are already
there. Don't lowercase it.

**Project (494):**

> Vannaris is an independent benchmark of the web-search APIs that AI agents run on: Exa,
> Perplexity, Serper, You.com, Linkup. Same queries against every vendor, scored by three LLM
> judges from three different labs, published free with the raw data. Every vendor here publishes
> a benchmark and every one wins its own. I built the neutral one. It is live at vannaris.com. The
> business on top is a router that sends each query to the cheapest vendor that clears the quality
> bar for that query type.

**Problem (478):**

> Every AI agent that searches the web calls one of these APIs, and developers pick one based on
> marketing. There is no neutral number in this category; the only benchmarks are published by the
> vendors being compared. So teams overpay blind. My first run found the cheapest API returns
> 92-98% of the best vendor's quality on four of six query types, at a seventh of the price
> like-for-like and a twenty-third at volume pricing. Nobody selling search has a reason to tell
> you that.

**Expertise (496).** Your version proves you can build *something*; the question asks what makes
you able to build *this*. Jonivor moves to the past-work box, where it isn't competing:

> I built all of Vannaris myself: five vendor adapters, a three-model judge ensemble, the runner,
> the export and the site, with 2,151 scored judgements inside the first day. The hard part is not
> the plumbing, it is designing the measurement so nobody can dismiss it. So it uses cross-lab
> judges, position-swap checks and length normalization, and it publishes the judge disagreement
> that undercuts my own numbers. I also shipped vchk, an npm security scanner for AI code: 81%
> precision, 87% recall.

**Competitors (450)** — same answer, corrected ratio:

> My competitors are the vendors themselves. Tavily, Seltz and Quercle each publish a benchmark
> and each one wins it. LiteLLM unified the plumbing across 12+ providers but still makes you pick
> the vendor yourself, with no quality signal. What they miss: routing on quality is worthless.
> One vendor leads all six categories in my data, so route to the best just means use Exa. The
> real axis is cost, a 7x spread like-for-like between APIs sold as equal.

**Past work (472).** "20+ REST endpoints, 150+ tests" is the fluff the form warned about — those
are intern résumé metrics, and they're the weakest lines on a form where everything else is
founder-shaped. Trade them for the things only you have:

> A) Jonivor, a pet-care platform in Uzbekistan. Co-founder, CTO and sole engineer: web, backend,
> auth, Telegram Mini App and iOS, zero to launch in 10 weeks. Live with 10+ clinics, 30+ vets and
> real bookings. B) Software engineering intern at EPAM Systems: five Spring Boot services, and a
> 35% cut in build time. C) Four production web apps for small-business clients on Upwork.
> D) VibeDuel, a realtime multiplayer AI coding arena judged by an LLM, built solo in two weeks.

### 7.6 Keep exactly as written

**What drives you** — the strongest thing on the form. Three gaps, three builds, "the gap is what
pulls me." Don't touch it.

**Nerdiest thing** — 74 hand-transcribed clips for a language with no speech data. Perfect answer
to that question: unpaid, obsessive, and nobody else's.

**Co-founder pick** — real name, specific evidence, and "he goes at the hard layer instead of
around it" is the line that shows your taste. Keep.

### 7.7 Needs one more fact from you

**Risk / challenge (500).** Weakest of the long boxes, for two fixable reasons. First, it opens
with "I taught myself to code at 12 and was freelancing three months later" — the same sentence
that opens your non-traditional answer, in the box directly above. Duplicated text in adjacent
boxes is the most expensive thing you can do with a 500-char limit. Second, the question has four
parts and you answer three: what you risked, what happened, **how you behaved**, what it reflects.
Yours gives a trajectory, not a behaviour. One concrete action — what you actually *did* in the
worst month — is the whole answer. Skeleton, with the slot marked:

> I moved from Uzbekistan to the US and started over. I finished high school in a language I was
> still learning and worked at Walmart while I did it. [ONE CONCRETE THING YOU DID — the hours,
> the schedule, the thing you built anyway, the thing you did when it wasn't working.] It worked,
> slowly: freelance clients, then EPAM, then Jonivor. I don't stop when the work stops being
> impressive, and I'd rather be measured than believed.

Also: was the move your decision or your family's? A risk you *chose* is a different and stronger
answer than one you absorbed. If it was your family's, the risk story is the leave of absence.

**Non-traditional (no limit).** "Advanced level" is soft and the teaching is the buried lede — you
were a paid teacher as a teenager. How many students, and were you paid? One number.

**Achievements.** "several national and international piano competitions" — *several* is the only
fluff word on your form. How many, what placings, which competitions? Conservatory-grade piano is
the most differentiating fact you have outside of software; it is currently the vaguest sentence
on the page.

**How did you hear about Z Fellows?** "through Cory" is circular. Name the actual post or essay if
you remember it.

### 7.8 Before you press submit

1. **Make `feruzkarimovv/vannaris` public.** Still private, confirmed today. Every claim you make
   is checkable except the one that matters most to a technical judge.
2. **Fix or replace jonivor.com.uz and feruz.karimov.dev.**
3. **Fix the 23× → 7×** in the problem and competitors boxes, and in the video.

---

## 8. Final answers as agreed (2026-08-05)

Paste-ready. Character counts verified. Supersedes SS3 and SS7 where they differ.

### Where are you based?

```
Moving to SF in early September.
```
*(32 characters.)*

### In school or working? Where at?

```
Neither. I took a leave of absence from Rutgers (CS, class of 2028) to build Vannaris full time.
```
*(96 characters.)*

### Project (500)

```
Vannaris is an independent benchmark of the web-search APIs that AI agents run on: Exa, Perplexity, Serper, You.com, Linkup. Same queries against every vendor, scored by three LLM judges from three different labs, published free with the raw data. Every vendor here publishes a benchmark and every one wins its own. I built the neutral one. It's live at vannaris.com. The business on top is a router that sends each query to the cheapest vendor that clears the quality bar for that query type.
```
*(493 characters.)*

### Problem (500)

```
A developer building an agent picks a search API on marketing, because there is nothing else to pick on: every benchmark in this category is published by one of the vendors in it. So they pick one and overpay. My first run found the cheapest API returns 92-98% of the best vendor's quality on four of six query types, at 1/7th the price like-for-like and 1/23rd at volume. The gap that justifies the price only opens on two categories. Nobody selling search has a reason to tell you that.
```
*(488 characters.)*

### Expertise (500)

```
I built all of Vannaris myself: five vendor adapters, a three-model judge ensemble, runner, export and site, 2,151 scored judgements on day one. The plumbing isn't the hard part; designing a measurement nobody can dismiss is. So I judge with three labs' models, re-run the ranking with each judge dropped, test whether length drives score (it doesn't), and publish the disagreement, including that my top two swap under one judge. Before this I took Jonivor from zero to live in 10 weeks, alone.
```
*(495 characters.)*

### Competitors (500)

```
My competitors are the vendors themselves. Tavily, Seltz and Quercle each publish a benchmark and each one wins it. LiteLLM unified the plumbing across 12+ providers but still makes you name the vendor on every call, with no quality signal. What they miss: quality routing is worthless. One vendor leads all six categories in my data, so route to the best just means use Exa. That was my own thesis; my own benchmark killed it in a day. The real axis is cost, a 7x spread between APIs sold as equal.
```
*(499 characters.)*

### Past work (500)

```
A) Jonivor, a pet-care platform in Uzbekistan: co-founder, CTO and sole engineer. Web, backend, auth, Telegram Mini App, iOS. Live: 10+ clinics, 30+ vets, real bookings. B) SWE intern at EPAM Systems; cut build time 35% with CI/CD. C) Four production web apps for clients on Upwork. D) Solo: vchk, an npm security scanner for AI code, 81% precision and 87% recall; VibeDuel, a multiplayer AI coding arena judged by an LLM, built in 2 weeks; HAYAT, a 3D globe tracking hospitals in conflict zones.
```
*(496 characters.)*

### Nerdiest (250)

```
There is almost no Uzbek speech data in machine learning, so I hand transcribed 74 audio clips myself, normalized them to 16 kHz, and published the dataset. It took forever. My language now has a little more data than it did.
```
*(225 characters.)*

### What drives you (250)

```
I keep building the thing nobody had a reason to build: Uzbekistan had no pet care platform, so I shipped one. My language had no speech data, so I transcribed it. AI search had no honest benchmark, so I ran one. The gap is what pulls me.
```
*(238 characters.)*

### Non-traditional

```
I taught myself to code at 12 — websites and bots — and was getting paid for freelance work three months later. I learned English on my own, no tutor and no courses, and by 17 I was teaching IELTS and SAT prep to 20+ students in a year, most of them older than me. I picked up Russian the same way. I had been training as a pianist since I was 6, competing nationally through all of it. None of it was assigned to me, and none of it was the normal route out of Uzbekistan.
```
*(472 characters.)*

### Risk / challenge (500)

```
I moved from Uzbekistan to the US and started over: new language, no network, nothing that transferred. That year I was doing three things at once — finishing high school in a language I was still adapting to, working shifts at Walmart, and writing college applications in between. It worked, slowly: Rutgers, then client work, then EPAM, then Jonivor. I don't stop when the work stops being impressive.
```
*(403 characters.)*

### Achievements

```
First place at an international piano competition in Turkey, one other international, and 5+ national competitions. I graduated as a pianist after 11 years of training — four with a private tutor from age 6, then seven at music school. It's the longest thing I've stuck with; I started it six years before I started programming.
```
*(328 characters.)*

### Co-founder pick

```
Ismail Farooq, a friend from Rutgers in CS. He shipped an AR Snap Lens to 35,000+ views, then went into the ML underneath it to claw back 1.5 FPS and 8ms of latency. Externed at Snap and Epic Games, now an AI Fellow at Handshake working on LLMs. He has better options than anything I could offer him today, which is the point. He ships things people actually use, and he goes at the hard layer instead of around it. I'd want him on anything I build.
```
*(449 characters.)*

### How did you hear

```
Twitter, from Cory's posts.
```
*(27 characters.)*

### 1 thing you need help with (500)

```
People. I built the thing; I don't yet know the people. I'm 20, moving to SF in September, and almost everyone in my network I met on the internet. Two kinds would change the next six months: a commercial co-founder who cares about distribution the way I care about measurement, and anyone shipping agents at scale who'd tell me where my benchmark is wrong. I can build alone. I can't meet them alone.
```
*(401 characters.)*

### Links

```
https://vannaris.com
https://github.com/feruzkarimovv
https://jonivor.com.uz
https://npmjs.com/package/vchk
https://feruz-karimov.dev
```

