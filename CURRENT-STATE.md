# Current state

Updated October 4, 2026 for the portfolio engineering release. This file describes the current checkout and separates implemented behavior from historical measurements and future work. Dated research, audits, plans, and applications remain preserved records.

## Shipped system

Vannaris is a Python evaluation pipeline with a static public-data explorer. It has five commercial search adapters, a three-family judge ensemble, SQLite persistence, human calibration tooling, a publication boundary, and an offline synthetic recovery demo. Its strongest portfolio focus is backend and AI evaluation engineering.

The commercial router, hosted score feed, classifier service, customer account system, and private-evaluation delivery workflow described in early business plans are not shipped products. They are not prerequisites for completing this engineering release.

## What the committed measurements establish

| Evidence | Current committed record |
| --- | --- |
| Published weeks | `2026-W31`, `2026-W33`, `2026-W34`, `2026-W35` |
| Scheduler-delivered weeks | W34 and W35 |
| Latest API retrieval | August 24, 2026 (`2026-W35`) |
| Public set | 150 queries, six categories, five vendors |
| Latest complete public panels | 530 / 750 responses, 70.7% |
| Latest vendor-call errors | 24 public responses |
| Withheld set | `ho-2026-08`, 30 questions, first observed in W35 |
| Latest complete withheld panels | 106 / 150 responses |
| Human calibration | One blinded pairwise pass on W31; 280 screens, one human labeller |
| Decisive-pair concordance | 117 / 148 = 79.1%; 95% Wilson interval 71.8–84.8% |
| Missing week | W32; never backfilled |

Sources: [`site/data/bundle.js`](site/data/bundle.js), [`site/data/latest.json`](site/data/latest.json), [`site/export/manifest.json`](site/export/manifest.json), and [`labels/96afde9bfef3.json`](labels/96afde9bfef3.json). Publication eligibility may suppress a category or overall score; these response counts do not assert that every vendor has a qualified overall ranking.

There is no committed API measurement after August 24. A configured cron and two historical scheduled runs do not prove current weekly operation. A stale archive remains useful when its age and gaps are explicit.

## Engineering release

The release implements local setup with locked dependencies; offline checks and a synthetic demo; run-bound query inputs; persisted judge checkpoints and recovery; revised derived statistics with provenance; and an archive-aware explorer with query evidence and data-health states. [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) defines scope and acceptance evidence.

The `publication-v3` analysis revision recomputes released measurements from CSVs. It preserves historical run IDs, retrieval dates, query-set hashes, and triggers, and records its input hashes separately. It creates no new vendor responses, judge calls, or human labels. Compare a result using both the run identity and analysis revision: the same measurements can acquire a corrected analysis without becoming new observations.

The public website is a previously deployed surface. Local release changes have not been deployed by this task. [release/LINKEDIN-POST.md](release/LINKEDIN-POST.md) is an unpublished draft, and [release/DEMO-WALKTHROUGH.md](release/DEMO-WALKTHROUGH.md) describes the local demo.

The local website now uses a shared light theme, simpler navigation and page introductions, and expandable publication notes. Its main comparison retains the historical dates, missing category cells, coverage, and evidence links. Results, methodology, data, vendor pages, and the separate synthetic demo use the same visual system. Archive distribution and disagreement figures require matching query detail and show explicit loading or unavailable states when it cannot load. Disagreement uses complete three-judge panels.

The weekly workflow now prepares sanitized run status rather than uploading plaintext database/log artifacts. Optional recovery encrypts the database to an owner-provided public X.509 certificate configured as `VANNARIS_RECOVERY_CERT`; the private key remains outside Actions. Local tests cover the encryption path, but no live workflow artifact roundtrip or historical remote artifact audit/deletion is claimed.

## Release validation — October 4, 2026

| Check | Observed result |
| --- | --- |
| Repeatable `make setup` | Passed; fresh Python 3.13 environment contains eight hash-locked runtime packages |
| Required offline checks after the website redesign | Passed: 414 unit tests; 13 repository gates with no skips |
| Real Chromium checks | 20 measured-archive checks and 17 synthetic-demo checks passed |
| Released-input recomputation | All four published weeks recomputed; original run identities and retrieval dates retained |
| Observation and commitment preservation | Eight response/judge CSVs, original public queries CSV, withheld manifest, and both label files match initial HEAD byte-for-byte |
| Publication bundle | 529,438 → 220,803 bytes (58.3% smaller); full audit JSON retained separately |

The integrated run used `VANNARIS_PYTHON=/tmp/vannaris-release-venv/bin/python` to prove the code does not rely on previously installed SDKs. A normal fresh setup uses `.venv/`. Existing test-only SQLite `ResourceWarning` messages and jsdom notices were nonfatal. The checks do not establish live API readiness, independent human validity, deployment, or historical remote artifact cleanup.

## Interpretation boundaries

- A three-model panel is not a human ground truth. The measured human audit covers ordering on one W31 sample, not absolute scores or later runs.
- Quality is conditional on API success. Vendor availability and judge completeness are separate observations, not hidden adjustments to a quality score.
- Vendors return different output modes and run at recorded product tiers. These scores describe the collected responses; they do not establish equal retrieval budgets or list-only retrieval quality across every vendor.
- Complete category coverage is required for an overall comparison. Missing cells must not change a vendor's category weights silently.
- Bootstrap intervals and multiplicity-adjusted paired tests express uncertainty under their assumptions. An unresolved difference does not prove two systems equivalent.
- The withheld diagnostic is a public/private-set gap. Difficulty, sampling, and missingness can produce that gap; it is not proof of vendor overfitting.
- Public CSVs permit recomputing aggregates and corrected analytics. Raw vendor content is not public, so original scoring cannot be fully replayed from the export alone.

## What remains open

1. Independent human labels and agreement between labellers; preregistered evaluation of any new scoring arm.
2. A parallel objective-scoring track with curated atomic facts or source criteria; comparative scoring tested against held-out human judgments.
3. Continued real scheduled operation, monitored freshness, account funding, and authorized live evaluation of the new recovery path.
4. Withheld-set rotation and retirement, governed by the existing commitment; no registration or question text is changed by this release.
5. Current vendor permissions and legal review. Existing exclusion and publication boundaries stay in place.
6. External usage evidence. This release does not invent customers, traffic, independent adoption, or savings realized by a user.
7. Controlled comparison of retrieval-only and synthesized-answer modes, with the budget and payload differences recorded. Correcting a description does not rejudge historical responses.

None of the first two items is fulfilled by synthetic data, another model acting as a human, or an unrun study plan. Paid API validation, participant recruitment, publishing, and posting need their own authorization.

## Record of superseded state descriptions

`CLAUDE.md` and `AUTONOMY.md` previously described the August 14 state: two published weeks, no scheduler success, no completed pairwise human calibration, and no heldout run. Those statements are preserved in labelled historical sections and are superseded by the committed evidence above.

The README previously summarized W34 as a dated snapshot. Its old bootstrap claim described a desired feature; the original implementation used normal-approximation paired intervals. The release replaces that unsupported claim with implemented, versioned analysis. Earlier `docs/`, applications, handoffs, and plans still refer to SearchBench, intended services, or earlier data; read their dates rather than treating them as current product claims.
