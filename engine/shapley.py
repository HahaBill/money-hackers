"""Exact-sum Shapley attribution over the café driver graph (§10)."""

from __future__ import annotations

from itertools import combinations
from math import factorial

from engine.graph_def import LeafState, blend, profit_fn


def subsets(leaves: list[str]):
    n = len(leaves)
    for r in range(n):
        yield from (set(c) for c in combinations(leaves, r))


def shapley(
    leaves: list[str],
    prior: LeafState,
    curr: LeafState,
    *,
    evaluator=profit_fn,
    tolerance: float = 0.01,
) -> dict[str, float]:
    n = len(leaves)
    if n == 0:
        return {}
    phi = {leaf: 0.0 for leaf in leaves}
    for coalition in subsets(leaves):
        weight = factorial(len(coalition)) * factorial(n - len(coalition) - 1) / factorial(n)
        base = evaluator(blend(coalition, prior, curr))
        for leaf in leaves:
            if leaf in coalition:
                continue
            with_leaf = evaluator(blend(coalition | {leaf}, prior, curr))
            phi[leaf] += weight * (with_leaf - base)
    delta = evaluator(curr) - evaluator(prior)
    residual = abs(sum(phi.values()) - delta)
    if residual >= tolerance:
        raise AssertionError(
            f"Shapley sum {sum(phi.values()):.4f} != Δprofit {delta:.4f} "
            f"(gap {residual:.4f})"
        )
    return phi
