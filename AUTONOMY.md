# Autonomy contract

Read this before any long unattended session. [`CURRENT-STATE.md`](CURRENT-STATE.md) says what exists; `CLAUDE.md` explains current development; this says what an agent working on it alone may and may not do.

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

1. **Never weaken the implemented judge mitigations** — the cross-family
   ensemble, length-normalisation instructions, `require_full=True`, and
   completeness floors. Preserve the position-swap and repeat controls in
   pairwise human calibration; do not claim the pointwise judge pipeline
   performs position swaps. `CLAUDE.md` names these as the product's credibility,
   not nice-to-haves. Making the pipeline faster or cheaper by relaxing one is
   the single most damaging change available in this repo.
2. **Never add a vendor** to `REGISTRY` in `src/vendors/adapters.py`. Adding a
   key there is the act of putting a vendor in a public benchmark, and two
   vendors have contract terms that forbid exactly this. `docs/03` governs.
3. **Never publish, deploy, or make anything public** — no repo visibility
   change, no Pages deploy, no domain, no post. Building it is fine; shipping it
   is a person's decision.
4. **Never spend vendor or judge API money.** No full runs, no smoke runs, no
   "just to check the adapter". A live run uses paid vendor and judge accounts.
   Use the committed derived exports for measurements and synthetic fixtures
   for offline behavior checks. A fresh checkout need not have any raw database.
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
9. **Never touch the withheld set's registration.** Do not register a new set,
   retire an active one, edit `src/queries/heldout/manifest.json`, or move any
   question text into the repository. The commitment in that file is dated and
   public, and an agent that regenerates it destroys the only thing that makes
   the withheld set worth more than a vendor's own private benchmark
   (`src/heldout.py`). Authoring *candidate* questions into a file outside git
   for the founder to register is fine; registering them is not.

## Free to change, alone

- The static site's markup, styles, and client-side behaviour, provided
  `check-quality.mjs` stays green — including its accessibility, weight, and
  no-external-requests invariants. Every figure must stay generated from the
  export; no hand-typed numbers, ever.
- Test coverage, gates, and tooling. Add checks that establish meaningful behavior; do not mirror implementation
  or count skipped checks as evidence.
- Refactoring with behaviour held constant, where a test proves it constant.
- Documentation of what exists — as opposed to claims about what it achieves.
- The offline demo and pipeline internals within the current release scope.
  Historical routing-client plans are not a current instruction to build a router.
- Query set additions, as separate candidates with explicit query-set identity; do not silently
  alter a historical run or smuggle in a gold answer that decays (`src/queries/full-v1.json` explains).

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
- The change would need one of the prohibitions above.
- Two reasonable approaches differ in what gets published or claimed.
- Something in `docs/` looks wrong. Flag it; do not quietly correct research.

## Current state and local workflow

[CURRENT-STATE.md](CURRENT-STATE.md) is authoritative for current implementation and committed evidence. It records four published weeks, two scheduled successes, a completed one-person pairwise calibration on W31, and a W35 heldout run. The latest live retrieval remains August 24, 2026; this release does not add measured live data.

Use the isolated checkout already provided by the cloud task. Do not create a worktree unless explicitly requested. `make setup`, `make check`, and `make demo` are the credential-free entry points. Use `make setup-browser` before `make verify` when the supported browser is not installed. The mock demo writes `.demo/` and is never a public measurement.

New runs preserve query snapshots and checkpoint retrieval/judge work. Recovery must keep original identity and retry missing work. Analysis revisions record provenance separately from observation dates. Legacy runs without immutable snapshots must remain explicitly identified; do not invent their missing evidence.

Workflow artifacts carry sanitized run status. Optional encrypted recovery uses an owner-provided public X.509 certificate; no private recovery key is sent to Actions. Do not upload plaintext databases/logs to public artifacts. Historical remote artifact review/deletion has not been performed by this task.

Dated studies, business plans, applications, and handoffs remain preserved records. The section below is historical, not a current instruction to retrieve, publish, or label anything.

---

## Archived known state — August 14, 2026

*Updated 2026-08-14. Anything here that can be checked, check — this paragraph
has been wrong before, and a stale statement of state is how an agent starts
work from a premise nobody holds any more.*

The runner is armed and fires Mondays 06:23 UTC — unattended agents must not
interfere with it, and must not dispatch it.

**Two weeks of real data are published, and none of them arrived on a schedule.**
`2026-W31` and `2026-W33`; `track_record.scheduled_weeks` is 0 and
`schedule_started` is false. Three scheduled attempts have not landed a week:
2026-08-03 died on a credit preflight, 2026-08-10 spent the vendor money and
then lost 336 judge calls to quota-exhaustion 429s, and 2026-W33 was published
by a hand-dispatched run. **`2026-W32` is a permanent gap** — a missed week is
not backfillable, which is what `heartbeat.yml` exists to notice.

**The judges have still never been measured against a human.** Total human
labels ever: 15, on the absolute set `07aa5e654034` — `docs/12` reports r = 0.10
with an interval that includes zero, over scores that barely vary. The
replacement design is a 280-screen pairwise set, `96afde9bfef3`, registered
2026-08-05 and **unlabelled**; its task can be rebuilt with `python -m
src.calibrate render --set 96afde9bfef3` and must never be re-drawn with
`sample-pairs`, which would replace a sample registered before anyone saw the
scores. Labelling it requires a person. Until a set clears chance, every page
must keep saying the judges are unaudited — the gate checks.

**The withheld set has never run.** `ho-2026-08` was registered 2026-08-04, 30
questions, hash committed; both published weeks carry `n_heldout_queries: 0`,
because the `SB_HELDOUT_JSON` Actions secret is not set. Nothing in code tracks
the rotation, and `first_week` in the manifest is written by nothing.

The name is `Vannaris`, chosen 2026-08-01. `docs/10` records the domain, package
and USPTO exact-match searches; what remains open there is the phonetic and
similar-mark search and the `.ai` domain. Nothing is registered.

The repository is public. `AUDIT-2026-08-13.md` records the site as live at
vannaris.com since early August and is the current statement of where the
project stands; `PLAN-2026-08-13.md` is the ordered response to it. Item 3
above still holds regardless: publishing anything further is a person's call.
