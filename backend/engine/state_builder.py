"""Build graph leaf states from reconciled transaction and operating data."""

from __future__ import annotations

from collections import defaultdict

from engine.graph_def import INPUTS, PRODUCTS, RECIPE, VARIABLE_SHARE, LeafState
from engine.model import OperationalMetric, Transaction
from engine.reconcile import map_category


class StateBuildError(ValueError):
    pass


def _product_stats(rows: list[Transaction]) -> tuple[float, dict[str, float], dict[str, float]]:
    quantity: dict[str, float] = defaultdict(float)
    revenue: dict[str, float] = defaultdict(float)
    for txn in rows:
        if txn.txn_type != "revenue":
            continue
        if not txn.product or txn.quantity is None:
            raise StateBuildError(
                f"revenue transaction {txn.txn_id} needs product and quantity for driver attribution"
            )
        if txn.product not in PRODUCTS:
            raise StateBuildError(f"revenue transaction {txn.txn_id} has unknown product {txn.product!r}")
        qty = float(txn.quantity)
        if qty < 0:
            raise StateBuildError(f"revenue transaction {txn.txn_id} has negative quantity")
        quantity[txn.product] += qty
        revenue[txn.product] += float(txn.amount)
    volume = sum(quantity.values())
    if volume <= 0:
        raise StateBuildError("period has no positive product volume")
    mix = {product: quantity.get(product, 0.0) / volume for product in PRODUCTS}
    prices = {
        product: revenue[product] / quantity[product]
        for product in PRODUCTS
        if quantity.get(product, 0.0) > 0
    }
    return volume, mix, prices


def build_leaf_state(
    rows: list[Transaction],
    *,
    category_map: dict[str, str],
    operational: OperationalMetric | None = None,
    fallback: LeafState | None = None,
) -> LeafState:
    volume, mix, observed_prices = _product_stats(rows)
    prices = dict(fallback.price) if fallback else {}
    prices.update(observed_prices)
    missing_prices = [product for product, share in mix.items() if share and product not in prices]
    if missing_prices:
        raise StateBuildError(f"missing prices for products: {missing_prices}")

    input_qty: dict[str, float] = defaultdict(float)
    input_spend: dict[str, float] = defaultdict(float)
    opex: dict[str, float] = defaultdict(float)
    for txn in rows:
        if txn.txn_type not in {"cogs", "opex"}:
            continue
        leaf = map_category(txn.category, category_map)
        if not leaf:
            continue  # reconciliation owns the blocking error
        spend = abs(float(txn.amount))
        if leaf in INPUTS:
            input_spend[leaf] += spend
            if txn.quantity is not None:
                input_qty[leaf] += abs(float(txn.quantity))
        else:
            opex[leaf] += spend

    implied_by_input = {
        item: sum(
            volume * mix.get(product, 0.0) * RECIPE[product].get(item, 0.0)
            for product in PRODUCTS
        )
        for item in INPUTS
    }
    unit_cost = dict(fallback.unit_cost) if fallback else {}
    for item in INPUTS:
        if input_qty.get(item):
            unit_cost[item] = input_spend[item] / input_qty[item]
        elif item not in unit_cost and (input_spend.get(item) or implied_by_input[item]):
            raise StateBuildError(f"missing quantity history needed to calculate {item} unit cost")
        elif item not in unit_cost:
            # An input that was neither purchased nor recipe-required in the
            # period is an inactive leaf, not a missing-data failure.
            unit_cost[item] = 0.0

    # Purchased quantities and recipe-implied usage are kept separate. This
    # makes stock build/spoilage visible as usage efficiency instead of folding
    # it into unit price.
    usage_efficiency = {}
    for item in INPUTS:
        implied = implied_by_input[item]
        purchased = input_qty.get(item, 0.0)
        usage_efficiency[item] = purchased / implied if implied and purchased else 1.0

    orders = float(operational.orders) if operational and operational.orders else volume
    items_per_order = volume / orders if orders else 1.0
    traffic = float(operational.foot_traffic) if operational and operational.foot_traffic else None
    conversion = orders / traffic if traffic else None

    labor = opex.get("labor", 0.0)
    electricity = opex.get("electricity", 0.0)
    other = opex.get("other_opex", 0.0)
    return LeafState(
        traffic=traffic,
        conversion=conversion,
        volume=0.0 if traffic is not None else volume,
        items_per_order=items_per_order,
        price=prices,
        mix=mix,
        unit_cost=unit_cost,
        usage_efficiency=usage_efficiency,
        variable_labor=labor * VARIABLE_SHARE["labor"],
        fixed_labor=labor * (1.0 - VARIABLE_SHARE["labor"]),
        electricity_variable=electricity * VARIABLE_SHARE["electricity"],
        electricity_fixed=electricity * (1.0 - VARIABLE_SHARE["electricity"]),
        rent=opex.get("rent", 0.0),
        other_variable=other * VARIABLE_SHARE["other_opex"],
        other_fixed=other * (1.0 - VARIABLE_SHARE["other_opex"]),
    )
