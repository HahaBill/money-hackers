"""Rule-based verdicts. No model (§17.4)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Verdict:
    label: str  # supported | weakening | rejected | unresolved
    posterior: float
    rule: str


def decide(
    *,
    posterior: float,
    has_tier2_nontemporal: bool,
    has_strong_against_internal: bool,
    previous: str | None = None,
    previous_posterior: float | None = None,
) -> Verdict:
    if has_strong_against_internal or posterior <= 0.15:
        return Verdict("rejected", posterior, "posterior<=0.15_or_strong_against")
    if (
        previous == "supported"
        and previous_posterior is not None
        and previous_posterior - posterior >= 0.2
    ):
        return Verdict("weakening", posterior, "prior_supported_dropped_0.2")
    if posterior >= 0.7 and has_tier2_nontemporal and not has_strong_against_internal:
        return Verdict("supported", posterior, "posterior>=0.7_and_tier<=2")
    return Verdict("unresolved", posterior, "default")
