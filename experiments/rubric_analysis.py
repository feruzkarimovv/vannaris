"""Does the strict rubric make the instrument discriminate, or just score lower?

Lowering every score by a point changes nothing that matters — the ranking is
identical and no two vendors separate that did not separate before. The question
is whether strictness *spreads* the vendors, so the analysis is the same paired
comparison the site publishes (export.paired_difference): mean per-query
difference between two vendors on the queries both answered, its standard error,
and whether the 95% interval clears zero.

Paired, not two independent means: every vendor sees the same questions, so
between-question variance — most of the variance here — cancels within a pair.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
Z95 = 1.96


def cells(rows):
    """(vendor, query) -> ensemble median, complete ensembles only."""
    out = {}
    for r in rows:
        vals = [v for v in r["scores"].values() if v is not None]
        if len(vals) == 3:
            out[(r["vendor"], r["query_id"])] = statistics.median(vals)
    return out


def paired(cell, a, b):
    qs = sorted({q for (v, q) in cell if v == a} & {q for (v, q) in cell if v == b})
    diffs = [cell[(a, q)] - cell[(b, q)] for q in qs]
    if len(diffs) < 2:
        return None
    mean = statistics.mean(diffs)
    se = statistics.stdev(diffs) / (len(diffs) ** 0.5)
    lo, hi = mean - Z95 * se, mean + Z95 * se
    return {"a": a, "b": b, "n": len(diffs), "mean_diff": round(mean, 4),
            "se": round(se, 4), "ci95": [round(lo, 3), round(hi, 3)],
            "separated": lo > 0 or hi < 0}


def report(name, rows):
    cell = cells(rows)
    vendors = sorted({v for (v, _) in cell})
    means = {v: statistics.mean([s for (vv, _), s in cell.items() if vv == v])
             for v in vendors}
    order = sorted(vendors, key=lambda v: -means[v])

    all_scores = list(cell.values())
    print(f"\n{'=' * 72}\n{name.upper()}\n{'=' * 72}")
    print(f"  n cells {len(all_scores)}   median {statistics.median(all_scores):.2f}"
          f"   mean {statistics.mean(all_scores):.2f}"
          f"   sd {statistics.pstdev(all_scores):.2f}")
    print(f"  >=9 {100 * sum(1 for s in all_scores if s >= 9) / len(all_scores):.1f}%"
          f"   >=8 {100 * sum(1 for s in all_scores if s >= 8) / len(all_scores):.1f}%"
          f"   <=6 {100 * sum(1 for s in all_scores if s <= 6) / len(all_scores):.1f}%")

    print("\n  ranking")
    for v in order:
        print(f"    {v:<12}{means[v]:.3f}")

    print("\n  adjacent pairs")
    sep = 0
    for x, y in zip(order, order[1:]):
        p = paired(cell, x, y)
        if not p:
            continue
        sep += p["separated"]
        flag = "SEPARATED" if p["separated"] else "-"
        print(f"    {x:<11} vs {y:<11} diff {p['mean_diff']:+.3f}  se {p['se']:.3f}  "
              f"ci [{p['ci95'][0]:+.3f},{p['ci95'][1]:+.3f}]  {flag}")
    print(f"  separated: {sep}/{len(order) - 1}")

    print("\n  all pairs")
    tot = allsep = 0
    for i, x in enumerate(order):
        for y in order[i + 1:]:
            p = paired(cell, x, y)
            if p:
                tot += 1
                allsep += p["separated"]
    print(f"  separated: {allsep}/{tot}")
    return {"median": statistics.median(all_scores),
            "sd": statistics.pstdev(all_scores),
            "adjacent_separated": sep, "all_separated": allsep, "all_pairs": tot}


def main():
    raw = json.loads((OUT / "rubric_experiment_raw.json").read_text())
    a = report("control rubric (what is published today)", raw["control"])
    b = report("strict rubric (anchored 0-10 scale)", raw["strict"])

    print(f"\n{'=' * 72}\nVERDICT\n{'=' * 72}")
    print(f"  median            {a['median']:.2f}  ->  {b['median']:.2f}")
    print(f"  spread (sd)       {a['sd']:.2f}  ->  {b['sd']:.2f}")
    print(f"  adjacent separated {a['adjacent_separated']}  ->  {b['adjacent_separated']}")
    print(f"  all pairs separated {a['all_separated']}/{a['all_pairs']}"
          f"  ->  {b['all_separated']}/{b['all_pairs']}")
    print()
    print("  A lower median alone is cosmetic. What would justify rewriting the")
    print("  rubric instead of writing 150 harder queries is MORE SEPARATION.")


if __name__ == "__main__":
    main()
