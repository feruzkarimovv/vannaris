# 14 — Exa, You.com and Perplexity terms, re-read 2026-08-07

`PUBLISH-CHECKLIST.md` §2 requires the vendor set to be confirmed against each vendor's *current*
terms, because terms change and `docs/03`'s readings were taken on 2026-07-30. `docs/11` closed
that item for Linkup and Serper on 2026-08-02. This closes it for **Exa** and **You.com**, and
records why **Perplexity could not be read** and is therefore still open.

**This is not legal advice and nothing here clears anything.** It is a record of what the primary
documents say, produced so that the attorney in checklist §2 spends their hour answering rather
than reading. The questions this raised are collected in `docs/15-attorney-brief.md`.

**Method, following `docs/11`.** Primary documents fetched directly from each vendor's own URL and
read end to end, not passed through a summariser — a paraphrase of a contract is not a contract.
Sizes and dates are given so anyone can tell whether the document read here is the document they
are looking at. Absences are reported as term-by-term searches over the complete text.

---

## Summary

| Vendor | Document read | Dated | Result |
|---|---|---|---|
| Exa | Terms of Service PDF, 8pp, complete | **no date visible in the document** | **Two findings that `docs/03` does not record.** §4.2(a) bars publishing information obtained through the Services; §4.2(f) bars using Output to develop a competitive product |
| You.com | Terms & Conditions (7,097 words) **and** Master Services Agreement (8pp, v.032025) | T&C **August 27, 2024**; MSA March 2025 | `docs/03`'s reading holds. The MSA is more favourable than the T&C on the point that matters, and **which document governs depends on how the account was opened** |
| Perplexity | — | — | **Not read. HTTP 403 on every route tried.** Still unverified |

Nothing here is a reason to pull a vendor on its own, and pulling one is a founder decision under
`AUTONOMY.md` item 2 in any case. Two items do need a decision before the next run.

---

## Exa — <https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf>

8 pages, read in full, §1 through §10.9. Governed by California law, San Francisco venue.
Arbitration and class-action waiver in §8, with a 30-day opt-out from first registering (§8.6).

**The document carries no visible "Last Revised" date**, although §10.2 refers to one ("we will
update the 'Last Revised' date at the top of these Terms"). There is therefore no way to tell from
the document whether it changed between 2026-07-30 and today. That is a limitation of this
re-read, not a finding about Exa.

### The finding: §4.2(a) is broader than `docs/03` records

`docs/03`'s Exa row reads, under storage/publication: *"Broad rights to host/reproduce/publish/modify
input and output; does not explicitly bar the customer from publishing query-response pairs."*

That describes **§1.2(c)**, which is the licence the customer grants *Exa*. It is not a statement
about what the customer may do. The restriction on the customer is **§4.2(a)**, which `docs/03`
does not quote:

> You may not do, and may not permit any of your Authorized Users to do, any of the following …
> unless applicable laws or regulations prohibit these restrictions **or you have our written
> permission** to do so:
> (a) download, modify, copy, distribute, transmit, display, perform, reproduce, duplicate,
> **publish**, license, create derivative works from, or offer for sale **any information contained
> on, or obtained from or through, the Services**, except for temporary files that are
> automatically cached by your web browser for display purposes …

On its face that covers both halves of what this benchmark does: it **stores** raw responses
(`raw_responses.raw_payload`) and it **publishes** numbers computed from them. Whether a derived
score is "information obtained from or through the Services" is exactly the boundary `docs/03`
identified as the mitigation — *"publishing only derived numeric scores rather than republishing
raw retrieved content"* — and it is the question this re-read cannot answer. It is question 1 in
`docs/15`.

Two things cut in the project's favour and should be stated alongside it:

- The benchmark **does not publish Exa's retrieved content**. `src/export.py` publishes scores,
  latencies and costs; the withheld-question gate and the derived-scores-only boundary are both
  enforced in code, not left to intent.
- **Written permission is an express cure**, in the preamble to §4.2. That is the same instrument
  `docs/03` already recommends pursuing for Tavily and Brave, and it would resolve this cleanly.

### §4.2(f) — the competitive-product clause, which does reach the router

> (f) access, use or exploit the Services (including Output) to develop any competitive product or
> service;

`docs/03` records this. It is worth restating that it says *including Output*, and that the product
`docs/01` describes is a router that sends queries to whichever vendor scores best — built, in
part, on Exa's Output. Whether a router is "competitive" with a search API is a real question and
not one this document can settle. It is question 2 in `docs/15`.

### §4.2(j), and why it probably does not bite

> (j) use any robot, spider, crawlers, scraper, or other automatic device, process, software or
> queries that intercepts, "mines," extracts, or otherwise accesses the Services to **monitor**,
> extract, copy or collect information or data from or through the Services;

A benchmark monitors by definition. But §1.1 grants an express right to use the API "for the
limited purposes set forth in the documentation", and reading (j) to forbid programmatic API use
would forbid the product Exa sells. The natural reading is that (j) targets non-API scraping.
Noted rather than relied on.

### Also worth knowing

- **§1.1** reserves Exa's right to "audit your use of our APIs" and to terminate API access "at any
  time". A benchmark that publishes an Exa score is a use Exa can end at will. That is a
  continuity risk to the *benchmark*, not a legal exposure.
- **§4.2(c)** bars using "any copyright, trademark, service mark, trade name, slogan, logo, image,
  or other proprietary notation displayed on or through the Services". The site prints "Exa" as a
  vendor name. See question 4 in `docs/15` — the same issue arises for You.com and is the more
  clearly answerable of the set.

---

## You.com — two documents, and the difference between them matters

### Terms & Conditions, <https://you.com/terms>

7,097 words extracted from the served page (including site navigation), **dated August 27, 2024** —
so this document has not changed since well before `docs/03` read it, and `docs/03`'s reading of it
stands. Legal entity is **SuSea, Inc.**, Palo Alto.

Term-by-term over the complete text: `benchmark` appears **twice and both are site navigation**
("Benchmarks" in the header and footer menus), not clauses. `competitive`, `comparative`, `resell`,
`cache`, `store`, `publish` and `scrape` appear **nowhere**. `docs/03`'s "no explicit
benchmarking-disclosure clause" is a genuine absence.

What §2.4 does prohibit, quoted because two items reach this project:

> … modifying, copying, sublicensing, leasing, selling or otherwise distributing any of our
> Services; … **automatically or programmatically extracting data or Output**; … **developing any
> products or services that compete with our Services, including the development or training of any
> artificial intelligence, machine learning algorithms or large language models**; … crawling,
> scraping, or otherwise harvesting data or information from our Services other than as may be
> expressly permitted …

**New, and not in `docs/03`'s table — §10.6 Publicity:**

> You may not, without our prior written permission, use our name, logos, tradenames, service marks
> or other trademarks in connection with products or services other than the Services, or in any
> other way that implies our affiliation, endorsement, or sponsorship.

A public leaderboard prints "You.com". The ordinary answer is nominative use — using a name to
refer to the thing itself is how comparison works, and the site already carries a "not affiliated
with any vendor" disclaimer on every page footer, which speaks directly to the second half of the
clause. It is still a clause aimed near what the site does, and it is question 4 in `docs/15`.

### Master Services Agreement, <https://home.you.com/hubfs/Legal/You.com%20MSA%20+%20SOW%20(March%202025).pdf>

8 pages, "MSA + SOW v.032025", read in full. **This is the document that governs API use for a
contracted customer** — it defines "API", "Customer Application", "Output" and "Prompts", which the
consumer T&C does not.

It is **more favourable** than the T&C on the point that matters most here:

- **§6.1 Customer Data.** *"You.com hereby assigns to Customer all of our right, title, and
  interest, if any, in and to Outputs."* Output is the customer's.
- **§1 Definitions / §7.** "Customer Data" means Prompts and Output, and **Customer Data is
  Customer's Confidential Information** — not You.com's. So publishing figures derived from Output
  is not a disclosure of You.com's confidential information.
- **§3.5(p)** carves out API access from the automation bar: *"except when you are accessing our
  Services via a You.com API key or where we otherwise explicitly permit it, to access the Services
  through automated or non-human means"*. **§3.5(j)** likewise excepts "as may be expressly
  permitted through use of the API". The bare prohibition on "automatically or programmatically
  extracting data or Output" at **§3.5(e)** carries no such carve-out, which is an internal tension
  in the document rather than a reading this benchmark has to resolve against itself.
- **§3.5(h)** keeps the competing-products bar, in the same sweeping form as the T&C.

**One clause to check against how the account is actually paid for — §7.1:**

> Neither Party will disclose the terms of this Agreement or any Ordering Document to any third
> party …

The site publishes a per-query price for You.com (`site/export/pricing.json`, `$0.005/query`, tier
"flat $5/1,000 calls"). If that number came from a **public price list**, publishing it discloses
nothing. If it came from an **Ordering Document**, publishing it is a disclosure of the agreement's
terms. `pricing.json` records the source as `https://api.you.com`, which suggests the public list.
**The founder should confirm which**, and it is question 3 in `docs/15`.

### The open question that decides which document applies

The MSA is a **template with unfilled blanks** — "entered into on [month, day, year] … and
[Customer Name]". It is the form You.com offers contracted customers, not evidence of what this
project signed. A self-serve API signup is generally governed by the T&C plus the AUP; a
negotiated account by the MSA.

**Only the founder knows which of these applies**, and it changes the answer: under the MSA, Output
is assigned to the customer and API automation is expressly carved out; under the T&C alone,
neither of those helpful provisions exists. Recorded as an open item rather than assumed either
way.

---

## Perplexity — not read, and this is the third time a WAF has blocked a legal check

Every route returned **HTTP 403**:

- `https://www.perplexity.ai/hub/legal/perplexity-api-terms-of-service` — 403 via plain fetch, 403
  with full browser headers, 403 via the fetching tool.
- `https://www.perplexity.ai/hub/legal/perplexity-api-terms-of-service-search` — 403 likewise.

Two things were learned without reading it, both from search-result metadata rather than the
document, and both flagged as **secondary**:

1. The API terms were **last updated 2026-01-23**, and cover "Sonar by Perplexity and Agentic
   Research API". The benchmark calls Sonar, so that is the applicable document.
2. There is a **separate addendum for the Search API** at the `-search` URL. `docs/03` did not
   record that a second document exists. If the vendor set ever moves from Sonar to Perplexity's
   Search API, that addendum governs and has never been read by anyone on this project.

**A secondary description of a contract is not a read of it, and this document does not treat it as
one.** Perplexity stays in the checklist §2 list as unverified.

**How to close it:** open either URL in a normal browser — they load fine interactively; it is
automated fetching that is refused — and save the page, or paste the text. It is a five-minute job
for a person and an impossible one from here. This is the same failure mode as `docs/10` §3, where
the USPTO register was unreachable programmatically for a week and took ninety seconds by hand.

---

## What this changes in `docs/03`

`docs/03` is left as written, per the precedent `docs/11` set: it records what a research session
found on 2026-07-30, and rewriting it to match a later read would falsify that record. Pointers to
this document have been added at its per-vendor table so a reader is not misled.

The two rows this supersedes:

- **Exa** — storage/publication. `docs/03` reads §1.2(c) (the licence granted to Exa) where the
  operative clause is §4.2(a) (the restriction on the customer). The corrected reading is above.
- **You.com** — the row is accurate for the T&C, but there is a **second and more favourable
  document** (the MSA) that `docs/03` does not mention, and a publicity clause at §10.6 that it
  does not record.
