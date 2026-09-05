"""Café driver graph and profit_fn. Adding a driver is adding a line here.

Leverage is evaluated on contribution, never gross profit. Mix is a first-class
leaf: "mix at current" means current shares applied to whatever volume the
other leaves imply (prior volume when volume is held at prior).
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

PRODUCTS = [
    "espresso",
    "latte",
    "iced_latte",
    "cold_brew",
    "drip",
    "pastry",
    "sandwich",
]
INPUTS = ["coffee_beans", "milk", "food", "packaging"]

# Quantity of each input per unit sold. usage_efficiency multiplies this (1 + waste).
RECIPE: dict[str, dict[str, float]] = {
    "espresso":   {"coffee_beans": 0.018, "milk": 0.00, "food": 0.00, "packaging": 0.010},
    "latte":      {"coffee_beans": 0.018, "milk": 0.30, "food": 0.00, "packaging": 0.010},
    "iced_latte": {"coffee_beans": 0.018, "milk": 0.35, "food": 0.00, "packaging": 0.015},
    "cold_brew":  {"coffee_beans": 0.022, "milk": 0.00, "food": 0.00, "packaging": 0.015},
    "drip":       {"coffee_beans": 0.012, "milk": 0.00, "food": 0.00, "packaging": 0.008},
    "pastry":     {"coffee_beans": 0.000, "milk": 0.00, "food": 1.00, "packaging": 0.020},
    "sandwich":   {"coffee_beans": 0.000, "milk": 0.00, "food": 1.20, "packaging": 0.030},
}

VARIABLE_SHARE = {
    "labor": 0.35,
    "electricity": 0.25,
    "other_opex": 0.30,
    "rent": 0.00,
}

# Controllability priors (§13). Café values only; stated limitation.
CONTROLLABILITY = {
    "price": 0.9,
    "items_per_order": 0.7,
    "mix": 0.6,
    "usage_efficiency": 0.7,
    "unit_cost": 0.5,
    "labor": 0.7,
    "conversion": 0.6,
    "traffic": 0.3,
    "volume": 0.3,
    "electricity": 0.4,
    "other_opex": 0.5,
    "rent": 0.1,
    "variable_labor": 0.7,
    "fixed_labor": 0.5,
    "electricity_variable": 0.4,
    "electricity_fixed": 0.3,
    "other_variable": 0.5,
    "other_fixed": 0.2,
}


@dataclass
class LeafState:
    """All attribution leaves. Dict fields are copied by blend(), never aliased."""

    traffic: float | None = None
    conversion: float | None = None
    volume: float = 0.0
    items_per_order: float = 1.0
    price: dict[str, float] = field(default_factory=dict)
    mix: dict[str, float] = field(default_factory=dict)
    unit_cost: dict[str, float] = field(default_factory=dict)
    usage_efficiency: dict[str, float] = field(default_factory=dict)
    variable_labor: float = 0.0
    fixed_labor: float = 0.0
    electricity_variable: float = 0.0
    electricity_fixed: float = 0.0
    rent: float = 0.0
    other_variable: float = 0.0
    other_fixed: float = 0.0

    def copy(self) -> "LeafState":
        return deepcopy(self)


def attribution_leaves(has_traffic: bool) -> list[str]:
    funnel = ["traffic", "conversion"] if has_traffic else ["volume"]
    costs = [f"unit_cost.{i}" for i in INPUTS]
    return [
        *funnel,
        "items_per_order",
        "price",
        "mix",
        *costs,
        "usage_efficiency",
        "variable_labor",
        "electricity_variable",
        "other_variable",
        "fixed_labor",
        "electricity_fixed",
        "rent",
        "other_fixed",
    ]


def _volume_and_orders(state: LeafState) -> tuple[float, float]:
    if state.traffic is not None and state.conversion is not None:
        orders = state.traffic * state.conversion
        volume = orders * state.items_per_order
        return volume, orders
    volume = state.volume
    ipo = state.items_per_order or 1.0
    return volume, volume / ipo


def _cogs_and_revenue(state: LeafState) -> tuple[float, float, float]:
    volume, orders = _volume_and_orders(state)
    units = {p: volume * state.mix.get(p, 0.0) for p in PRODUCTS}
    aov = sum(state.mix.get(p, 0.0) * state.price.get(p, 0.0) for p in PRODUCTS) * (
        state.items_per_order or 1.0
    )
    revenue = orders * aov
    cogs = 0.0
    for inp in INPUTS:
        qty = sum(units[p] * RECIPE[p].get(inp, 0.0) for p in PRODUCTS)
        qty *= state.usage_efficiency.get(inp, 1.0)
        cogs += qty * state.unit_cost.get(inp, 0.0)
    return revenue, cogs, orders


def contribution_fn(state: LeafState) -> float:
    revenue, cogs, _ = _cogs_and_revenue(state)
    return (
        revenue
        - cogs
        - state.variable_labor
        - state.electricity_variable
        - state.other_variable
    )


def profit_fn(state: LeafState) -> float:
    """operating_profit through GRAPH. Pure arithmetic."""
    return (
        contribution_fn(state)
        - state.fixed_labor
        - state.rent
        - state.electricity_fixed
        - state.other_fixed
    )


def scale_leaf(state: LeafState, leaf: str, factor: float) -> LeafState:
    out = state.copy()
    if leaf == "price":
        out.price = {k: v * factor for k, v in out.price.items()}
    elif leaf == "volume":
        out.volume *= factor
    elif leaf == "traffic" and out.traffic is not None:
        out.traffic *= factor
    elif leaf == "items_per_order":
        out.items_per_order *= factor
    elif leaf.startswith("unit_cost."):
        key = leaf.split(".", 1)[1]
        out.unit_cost = dict(out.unit_cost)
        out.unit_cost[key] *= factor
    elif leaf == "usage_efficiency":
        out.usage_efficiency = {k: v * factor for k, v in out.usage_efficiency.items()}
    elif leaf == "variable_labor":
        out.variable_labor *= factor
    elif leaf == "electricity_variable":
        out.electricity_variable *= factor
    elif leaf == "electricity_fixed":
        out.electricity_fixed *= factor
    elif leaf == "electricity":
        out.electricity_variable *= factor
        out.electricity_fixed *= factor
    elif leaf == "labor":
        out.variable_labor *= factor
        out.fixed_labor *= factor
    elif leaf == "other_variable":
        out.other_variable *= factor
    else:
        raise KeyError(leaf)
    return out


def apply_leaf(dst: LeafState, src: LeafState, leaf: str) -> None:
    if leaf == "traffic":
        dst.traffic = src.traffic
    elif leaf == "conversion":
        dst.conversion = src.conversion
    elif leaf == "volume":
        dst.volume = src.volume
    elif leaf == "items_per_order":
        dst.items_per_order = src.items_per_order
    elif leaf == "price":
        dst.price = dict(src.price)
    elif leaf == "mix":
        dst.mix = dict(src.mix)
    elif leaf.startswith("unit_cost."):
        key = leaf.split(".", 1)[1]
        dst.unit_cost = dict(dst.unit_cost)
        dst.unit_cost[key] = src.unit_cost[key]
    elif leaf == "usage_efficiency":
        dst.usage_efficiency = dict(src.usage_efficiency)
    elif leaf == "variable_labor":
        dst.variable_labor = src.variable_labor
    elif leaf == "fixed_labor":
        dst.fixed_labor = src.fixed_labor
    elif leaf == "electricity_variable":
        dst.electricity_variable = src.electricity_variable
    elif leaf == "electricity_fixed":
        dst.electricity_fixed = src.electricity_fixed
    elif leaf == "rent":
        dst.rent = src.rent
    elif leaf == "other_variable":
        dst.other_variable = src.other_variable
    elif leaf == "other_fixed":
        dst.other_fixed = src.other_fixed
    else:
        raise KeyError(f"unknown leaf: {leaf}")


def blend(coalition: set[str], prior: LeafState, curr: LeafState) -> LeafState:
    """Leaves in the coalition take current values; all others stay at prior."""
    out = prior.copy()
    for leaf in coalition:
        apply_leaf(out, curr, leaf)
    return out


def controllability_for(leaf: str) -> float:
    if leaf.startswith("unit_cost."):
        return CONTROLLABILITY["unit_cost"]
    if leaf.startswith("usage_efficiency"):
        return CONTROLLABILITY["usage_efficiency"]
    return CONTROLLABILITY.get(leaf, 0.5)


def leaf_state_from_mapping(data: dict[str, Any]) -> LeafState:
    return LeafState(
        traffic=data.get("traffic"),
        conversion=data.get("conversion"),
        volume=float(data.get("volume") or 0.0),
        items_per_order=float(data.get("items_per_order") or 1.0),
        price=dict(data.get("price") or {}),
        mix=dict(data.get("mix") or {}),
        unit_cost=dict(data.get("unit_cost") or {}),
        usage_efficiency=dict(data.get("usage_efficiency") or {i: 1.0 for i in INPUTS}),
        variable_labor=float(data.get("variable_labor") or 0.0),
        fixed_labor=float(data.get("fixed_labor") or 0.0),
        electricity_variable=float(data.get("electricity_variable") or 0.0),
        electricity_fixed=float(data.get("electricity_fixed") or 0.0),
        rent=float(data.get("rent") or 0.0),
        other_variable=float(data.get("other_variable") or 0.0),
        other_fixed=float(data.get("other_fixed") or 0.0),
    )
