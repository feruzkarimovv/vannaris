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

---

## Correction, 2026-08-05: reason 1 is overstated, and the interval is the finding

Everything above is left as written. Every figure in it reproduces exactly from
`labels/07aa5e654034.json` against `data/vannaris.db`, using the same median-of-judges
aggregation `calibrate.py` uses: r = 0.0972, ρ = 0.1886, 12 of 15 human scores at 9 or 10.

**Reason 1 ("ceiling compression") does not carry the weight the section gives it.** The
claim is checkable and was not checked when it was written. Holding both observed
distributions fixed and rearranging them into the best possible alignment — the
comonotonic rearrangement, which is the largest correlation these two sets of numbers can
produce — gives **r_max = 0.9352**. Compression therefore accounts for at most **0.065** of
the shortfall from 1.0, against an observed shortfall of 0.903: about **7%**. It is real
and it is nearly all of what is left unexplained. The observed r is not "partly an
artefact of the distribution" in any sense that matters; 93% of the gap is something else.

Reasons 2 (n = 15) and 3 (22s median) stand, and reason 2 is the one doing the work.

**The interval is what should have been reported.** r = 0.10, 95% CI (Fisher z)
**[−0.437, +0.581]**. Both signs are inside it, so the pass does not establish that the
judges agree with human judgement, and equally does not establish that they do not. Worth
stating plainly: the *upper* bound is the informative end. Even the most favourable value
this pilot is compatible with is far below what a published ranking would need to lean on.

**A second reading of the same labels, which is what argues for the switch to pairwise.**
Of the 105 unordered item pairs, 66 carry a strict human preference. The ensemble agrees on
31 of them and is itself tied on 15:

| basis | concordance | 95% CI (Wilson) |
|---|---|---|
| all 66 pairs, ensemble ties counted as misses | 31/66 = **47.0%** | [0.354, 0.588] |
| 51 pairs where the ensemble expresses a preference | 31/51 = **60.8%** | [0.471, 0.730] |

The 60.8% figure is conditional on the ensemble having an opinion, and conditioning on the
thing under audit is not free — quote it with its denominator or not at all. **Both
intervals contain 0.5.** Neither is evidence of agreement above chance; the second is
simply a less noisy way of spending the same labelling effort, which is the actual argument
for pairwise and is worth less than "4× the information" makes it sound.

**Implication for the next pass, stated before it is run.** At a true concordance of 60.8%,
n = 75 is the smallest decisive stratum whose Wilson interval clears chance — meaning it
clears only if the point estimate is exactly right, and fails on any adverse draw. A
decisive stratum of 75 is therefore not a design, it is a coin flip about whether the
result will be reportable. Reaching a ±0.10 interval needs n ≈ 69 at 75% concordance, and
substantially more if the true value sits nearer 0.61. Likewise a 25-item order-swapped
stratum can only detect a position effect larger than about 18 points, which is not a
check, it is a formality.

Availability is not the constraint: run `50fbea16` yields **821** public pairs at an
ensemble gap ≥ 1.0 and **553** at ≤ 0.5. Labelling effort is the constraint, and it should
be spent on the decisive stratum first.

Nothing here changes the site. No agreement figure from any pass goes on it, and the copy
saying the judges are unaudited stays up.
