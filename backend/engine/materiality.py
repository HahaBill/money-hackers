"""Gated, log-scaled materiality. Exponents are declared constants (§13)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from engine.graph_def import controllability_for

# Relative weight of dollars vs abnormality. Changing these changes the ranking;
# the narrative answer to "why ingredients beat electricity" is this formula.
DOLLAR_EXPONENT = 0.5
ABNORMALITY_EXPONENT = 0.3
GATE_DOLLARS = 150.0
GATE_REVENUE_PCT = 0.0025


@dataclass
class RankedLeaf:
    leaf: str
    dollar_impact: float
    z: float
    persistence: int
    hhi: float | None
    controllability: float
    raw_score: float
    score: float  # rescaled so top = 100


def gate_floor(revenue: float) -> float:
    return max(GATE_DOLLARS, GATE_REVENUE_PCT * abs(revenue))


def materiality_score(
    dollar_impact: float,
    z: float,
    persistence: int,
    hhi: float | None,
    controllability: float,
    *,
    revenue: float,
    max_impact: float,
) -> float | None:
    floor = gate_floor(revenue)
    if abs(dollar_impact) < floor:
        return None
    d = math.log1p(abs(dollar_impact) / floor) / math.log1p(max(max_impact, floor) / floor)
    a = min(1.0, max(0.15, (abs(z) - 1.0) / 3.0))
    p = 1.0 + 0.15 * min(max(persistence, 1) - 1, 3)
    h = 0.7 + 0.3 * (hhi if hhi is not None else 0.0)
    return 100.0 * (d**DOLLAR_EXPONENT) * (a**ABNORMALITY_EXPONENT) * p * controllability * h


def rank(
    items: list[dict],
    *,
    revenue: float,
) -> list[RankedLeaf]:
    """items: leaf, dollar_impact, z, persistence, hhi?"""
    if not items:
        return []
    max_impact = max(abs(i["dollar_impact"]) for i in items)
    scored: list[RankedLeaf] = []
    for item in items:
        leaf = item["leaf"]
        ctrl = item.get("controllability", controllability_for(leaf))
        raw = materiality_score(
            item["dollar_impact"],
            item.get("z", 0.0),
            item.get("persistence", 1),
            item.get("hhi"),
            ctrl,
            revenue=revenue,
            max_impact=max_impact,
        )
        if raw is None:
            continue
        scored.append(
            RankedLeaf(
                leaf=leaf,
                dollar_impact=item["dollar_impact"],
                z=item.get("z", 0.0),
                persistence=item.get("persistence", 1),
                hhi=item.get("hhi"),
                controllability=ctrl,
                raw_score=raw,
                score=raw,
            )
        )
    if not scored:
        return []
    top = max(r.raw_score for r in scored)
    for row in scored:
        row.score = 100.0 * row.raw_score / top
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored
