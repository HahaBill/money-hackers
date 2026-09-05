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


def evaluate(prior: PeriodMetrics, curr: PeriodMetrics, *, patterns: list[dict] | None = None) -> list[RelationshipFlag]:
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
    var_curr = sum(curr.input_spend.values()) + 0.0
    var_prior = sum(prior.input_spend.values()) + 0.0
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
    for inp, spend in curr.input_spend.items():
        prior_spend = prior.input_spend.get(inp) or 0
        qty_d = pct(spend, prior_spend)
        if qty_d > orders_d + 0.08:
            flags.append(
                RelationshipFlag(
                    "cost_without_volume",
                    (qty_d - orders_d) * spend,
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
    for name, curr_v, prior_v in (
        ("electricity", curr.operating_profit, prior.operating_profit),
    ):
        _ = name
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
