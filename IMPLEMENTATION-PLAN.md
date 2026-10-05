# Portfolio engineering release: implementation and acceptance

Updated October 4, 2026. The goal is a reviewable backend/AI evaluation project: a newcomer can run it without credentials, recover a failed pipeline, trace a result to its measurements, and understand where its conclusions stop.

This is a release plan for code and documentation, not a promise of a new benchmark run or a startup roadmap. Original retrieval dates and research records are preserved. Deployment, LinkedIn publication, paid API calls, new vendor participation, and a new human study are outside this task.

**Release status:** phases 1–5 are implemented and passed integrated validation on October 4, 2026. Phase 6 remains deferred with its external prerequisites. The optional rendered-video artifact is supplementary to the verified runnable demo.

Evidence: repeatable setup; a fresh Python 3.13 environment with eight locked runtime packages; 414 unit tests; 13 repository gates with no skips; 17 measured-browser and 17 synthetic-browser checks. All four weeks were recomputed without new observations. The eight source response/judge CSVs, public query CSV, withheld commitment, and both label files remained byte-for-byte identical to initial HEAD. See [CURRENT-STATE.md](CURRENT-STATE.md) for the validation boundary.

## Phase 1 — A reproducible local entry point

| Finding | Change | Acceptance evidence |
| --- | --- | --- |
| README starts from paid live evaluation; contributor setup is stale | Add `make setup`, `make check`, `make demo`, `make serve`; document credential-free development first | Fresh setup resolves the locked toolchain; the offline gate runs without keys |
| Python dependencies have only lower bounds | Lock supported Python dependencies and retain npm's committed lock | Installation uses the lock; runtime versions are stated; checks do not depend on ad hoc packages |
| Duplicate tracked package/check files obscure canonical tools | Remove accidental duplicates; retain one canonical manifest and quality check | No `package 2.json` or `check-quality 2.mjs`; gates use canonical paths |
| Fixture checks do not provide a reviewer demo | Add an executable mock pipeline with its own DB/site/log | `make demo-build` completes without external calls and does not alter measured `site/` data |

**Completion boundary:** commands execute and are validated. `make demo` serves `.demo/site` at port 8000; `make serve` serves `site/`. They are separate local sessions.

## Phase 2 — Run integrity and recoverability

| Finding | Change | Acceptance evidence |
| --- | --- | --- |
| Historical query metadata can depend on the current query file | Store a run-bound query snapshot and resolve export/calibration from the selected run | Later query edits leave earlier text, gold, category, and identity unchanged |
| Judge work can be lost when a stage fails | Persist raw responses first and checkpoint successful judge calls | Injected interruption preserves accepted calls and responses needed to resume |
| Recovery can change the original week or redo completed work | Rejudge missing work while preserving run identity; allow missing retrieval only on the original UTC date | Recovery proves stable metadata and reused calls; later-day retrieval/backfill refused; checkpoint times record collection |
| Runner and exporter can use different validity rules | Align publication eligibility; distinguish quality from availability | An insufficient or rejected run cannot become published through manual export |
| Returned model identity can drift from its pin | Validate returned identity against an explicit accepted policy | Unexpected identity is rejected; accepted provider aliases are explicit |
| Public workflow artifacts can expose raw response evidence | Upload sanitized run status; optionally CMS-encrypt recovery DB to an owner's public certificate | Sanitized artifact contains no raw text; encrypted local roundtrip succeeds; no private key in Actions |
| A manual publication can silence a scheduled-run heartbeat; year arithmetic assumes 52 weeks | Check scheduled trigger and actual ISO calendar dates | Manual-only week fails scheduled heartbeat; ISO week 53 boundary is covered |

**Completion boundary:** offline failure tests prove the real pipeline path. They do not establish current provider account/SDK readiness; that requires a separately authorized live run.

## Phase 3 — Correct analysis and provenance

| Finding | Change | Acceptance evidence |
| --- | --- | --- |
| Different totals can use different category populations | Require all six qualified cells for an overall; retain consistent weights | Suppressed category produces unavailable overall, not an average over survivors |
| README claims bootstrap while code uses a normal interval | Implement deterministic category-stratified bootstrap 95% percentile intervals | Seeded analysis is reproducible; known-difference and missing-category fixtures exercise it |
| Repeated unadjusted comparisons encourage false separation | Paired sign-flip tests and Holm adjustment across a declared family | Corrected probabilities honor the family; separation also requires an interval excluding zero |
| Partial panels can distort disagreement | Analyze disagreement on full three-judge panels; report partial coverage separately | Partial panel never enters full-panel denominator |
| Withheld gaps invite unsupported overfitting claims | Describe diagnostic with coverage and uncertainty | No gap is called proof of overfitting or decisive after an arbitrary number of weeks |
| Vendor output modes and product tiers differ | Disclose recorded payload modes; keep historical scores intact | No list-only or equal-budget claim where the recorded prompts/configuration do not establish it |
| Corrected analysis can look like new observations | Recompute only from released CSVs with a revision and input SHA-256 hashes | Run identity, retrieval date, trigger, query hash, and original observations unchanged |

Equal category weights remain fixed. Overall paired inference requires at least two common scored questions per category. Sign-flip inference assumes exchangeable signs under the paired null; bootstrap resampling treats observed questions as the empirical population within each category. Assumptions belong beside the result.

**Completion boundary:** corrected analytics are testable now. New live scores, human ground truth, validated absolute scores, and stronger generalization are not produced by recomputation.

## Phase 4 — A usable archive and evidence explorer

| Finding | Change | Acceptance evidence |
| --- | --- | --- |
| Cadence claim can outlive freshness | Show selected date, latest-publication age, and archive/stale states | Historical selection never becomes a fresh measurement |
| Old run can reuse latest detail | Bind detail to the run; unavailable state with matching downloads | Changing `?run=` never leaves another week's evidence visible |
| Totals conceal missing cells/panels | Add data-health/incomplete-coverage states | W35 missingness and unavailable overalls visible without CSV archaeology |
| Query evidence is cumbersome | URL-backed search, category, paging, accessible evidence drawer | Browser checks cover deep links, keyboard opening, Escape, focus return, matching run/query |
| DOM-only checks miss rendering/interaction defects | Real-browser checks alongside existing gates | Chromium exercises viewport/interaction; absent validation cannot silently pass |
| Mock results could look measured | Separate synthetic demo page and outputs | Labels/mock identifiers/provenance; measured site never loads demo scores |

**Completion boundary:** local rendering and usability verified. Website not deployed; no traffic or user-study claim.

## Phase 5 — Engineering story and reviewable release

| Finding | Change | Acceptance evidence |
| --- | --- | --- |
| Active guidance contradicts archive | Current-state summary and updated active entry points | Four published weeks, two scheduled, limited completed calibration, W35 heldout accurate |
| Engineering decisions buried in plans | Case study with architecture, incidents, invariants, evidence, limits | Technical claims link to implementation/tests/released evidence |
| Pitch mixes pipeline with unbuilt router | Focus on backend/AI evaluation | Shipped, experimental, and unbuilt services distinct |
| Demo/launch need reviewable artifacts | 90-second walkthrough and LinkedIn draft | No invented adoption, human labels, deployment, or new benchmark run |
| A release recording should show the real local UI | Optional `make demo-video` with Chromium/ffmpeg; rendered frames and capture metadata | Generated clip is labelled synthetic and described as a still-frame walkthrough, not execution timing |

Validation commands:

```bash
make setup
make setup-browser
make check
make check-browser
make check-demo-browser
```

`make verify` combines the latter three checks; `make check-demo-browser` first generates the demo. The integrated execution passed as recorded above; any subsequent changes require relevant revalidation. Historical remote artifact inspection/deletion and a live workflow recovery roundtrip remain unperformed external operations.

## Phase 6 — Deferred evidence improvements

Useful future work with external prerequisites; none is marked complete:

| Work | Prerequisite and bounded deliverable | Acceptance |
| --- | --- | --- |
| Independent human calibration | Preregister sampling/analysis; recruit independent labeller; blind vendors/scores | Genuine labels, inter-labeller agreement, uncertainty, protocol, all outcomes |
| Objective-scoring track | Curate atomic fact/source criteria with licences/freshness | Held-out human verification; parallel results; no opaque blended “truth” score |
| Comparative-scoring experiment | Preregister hypotheses, budget, sampling, held-out evaluation | Out-of-sample improvement or documented null; controlled changes |
| Controlled payload-mode comparison | Explicit retrieval budget/output contract; access to original raw content or an authorized new run | Retrieval-only and synthesis effects reported separately without relabelling historical scores |
| Continued scheduled measurement | Owner approves budget, verifies accounts, monitors runs | Real scheduled publications with gaps/failures visible; no backfilled cadence |
| Withheld rotation | Maintainer follows existing registration/retirement | Commitment intact; retired questions published according to policy |
| External usefulness | Real developer inspects/recomputes evidence | Reproducible correction or measured usage with consent/provenance |

Do not substitute model-generated labels for people or call an unperformed study “human calibrated.” The prior single-labeller W31 result remains limited evidence.

## Deliberately excluded

Authentication, billing, enterprise SSO, a hosted key-holding proxy, Kubernetes, a frontend framework migration, a speculative router, more vendor logos, and a new startup pitch do not improve these engineering guarantees. Add one only for a demonstrated requirement.

Keep historical research and failed experiments. Their value is the recorded reasoning, including the original routing thesis's small measured benefit and the hard-query pilot's failed target. Finish the bounded pipeline and evidence story before expanding the product.
