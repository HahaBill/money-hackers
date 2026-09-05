"""Target directives. Indicators are rule-based, never LLM (§16)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

HIGHER_IS_BETTER = {"traffic", "volume", "conversion", "items_per_order", "price"}


@dataclass
class Directive:
    driver: str
    current: float
    unit: str
    normal_range: tuple[float, float]
    direction: str
    target: float
    gap_dollars_month: float
    controllability: float
    indicator: str
    justifies: list[str]
    review_period: str


def indicator(
    *,
    current: float,
    lo: float,
    hi: float,
    gap: float,
    higher_better: bool,
    drifted: bool,
    was_flagged: bool,
) -> str:
    inside = lo <= current <= hi
    if was_flagged and inside:
        return "green_check"
    if inside:
        return "amber" if drifted else "grey"
    if abs(gap) < 250:
        return "amber"
    if higher_better:
        return "red_up" if current < lo else "red_down"
    return "red_down" if current > hi else "red_up"


def issue(
    *,
    leaf: str,
    current: float,
    center: float,
    scale: float,
    gap_dollars: float,
    controllability: float,
    review_period: str,
    justifies: list[str],
    unit: str = "USD",
    drifted: bool = False,
    was_flagged: bool = False,
) -> Directive:
    lo, hi = center - scale, center + scale
    higher = leaf in HIGHER_IS_BETTER
    if higher:
        target = max(current, center)
        direction = "up" if current < center else "hold"
    else:
        target = min(current, center)
        direction = "down" if current > center else "hold"
    return Directive(
        driver=leaf,
        current=current,
        unit=unit,
        normal_range=(round(lo, 4), round(hi, 4)),
        direction=direction,
        target=round(target, 4),
        gap_dollars_month=round(gap_dollars, 2),
        controllability=controllability,
        indicator=indicator(
            current=current,
            lo=lo,
            hi=hi,
            gap=gap_dollars,
            higher_better=higher,
            drifted=drifted,
            was_flagged=was_flagged,
        ),
        justifies=justifies,
        review_period=review_period,
    )


def score_prior(prior: list[dict[str, Any]], realized: dict[str, float]) -> dict[str, float]:
    if not prior:
        return {"directive_hit_rate": 0.0, "impact_calibration": 0.0, "n": 0}
    hits = 0
    calib = []
    for d in prior:
        leaf = d["driver"]
        now = realized.get(leaf)
        if now is None:
            continue
        toward = (now - d["current"]) * (1 if d["direction"] == "up" else -1) > 0
        hits += int(toward)
        modeled = d.get("gap_dollars_month") or 0
        if modeled:
            calib.append((now - d["current"]) / modeled)
    n = max(1, len(prior))
    return {
        "directive_hit_rate": hits / n,
        "impact_calibration": sum(calib) / len(calib) if calib else 0.0,
        "n": len(prior),
    }


def as_json(d: Directive) -> dict[str, Any]:
    blob = asdict(d)
    blob["normal_range"] = list(d.normal_range)
    return blob
