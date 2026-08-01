# 10 — Name clearance, checked 2026-08-01

`docs/03` §Naming left three things unresolved and `docs/08` said to close them in week one. This
document closes two of them against primary sources and records exactly why the third is still open.
It supersedes `docs/03`'s domain paragraph, which was explicitly inconclusive.

> **Outcome, same day: the name is now `Vannaris`.** §1–§5 are the case against keeping
> "SearchBench" and are left exactly as they were written; §6 records the replacement and how it was
> chosen. This file keeps saying "SearchBench" throughout because it is a record of a decision, not
> product surface — `scripts/rename.py` skips `docs/` and `applications/` for that reason.

**Method.** Domains via RDAP queries to the registries themselves (`rdap.org` bootstrap → registry
RDAP), which is the registry's own record rather than a resolver guess or a reseller's "is it
available" widget. Repositories via the GitHub API. Package names via the PyPI and npm registry APIs.
Everything below was observed on 2026-08-01; all of it can drift, and the trademark position in
particular is **not** established here.

---

## 1. Domains — resolved

| Domain | Status | Registry record |
|---|---|---|
| `searchbench.com` | **taken** | registered 2003-06-26, expires 2027-06-26, registrar **Nom-iq Ltd. dba COM LAUDE**, NS on `azure-dns` |
| `searchbench.ai` | **taken** | registered 2024-09-09, **expires 2026-09-09**, registrar NameCheap, parked on `registrar-servers.com` |
| `searchbench.dev` | available | no registry record |
| `searchbench.io` | available | no registry record |
| `searchref.com` | **taken** | registered 2011-11-19, NS on **`afternic.com`** — listed on the resale market |
| `searchref.ai` / `.dev` / `.io` | available | no registry record |
| `retrievalreferee.com` / `.ai` / `.dev` / `.io` | **all available** | no registry record |

Neither `searchbench.com` nor `searchbench.ai` serves any content — both are held, not used.

Two details matter more than the availability itself:

- **COM LAUDE is a corporate brand-protection registrar**, and the domain runs on Azure DNS. That
  combination is what an enterprise with a trademark portfolio and outside counsel looks like, not a
  squatter. It is not evidence of a registered mark, but it is the opposite of a name nobody wants.
- **`searchbench.ai` expires 2026-09-09** — five weeks out. If it lapses it becomes available; if it
  renews, someone is actively paying to hold it. Worth re-checking in October either way. Do not plan
  around a lapse: most parked domains renew.

## 2. Repository and package namespace — resolved, and worse than `docs/03` recorded

`docs/03` found one dormant conflict. There are now four projects carrying the exact name, in this
exact vertical, and the space around the name is busy:

| Repository | Stars | Last push | What it is |
|---|---|---|---|
| `serenedb/searchbench` | 2 | **2026-07-31** | benchmark for full-text search engines on log-shaped data |
| `realbazer/SearchBench` | 0 | 2026-07-24 | — |
| `hengzzzhou/LiveSearchbench` | 5 | 2026-01-06 | — |
| `Talc-AI/search-bench` | 20 | 2024-09-13 | the conflict `docs/03` names: LLM-judge scoring of consumer AI search products |
| `VibeBench/VibeSearchBench` | **404** | 2026-05-28 | "the hardest search benchmark in the wild" — live, popular, same niche |
| `LessieAI/people-search-bench` | 127 | 2026-04-07 | open benchmark for AI people-search |

**Correction to `docs/03`:** `Talc-AI/search-bench` **is MIT licensed** (docs/03 says no licence file
was found) and is **not archived**. Dormant since 2024-09-13, 20 stars, 1 fork. The licence lowers
the legal question further and leaves the confusion question exactly where it was.

The new fact is `serenedb/searchbench`, pushed the day before this check — an actively-developed
project with the identical name benchmarking search engines. And `VibeSearchBench` at 404 stars means
"search benchmark" as a phrase already has an occupant with mindshare.

Package namespaces do not discriminate — `searchbench`, `search-bench`, `searchref`,
`retrieval-referee` and `retrievalreferee` are **all free on both PyPI and npm**. So the router SDK's
package name is not an argument for or against any candidate.

## 3. USPTO — still open, and still blocking

**This was not completed, and it is the item `PUBLISH-CHECKLIST.md` §1 actually blocks on.** Every
programmatic route to the federal register is closed:

- `tmsearch.uspto.gov` (Trademark Search, the TESS successor) sits behind an **AWS WAF challenge**;
  the host itself serves a static bundle from S3 and returns `NoSuchKey` for the documented API path.
- USPTO's Open Data Portal (`api.uspto.gov`) returns `Missing Authentication Token` — it requires a
  free API key obtained through an interactive account signup.
- `assignment-api.uspto.gov` **no longer resolves in DNS** — that service is gone, folded into ODP.
- TMview (`tmdn.org`), which mirrors the USPTO register, serves its page but **resets the connection**
  on its search API.
- Driving the real UI in a browser was attempted; the Chrome extension is not currently connected.

Two ways to close it, in order of cost:

1. **Connect the Chrome extension** and the search can be run against the official UI directly.
2. **Run it by hand** at <https://tmsearch.uspto.gov> — search `SEARCHBENCH`, `SEARCH BENCH` and the
   chosen alternative, in classes **009** (software) and **042** (SaaS). A federal search is free.

A general web search finding nothing is **not** clearance and must not be recorded as one. The same
applies to this document: nothing here says the name is trademark-clear.

## 4. Where this leaves the decision

Not a recommendation to rename — that is the founder's call per `CLAUDE.md`. What the evidence says:

**"SearchBench" is descriptive, crowded, and unowned.** Descriptive names are weak marks and hard to
enforce; the two most valuable TLDs are held, one of them by an entity that pays for brand-protection
registration; four repositories in the same vertical carry the name, one updated the day before this
check; and the phrase already has a 404-star occupant. None of that is a legal barrier. All of it is
friction on the exact axis this project competes on — being the thing people find and cite when they
ask which search API is best.

**"Retrieval Referee" / SearchRef is clean on everything checkable here.** All four `retrievalreferee`
TLDs free, `searchref.ai/.dev/.io` free, no meaningful repository collision, all package names free.
`searchref.com` is on the resale market, so the spelled-out form is the cheaper one to own outright.
Its trademark position is **equally unchecked** — §3 applies to it too.

**The switching cost will never be lower than it is right now.** The repository is private, the site is
built but unpublished, and `scripts/rename.py` does the whole rename in one command. Every week of
public track record accrued under a name raises the cost of changing it — and the runner is now armed,
so that clock is running.

## 5. Carried forward from `docs/03`, not re-verified here

"SearchArena" (collides with LMArena's live Search Arena) and "QueryBench" (collides with
`querybench.com`) were ruled out in `docs/03` and were **not** re-checked on 2026-08-01. If either
returns to consideration, re-verify — those findings are now over a week old and, as §2 shows, this
space moves.

---

## 6. The replacement: `Vannaris`, chosen 2026-08-01

The founder rejected "SearchBench" outright — it had always been a placeholder — and asked for a name
that is distinctive rather than descriptive: not a label that explains the product, a word that can
come to mean it.

### What the sweep found about the landscape

Roughly 250 candidates were checked across twelve passes: dictionary words, Latin and Greek roots for
judging/measuring/finding, instruments of measurement, obscure birds and animals, and invented words
in several phonetic families. The finding is blunt and worth recording, because it constrains any
future rename:

**Every short pronounceable name is registered.** All 30 dictionary words, all 49 invented five-to-
seven-letter names, and every bird and animal vocabulary tried were taken on `.com` — and, with a
handful of exceptions, on `.ai` and `.io` as well. `.dev` is the only TLD with meaningful short-name
availability left. Free `.com`s begin at roughly eight letters and are overwhelmingly invented words.

Several names that *looked* free died on inspection, which is the reason the deep check exists:

| Candidate | Why it was rejected |
|---|---|
| `dunlin` | `.ai` free, but PyPI, npm, the GitHub handle and a 19★ repository are all taken |
| `numbat` | a 2,619★ Rust tool — **and** a 552★ repository belonging to Perplexity, a benchmarked vendor |
| `saiga` | a well-known open LLM series with models published on Hugging Face |
| `thalo` | a 676★ Rust framework |
| `avocet` | PyPI and the GitHub handle taken; multiple existing companies |
| `perquire` | clean on domains, but collides with an active Python legal-search-engine project |
| `retrievalarbiter` | commercially clean, but "Retrieval Arbiter" is a named component in a 2026 agent-memory paper — the same search-noise problem that sank SearchBench |
| `mirvaris` | free `.com`, but the GitHub handle is taken and two repositories sit under it |

An earlier round produced `QueryArbiter` and `SearchArbiter`, both fully clean. Both were rejected by
the founder as too descriptive — they name the function rather than the company.

### Vannaris, verified

Checked 2026-08-01 against registry RDAP records, the PyPI and npm registry APIs, the GitHub API, the
Hugging Face API, and open web search:

| Surface | Status |
|---|---|
| `vannaris.com` / `.ai` / `.dev` / `.io` | **all free** |
| PyPI, npm | **both free** |
| GitHub organisation `vannaris` | **free** |
| GitHub repositories carrying the name | **none** |
| Hugging Face models or datasets | **none** |
| Open web | **zero results** — no company, product, project or person |

It is an invented word built from Latin *vannus*, the winnowing fan that separates grain from chaff.
That is a story the project can tell later, not a claim the name makes on its own — which is exactly
the property the founder asked for and the property "SearchBench" lacked.

### Still not established

**The USPTO check in §3 is unchanged and still open** — it now applies to `VANNARIS`, in classes 009
and 042. An invented word is inherently distinctive and therefore the strongest kind of mark to
register and the hardest to challenge, so this is likely to clear. Likely is not cleared, and nothing
here says otherwise. The X/Twitter handle is also unchecked; that API needs authentication.

**Nothing is registered.** Free means unowned, not reserved — see `PUBLISH-CHECKLIST.md` §1.
