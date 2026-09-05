"""Forward sensitivity on contribution, with an explicit elasticity sweep (§15)."""

from __future__ import annotations

from dataclasses import dataclass

from engine.graph_def import LeafState, contribution_fn, scale_leaf

DEFAULT_ELASTICITY = -0.4
SWEEP = (-0.2, -0.4, -0.8)
DELTAS = (-0.10, -0.05, 0.05, 0.10)
CONTROLLABLE = (
    "price",
    "unit_cost.milk",
    "usage_efficiency",
    "electricity_fixed",
    "variable_labor",
)


@dataclass
class Intervention:
    leaf: str
    delta: float
    d_contribution: float
    assumptions: dict
    sweep_range: tuple[float, float] | None
    confidence: float


def _with_price(state: LeafState, delta: float, elasticity: float) -> LeafState:
    out = scale_leaf(state, "price", 1.0 + delta)
    volume_factor = 1.0 + delta * elasticity
    if out.traffic is not None and out.conversion is not None:
        out.conversion = out.conversion * volume_factor
    else:
        out.volume *= volume_factor
    return out


def simulate(
    curr: LeafState,
    *,
    elasticity: float = DEFAULT_ELASTICITY,
    leaves: tuple[str, ...] = CONTROLLABLE,
) -> list[Intervention]:
    base = contribution_fn(curr)
    out: list[Intervention] = []
    price_ranks: dict[float, list[str]] = {}
    for leaf in leaves:
        for delta in DELTAS:
            if leaf == "price":
                values = []
                for e in SWEEP:
                    values.append(contribution_fn(_with_price(curr, delta, e)) - base)
                mid = contribution_fn(_with_price(curr, delta, elasticity)) - base
                lo, hi = min(values), max(values)
                out.append(
                    Intervention(
                        leaf=leaf,
                        delta=delta,
                        d_contribution=mid,
                        assumptions={
                            "own_price_elasticity": elasticity,
                            "sweep": list(SWEEP),
                            "volume_response": f"assuming about {abs(delta * elasticity)*100:.0f}% of volume is lost"
                            if delta > 0
                            else "assuming volume holds",
                        },
                        sweep_range=(lo, hi),
                        confidence=0.72,
                    )
                )
            else:
                nxt = scale_leaf(curr, leaf, 1.0 + delta)
                d = contribution_fn(nxt) - base
                out.append(
                    Intervention(
                        leaf=leaf,
                        delta=delta,
                        d_contribution=d,
                        assumptions={"elasticity": None, "volume_response": "assuming volume holds"},
                        sweep_range=None,
                        confidence=0.70,
                    )
                )
    plus5 = [i for i in out if abs(i.delta - 0.05) < 1e-9]
    plus5.sort(key=lambda i: i.d_contribution, reverse=True)
    return out


def estimate_elasticity(price_changes: list[tuple[float, float]]) -> tuple[float, int]:
    """log-log ΔQ vs ΔP. Returns (elasticity, n)."""
    if len(price_changes) < 2:
        return DEFAULT_ELASTICITY, 0
    nums = []
    for dp, dq in price_changes:
        if dp == 0 or 1 + dp <= 0 or 1 + dq <= 0:
            continue
        import math

        nums.append(math.log(1 + dq) / math.log(1 + dp))
    if not nums:
        return DEFAULT_ELASTICITY, 0
    return sum(nums) / len(nums), len(nums)
