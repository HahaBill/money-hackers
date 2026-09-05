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
    relationship_flags: list[dict[str, Any]] | None = None,
    simulations: list[dict[str, Any]] | None = None,
    verify_items: list[dict[str, Any]] | None = None,
    directives: list[dict[str, Any]] | None = None,
    attribution_nodes: dict[str, str] | None = None,
    concentrations: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings = []
    questions = []
    attribution_nodes = attribution_nodes or {}
    concentrations = concentrations or {}
    simulations = simulations or []
    directives = directives or []
    for i, item in enumerate(ranked[:4], start=1):
        hyps = [h for h in investigation.results if h.leaf == item.leaf]
        confidence_cap = {
            "prior_dominant": 0.60,
            "prior_assisted": 0.80,
        }.get(confidence_regime, 1.00)
        # Attribution is deterministic; causal confidence is bounded by the
        # strongest hypothesis and the amount of business history available.
        causal_confidence = max((h.posterior for h in hyps), default=0.50)
        confidence = min(confidence_cap, max(0.50, causal_confidence))
        fid = f"f_{i:03d}"
        findings.append(
            {
                "id": fid,
                "severity": "high" if i == 1 else "medium",
                "title": f"{item.leaf} {item.dollar_impact:+.0f}",
                "leaf": item.leaf,
                "attribution_dollars": round(item.dollar_impact, 2),
                "z": round(item.z, 2),
                "attribution": [attribution_nodes[item.leaf]] if item.leaf in attribution_nodes else [],
                "concentration": [concentrations[item.leaf]["node"]]
                if item.leaf in concentrations
                else [],
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
                "confidence": round(confidence, 3),
                "confidence_cap": confidence_cap,
                "evidence": list(
                    dict.fromkeys(
                        update.evidence_id
                        for hypothesis in hyps
                        for update in hypothesis.updates
                    )
                ),
                "simulations": [row["node"] for row in simulations if row["leaf"] == item.leaf],
                "directives": [row["node"] for row in directives if row["driver"] == item.leaf],
            }
        )
        for h in hyps:
            if h.question:
                questions.append(h.question)
    from agent.questions import select

    questions = select(questions)
    return {
        "period": period,
        "run_id": run_id,
        "status": "complete",
        "reconciliation": reconciliation,
        "confidence_regime": confidence_regime,
        "headline": headline,
        "findings": findings,
        "verify": verify_items or [],
        "improved": [],
        "questions": questions,
        "revisions": revisions,
        "next_period_watch": [r.leaf for r in ranked[:2]],
        "relationship_flags": relationship_flags or [],
        "simulations": simulations,
        "directives": directives,
        "concentrations": list(concentrations.values()),
    }


def _fallback_narrative(findings: dict[str, Any]) -> dict[str, Any]:
    h = findings["headline"]
    top = findings["findings"][0] if findings["findings"] else {}
    briefing = (
        f"I've analyzed {findings['period']}. Operating profit changed "
        f"{h['change']:+.0f} ({h.get('change_pct', 0):+.1f}%). "
        f"The leading driver is {top.get('leaf', 'unknown')} at "
        f"{top.get('attribution_dollars', 0):+.0f}."
    )
    lines = [briefing]
    finding_texts = {}
    for item in findings["findings"][:3]:
        hyps = item.get("hypotheses") or []
        lead = hyps[0] if hyps else {}
        verdict = lead.get("verdict", "unresolved")
        cls = lead.get("class", "the cause")
        if verdict == "supported":
            assessment = f"The evidence points to {cls}"
        elif verdict == "rejected":
            assessment = f"The evidence weighs against {cls}"
        else:
            assessment = f"{cls} remains {verdict}"
        rendered = f"{item['title']}. {assessment} (posterior {lead.get('posterior', 0):.2f})."
        lines.append(rendered)
        finding_texts[item["id"]] = rendered
    simulations = findings.get("simulations") or []
    if simulations:
        rec_lines = []
        for sim in simulations[:3]:
            direction = f"{sim['delta_pct']:+.0f}%"
            rec_lines.append(
                f"{sim['leaf']} {direction} models to ${abs(sim['delta_profit']):,.0f} "
                f"more profit, {sim['assumption']}."
            )
        recommendations = " ".join(rec_lines)
    else:
        recommendations = "No modeled intervention cleared the positive-impact filter."
    verify_items = findings.get("verify") or []
    if verify_items:
        verify_lines = [
            f"Worth verifying with {item['entity']}: about ${abs(item['gap_dollars']):,.0f}. "
            f"{item['counter_explanation']}"
            for item in verify_items[:3]
        ]
        verify_text = " ".join(verify_lines)
    else:
        verify_text = "No leakage items on this run."
    return {
        "briefing": briefing,
        "walkthrough": " ".join(lines),
        "recommendations": recommendations,
        "verify": verify_text,
        "finding_texts": finding_texts,
    }


def render_narrative(findings: dict[str, Any], node_values: dict[str, Any], *, use_llm: bool) -> dict[str, Any]:
    fallback = _fallback_narrative(findings)
    pack = dict(fallback)
    if use_llm and llm.available():
        try:
            drafted = llm.complete_json(
                "You are a café financial analyst. Write short plain sentences. "
                "Use ONLY these figures. Never invent a number. Never say fraud, scam, cheat, or overcharge. "
                "Say 'the evidence points to' not 'proven'. "
                "If confidence_regime is prior_dominant, say you are measuring against café-sector norms.\n"
                f"findings={findings}\n"
                'Return {"briefing": "...", "walkthrough": "...", "recommendations": "...", "verify": "..."}',
                route="judgment",
            )
            if isinstance(drafted, dict) and "briefing" in drafted:
                pack = {
                    **pack,
                    **{
                        key: str(value)
                        for key, value in drafted.items()
                        if key in {"briefing", "walkthrough", "recommendations", "verify"}
                    },
                }
        except Exception:
            pass
    for key, value in list(pack.items()):
        if isinstance(value, dict):
            for subkey, text in list(value.items()):
                try:
                    validate_text(text, {**node_values, "findings": findings})
                except ValidationError:
                    value[subkey] = fallback[key][subkey]
                    validate_text(value[subkey], {**node_values, "findings": findings})
            continue
        try:
            validate_text(value, {**node_values, "findings": findings})
        except ValidationError:
            pack[key] = fallback.get(key, value)
            validate_text(pack[key], {**node_values, "findings": findings})
    return pack
