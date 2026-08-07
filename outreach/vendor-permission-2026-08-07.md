# Vendor permission requests — drafted 2026-08-07, not sent

Three emails. One asks Exa for the written permission its own terms name as the cure; two ask
Tavily and Brave for the consent that would let them into the benchmark they are currently excluded
from. All three are the founder's to send, edit or bin.

**Why these exist.** `docs/14` found that Exa's ToS §4.2(a) bars publishing "any information
contained on, or obtained from or through, the Services" absent written permission, and that the
clause names written permission as its own cure. `docs/03` recommended the same instrument for
Tavily and Brave from the beginning. Attorney review is deferred (`PUBLISH-CHECKLIST.md` §2), which
makes asking directly the cheapest way to close the largest open question — a business email rather
than a legal opinion.

## What these emails must not offer, per `docs/13`

The conflict-of-interest policy is in force and binds this correspondence. None of the drafts
offer, and no reply should be answered with:

- **A preview of any score.** Commitment 3: no embargo, no advance notice, no right of reply before
  publication. A vendor comments on published numbers like anyone else.
- **Any influence over the query set, the rubric or the judges** (commitment 4). Suggestions are
  welcome and are treated exactly like anyone else's, and recorded as vendor-suggested if adopted.
- **Any commercial relationship.** No vendor pays anything for any reason, and no vendor supplies
  credits or comped usage (commitment 1, and the disclosure register).

If a vendor offers money, credits or a partnership in reply, the answer is no, and the offer gets
recorded in the disclosure register in `docs/13` whether or not it was accepted.

---

## 1 — Exa

**To:** hello@exa.ai
**Subject:** Written permission request under ToS §4.2(a) — Vannaris benchmark

> Hi,
>
> I run Vannaris (<https://vannaris.com>), a free public benchmark of web-search APIs used by AI
> agents. Exa is one of five vendors in it. I'm writing to ask for written permission under your
> Terms of Service §4.2(a), which requires it before publishing information obtained through the
> Services.
>
> Exactly what the benchmark does with your API: it sends 150 questions, paid for at list rate on
> my own account, and stores the responses privately. What gets published is derived numbers only —
> a 0–10 quality score from an ensemble of three LLM judges, measured latency, and per-query cost.
> **No retrieved content, no answer text, no snippets and no result URLs are published, ever.** That
> boundary is enforced in code, and the code is public:
> <https://github.com/feruzkarimovv/vannaris>.
>
> I read §4.2(a) as broad enough to reach a derived score, and I'd rather ask than assume. I'm
> asking for permission for that narrow use — publishing scores and measurements derived from Exa
> API responses, not the responses themselves.
>
> Two things so this doesn't read as anything other than what it is. **Your answer will not affect
> your score.** Exa currently ranks first on the published table, which was true before I wrote
> this and will stay true regardless of your reply. And if you say no, I'll remove Exa from the
> public benchmark and state that it was removed at your request — I won't adjust anything else.
>
> No vendor pays anything to be in this, no vendor sees a score before the public does, and no
> vendor has any say in the methodology. That policy is published at
> <https://vannaris.com/methodology.html#conflicts>.
>
> If the configuration I'm testing misrepresents Exa — wrong tier, depth or parameters — I'd
> genuinely like to know, and I'll correct and rerun.
>
> Thanks,
> Feruz Karimov

---

## 2 — Tavily

**To:** support@tavily.com
**Subject:** Consent to include Tavily in a public search-API benchmark (§3.2(x))

> Hi,
>
> I run Vannaris (<https://vannaris.com>), a free public benchmark of web-search APIs used by AI
> agents. **Tavily is not in it**, deliberately: your Terms §3.2(x) bar disclosing "any performance
> information or analysis" to third parties without consent, and that's exactly what a published
> benchmark is. The site says so by name — Tavily is listed as excluded, with the reason given.
>
> I'd like to include you, and I'm asking for that consent.
>
> What inclusion means: the same 150 questions every other vendor gets, on an account I pay for at
> list rate, scored by three LLM judges from three labs against a published rubric. Published output
> is derived numbers only — score, latency, cost. No retrieved content is ever published. The
> method, the questions, the per-judge scores and the code are all public.
>
> For what it's worth, `tavily-ai/tavily-search-evals` publishes this kind of head-to-head
> comparison already, which is part of why I think third-party measurement is something Tavily is
> comfortable with in principle. The difference here is just that the party running it isn't a
> vendor.
>
> To be clear about what consent does not buy: no vendor pays anything, no vendor sees a score
> before the public does, and no vendor influences the questions, the rubric or the judges. If the
> answer is no, Tavily stays excluded and the site keeps saying why.
>
> Thanks,
> Feruz Karimov

---

## 3 — Brave

**To:** bizdev@brave.com (see the addresses note below — Brave publishes no Search API support address)
**Subject:** Consent to include Brave Search API in a public benchmark (ToS §2(b)(xvi))

> Hi,
>
> I run Vannaris (<https://vannaris.com>), a free public benchmark of web-search APIs used by AI
> agents. **Brave is not in it**, deliberately: ToS §2(b)(xvi) bars using content to "create, train,
> evaluate, or improve" services, which reads squarely onto what a benchmark does, and §2(b)(xv)
> separately covers algorithmic use. The site names Brave as excluded and gives that reason.
>
> I'd like to include you, and I'm asking for consent.
>
> What inclusion means: the same 150 questions every other vendor gets, on a paid account at list
> rate, scored by three LLM judges from three labs against a published rubric. Published output is
> derived numbers only — score, latency, cost — and no retrieved content is published, which I
> understand also matters given the §2 restrictions on storing results and building a database of
> Content. I'd honour the "POWERED BY BRAVE" attribution requirement on every page showing a Brave
> number.
>
> No vendor pays anything, no vendor sees a score before the public does, and no vendor influences
> the methodology. If the answer is no, Brave stays out and the site keeps saying why.
>
> Method, questions, per-judge scores and code are all public:
> <https://github.com/feruzkarimovv/vannaris>.
>
> Thanks,
> Feruz Karimov

---

## Addresses — checked 2026-08-07

- **Exa — `hello@exa.ai`. Confirmed.** It is the contact address in Exa's own ToS §10.9 ("You may
  contact us regarding the Services or these Terms by e-mail at hello@exa.ai"), which makes it the
  correct address for a request *about the terms* specifically.
- **Tavily — `support@tavily.com`. Confirmed** against Tavily's own privacy and terms pages. There
  is also a form at <https://www.tavily.com/contact>. Worth knowing for the letterhead: the legal
  entity is **AlphaAI Technologies Inc. dba Tavily**, 33 W 60th St, New York, NY 10023 — and
  `docs/02` records an agreed acquisition by Nebius, so the counterparty may be changing.
- **Brave — no Search API address is published.** The API page offers only a HubSpot enterprise
  form and points technical questions at `community.brave.app`; the footer's business-development
  address is **`bizdev@brave.com`**, which is the closest fit for a licensing/consent request and is
  what the draft now uses. The enterprise form is the fallback if that bounces or goes unanswered.

A wrong address is a silent failure, and silence reads identically to refusal — so if any of these
gets no reply, treat "no answer" as "not asked" rather than as "asked and declined", and try the
other channel before concluding anything.

## If a vendor says yes

Record it. A consent that exists only in an inbox is not much better than no consent: put the date,
the vendor, the person, and the scope of what was permitted into `docs/03`'s per-vendor table and
into the disclosure register in `docs/13`. For Tavily or Brave, adding the vendor to
`src/vendors/adapters.py::REGISTRY` is the act that puts them in the published benchmark and is
gated by `AUTONOMY.md` item 2 — a person does it, deliberately, after the consent is filed.
