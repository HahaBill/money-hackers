"""Structured belief update. LLM picks a support label; LR is a lookup. Temporal cap is mandatory."""

from __future__ import annotations

from dataclasses import dataclass

LR = {
    "strong_for": 8.0,
    "weak_for": 4.0,
    "neutral": 1.0,
    "weak_against": 0.25,
    "strong_against": 0.125,
}
TEMPORAL_CAP = 1.5  # weak_for ceiling for temporal-only evidence


@dataclass
class BeliefUpdate:
    hypothesis_id: str
    evidence_id: str
    support: str
    likelihood_ratio: float
    temporal_cap_applied: bool
    note: str


def lr_for(support: str, *, temporal_only: bool) -> tuple[float, bool]:
    if support not in LR:
        raise ValueError(f"unknown support label: {support}")
    raw = LR[support]
    if temporal_only and raw > TEMPORAL_CAP:
        return TEMPORAL_CAP, True
    return raw, False


def posterior_from(prior: float, ratios: list[float]) -> float:
    prior = min(0.95, max(0.05, prior))
    odds = prior / (1.0 - prior)
    for ratio in ratios:
        odds *= ratio
    return odds / (1.0 + odds)
