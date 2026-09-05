"""Robust median/MAD baselines with café-sector prior shrinkage (§12)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import statistics

N0 = 3.0
MAD_TO_SD = 1.4826

PRIORS: dict[str, tuple[float, float]] = {
    # center0, scale0
    "gross_margin": (0.68, 0.05),
    "cogs_pct": (0.31, 0.05),
    "labor_pct": (0.30, 0.05),
    "rent_pct": (0.11, 0.03),
    "utilities_pct": (0.03, 0.01),
    "other_opex_pct": (0.07, 0.025),
    "net_margin": (0.12, 0.05),
    "milk_cogs": (0.18, 0.04),
    "beans_cogs": (0.30, 0.06),
    "food_cogs": (0.35, 0.08),
    "packaging_cogs": (0.08, 0.03),
    "aov_drift": (0.0, 0.03),
    "volume_drift": (0.0, 0.08),
}


@dataclass
class Baseline:
    center: float
    scale: float
    n: int
    prior_weight: float
    z: float
    tag: str  # prior_dominant | prior_assisted | ""


def _mad(xs: list[float]) -> float:
    if not xs:
        return 0.0
    med = statistics.median(xs)
    return statistics.median([abs(x - med) for x in xs])


def shrink(
    history: list[float],
    current: float,
    *,
    prior_center: float,
    prior_scale: float,
    n0: float = N0,
) -> Baseline:
    n = len(history)
    if n == 0:
        center = prior_center
        scale = prior_scale
    else:
        med = statistics.median(history)
        mad = _mad(history)
        obs_scale = MAD_TO_SD * mad if mad > 0 else prior_scale
        center = (n0 * prior_center + n * med) / (n0 + n)
        scale = math.sqrt((n0 * prior_scale**2 + n * obs_scale**2) / (n0 + n))
    prior_weight = n0 / (n0 + n)
    scale = scale or 1e-9
    z = (current - center) / scale
    if n <= 2:
        tag = "prior_dominant"
        z = max(-2.0, min(2.0, z))  # confidence cap 0.60 is applied at findings
    elif n <= 5:
        tag = "prior_assisted"
    else:
        tag = ""
    return Baseline(center=center, scale=scale, n=n, prior_weight=prior_weight, z=z, tag=tag)


def persistence(z_series: list[float], threshold: float = 1.5) -> int:
    """Consecutive trailing periods with |z| > threshold."""
    count = 0
    for z in reversed(z_series):
        if abs(z) > threshold:
            count += 1
        else:
            break
    return count
