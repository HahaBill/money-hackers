"""Exact-sum Shapley attribution over the café driver graph (§10)."""

from __future__ import annotations

from itertools import combinations
from math import factorial
from typing import Callable

from engine.graph_def import LeafState, blend, profit_fn


def subsets(leaves: list[str], *, include_full: bool = False):
    n = len(leaves)
    stop = n + 1 if include_full else n
    for r in range(stop):
        yield from (set(c) for c in combinations(leaves, r))


def _leaf_value(state: LeafState, leaf: str):
    """Return the part of state controlled by one attribution leaf."""
    if leaf.startswith("unit_cost."):
        return state.unit_cost.get(leaf.split(".", 1)[1])
    if leaf in {"price", "mix", "usage_efficiency"}:
        return getattr(state, leaf)
    return getattr(state, leaf)


def shapley(
    leaves: list[str],
    prior: LeafState,
    curr: LeafState,
    *,
    evaluator: Callable[[LeafState], float] = profit_fn,
    tolerance: float = 0.01,
) -> dict[str, float]:
    if not leaves:
        return {}

    # Unchanged leaves are null players. Removing them before enumeration is
    # exactly Shapley-equivalent and turns the common "two things changed"
    # case from 2^16 state evaluations into four.
    active = [leaf for leaf in leaves if _leaf_value(prior, leaf) != _leaf_value(curr, leaf)]
    phi = {leaf: 0.0 for leaf in leaves}
    n = len(active)
    if n == 0:
        return phi

    # Evaluate every coalition once. The previous implementation evaluated a
    # coalition again for every candidate leaf, making even small regressions
    # take tens of seconds.
    values: dict[frozenset[str], float] = {}
    for coalition in subsets(active, include_full=True):
        key = frozenset(coalition)
        values[key] = evaluator(blend(coalition, prior, curr))

    for coalition in subsets(active):
        weight = factorial(len(coalition)) * factorial(n - len(coalition) - 1) / factorial(n)
        base = values[frozenset(coalition)]
        for leaf in active:
            if leaf in coalition:
                continue
            with_leaf = values[frozenset(coalition | {leaf})]
            phi[leaf] += weight * (with_leaf - base)
    delta = evaluator(curr) - evaluator(prior)
    residual = abs(sum(phi.values()) - delta)
    if residual >= tolerance:
        raise AssertionError(
            f"Shapley sum {sum(phi.values()):.4f} != Δprofit {delta:.4f} "
            f"(gap {residual:.4f})"
        )
    return phi
