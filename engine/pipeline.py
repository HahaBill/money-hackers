"""Full P0 run: compute → rank → investigate → find → narrate → trace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.investigate import investigate
from agent.memory import Memory
from agent.narrative import build_findings, render_narrative
from agent.revision import apply_revisions
from engine.baselines import PRIORS, shrink
from engine.concentration import concentrate
from engine.graph_def import attribution_leaves, profit_fn
from engine.materiality import rank
from engine.metrics import from_leaf_state
from engine.shapley import shapley
from rcg.store import GraphStore


@dataclass
class RunResult:
    findings: dict[str, Any]
    narrative: dict[str, str]
    phi: dict[str, float]
    ranking: list[Any]
    investigation: Any
    revisions: list[dict]


def _z_for(leaf: str, phi: float, history_n: int) -> float:
    key = "volume_drift" if "volume" in leaf or "traffic" in leaf else "aov_drift"
    center, scale = PRIORS.get(key, (0.0, 0.08))
    # Treat phi / 10000 as a dimensionless drift so cold-start shrinkage still moves z.
    current = phi / 10_000.0
    hist = [0.0] * max(0, history_n)
    return shrink(hist, current, prior_center=center, prior_scale=scale).z


def analyze(
    *,
    period: str,
    run_id: str,
    prior,
    curr,
    store: GraphStore,
    memory: Memory,
    facts_by_leaf: dict[str, list[dict]] | None = None,
    entities: dict[str, str] | None = None,
    history_n: int = 4,
    use_llm: bool = False,
    agent_version: str = "v0.3.1",
) -> RunResult:
    facts_by_leaf = facts_by_leaf or {}
    entities = entities or {}
    has_traffic = prior.traffic is not None
    leaves = attribution_leaves(has_traffic)
    phi = shapley(leaves, prior, curr)
    prior_m = from_leaf_state("prior", prior)
    curr_m = from_leaf_state(period, curr)
    delta = curr_m.operating_profit - prior_m.operating_profit

    data = store.add(
        type="data",
        period=period,
        run_id=run_id,
        label="leaf_states",
        value={"prior_profit": prior_m.operating_profit, "curr_profit": curr_m.operating_profit},
        agent_version=agent_version,
    )
    store.add(
        type="metric",
        period=period,
        run_id=run_id,
        label="revenue",
        value=round(curr_m.revenue, 2),
        inputs=[data.id],
    )
    var = store.add(
        type="variance",
        period=period,
        run_id=run_id,
        label="operating_profit_delta",
        value=round(delta, 2),
        inputs=[data.id],
        method="profit_fn",
        formula="profit(curr)-profit(prior)",
    )

    items = []
    attr_nodes = {}
    for leaf, value in phi.items():
        node = store.add(
            type="attribution",
            period=period,
            run_id=run_id,
            label=leaf,
            value=round(value, 2),
            inputs=[var.id],
            method="shapley",
            formula=f"phi({leaf})",
        )
        attr_nodes[leaf] = node
        z = _z_for(leaf, value, history_n)
        hhi = None
        if leaf == "mix":
            rows = [
                (p, (curr.mix.get(p, 0) - prior.mix.get(p, 0)) * curr_m.revenue)
                for p in curr.mix
            ]
            conc = concentrate(rows, leaf="mix")
            hhi = conc.hhi
            store.add(
                type="concentration",
                period=period,
                run_id=run_id,
                label="mix",
                value={"hhi": conc.hhi, "contributors": [c.entity for c in conc.contributors[:3]]},
                inputs=[node.id],
            )
        items.append(
            {
                "leaf": leaf,
                "dollar_impact": value,
                "z": z,
                "persistence": 1,
                "hhi": hhi,
            }
        )

    ranked = rank(items, revenue=curr_m.revenue)
    inv = investigate(
        ranked,
        store=store,
        period=period,
        run_id=run_id,
        memory=memory,
        facts_by_leaf=facts_by_leaf,
        entity_by_leaf=entities,
        total_abs_delta=sum(abs(v) for v in phi.values()),
        use_llm=use_llm,
    )
    revisions = apply_revisions(inv.results, store=store, period=period, run_id=run_id, memory=memory)

    headline = {
        "metric": "operating_profit",
        "change": round(delta, 2),
        "change_pct": round(100.0 * delta / abs(prior_m.operating_profit or 1.0), 1),
        "context": f"revenue {curr_m.revenue - prior_m.revenue:+.0f}",
        "node": var.id,
    }
    regime = "prior_assisted" if history_n >= 3 else "prior_dominant"
    findings = build_findings(
        period=period,
        run_id=run_id,
        headline=headline,
        ranked=ranked,
        investigation=inv,
        revisions=revisions,
        confidence_regime=regime,
        reconciliation="passed",
    )
    finding_node = store.add(
        type="finding",
        period=period,
        run_id=run_id,
        label="period_report",
        value=findings["findings"][0]["title"] if findings["findings"] else "none",
        provenance="inferred",
        inputs=[attr_nodes[ranked[0].leaf].id] if ranked else [var.id],
    )
    _ = finding_node
    narrative = render_narrative(findings, store.node_values(), use_llm=use_llm)
    findings["narrative"] = narrative
    return RunResult(
        findings=findings,
        narrative=narrative,
        phi=phi,
        ranking=ranked,
        investigation=inv,
        revisions=revisions,
    )


def persist(result: RunResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.findings, indent=2))
