# Z Fellows interview — every number, in plain language

Written 2026-08-17, from `site/data/2026-W34.json` on `origin/main` and the published bundle.
Every figure here is checkable on vannaris.com or in the repo. Nothing is rounded up.

---

## 1. The two things that changed after you applied

You submitted on 2026-08-04. Both of these happened after.

**This morning the benchmark ran itself for the first time.** At 07:28 UTC on Monday 2026-08-17 the
scheduled job fired with no human involved, ran for 16 minutes, and committed the week at 07:44.
`trigger: "scheduled"`. Before today, every published week was started by a person — three
scheduled attempts had failed (Aug 3 died on a billing check, Aug 10 lost 336 judge calls to
rate-limit exhaustion, and week 33 had to be run by hand). `schedule_started` is now true and
`scheduled_weeks` is 1.

*Say it like this:* "Until this morning I couldn't honestly call it weekly, so I didn't. It ran
itself for the first time today."

**Yesterday the judges got checked against a human.** Until 2026-08-16 the site carried a caveat
saying the LLM judges had never been compared with human judgement. That's now measured and
published — details in §5.

*Say it like this:* "Everyone building LLM evals has the same unanswered question: do your model
judges agree with people? I answered mine yesterday. 79%."

---

## 2. What one run is

| Thing | Number | Plain meaning |
|---|---|---|
| Questions | 150 | The same 150 questions every week, across 6 categories |
| Vendors | 5 | Exa, Perplexity, Serper, You.com, Linkup |
| Searches | 750 | 150 questions × 5 vendors |
| Judges | 3 | One model each from Anthropic, OpenAI, Google |
| Grades | 2,238 | Every answer graded independently by all three |
| Complete | 99.5% | 746 of 750 answers got all three grades |
| Vendor cost | $3.36 | What the searches cost, per run |
| Total cost | ~$24/mo | Everything: searches, judge tokens, hosting |
| Runtime | 16 min | Start to published |

**The six categories:** general facts, breaking news, local/shopping, code/technical, multi-hop
(questions needing two steps), long-tail (obscure).

**Why $24/month matters:** the track record accrues whether or not anyone funds this. It's on a
personal card and it stays running.

---

## 3. Weeks published

| Week | Date | Started by | Grades | Complete |
|---|---|---|---|---|
| 2026-W31 | Jul 31 | person | 2,151 | 95.6% |
| 2026-W33 | Aug 13 | person | 2,010 | 89.3% |
| 2026-W34 | **Aug 17** | **scheduler** | 2,238 | **99.5%** |

**W32 is a permanent gap** — a week that didn't run can't be backfilled, and the site says so.
Volunteer this. It's the kind of thing that proves the record is real.

**W33 → W34 completeness went 89.3% → 99.5%** because of run-path fixes shipped Aug 14: vendor
responses are now saved *before* judging, so a failure mid-grading leaves a recoverable week
instead of a lost one.

---

## 4. What the benchmark found (week 34)

**Quality, 0–10, ensemble median:**

| Vendor | Score | Cost/query | Median latency |
|---|---|---|---|
| Exa | 9.253 | $0.0070 | 1,782 ms |
| Perplexity | 9.241 | $0.0051 | 3,303 ms |
| Serper | 8.520 | $0.0003 | 795 ms |
| You.com | 8.333 | $0.0050 | 624 ms |
| Linkup | 8.253 | $0.0050 | 1,906 ms |

**The cost spread.** Cheapest to dearest is **7× like-for-like** on pay-as-you-go rates, or **23×**
using Serper's top volume tier. Always quote the 7× first — it's the conservative one and it's what
the site renders. The 23× is true but flattering, and volunteering the difference is the point.

**Serper is the interesting vendor:** roughly a seventh of Exa's price, 92–98% of its quality on
four of the six categories, and the second-fastest in the set. It only falls off on multi-hop and
long-tail.

**Statistical tiers.** Exa and Perplexity are now **tied at the top** — the gap is 0.014 points,
nowhere near significant. Serper and You.com are tied below them. Linkup is last alone. So the
honest statement is three tiers, not five ranks.

**74% of individual questions have no separable winner** (111 of 150). Up from 67% in W31. Most of
the time, on most questions, these APIs are indistinguishable — which is itself the finding nobody
selling search will tell you.

**Routing gain: 0.08 points out of 10.** This is the number that killed your product. If you had
perfect foresight and sent every question to whichever vendor is best for that category, you'd beat
just always calling the single best vendor by 0.08 points. Across three weeks: **0.000, 0.017,
0.08**. There is nothing to route on for quality.

**Category leaders:** Exa wins four (general facts, breaking news, local/shopping, multi-hop),
Perplexity wins two (code/technical, long-tail).

---

## 5. Why the measurement can be trusted — the differentiator

This is the part no vendor benchmark has, and it's where the interview should go.

**Three judges from three different labs.** Claude Haiku 4.5, GPT-5.4-mini, Gemini 3.1 Flash Lite.
Nobody grades with one model, because one model's quirks become the results.

**The judges disagree, and it's published.** Their average scores are 8.106, 8.861 and 9.117 — a
**1.011-point spread between labs on identical answers**. Mean disagreement per answer is 1.436
points. Only **22% of answers were unanimous**. **8.85% split the judges by more than three
points.**

*Say it like this:* "Every benchmark that reports a single number is hiding this. I publish it,
because if my judges disagree by a point on average, you should know that before you trust a
0.3-point gap between vendors."

**Disagreement by category** — the judges agree on easy questions and fight over hard ones:

| Category | Mean disagreement |
|---|---|
| General facts | 0.484 |
| Local/shopping | 1.216 |
| Code/technical | 1.248 |
| Breaking news | 1.500 |
| Long-tail | 1.568 |
| Multi-hop | **2.576** |

**Drop-one-judge test.** Re-run the whole ranking three times, each time removing one lab's judge.
The order barely moves — except that **under Google's judge alone, Perplexity beats Exa.** That's
published too. It's the finding that most undermines the headline, and it's on the site.

**Length bias, measured not assumed.** Longer answers could score higher just for being longer. The
correlation between answer length and score is negative or near-zero for four of five vendors
(Perplexity −0.28, Linkup −0.23, Serper −0.21, You.com +0.04). **Exa is +0.347 this week**, which
is a real caveat and you should say so if asked — it was negative in earlier weeks and it's worth
watching.

**Human calibration — cleared 2026-08-16.** 280 blind comparisons. Vendor names hidden, judge
scores hidden, the margin hidden, left/right randomised, repeats and side-swaps held back so the
labeller couldn't game them.

| Check | Result | Plain meaning |
|---|---|---|
| Agreement | **117 of 148 = 79.1%** (95% CI 71.8–84.8) | When the models had a clear opinion, the human agreed four times in five |
| Position bias | **0 of 49** | Shown the same answer on either side, the human never just picked a side |
| Self-agreement | **30 of 30** | Shown the same pair twice, the human answered the same way every time |
| Near-ties | 48 of 50 | Where the models called it close, the human still had a preference — the models are under-separating, not over-separating |

**The honest limit:** one labeller. Say it before they ask. "It's one person — me — and the next
version needs more. But the blinding is real and the position-bias and self-agreement checks are
what stop a single labeller from being worthless."

---

## 6. Engineering, in one line each

- **Repository is public**, code and raw data both. Weekly CSV exports of every judge score.
- **308 automated tests**, and a single command runs **14 gates** before anything publishes.
- **A bad week can't reach the site** — the runner exits non-zero on a methodologically invalid run.
- **No number on the site is typed by hand.** Every figure, including ones inside sentences, is
  filled from the generated data file at page load, and the build fails if any doesn't resolve.
- **Cadence claims are derived, not written.** The site reads whether a scheduler or a person
  started each run. That's why nothing had to be edited this morning when the schedule started.
- **A withheld question set** exists with its hash committed to git before it runs, so scores on
  unseen questions can't be gamed. (See §7 — it hasn't produced data yet.)

---

## 7. What is not true yet — say these before they find them

**The withheld set has never run.** Registered Aug 4, hash committed, described on the site, and
`n_heldout_queries` is 0 in all three published weeks including this morning's. A secret isn't
configured. Its rotation promise expires 2026-09-01.

**Nobody has been asked to pay.** Zero private evals sold, pitched, or discussed. Every business
model so far — routing, a score feed, private evals — was reasoned to alone.

**No public launch.** No Show HN, and the LiteLLM thread where developers reported this exact
problem has never been contacted.

**One scheduled week, not a track record.** It started today. Three weeks published total.

**The instrument is saturating.** Four of five vendors sit at a median of 9 out of 10, and 74% of
questions produce no separable winner. A harder question set is the top priority — without it, the
table stops changing and there's no reason to visit weekly.

---

## 8. Three sentences to have ready

**If asked what you built:** "An independent benchmark of the five search APIs AI agents run on.
Same 150 questions, every vendor, every answer graded by three LLMs from three different labs, all
of it published free with the raw data. Every vendor in the category publishes a benchmark and
every one wins its own — I built the neutral one."

**If asked what you learned:** "That the product I was building shouldn't exist. I wanted a router
that picks the best vendor per query. Perfect routing beats just always using the best single
vendor by 0.08 points out of 10. There's nothing to route on, so I changed the product and kept
the instrument."

**If asked what's hard now:** "I've built the thing and never asked anyone to pay for it. My
instinct when I don't know something is to build more, and that's the habit I need broken."
