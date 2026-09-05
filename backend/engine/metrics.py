"""Deterministic period metrics. DuckDB when transactions exist; else leaf-state."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from engine.graph_def import PRODUCTS, RECIPE, INPUTS, LeafState, _volume_and_orders


@dataclass
class PeriodMetrics:
    period: str
    revenue: float
    cogs: float
    contribution: float
    operating_profit: float
    orders: float
    volume: float
    aov: float
    items_per_order: float
    traffic: float | None
    conversion: float | None
    product_revenue: dict[str, float]
    product_share: dict[str, float]
    input_spend: dict[str, float]
    input_quantity: dict[str, float]
    variable_costs: dict[str, float]
    fixed_costs: dict[str, float]


def from_leaf_state(period: str, state: LeafState) -> PeriodMetrics:
    volume, orders = _volume_and_orders(state)
    units = {p: volume * state.mix.get(p, 0.0) for p in PRODUCTS}
    aov = sum(state.mix.get(p, 0.0) * state.price.get(p, 0.0) for p in PRODUCTS) * (
        state.items_per_order or 1.0
    )
    revenue = orders * aov
    input_spend = {}
    input_quantity = {}
    cogs = 0.0
    for inp in INPUTS:
        qty = sum(units[p] * RECIPE[p].get(inp, 0.0) for p in PRODUCTS)
        qty *= state.usage_efficiency.get(inp, 1.0)
        spend = qty * state.unit_cost.get(inp, 0.0)
        input_quantity[inp] = qty
        input_spend[inp] = spend
        cogs += spend
    contribution = (
        revenue - cogs - state.variable_labor - state.electricity_variable - state.other_variable
    )
    profit = (
        contribution
        - state.fixed_labor
        - state.rent
        - state.electricity_fixed
        - state.other_fixed
    )
    return PeriodMetrics(
        period=period,
        revenue=revenue,
        cogs=cogs,
        contribution=contribution,
        operating_profit=profit,
        orders=orders,
        volume=volume,
        aov=aov,
        items_per_order=state.items_per_order,
        traffic=state.traffic,
        conversion=state.conversion,
        product_revenue={p: units[p] * state.price.get(p, 0.0) for p in PRODUCTS},
        product_share=dict(state.mix),
        input_spend=input_spend,
        input_quantity=input_quantity,
        variable_costs={
            "inputs": cogs,
            "labor": state.variable_labor,
            "electricity": state.electricity_variable,
            "other_opex": state.other_variable,
        },
        fixed_costs={
            "labor": state.fixed_labor,
            "electricity": state.electricity_fixed,
            "rent": state.rent,
            "other_opex": state.other_fixed,
        },
    )


def product_table(con: duckdb.DuckDBPyConnection, period: str) -> list[dict]:
    return con.execute(
        """
        SELECT product,
               SUM(quantity) AS qty,
               SUM(amount)   AS revenue,
               SUM(amount) / NULLIF(SUM(quantity), 0) AS avg_price
        FROM transactions
        WHERE txn_type = 'revenue' AND period = ?
        GROUP BY 1
        ORDER BY 1
        """,
        [period],
    ).fetchdf().to_dict("records")
