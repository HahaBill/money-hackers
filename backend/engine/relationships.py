"""Deterministic relationship rules. No LLM in the trigger (§13b)."""

from __future__ import annotations

from dataclasses import dataclass

from engine.metrics import PeriodMetrics


@dataclass
class RelationshipFlag:
    rule: str
    dollars: float
    drill: list[str]
    detail: str


def evaluate(
    prior: PeriodMetrics,
    curr: PeriodMetrics,
    *,
    patterns: list[dict] | None = None,
    context: dict | None = None,
) -> list[RelationshipFlag]:
    flags: list[RelationshipFlag] = []
    def pct(a, b):
        return 0.0 if b == 0 else (a - b) / abs(b)

    rev_d = pct(curr.revenue, prior.revenue)
    traf_d = pct(curr.traffic or 0, prior.traffic or 0) if curr.traffic and prior.traffic else None
    contrib_d = pct(curr.contribution, prior.contribution)
    orders_d = pct(curr.orders, prior.orders)
    prior_cm = prior.contribution / prior.revenue if prior.revenue else 0
    curr_cm = curr.contribution / curr.revenue if curr.revenue else 0
    cm_pp = (curr_cm - prior_cm) * 100

    if traf_d is not None and (traf_d - rev_d) * 100 > 3:
        dollars = (traf_d - rev_d) * curr.revenue
        flags.append(
            RelationshipFlag(
                "traffic_revenue_gap",
                dollars,
                ["conversion", "items_per_order"],
                f"traffic {traf_d*100:+.1f}% vs revenue {rev_d*100:+.1f}%",
            )
        )
    if rev_d > 0 and contrib_d < 0:
        flags.append(
            RelationshipFlag(
                "revenue_profit_divergence",
                curr.contribution - prior.contribution,
                ["mix", "unit_cost", "usage_efficiency"],
                "revenue up, contribution down",
            )
        )
    if rev_d > 0 and cm_pp < -1.5:
        flags.append(
            RelationshipFlag(
                "margin_compression",
                (cm_pp / 100.0) * curr.revenue,
                ["mix", "price", "unit_cost"],
                f"contribution margin {cm_pp:.1f}pp",
            )
        )
    var_curr = sum(curr.variable_costs.values())
    var_prior = sum(prior.variable_costs.values())
    var_d = pct(var_curr, var_prior)
    if orders_d > 0.05 and var_d < 0.01:
        flags.append(
            RelationshipFlag(
                "volume_without_cost_scaling",
                0.0,
                ["basis"],
                "orders up, variable cost flat — costs may be lagging",
            )
        )
    for inp, qty in curr.input_quantity.items():
        prior_qty = prior.input_quantity.get(inp) or 0
        qty_d = pct(qty, prior_qty)
        if qty_d > orders_d + 0.08:
            excess_qty = max(0.0, qty - prior_qty * (1.0 + orders_d))
            unit_cost = curr.input_spend.get(inp, 0.0) / qty if qty else 0.0
            flags.append(
                RelationshipFlag(
                    "cost_without_volume",
                    excess_qty * unit_cost,
                    ["usage_efficiency"],
                    f"{inp} qty grew faster than orders",
                )
            )
    if curr.volume and prior.volume:
        price_d = pct(curr.aov / (curr.items_per_order or 1), prior.aov / (prior.items_per_order or 1))
        vol_d = pct(curr.volume, prior.volume)
        if price_d >= 0.03 and vol_d >= 0:
            flags.append(
                RelationshipFlag(
                    "price_no_volume_response",
                    0.0,
                    ["elasticity"],
                    "price up, volume did not fall",
                )
            )
    for name, curr_v in curr.fixed_costs.items():
        prior_v = prior.fixed_costs.get(name, 0.0)
        step = pct(curr_v, prior_v)
        if abs(step) >= 0.08:
            flags.append(
                RelationshipFlag(
                    "fixed_cost_step",
                    curr_v - prior_v,
                    ["contract_change", "one_off"],
                    f"{name} fixed cost changed {step*100:+.1f}%",
                )
            )
    context = context or {}
    recurring_share_delta = context.get("recurring_revenue_share_delta")
    if recurring_share_delta is not None and recurring_share_delta <= -0.03 and abs(rev_d) < 0.01:
        flags.append(
            RelationshipFlag(
                "recurring_revenue_erosion",
                recurring_share_delta * curr.revenue,
                ["retention"],
                "recurring-customer revenue share fell while revenue was flat",
            )
        )
    concentration_delta = context.get("top3_counterparty_share_delta_3p")
    if concentration_delta is not None and concentration_delta >= 0.10:
        leaf_spend = float(context.get("concentrated_leaf_spend") or 0.0)
        flags.append(
            RelationshipFlag(
                "concentration_creep",
                concentration_delta * leaf_spend,
                ["supplier_dependency"],
                "top-three counterparty concentration increased over three periods",
            )
        )
    if patterns:
        for pat in patterns:
            metric = pat.get("metric")
            expected = pat.get("expected")
            sigma = pat.get("sigma") or 1
            observed = getattr(curr, metric, None) if metric else None
            if observed is None or expected is None:
                continue
            if abs(observed - expected) > 2 * sigma:
                flags.append(
                    RelationshipFlag(
                        "seasonal_break",
                        float(observed - expected),
                        ["pattern"],
                        f"{metric} departed from seasonal pattern",
                    )
                )
    return flags
