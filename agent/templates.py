"""Hypothesis templates. The LLM chooses and instantiates; it does not free-associate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    leaf_prefix: str
    cls: str
    claim: str
    prior: float
    internal: str
    external: str | None
    owner_resolvable: bool = False


TEMPLATES: list[Template] = [
    Template("unit_cost", "market_inflation", "input {i} rose with the broader market", 0.40, "all suppliers of {i} rose similarly", "market_conditions"),
    Template("unit_cost", "supplier_specific", "{supplier} raised price beyond market", 0.30, "only {supplier} rose; others flat", "market_conditions"),
    Template("unit_cost", "order_tier", "order size fell, lost volume discount", 0.20, "order qty down; unit cost step-change", None, True),
    Template("unit_cost", "product_switch", "switched to premium variant", 0.10, "SKU / description changed", None, True),
    Template("mix", "seasonal", "iced share rises in warm months", 0.35, "same pattern prior year; cooling degree days", "weather"),
    Template("mix", "menu_change", "new item cannibalized high-margin items", 0.25, "new SKU; loser decline ≈ winner gain", None, True),
    Template("mix", "promo", "discount drove low-margin volume", 0.20, "avg price of winner down", None, True),
    Template("volume", "traffic", "fewer / more customers", 0.45, "traffic metric; orders count", "local_events"),
    Template("volume", "conversion", "same traffic, fewer orders", 0.25, "traffic flat, orders down", None),
    Template("volume", "competitor", "new competitor nearby", 0.15, "gradual decline, no internal cause", "competitor_prices"),
    Template("traffic", "traffic", "visitor count changed", 0.50, "foot_traffic metric", "local_events"),
    Template("conversion", "checkout_friction", "queue / POS / staffing at peak reduced completed orders", 0.40, "orders per traffic down in peak hours", None, True),
    Template("conversion", "browse_traffic", "traffic rose with non-buying visitors", 0.30, "traffic up evenly, orders flat", "local_events"),
    Template("electricity", "weather", "heat drove cooling load", 0.40, "cooling degree days up", "weather"),
    Template("electricity", "equipment", "equipment inefficiency or fault", 0.30, "elevation persists after weather normalizes", None, True),
    Template("electricity", "tariff", "rate change", 0.20, "kWh flat, $ up", "market_conditions"),
    Template("labor", "hours", "more hours scheduled", 0.45, "hours metric; opening hours", None, True),
    Template("labor", "rate", "wage rate change", 0.35, "hours flat, $ up", "market_conditions"),
    Template("usage_efficiency", "waste", "portioning / spoilage", 0.50, "input qty per drink up", None, True),
]


def templates_for(leaf: str) -> list[Template]:
    key = leaf.split(".", 1)[0]
    if key in {"variable_labor", "fixed_labor"}:
        key = "labor"
    if key in {"electricity_variable", "electricity_fixed"}:
        key = "electricity"
    return [t for t in TEMPLATES if t.leaf_prefix == key]


def instantiate(template: Template, *, leaf: str, entity: str | None) -> str:
    inp = leaf.split(".", 1)[1] if "." in leaf else leaf
    return template.claim.format(i=inp, supplier=entity or "the supplier")
