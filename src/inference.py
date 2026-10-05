"""Deterministic query-level inference for publication revision v3.

The authored questions are a fixed workload, not a random sample of all user
traffic. Intervals describe resampling that workload; they do not establish
general performance on the web. Paired sign-flip tests additionally assume
exchangeable signs under the no-difference null. No judge calls are resampled
as if they were independent questions.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from functools import lru_cache

VERSION = "publication-v3"
BOOTSTRAP_DRAWS = 10_000
PERMUTATION_DRAWS = 4_999
SEED = 20261004
ALPHA = 0.05


def seed_for(label: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{SEED}:{label}".encode()).digest()[:8], "big")


def quantile(values: list[float], p: float) -> float:
    """Linear interpolation, explicitly pinned rather than library-dependent."""
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


@lru_cache(maxsize=512)
def bootstrap_mean(groups: tuple[tuple[float, ...], ...], label: str,
                   draws: int = BOOTSTRAP_DRAWS) -> dict:
    """Resample queries within each category; give categories equal weight.

    Each group is one category. For a paired comparison its observations are
    the per-query differences, preserving the pairing through every draw.
    Fewer than two observations in a required category cannot support an
    interval. A constant observed group can yield a degenerate bootstrap
    interval; it is never, by itself, evidence of a statistically certain win.
    """
    if not groups or any(len(g) < 2 for g in groups):
        return {"ci95": None, "se": None, "status": "insufficient_paired_queries"}
    if draws < 100:
        raise ValueError("at least 100 bootstrap draws are required")
    rng = random.Random(seed_for(label))
    estimates = []
    sizes = [len(g) for g in groups]
    for _ in range(draws):
        estimates.append(sum(sum(rng.choices(g, k=n)) / n
                             for g, n in zip(groups, sizes)) / len(groups))
    return {
        "ci95": [round(quantile(estimates, ALPHA / 2), 3),
                 round(quantile(estimates, 1 - ALPHA / 2), 3)],
        "se": round(statistics.stdev(estimates), 3),
        "status": "estimated",
    }


@lru_cache(maxsize=512)
def paired_sign_flip(groups: tuple[tuple[float, ...], ...], label: str,
                     draws: int = PERMUTATION_DRAWS) -> dict:
    """Two-sided paired sign-flip p, exact for <=16 nonzero observations.

    Weights preserve the equal-category estimator. The add-one Monte Carlo
    p-value is never zero and records its finite simulation resolution. Zero
    differences contribute neither a random sign nor spurious sample size.
    """
    if not groups or any(len(g) < 2 for g in groups):
        return {"p_value": None, "test": "unavailable", "permutations": 0}
    weighted = tuple(x / len(g) / len(groups) for g in groups for x in g if x != 0)
    observed = abs(sum(weighted))
    if not weighted:
        return {"p_value": 1.0, "test": "exact_paired_sign_flip", "permutations": 1}
    tolerance = max(1e-12, observed * 1e-12)
    if len(weighted) <= 16:
        sums = [0.0]
        for x in weighted:
            sums = [s + x for s in sums] + [s - x for s in sums]
        extreme = sum(abs(s) >= observed - tolerance for s in sums)
        p = extreme / len(sums)
        test, count = "exact_paired_sign_flip", len(sums)
    else:
        if draws < 99:
            raise ValueError("at least 99 permutation draws are required")
        rng = random.Random(seed_for(label + ":signs"))
        extreme = 0
        for _ in range(draws):
            bits = rng.getrandbits(len(weighted))
            value = sum(x if (bits >> i) & 1 else -x for i, x in enumerate(weighted))
            extreme += abs(value) >= observed - tolerance
        p = (extreme + 1) / (draws + 1)
        test, count = "monte_carlo_paired_sign_flip", draws
    return {"p_value": p, "test": test, "permutations": count,
            "nonzero_differences": len(weighted)}


def holm_adjust(p_values: list[float | None]) -> list[float | None]:
    """Holm family-wise adjustment; unavailable comparisons retain a slot.

    The family is fixed before selecting leaders. Missing/invalid comparisons
    count as p=1 for adjustment but are returned as None, not discoveries.
    """
    ordered = sorted(enumerate(p_values), key=lambda item: (
        1.0 if item[1] is None else item[1], item[0]))
    result: list[float | None] = [None] * len(p_values)
    running = 0.0
    for rank, (index, p) in enumerate(ordered):
        if p is not None and (not math.isfinite(p) or not 0 <= p <= 1):
            raise ValueError("p-values must be finite numbers between zero and one")
        running = min(1.0, max(running, (len(ordered) - rank) * (1.0 if p is None else p)))
        if p is not None:
            result[index] = running
    return result


def protocol() -> dict:
    return {
        "version": VERSION,
        "interval_method": "category-stratified query bootstrap, percentile 95%",
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "seed": SEED,
        "comparison_test": "two-sided paired sign flip; exact <=16 nonzero differences",
        "permutation_draws": PERMUTATION_DRAWS,
        "multiplicity": "Holm across all vendor pairs in every category and overall",
        "alpha": ALPHA,
        "category_weighting": "equal; overall requires every declared category",
        "assumptions": "query-level resampling; exchangeable paired signs under the test null",
        "scope": "fixed authored workload; quality conditional on API success and complete judges",
        "interval_warning": "marginal bootstrap estimates, not simultaneous intervals or population guarantees",
        "tier_interpretation": "unresolved comparisons; not evidence of equivalence",
    }
