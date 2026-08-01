# Autonomy contract

Read this before any long unattended session. `CLAUDE.md` says what the project
is; this says what an agent working on it alone may and may not do.

The premise: this project's only asset is that its numbers are believable. An
agent optimising "make it better" will, given enough rope, make the site look
more impressive and the benchmark less honest — those two moves feel identical
from the inside. Everything below exists to make the second one impossible to do
by accident.

## The gate

`scripts/check-all.sh` is the definition of "did that work". Nothing merges
without it green. It runs strict (`CHECK_STRICT=1`), so a check whose
dependencies are missing **fails** rather than printing "skipping" and exiting 0
— a distinction that has already cost this repo two silently-skipped gates.

A change that cannot be validated by an existing gate needs a new gate first.
"I inspected it and it looks right" is not a result.

## Never, without a human

These are not preferences. Each one is a claim the project makes in public.

1. **Never weaken the judge's bias mitigations** — the cross-family ensemble,
   position-swap checks, length normalisation, `require_full=True`, the
   completeness floors. `CLAUDE.md` names these as the product's credibility,
   not nice-to-haves. Making the pipeline faster or cheaper by relaxing one is
   the single most damaging change available in this repo.
2. **Never add a vendor** to `REGISTRY` in `src/vendors/adapters.py`. Adding a
   key there is the act of putting a vendor in a public benchmark, and two
   vendors have contract terms that forbid exactly this. `docs/03` governs.
3. **Never publish, deploy, or make anything public** — no repo visibility
   change, no Pages deploy, no domain, no post. Building it is fine; shipping it
   is a person's decision.
4. **Never spend vendor or judge API money.** No full runs, no smoke runs, no
   "just to check the adapter". A full run is ~$3.40 and the keys are live.
   Every benchmark question can be answered from the database already in
   `data/`, which holds two complete runs.
5. **Never claim a cadence the data does not support.** The site derives its
   cadence copy from `track_record.schedule_started`; keep it derived. Hand-typed
   claims about weekly or continuous running are forbidden until the scheduled
   runs exist, and the gate greps for them.
6. **Never fabricate evidence.** No invented human labels, no synthetic scores
   written into the real database, no plausible-looking numbers in docs. If a
   number is not measured, it does not get written down. Test fixtures go in a
   copy of the database and say so.
7. **Never rewrite `docs/` or `applications/`.** They record research and
   correspondence as they were. Correct them by appending a dated note, the way
   `docs/10` and the session handoff do.
8. **Never commit `.env`, `*.db`, or `calibration/`.** Raw vendor content is
   stored for reproducibility and never republished (`docs/03`).

## Free to change, alone

- The static site's markup, styles, and client-side behaviour, provided
  `check-quality.mjs` stays green — including its accessibility, weight, and
  no-external-requests invariants. Every figure must stay generated from the
  export; no hand-typed numbers, ever.
- Test coverage, gates, and tooling. More gates is always allowed.
- Refactoring with behaviour held constant, where a test proves it constant.
- Documentation of what exists — as opposed to claims about what it achieves.
- The router SDK, which has no published surface yet.
- Query set additions, provided the taxonomy balance holds and no query
  smuggles in a gold answer that decays (`src/queries/full-v1.json` explains).

## How work lands

One PR per coherent change, against `main`, never pushed to `main` directly.
The PR body states what was claimed, which gate proves it, and what was **not**
checked. A PR whose description cannot name its evidence is not ready.

Merging is a human's job. That is the whole safety model: the loop's output is
reviewable work, not deployed work.

## When to stop and ask

- A gate fails in a way that suggests the gate is wrong. Weakening a check to
  make a change pass is the exact failure this document exists to prevent — and
  it has a tell: the diff makes an assertion looser rather than the code better.
- The change would need one of the eight prohibitions above.
- Two reasonable approaches differ in what gets published or claimed.
- Something in `docs/` looks wrong. Flag it; do not quietly correct research.

## Known state to work from

The runner is armed and fires Mondays 06:23 UTC — unattended agents must not
interfere with it. One week of real data is published. The judges have never
been measured against a human; a 150-item calibration set is drawn and unlabelled
at `calibration/`, and labelling it requires a person. The name is `Vannaris`,
chosen 2026-08-01, and nothing is registered. The USPTO check is open.
