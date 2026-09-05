"""Findings JSON first. Prose is generated from nodes and then validated."""

from __future__ import annotations

from typing import Any

from agent import llm
from rcg.validator import ValidationError, validate_text


def build_findings(
    *,
    period: str,
    run_id: str,
    headline: dict[str, Any],
    ranked: list[Any],
    investigation: Any,
    revisions: list[dict],
    confidence_regime: str,
    reconciliation: str,
) -> dict[str, Any]:
    findings = []
    questions = []
    for i, item in enumerate(ranked[:4], start=1):
        hyps = [h for h in investigation.results if h.leaf == item.leaf]
        fid = f"f_{i:03d}"
        findings.append(
            {
                "id": fid,
                "severity": "high" if i == 1 else "medium",
                "title": f"{item.leaf} {item.dollar_impact:+.0f}",
                "leaf": item.leaf,
                "attribution_dollars": round(item.dollar_impact, 2),
                "z": round(item.z, 2),
                "hypotheses": [
                    {
                        "id": h.id,
                        "class": h.cls,
                        "verdict": h.verdict.label,
                        "posterior": round(h.posterior, 3),
                        "claim": h.claim,
                    }
                    for h in hyps
                ],
                "confidence": 0.6 if confidence_regime == "prior_dominant" else 0.79,
            }
        )
        for h in hyps:
            if h.question:
                questions.append({"id": f"q_{h.id}", "text": h.question, "leaf": h.leaf})
    return {
        "period": period,
        "run_id": run_id,
        "status": "complete",
        "reconciliation": reconciliation,
        "confidence_regime": confidence_regime,
        "headline": headline,
        "findings": findings,
        "verify": [],
        "improved": [],
        "questions": questions[:3],
        "revisions": revisions,
        "next_period_watch": [r.leaf for r in ranked[:2]],
    }


def _fallback_narrative(findings: dict[str, Any]) -> dict[str, str]:
    h = findings["headline"]
    top = findings["findings"][0] if findings["findings"] else {}
    briefing = (
        f"I've analyzed {findings['period']}. Operating profit changed "
        f"{h['change']:+.0f} ({h.get('change_pct', 0):+.1f}%). "
        f"The leading driver is {top.get('leaf', 'unknown')} at "
        f"{top.get('attribution_dollars', 0):+.0f}."
    )
    lines = [briefing]
    for item in findings["findings"][:3]:
        hyps = item.get("hypotheses") or []
        lead = hyps[0] if hyps else {}
        lines.append(
            f"{item['title']}. The evidence points to {lead.get('class', 'an open question')} "
            f"(posterior {lead.get('posterior', 0):.2f}, {lead.get('verdict', 'unresolved')})."
        )
    return {
        "briefing": briefing,
        "walkthrough": " ".join(lines),
        "recommendations": "I will rank interventions after the next sensitivity pass.",
        "verify": "No leakage items on this run.",
    }


def render_narrative(findings: dict[str, Any], node_values: dict[str, Any], *, use_llm: bool) -> dict[str, str]:
    pack = _fallback_narrative(findings)
    if use_llm and llm.available():
        try:
            drafted = llm.complete_json(
                "You are a café financial analyst. Write short plain sentences. "
                "Use ONLY these figures. Never invent a number. Never say fraud, scam, cheat, or overcharge. "
                "Say 'the evidence points to' not 'proven'. "
                "If confidence_regime is prior_dominant, say you are measuring against café-sector norms.\n"
                f"findings={findings}\n"
                'Return {"briefing": "...", "walkthrough": "...", "recommendations": "...", "verify": "..."}'
            )
            if isinstance(drafted, dict) and "briefing" in drafted:
                pack = {**pack, **{k: str(v) for k, v in drafted.items()}}
        except Exception:
            pass
    for key, text in pack.items():
        try:
            validate_text(text, {**node_values, "findings": findings})
        except ValidationError:
            pack[key] = _fallback_narrative(findings)[key] if key in _fallback_narrative(findings) else text
            validate_text(pack[key], {**node_values, "findings": findings})
    return pack
