# 15 — Brief for counsel

**Status: prepared 2026-08-07, not yet sent. No attorney has reviewed this project.**

`PUBLISH-CHECKLIST.md` §2 blocks on an attorney reading the methodology. This document does not
satisfy that item and is not legal advice — it is the packet that makes the item cheap, so that the
hour is spent answering rather than reading a repository. `docs/03` says explicitly that this is
the highest-value dollar spent before going public and that nothing written by this project
substitutes for counsel.

**One thing to say up front, because it changes the reading: the site is already live.** It went
public on 2026-08-03 at <https://vannaris.com> with this item open (`PUBLISH-CHECKLIST.md` records
that decision and that it was deliberate). The questions below are therefore not "may we launch"
but "what is live now that should change".

---

## 1. What the thing is, in one paragraph

Vannaris is a free public benchmark of commercial web-search APIs used by AI agents. It sends an
identical set of 150 authored questions to five vendors' APIs — **Exa, Perplexity, Serper, You.com
and Linkup** — using accounts and API keys the founder pays for personally, then has three
commercial LLMs from three different labs score each response 0–10 against a published rubric. The
median score per vendor per category is published as a leaderboard, with the raw per-judge scores,
the methodology, and the full question set published alongside it. The repository is public
(<https://github.com/feruzkarimovv/vannaris>). One week of data has been published; the run costs
about $5.45 and is intended to repeat weekly.

## 2. What is stored, and what is published — these are different sets

**Stored, privately, never published** (SQLite, `data/*.db`, git-ignored):

- The full raw response payload from each vendor for each query: answer text, result URLs, titles,
  and snippets of retrieved page content (`raw_responses.raw_payload`).
- Per-judge scores and free-text rationales.

**Published** (`site/export/`, CC-licensed, and the site itself):

- Numeric scores per vendor per category, medians, standard errors, paired-comparison tiers.
- Measured latency and per-query cost, the latter taken from vendors' published price lists or from
  a billed figure the vendor returns on the call.
- The full text of the 150 questions.
- Per-judge numeric scores.
- **No vendor-retrieved content.** No answer text, no snippets, no result URLs. This boundary is
  enforced in code: `src/export.py` builds the published artefacts from the score tables and fails
  the build if withheld question text reaches a published file, and `scripts/check_vendors.py`
  fails if a vendor outside the cleared set carries a published score.

The distinction between the two lists is the project's principal legal mitigation, recommended in
`docs/03` before any code was written: publish derived numbers, never republish retrieved content.

## 3. The questions, in priority order

### Q1 — Does storing and publishing derived scores breach Exa's §4.2(a)? *(highest value)*

Exa's Terms of Service §4.2 provides that the customer may not, "unless … you have our written
permission":

> (a) download, modify, copy, distribute, transmit, display, perform, reproduce, duplicate,
> **publish**, license, create derivative works from, or offer for sale **any information contained
> on, or obtained from or through, the Services** …

Two sub-questions:

- **(a) Storage.** The benchmark retains complete raw responses in a private database, indefinitely,
  and never publishes them. Is that "download … copy … reproduce"?
- **(b) Publication.** It publishes a number — a judge's 0–10 rating of a response — computed from
  that response. Is a derived score "information obtained from or through the Services", or is the
  derivation far enough removed?

Exa is the vendor that currently ranks **first** on the published leaderboard, which is worth
knowing when weighing how the conversation is likely to go. **Written permission is an express cure
in the clause itself**, and the practical question may be whether to ask rather than whether it is
needed. Full text and context: `docs/14`.

### Q2 — Is a benchmark, or the router built on it, a "competitive product or service"?

Both Exa (§4.2(f), "access, use or exploit the Services **including Output** to develop any
competitive product or service") and You.com (§3.5(h) of its MSA, "developing products or services
to compete with our Services, including to develop or train any artificial intelligence or machine
learning models") bar this in broad terms.

- Is a **neutral comparative benchmark** a competitive product with respect to the APIs it measures?
- Is a **router** that directs a developer's query to whichever vendor scores best — using the
  vendors' own Output to decide — a competitive product with respect to those vendors?

The second is the commercially important one: `docs/01` describes a router as a planned product,
and the router would be built on measurements derived from vendor Output.

### Q3 — Does publishing a per-query price disclose the terms of an agreement?

You.com's MSA §7.1: "Neither Party will disclose the terms of this Agreement or any Ordering
Document to any third party." The site publishes a per-query cost for every vendor. Where the
figure comes from a **public price list**, this appears to be a non-issue; where it comes from a
**negotiated Ordering Document**, it may not be. The same question arises for Serper, whose
published figure is its top volume tier rather than its list rate.

*Founder input needed before counsel can answer: for each vendor, was the account opened self-serve
against public pricing, or under a signed agreement?* This also determines, for You.com, whether the
consumer Terms & Conditions or the Master Services Agreement governs at all — they differ
materially, and the MSA is the more favourable of the two (`docs/14`).

### Q4 — Nominative use of vendor names and marks on a comparative leaderboard

The site prints each vendor's name, and links to its site. Exa §4.2(c) bars use of "any copyright,
trademark, service mark, trade name, slogan, logo … displayed on or through the Services".
You.com §10.6 bars use of "our name, logos, tradenames, service marks or other trademarks in
connection with products or services other than the Services, or in any other way that implies our
affiliation, endorsement, or sponsorship."

Comparative reference is the ordinary case for nominative fair use, and every page footer already
carries a "not affiliated with any vendor" disclaimer. **Is the current treatment sufficient, and
does anything need to change — a trademark-attribution line, dropping vendor logos (none are used
today), different link treatment?** This is expected to be the cheapest question to answer and the
easiest to remediate.

### Q5 — Does BYOK actually insulate the router layer?

The architecture is BYOK by design and by necessity: every vendor's terms bar resale, sublicensing
or proxying, so the router orchestrates calls using **the end user's own API keys and the end
user's own vendor relationship**, and Vannaris never holds, resells or marks up vendor access
(`CLAUDE.md` treats this as non-negotiable; `docs/05` has the architecture).

- Does that structure hold as a matter of the vendors' terms, or does *orchestrating* a call with
  someone else's key still implicate the sublicensing prohibitions?
- Does the answer change for a **hosted** component — a score feed and query classifier sold as a
  service — that never touches a vendor call?

### Q6 — Exposure from publishing comparative performance claims

The site publishes statements of the form "Vendor A scores 9.12 and Vendor B scores 7.94 on this
question set". If a vendor disputes a score:

- What is the realistic exposure — trade libel, Lanham Act §43(a) false advertising, tortious
  interference — for a **non-commercial, methodologically documented, reproducible** comparison?
- Does the current design meaningfully reduce it? Everything is published: the questions, the
  rubric, the per-judge scores, the disagreement rates between judges, and the statistical
  intervals showing which differences the run **cannot** resolve. The site states plainly where the
  ranking is not firm — including that dropping any one judge reorders the table.
- **Does the fact that the benchmark's own conflict-of-interest policy is published (`docs/13`),
  before any vendor has disputed anything, help or is it immaterial?**

### Q7 — Copyright in retrieved content

Raw vendor responses include snippets of third-party web content. These are stored privately and
never published. Is private retention for scoring purposes a problem, and is there a retention
period worth adopting?

### Q8 — Trademark: the remaining half of the clearance

A USPTO search for the exact wordmark `vannaris` was run on 2026-08-07 across all classes, live and
dead: **zero results** (`docs/10` §3). That is not clearance — the test is likelihood of confusion,
not identity. **Please run or commission a similar-mark/phonetic search** (`VANARIS`, `VENARIS`,
design marks) in classes 009 and 042, and advise whether the mark is worth filing. The name is an
invented word with no web presence, which should make this cheap.

---

## 4. Vendor-by-vendor, as currently understood

Full readings in `docs/03` (2026-07-30), `docs/11` (Linkup and Serper, read in full 2026-08-02) and
`docs/14` (Exa and You.com, read in full 2026-08-07).

| Vendor | Governing law | No-benchmarking clause? | The clause that matters here |
|---|---|---|---|
| **Serper** | United Kingdom | None — verified absent term-by-term | Least restrictive of the five. No storage, caching, resale or competing-product clause at all |
| **Linkup** | France | None found | See `docs/11` |
| **Exa** | California (SF venue, arbitration + class waiver, 30-day opt-out) | None explicit | **§4.2(a)** publication/copying; **§4.2(f)** competitive product. Written permission is an express cure |
| **You.com** (SuSea, Inc.) | — | None — "benchmark" appears only in site navigation | **§3.5(e)/(h)** programmatic extraction and competing products; **§10.6** publicity. MSA §6.1 assigns Output to the customer |
| **Perplexity** | — | Unknown | **Not read — 403 on every automated route.** Last updated 2026-01-23 per secondary sources. A separate addendum governs its Search API |

**Deliberately excluded, and why**, since it goes to the project's good faith:

- **Tavily** (§3.2(x) bars disclosing "any performance information or analysis" to third parties)
  and **Brave** (ToS §2(b)(xvi) bars using content to "create, train, evaluate, or improve …
  services") are **not benchmarked**, pending written consent. Both, notably, publish their own
  comparative benchmarks.
- **Seltz** and **Search Router** carry explicit no-benchmarking bars and are excluded outright.

The exclusions are enforced in code rather than by intention: `src/vendors/adapters.py::REGISTRY`
is the single gate, and `scripts/check_vendors.py` fails the build if a vendor outside the cleared
set reaches a published artefact.

## 5. What counsel would find useful to look at

- <https://vannaris.com> — the live site; the methodology page is the substantive one.
- <https://vannaris.com/methodology.html> — what is measured, how, and the published limitations.
- `docs/03-legal-and-vendor-terms.md` — the original vendor-terms research, 2026-07-30.
- `docs/11-…` and `docs/14-…` — the two full re-reads.
- `docs/13-conflict-of-interest.md` — the disclosure register and the one pricing model that
  creates a real conflict.
- `src/export.py` — the only code that turns stored data into published numbers, i.e. the
  enforcement point for the derived-scores-only boundary.

## 6. Questions counsel will ask that only the founder can answer

1. For each of the five vendors: self-serve signup against public pricing, or a signed agreement?
   (Decides Q3, and decides which You.com document governs.)
2. Has any vendor been contacted about this benchmark, in any form?
3. Is the intention to seek written permission from Exa — and from Tavily and Brave — or to
   proceed without and respond if approached?
4. What is the budget and appetite for a trademark filing on `VANNARIS`?
