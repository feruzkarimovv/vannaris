# 12 — Judge calibration, first pass, 2026-08-02

**No publishable calibration figure exists yet.** That is the headline, and everything
below is the detail behind it. The site's statement that the judges are unaudited stays
true and stays up.

Two passes were run over the same 42-item, category-balanced set drawn from run
`50fbea16` (seed 2, random stratum only, blinded: vendor identity hidden, judge scores
hidden, order shuffled). Both are stored in `labels/07aa5e654034.json`.

| Pass | n | Mean | SD | Median time |
|---|---|---|---|---|
| `claude-opus-5` (**model**) | 42 | 7.93 | 1.34 | — |
| `feruz` (**human**) | 15 | 9.13 | 1.41 | 22s |
| judge ensemble (same items) | — | 8.67 | 1.30 | — |

## Why the model pass is not the calibration

`docs/04` requires agreement against *human* judgement. The judges are LLMs; scoring
them against another LLM measures agreement between models, which is a different
quantity and a much weaker one — where the two agree, that may be a shared blind spot
rather than a correct answer. This is enforced rather than remembered:
`human_labels.labeller_kind` records the distinction, `calibrate import` refuses to
guess it, and `calibrate report` withholds the headline framing and prints a warning
banner for any set that is not entirely human-labelled.

## What the model pass suggests — a hypothesis, not a finding

Against the model pass the ensemble runs **+0.55 generous** (MAE 0.79, r 0.73), and it
concentrates by category: `breaking_news` **+1.00**, `multi_hop` +0.86, down to
`long_tail` −0.29.

Reading the disagreements one at a time, they share a shape. The judges appear to score
**source authority and topical fit** and to under-weight **whether the answer is
actually present and current in what was returned**:

- *current population of India* — worldometers renders its figure in JavaScript, so most
  snippets contained no number at all; the only visible figure came from the weakest
  aggregator. Ensemble 9.
- *most recent Node.js LTS* — the set included a 2016 article about Node v6 and a video
  asserting v22 is current LTS, both now false. Ensemble 9.
- *current EU Council presidency* — `consilium.europa.eu`'s own page showed the
  superseded Polish presidency and three results said Cyprus. Correct answer available;
  a careless reader lands wrong.

If that holds up, it is a rubric-level defect: `freshness` exists precisely to catch it
and is not catching it in the category where it matters most. **It has not held up yet**
— see below.

## What the human pilot showed, and what it does not

Fifteen items, and the numbers are stark: ensemble MAE 1.40, **r 0.10, ρ 0.19**, with
two judge families slightly negative. Against the human the ensemble is mildly *harsh*
(−0.47), the opposite sign to the model pass, and the worst category is `long_tail`
(−3.00) rather than `breaking_news`. The model pass's prediction was wrong in both sign
and location — which is the value of having written it down first.

**This does not establish that the judges are uncorrelated with human judgement.** Three
reasons, all about the labels rather than the judging:

1. **Ceiling compression.** 12 of 15 scores were 9 or 10. Correlation is mechanically
   suppressed when one variable barely varies; r near zero is partly an artefact of the
   distribution, not a measurement of the judges.
2. **n = 15**, where two items move r substantially.
3. **22s median, two items under 10 seconds** — quick for reading ten results each.

What it *does* establish is a defect in the tool: the labelling task offers no anchors.
Nothing shows a labeller what a 5 or a 7 looks like, so "it answered my question" becomes
10 repeatedly. That is fixable, and it is the first thing to fix.

Two disagreements are worth keeping regardless, because they run opposite ways:
*criticisms of replication-crisis reforms* — human 9, both models 5–6, which penalised
results that answer the general topic rather than the specific angle asked; and *N+1 in
SQLAlchemy 2.0* — human 5, ensemble 9.

## What must not happen next

- Model labels must not be published as calibration, or counted toward the 100–200
  expert-labelled examples `docs/04` requires.
- The rubric must not be "fixed" against the model pass alone. The judge models and
  rubric are pinned because changing them breaks week-over-week comparability; a rubric
  change is a new methodology version, not an edit, and it needs human evidence first.
- No agreement figure from either pass goes on the site.

## What should happen next

Anchored labelling — a short warm-up showing worked examples of a 3, a 6 and a 9 before
the real items begin — then a fresh human pass of 20 or more, ideally by more than one
person so inter-human disagreement can be separated from human-versus-judge
disagreement. `calibrate report` already computes labeller-versus-labeller agreement
where two labellers share items.
