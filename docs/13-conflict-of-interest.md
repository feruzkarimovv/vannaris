# 13 — Conflict-of-interest policy

**Status: policy, in force from 2026-08-04. Written before any vendor has disputed a score, which is the only time it is worth anything.**

A conflict-of-interest policy published in response to an accusation is a defence. The same policy published before there is anything to defend is evidence. This document exists because the second is cheap and the first is worthless, and because the commercial plan in `06-business-model.md` creates a real conflict that it would be dishonest to leave for a vendor to discover and name first.

## The conflict, stated plainly

Vannaris publishes a free benchmark that ranks web-search APIs, and intends to earn money from three things layered on top of it: a routing client, a live score feed, and private evaluations run against a customer's own traffic (`01-product-spec.md`). Every one of those is more valuable when the benchmark is widely trusted, which is an incentive toward rigour. But two of them create pressure in specific directions, and both are named here rather than left implicit:

**Savings-share pricing is a live conflict.** `06-business-model.md` recommends charging, on some tiers, a share of the spend reduction a customer achieves by routing. Under that model Vannaris earns more when traffic moves to cheaper vendors — which is a direct financial interest in the cheap vendors scoring well relative to the expensive ones. This is not hypothetical or subtle: the headline finding of the first run is a cost spread, and the party publishing that finding would be paid more if it were larger. Mitigations are in the next section, but the mitigations are the answer to a real conflict, not a denial that one exists.

**Private evaluations create a relationship with the customer, not the vendor.** A customer paying for an eval on their own traffic has an interest in the result. They do not have an interest in the public leaderboard, and the two data sets never mix — private eval results are never published, never merged into a weekly run, and never influence a public score. The failure mode to guard against is the reverse of the usual one: a customer asking for the public methodology to be shaped so that their preferred vendor looks better.

**Per-decision routing fees are deliberately conflict-neutral.** A flat fee per routing decision pays the same whichever vendor is chosen. Where a pricing model can be made neutral by construction rather than by policy, it should be, and that is an argument for weighting revenue toward the metered tier over the savings-share tier as the business matures.

## Rules in force

These are commitments, not aspirations. Each is written so that a violation would be observable from outside.

1. **No vendor pays anything, for any reason.** No sponsorship, no placement, no listing fee, no paid tier, no "featured vendor", no paid support contract, no advertising. If money ever moves from a benchmarked vendor to Vannaris or to its founder in any form, that vendor is removed from the public benchmark until the relationship ends and is disclosed for the period it covered.
2. **No equity, no employment, no advisory role, no paid consulting** with any vendor in the benchmark, or with any company that owns one. Tavily's agreed acquisition by Nebius (`02-competitive-landscape.md`) is the reminder that ownership moves and that this rule has to be checked against the parent, not just the brand.
3. **No vendor sees a score before the public does.** No embargo, no preview, no advance notice, no right of reply prior to publication. A vendor that wants to comment comments on published numbers like anyone else.
4. **No vendor influences the query set, the rubric, or the judge models.** Suggestions are welcome and are treated exactly like anyone else's; a suggestion adopted from a vendor is recorded as such in the methodology changelog.
5. **The methodology is versioned, not edited.** Changing the rubric, the judge models, or the scoring is a new methodology version with a dated changelog entry, because a silent change is indistinguishable from a change made to move a rank. Retroactive rescoring of a published week does not happen; a week is corrected by publishing a correction beside it.
6. **The withheld set is committed before it runs.** Its SHA-256 is in this repository, dated, before it is ever used, and its questions are published in full on retirement (`src/heldout.py`). This is the specific defence against the accusation that a private set was chosen after the fact to produce a wanted result — including if that accusation is aimed at Vannaris.
7. **Disagreement is published, not summarised.** Judge disagreement rates, per-category, are exported and shown, including the categories where the ensemble is least reliable. A benchmark that publishes only the numbers that flatter its own method has no standing to criticise vendors for doing the same.
8. **Every figure on the site comes from the generated export.** Enforced in code (`scripts/check-site.mjs`), so a hand-typed number cannot enter a page — including a hand-typed number that happens to be favourable.

## Disclosure register

Kept current on the public site and here. As of 2026-08-04:

| Relationship | Status |
|---|---|
| Payment received from any benchmarked vendor | None |
| Equity or options in any benchmarked vendor or parent | None |
| Employment, advisory or consulting with any benchmarked vendor | None |
| Vendor-supplied API credits or comped usage | None — every vendor account is paid for at list price from the founder's own funds |
| Investor with a position in a benchmarked vendor | None (no outside investment taken as of this date) |
| Revenue from the router, feed, or private evals | None — none of the three has shipped or been sold |

The last two rows will change. When they do, they change here first, in a commit with a date on it, and the site reads from the same source.

**The investor case is the one to think about before it happens.** Vannaris intends to raise (`07-build-plan.md`). Search-infrastructure investors hold positions in search vendors; Gradient led Linkup's seed, a16z and Menlo are in the adjacent routing layer. Taking money from an investor with a position in a benchmarked vendor is not automatically disqualifying, but it is automatically disclosable, and the disclosure has to name the position rather than the fund. If an investor's position is large enough that a reasonable reader would discount the benchmark, the right answer is to decline the money — the benchmark is the asset, and a benchmark nobody believes is worth less than the round.

## How a vendor disputes a score

Publicly, in writing, with the dispute and the response both published. Specifically:

1. Any vendor, or anyone else, may dispute a published number. The raw judge scores, per-query and per-judge, are already in the export, so a dispute can be specific rather than a complaint about a total.
2. Configuration disputes — wrong endpoint, wrong tier, wrong parameters — are treated as the most likely kind and are the fastest to fix. `src/vendors/adapters.py` is public; the exact request made to each vendor is inspectable. If it is wrong, it is wrong, and it gets corrected and rerun.
3. A correction that moves a published number gets a dated changelog entry on the methodology page, never a silent edit.
4. A dispute about the rubric or the judges is a methodology-version question and is answered in public rather than in a private thread. A vendor is welcome to publish its own scores of the same query set — the set, the rubric and the scores are all exported for exactly that purpose.
5. Vannaris does not sign NDAs covering the public benchmark, and does not enter private discussions about a published score. A private resolution of a public dispute is indistinguishable from a settlement.

## What should make a reader distrust this

The honest version of a conflict policy names the tests it could fail. A reader is right to discount the benchmark if any of the following becomes true, and each is externally checkable:

- The cheap vendors' advantage grows over time in a way that tracks the introduction of savings-share pricing. Watch the published week-over-week series against the pricing page.
- The methodology changes shortly after a vendor relationship changes.
- The held-out set stops being published on retirement, or its retirement is postponed indefinitely.
- Judge disagreement figures disappear from the site, or stop being broken out by category.
- A vendor is removed from the benchmark without a stated reason. The two vendors excluded for contractual reasons (`03-legal-and-vendor-terms.md`) are named and the reason is given; every future exclusion gets the same treatment.
- The disclosure register above stays empty after the router starts earning revenue.

## Open questions

Whether a savings-share tier should exist at all, given that it is the only structural conflict in the pricing model that cannot be mitigated away — the alternative is capping upside on precisely the customers who benefit most, which is the problem `06-business-model.md` set out to fix. The current position is that it can exist provided it is disclosed here, that the metered tier stays the default, and that the conflict is named on the pricing page itself rather than only in this document. That is a judgement call and the founder should revisit it before the first savings-share contract is signed, not after.

Whether an independent reviewer should hold a standing role — someone outside the project who can inspect the runner, the raw layer and the private eval boundary, and say so publicly. This is what would most cheaply convert "the methodology is public" into "someone who is not the founder has actually read it". Not resolved; no reviewer approached as of this date.

Whether this policy needs an attorney's read before the site goes public. `PUBLISH-CHECKLIST.md` already gates publication on an attorney reading the methodology; this document should be in the same read, because the disclosure commitments above are promises made in public by a named person.
