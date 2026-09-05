"""Full P0 run: compute → rank → investigate → find → narrate → trace."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.investigate import investigate
from agent.memory import Memory
from agent.narrative import build_findings, render_narrative
from agent.revision import apply_revisions
from agent.tavily_tool import TavilyResearcher
from engine.baselines import PRIORS, shrink
from engine.concentration import concentrate
from engine.directives import as_json as directive_json
from engine.directives import issue
from engine.graph_def import attribution_leaves, controllability_for, profit_fn
from engine.leakage import scan as scan_leakage
from engine.materiality import rank
from engine.metrics import from_leaf_state
from engine.relationships import evaluate as evaluate_relationships
from engine.sensitivity import simulate
from engine.shapley import shapley
from rcg.invariants import check_all
from engine.model import Transaction
from engine.reconcile import map_category
from rcg.store import Edge, GraphStore


@dataclass
class RunResult:
    findings: dict[str, Any]
    narrative: dict[str, Any]
    phi: dict[str, float]
    ranking: list[Any]
    investigation: Any
    revisions: list[dict]
    relationship_flags: list[dict]
    simulations: list[dict]
    leakage_flags: list[dict]
    directives: list[dict]


def _next_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-", 1))
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


def _leaf_scalar(state, leaf: str) -> float | None:
    if leaf.startswith("unit_cost."):
        return state.unit_cost.get(leaf.split(".", 1)[1])
    if leaf == "usage_efficiency":
        values = list(state.usage_efficiency.values())
        return sum(values) / len(values) if values else None
    if leaf in {
        "volume",
        "traffic",
        "conversion",
        "items_per_order",
        "variable_labor",
        "fixed_labor",
        "electricity_variable",
        "electricity_fixed",
        "rent",
        "other_variable",
        "other_fixed",
    }:
        value = getattr(state, leaf)
        return float(value) if value is not None else None
    return None


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _period_index(period: str) -> int:
    year, month = (int(part) for part in period.split("-", 1))
    return year * 12 + month


def _historical_nodes(
    store: GraphStore,
    *,
    type_: str,
    label: str,
    before_period: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in store.nodes(type=type_, label=label)
        if row["period"] < before_period and row["status"] == "active"
    ]
    rows.sort(key=lambda row: (row["period"], row["created_at"]), reverse=True)
    unique = []
    seen_periods: set[str] = set()
    for row in rows:
        if row["period"] in seen_periods:
            continue
        seen_periods.add(row["period"])
        unique.append(row)
        if len(unique) >= limit:
            break
    return list(reversed(unique))


def _leaf_observation(prior, curr, leaf: str, phi: float, revenue: float) -> tuple[float, str]:
    prior_value = _leaf_scalar(prior, leaf)
    current_value = _leaf_scalar(curr, leaf)
    if prior_value is not None and current_value is not None and abs(prior_value) > 1e-9:
        return (current_value - prior_value) / abs(prior_value), "leaf_percent_change"
    return phi / max(abs(revenue), 1.0), "attribution_share_of_revenue"


def _baseline_for(
    store: GraphStore,
    *,
    period: str,
    leaf: str,
    observation: float,
):
    rows = _historical_nodes(
        store,
        type_="baseline",
        label=leaf,
        before_period=period,
    )
    history = [float(_json_value(row["value"])["observation"]) for row in rows]
    key = "volume_drift" if leaf in {"volume", "traffic", "conversion"} else "aov_drift"
    center, scale = PRIORS[key]
    baseline = shrink(
        history,
        observation,
        prior_center=center,
        prior_scale=scale,
    )
    count = 1 if abs(baseline.z) > 1.5 else 0
    expected = _period_index(period) - 1
    for row in reversed(rows):
        if _period_index(row["period"]) != expected:
            break
        previous = _json_value(row["value"])
        if abs(float(previous["z"])) <= 1.5:
            break
        count += 1
        expected -= 1
    return baseline, max(1, count), (rows[-1] if rows else None), history


def _level_drift(observations: list[float], *, periods: int = 6) -> tuple[bool, float]:
    if len(observations) < periods:
        return False, 0.0
    window = observations[-periods:]
    same_direction = all(value >= 0.025 for value in window) or all(
        value <= -0.025 for value in window
    )
    cumulative = sum(window)
    return same_direction and abs(cumulative) >= 0.20, cumulative


def _concentration_rows(
    *,
    transactions: list[Transaction],
    category_map: dict[str, str],
    period: str,
    leaf: str,
    impact: float,
    prior,
    curr,
    revenue: float,
) -> list[tuple[str, float]]:
    if abs(impact) < 0.01:
        return []
    if leaf == "mix":
        return [
            (product, (curr.mix.get(product, 0) - prior.mix.get(product, 0)) * revenue)
            for product in curr.mix
        ]
    rows = [txn for txn in transactions if txn.period == period]
    weights: dict[str, float] = defaultdict(float)
    mapped_leaf = None
    if leaf.startswith("unit_cost."):
        mapped_leaf = leaf.split(".", 1)[1]
    elif leaf in {"variable_labor", "fixed_labor"}:
        mapped_leaf = "labor"
    elif leaf in {"electricity_variable", "electricity_fixed"}:
        mapped_leaf = "electricity"
    elif leaf == "rent":
        mapped_leaf = "rent"
    elif leaf in {"other_variable", "other_fixed"}:
        mapped_leaf = "other_opex"

    if mapped_leaf:
        for txn in rows:
            if txn.txn_type not in {"cogs", "opex"}:
                continue
            if map_category(txn.category, category_map) != mapped_leaf:
                continue
            weights[txn.counterparty or "unknown"] += abs(float(txn.amount))
    elif leaf == "price":
        for txn in rows:
            if txn.txn_type != "revenue" or not txn.product or txn.quantity is None:
                continue
            change = abs(curr.price.get(txn.product, 0.0) - prior.price.get(txn.product, 0.0))
            weights[txn.product] += abs(float(txn.quantity)) * change
    elif leaf in {"volume", "traffic", "conversion", "items_per_order"}:
        for txn in rows:
            if txn.txn_type != "revenue":
                continue
            quantity = abs(float(txn.quantity)) if txn.quantity is not None else abs(float(txn.amount))
            bucket = txn.hour_bucket or f"weekday_{txn.day_of_week}"
            weights[bucket] += quantity
    elif leaf == "usage_efficiency":
        for txn in rows:
            if txn.txn_type == "cogs":
                weights[txn.counterparty or "unknown"] += abs(float(txn.amount))

    total = sum(weights.values())
    if total <= 0:
        return []
    return [(entity, impact * weight / total) for entity, weight in weights.items()]


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
    data_payload: dict[str, Any] | None = None,
    transactions: list[Transaction] | None = None,
    category_map: dict[str, str] | None = None,
    researcher: TavilyResearcher | None = None,
    research_context: dict[str, Any] | None = None,
) -> RunResult:
    facts_by_leaf = facts_by_leaf or {}
    entities = entities or {}
    category_map = category_map or {}
    has_traffic = prior.traffic is not None
    leaves = attribution_leaves(has_traffic)
    phi = shapley(leaves, prior, curr)
    prior_m = from_leaf_state("prior", prior)
    curr_m = from_leaf_state(period, curr)
    delta = curr_m.operating_profit - prior_m.operating_profit

    relationship_flags = evaluate_relationships(
        prior_m,
        curr_m,
        patterns=memory.learned_patterns,
    )
    leakage_flags = scan_leakage(transactions or [], period=period) if transactions else []

    data = store.add(
        type="data",
        period=period,
        run_id=run_id,
        label="leaf_states",
        value={
            "prior_profit": prior_m.operating_profit,
            "curr_profit": curr_m.operating_profit,
            **(data_payload or {}),
        },
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
        value=delta,
        inputs=[data.id],
        method="profit_fn",
        formula="profit(curr)-profit(prior)",
    )

    items = []
    attr_nodes = {}
    concentration_json: dict[str, dict[str, Any]] = {}
    level_drift_json: list[dict[str, Any]] = []
    for leaf, value in phi.items():
        node = store.add(
            type="attribution",
            period=period,
            run_id=run_id,
            label=leaf,
            value=value,
            inputs=[var.id],
            method="shapley",
            formula=f"phi({leaf})",
        )
        attr_nodes[leaf] = node
        observation, observation_method = _leaf_observation(
            prior,
            curr,
            leaf,
            value,
            curr_m.revenue,
        )
        baseline, persistence_count, previous_baseline, observation_history = _baseline_for(
            store,
            period=period,
            leaf=leaf,
            observation=observation,
        )
        baseline_node = store.add(
            type="baseline",
            period=period,
            run_id=run_id,
            label=leaf,
            value={
                "observation": observation,
                "observation_method": observation_method,
                "center": baseline.center,
                "scale": baseline.scale,
                "n": baseline.n,
                "prior_weight": baseline.prior_weight,
                "z": baseline.z,
                "tag": baseline.tag,
            },
            unit="ratio",
            inputs=[node.id],
            method="median_mad_prior_shrinkage",
        )
        if (
            previous_baseline
            and _period_index(period) - _period_index(previous_baseline["period"]) == 1
        ):
            store.write_edge(
                Edge(previous_baseline["id"], baseline_node.id, "recurs_from", period, run_id)
            )
        drifted, cumulative_drift = _level_drift([*observation_history, observation])
        if drifted:
            drift_node = store.add(
                type="relationship_flag",
                period=period,
                run_id=run_id,
                label=f"level_drift:{leaf}",
                value={
                    "dollars": value,
                    "detail": "six-period same-direction level drift",
                    "drill": [leaf],
                    "cumulative_change": cumulative_drift,
                },
                inputs=[baseline_node.id],
            )
            level_drift_json.append(
                {
                    "node": drift_node.id,
                    "rule": "level_drift",
                    "leaf": leaf,
                    "dollars": round(value, 2),
                    "detail": "six-period same-direction level drift",
                    "drill": [leaf],
                    "cumulative_change": round(cumulative_drift, 4),
                }
            )
        previous_attributions = _historical_nodes(
            store,
            type_="attribution",
            label=leaf,
            before_period=period,
            limit=1,
        )
        if previous_attributions:
            previous = previous_attributions[-1]
            previous_value = float(_json_value(previous["value"]))
            if (
                _period_index(period) - _period_index(previous["period"]) == 1
                and previous_value * value > 0
            ):
                store.write_edge(Edge(previous["id"], node.id, "recurs_from", period, run_id))
        z = baseline.z
        hhi = None
        rows = _concentration_rows(
            transactions=transactions or [],
            category_map=category_map,
            period=period,
            leaf=leaf,
            impact=value,
            prior=prior,
            curr=curr,
            revenue=curr_m.revenue,
        )
        if rows:
            prior_concentrations = _historical_nodes(
                store,
                type_="concentration",
                label=leaf,
                before_period=period,
                limit=1,
            )
            prior_top3: set[str] = set()
            if prior_concentrations:
                previous_concentration = _json_value(prior_concentrations[-1]["value"])
                prior_top3 = {
                    item["entity"]
                    for item in previous_concentration.get("contributors", [])[:3]
                }
            conc = concentrate(rows, leaf=leaf, prior_top3=prior_top3)
            hhi = conc.hhi
            conc_node = store.add(
                type="concentration",
                period=period,
                run_id=run_id,
                label=leaf,
                value={
                    "hhi": conc.hhi,
                    "label": conc.label,
                    "contributors": [
                        {
                            "entity": contributor.entity,
                            "dollars": contributor.dollars,
                            "share": contributor.share,
                            "recurring_top": contributor.recurring_top,
                        }
                        for contributor in conc.contributors[:3]
                    ],
                },
                inputs=[node.id],
            )
            concentration_json[leaf] = {
                "node": conc_node.id,
                "leaf": leaf,
                "hhi": conc.hhi,
                "label": conc.label,
                "contributors": [
                    {
                        "entity": contributor.entity,
                        "dollars": round(contributor.dollars, 2),
                        "share": round(contributor.share, 4),
                        "recurring_top": contributor.recurring_top,
                    }
                    for contributor in conc.contributors[:3]
                ],
            }
        items.append(
            {
                "leaf": leaf,
                "dollar_impact": value,
                "z": z,
                "persistence": persistence_count,
                "hhi": hhi,
            }
        )

    ranked = rank(items, revenue=curr_m.revenue)
    relationship_json = list(level_drift_json)
    for flag in relationship_flags:
        node = store.add(
            type="relationship_flag",
            period=period,
            run_id=run_id,
            label=flag.rule,
            value={"dollars": flag.dollars, "detail": flag.detail, "drill": flag.drill},
            inputs=[var.id],
        )
        relationship_json.append(
            {
                "node": node.id,
                "rule": flag.rule,
                "dollars": round(flag.dollars, 2),
                "detail": flag.detail,
                "drill": flag.drill,
            }
        )

    leakage_json = []
    for flag in leakage_flags:
        node = store.add(
            type="leakage_flag",
            period=period,
            run_id=run_id,
            label=f"{flag.rule}:{flag.entity}",
            value=flag.as_json(),
            inputs=[data.id],
        )
        leakage_json.append({"node": node.id, **flag.as_json()})

    beneficial = [row for row in simulate(curr) if row.d_profit > 0]
    beneficial.sort(key=lambda row: row.d_profit, reverse=True)
    # Keep one best intervention per leaf so the recommendation list is useful.
    simulation_json = []
    seen_sim_leaves: set[str] = set()
    for intervention in beneficial:
        if intervention.leaf in seen_sim_leaves:
            continue
        seen_sim_leaves.add(intervention.leaf)
        node = store.add(
            type="simulation",
            period=period,
            run_id=run_id,
            label=f"{intervention.leaf}:{intervention.delta:+.2f}",
            value=intervention.d_profit,
            payload={
                "delta": intervention.delta,
                "assumptions": intervention.assumptions,
                "sweep_range": intervention.sweep_range,
                "confidence": intervention.confidence,
            },
            inputs=[data.id],
            method="profit_fn",
        )
        simulation_json.append(
            {
                "node": node.id,
                "leaf": intervention.leaf,
                "delta_pct": intervention.delta * 100.0,
                "delta_profit": round(intervention.d_profit, 2),
                "assumption": intervention.assumptions["volume_response"],
                "volume_response_pct": intervention.assumptions.get("volume_response_pct"),
                "sweep_range": list(intervention.sweep_range) if intervention.sweep_range else None,
                "confidence": intervention.confidence,
            }
        )

    directives_json = []
    for item in ranked:
        if item.dollar_impact >= 0:
            continue
        current_value = _leaf_scalar(curr, item.leaf)
        prior_value = _leaf_scalar(prior, item.leaf)
        if current_value is None or prior_value is None:
            continue
        scale = max(abs(prior_value) * 0.05, 0.01)
        justification = [attr_nodes[item.leaf].id]
        sim = next((row for row in simulation_json if row["leaf"] == item.leaf), None)
        if sim:
            justification.append(sim["node"])
        directive = issue(
            leaf=item.leaf,
            current=current_value,
            center=prior_value,
            scale=scale,
            gap_dollars=abs(item.dollar_impact),
            controllability=controllability_for(item.leaf),
            review_period=_next_period(period),
            justifies=justification,
            unit="ratio" if item.leaf in {"conversion", "usage_efficiency"} else "USD",
        )
        payload = directive_json(directive)
        node = store.add(
            type="directive",
            period=period,
            run_id=run_id,
            label=item.leaf,
            value=payload,
            inputs=justification,
        )
        payload["node"] = node.id
        directives_json.append(payload)
        memory.add_directive(payload)
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
        researcher=researcher,
        research_context=research_context,
    )
    revisions = apply_revisions(inv.results, store=store, period=period, run_id=run_id, memory=memory)

    headline = {
        "metric": "operating_profit",
        "change": round(delta, 2),
        "change_pct": round(100.0 * delta / abs(prior_m.operating_profit or 1.0), 1),
        "context": f"revenue {curr_m.revenue - prior_m.revenue:+.0f}",
        "node": var.id,
    }
    if history_n <= 2:
        regime = "prior_dominant"
    elif history_n <= 5:
        regime = "prior_assisted"
    else:
        regime = ""
    findings = build_findings(
        period=period,
        run_id=run_id,
        headline=headline,
        ranked=ranked,
        investigation=inv,
        revisions=revisions,
        confidence_regime=regime,
        reconciliation="passed",
        relationship_flags=relationship_json,
        simulations=simulation_json,
        verify_items=leakage_json,
        directives=directives_json,
        attribution_nodes={leaf: node.id for leaf, node in attr_nodes.items()},
        concentrations=concentration_json,
    )
    for finding in findings["findings"]:
        finding_node = store.add(
            type="finding",
            period=period,
            run_id=run_id,
            label=finding["id"],
            value=finding["title"],
            provenance="inferred",
            inputs=finding["attribution"],
        )
        finding["node"] = finding_node.id
    narrative = render_narrative(
        findings,
        store.node_values(run_id=run_id),
        use_llm=use_llm,
    )
    findings["narrative"] = narrative
    check_all(store, period, run_id)
    return RunResult(
        findings=findings,
        narrative=narrative,
        phi=phi,
        ranking=ranked,
        investigation=inv,
        revisions=revisions,
        relationship_flags=relationship_json,
        simulations=simulation_json,
        leakage_flags=leakage_json,
        directives=directives_json,
    )


def persist(result: RunResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.findings, indent=2))
