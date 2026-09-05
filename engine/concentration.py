"""Transaction-grain concentration inside a material leaf (§11)."""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass
class Contributor:
    entity: str
    dollars: float
    share: float
    recurring_top: bool = False


@dataclass
class Concentration:
    leaf: str
    contributors: list[Contributor]
    hhi: float
    label: str  # concentrated | diffuse
    stop_entity: str | None


def herfindahl(shares: list[float]) -> float:
    return sum(s * s for s in shares)


def concentrate(
    rows: list[tuple[str, float]],
    *,
    leaf: str,
    prior_top3: set[str] | None = None,
) -> Concentration:
    """rows: (entity, dollar contribution). Stop when top-1 ≥ 50% or HHI ≥ 0.5."""
    prior_top3 = prior_top3 or set()
    totals: dict[str, float] = defaultdict(float)
    for entity, dollars in rows:
        totals[entity] += dollars
    grand = sum(abs(v) for v in totals.values()) or 1.0
    ordered = sorted(totals.items(), key=lambda kv: abs(kv[1]), reverse=True)
    contributors = [
        Contributor(
            entity=name,
            dollars=amt,
            share=abs(amt) / grand,
            recurring_top=name in prior_top3,
        )
        for name, amt in ordered
    ]
    hhi = herfindahl([c.share for c in contributors])
    label = "concentrated" if hhi > 0.25 else "diffuse" if hhi < 0.15 else "mixed"
    stop = None
    if contributors and (contributors[0].share >= 0.50 or hhi >= 0.5):
        stop = contributors[0].entity
    return Concentration(
        leaf=leaf,
        contributors=contributors,
        hhi=hhi,
        label=label,
        stop_entity=stop,
    )
