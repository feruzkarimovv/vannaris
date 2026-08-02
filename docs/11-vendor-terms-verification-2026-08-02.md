# 11 — Linkup and Serper terms, read in full, 2026-08-02

`docs/03` closes by flagging two of the five published vendors as not actually verified:
Linkup's terms "did not fully load during this research (client-rendered placeholder)" and the
clauses reported "came from secondary search-result fragments, not a direct read of the primary
document"; Serper's extraction "was thin", and "the absence of explicit competing-product or
benchmarking clauses may reflect incomplete extraction rather than genuine absence, and should be
manually re-read before relying on 'Serper has no such clause' as a green light."

Both are now read in full from the primary documents. This supersedes those two rows of the
`docs/03` per-vendor table. `docs/03` itself is left as written — it is a record of what a research
session found, and correcting it in place would falsify that record.

**Method.** Raw HTML fetched from each vendor's own terms URL, tags stripped, and the resulting
text read end to end — not passed through a summariser, because a paraphrase of a contract is not a
contract. Word counts are given so anyone can tell whether the document I read is the document they
are looking at. Absences are reported as term-by-term searches over the complete text rather than
as an impression.

---

## Serper — the green light is genuine

<https://serper.dev/terms> · 1,201 words · "Updated on May 29, 2024" · governed by the laws of the
United Kingdom.

This is a short document and I read all of it. Searched term by term across the complete text, the
following appear **nowhere**:

`benchmark` · `performance test` · `competitive` · `compete` · `comparative` · `evaluat` ·
`disclos` · `resell` · `sublicen` · `cache` · `retain` · `store` · `train`

So `docs/03`'s "not found in fetched content" was a genuine absence, not a thin extraction. **There
is no no-benchmarking clause, no competing-product clause, no restriction on storing or caching
returned data, and no blanket resale prohibition.** Serper is the least restrictive vendor in the
set, and the benchmark's use of it is squarely inside what the terms allow.

What the terms *do* restrict, none of which the benchmark trips:

- **One account.** "Register more than one account at any point in time" is prohibited. Operational,
  not legal — but worth knowing before anyone creates a second key for CI.
- **No mirroring** "the materials on any other server as-is with no-value-added." Publishing derived
  scores is the opposite of as-is with no value added; publishing raw result sets would be closer to
  the line, which the project already does not do.
- **No circumventing** limits on the API key.
- **Attribution integrity** on returned Data: no misrepresenting ownership or source, no obscuring
  copyright or trademark notices, no falsifying or deleting author attributions.
- Serper "reserves the right, at its sole discretion, to modify these Terms at any time **without
  notice**." So this reading has a shelf life. Re-read before launch and periodically after.

**A supply-chain finding, not a legal one.** Serper's own terms open by stating it "is not
affiliated with or endorsed by Google in any way" and "provides web-scraped data collected from
public domain sources." That is the same posture as SerpApi, whose litigation `docs/03` analyses at
length. `docs/03`'s conclusion still holds — Vannaris is an authorised paying customer of Serper and
inherits no CFAA theory from Serper's relationship with Google — but it means one vendor in the
published set depends on scraping a party that has litigated against scrapers. That is a continuity
risk to the benchmark's vendor set, not a liability, and it belongs in the risk register rather than
the legal one.

---

## Linkup — no benchmarking clause, and one clause that matters for the router

<https://www.linkup.so/terms-of-use> · 5,673 words · governed by **French law**, disputes to the
courts of **Paris**. The page rendered fully this time; `docs/03`'s placeholder problem did not
recur.

**No benchmarking clause.** Nothing in the document restricts performance testing, comparative
analysis, or publishing the results of either. The only occurrence of "Benchmarks" is a navigation
item — Linkup publishes its own.

**Correction to `docs/03`.** It reports that Linkup "bars using the service *for reasons that
compete with LinkUp* and using data *for any competitive purpose*." Neither phrase is in the terms,
and the actual restriction is materially narrower and attaches to a specific object. Article 6.4:

> "Client shall not resell, sublicense, or otherwise make available the Answers in a manner that
> amounts to providing a substantially similar or competing service to Linkup Solution (including,
> without limitation, acting as a wrapper of the Linkup APIs)."

The bar is on redistributing **Answers**, not on competing generally. The correction runs in the
safer direction for the benchmark.

**The Answers licence is narrow, and the derived-scores-only design is what keeps the benchmark
inside it.** Article 4.2 grants a "personal, non-exclusive, non-transferable, worldwide right to use,
reproduce and modify Answers, for its internal needs and/or for its end-users' internal needs",
and states the Client "is not authorized to use, including to provide or to resell, the Answers for
any purpose other than strictly specified above." Publishing a score computed from an Answer is not
providing the Answer. Publishing the Answer text would be. This is the clause that makes
`src/export.py`'s vendor-content assertion a legal control rather than a stylistic one — and it is
why the `[:50]` sampling bug in that assertion, fixed on 2026-08-01, mattered.

**The storage question `docs/03` left unverified is answered, and the answer is favourable.**
Articles 4.1 and 6.3 confine the Client's use of Open Web Content to the text-and-data-mining
exception of Articles 3 and 4 of **EU Copyright Directive 2019/790**. Storing retrieved results
privately in order to compute and reproduce scores is text and data mining in the ordinary sense of
that exception. Two conditions ride along: the Client must check that content is lawfully
accessible, and rightsholders may reserve their rights by machine-readable means (`robots.txt`,
TDMRep). Linkup undertakes best efforts to detect those reservations but disclaims responsibility
for non-detection, and Article 6.3 makes the Client "solely responsible for any use of Open Web
Content that does not comply." The benchmark never republishes that content, which is the main
protection.

### The finding that changes something: the router

Article 6.4 names, as its own example of a competing service, **"acting as a wrapper of the Linkup
APIs."** That is a description of the router's shape.

`docs/05` and `docs/06` assume BYOK insulates the router layer — the end user's own credentials, no
resale, no markup. That argument is still available here, and it is a good one: under BYOK, Vannaris
never makes Answers available to anyone, because the Answers go to the key-holder who requested
them. But this is now a specific, quotable clause naming the exact architecture, from the one vendor
in the set governed by French law, rather than a general competing-product concern.

**This does not affect the benchmark, which ships today's scores and no Answers.** It is a question
for the router, and it is the single most valuable thing to put in front of the attorney whose
review `PUBLISH-CHECKLIST.md` §2 already requires — with this clause quoted, rather than as an
abstract question about BYOK.

---

## What this changes

- `PUBLISH-CHECKLIST.md` §2's "confirm the vendor set against each vendor's *current* terms" is now
  done for two of five. Exa, Perplexity and You.com were read directly in the original research and
  were not flagged as thin; they should still be re-read before launch, since all of these documents
  can change and Serper's may change without notice.
- The v1 vendor set stands. Nothing found here removes a vendor from the published benchmark.
- The router's Linkup exposure is now a named clause rather than an open question, and goes to
  counsel.

## What is still not established

This is a careful reading, not legal advice, and `docs/03` is explicit that an attorney's review is
the highest-value dollar spent before launch. Nothing here substitutes for it. Both documents were
read on 2026-08-02 and either vendor may change them — Serper explicitly reserves the right to do so
without notice.
