"""Deterministic spend checks with mandatory benign counter-explanations (§14)."""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable

from engine.model import Transaction


@dataclass(frozen=True)
class LeakageFlag:
    rule: str
    entity: str
    gap_dollars: float
    evidence_rows: list[str]
    counter_explanation: str
    detail: str

    def as_json(self) -> dict:
        return asdict(self)


def _cost(txn: Transaction) -> float:
    return abs(float(txn.amount))


def _unit_cost(txn: Transaction) -> float | None:
    if txn.quantity and txn.quantity != 0:
        return _cost(txn) / abs(float(txn.quantity))
    if txn.unit_price is not None:
        return abs(float(txn.unit_price))
    return None


def _duplicate_flags(current: list[Transaction]) -> list[LeakageFlag]:
    flags: list[LeakageFlag] = []
    costs = [txn for txn in current if txn.txn_type in {"cogs", "opex"}]
    for i, left in enumerate(costs):
        for right in costs[i + 1 :]:
            if left.counterparty_id != right.counterparty_id:
                continue
            largest = max(_cost(left), _cost(right), 1.0)
            if abs(_cost(left) - _cost(right)) / largest > 0.01:
                continue
            if abs((left.date - right.date).days) > 3:
                continue
            flags.append(
                LeakageFlag(
                    rule="duplicate_payment",
                    entity=left.counterparty or left.counterparty_id,
                    gap_dollars=min(_cost(left), _cost(right)),
                    evidence_rows=[left.txn_id, right.txn_id],
                    counter_explanation="The entries may represent legitimate split deliveries or separate invoices.",
                    detail="Two same-supplier charges are within 1% and three days of each other.",
                )
            )
    return flags


def _unit_cost_flags(current: list[Transaction], history: list[Transaction]) -> list[LeakageFlag]:
    by_key: dict[tuple[str, str], list[float]] = {}
    for txn in history:
        value = _unit_cost(txn)
        if value is not None:
            by_key.setdefault((txn.counterparty_id, txn.category), []).append(value)

    flags: list[LeakageFlag] = []
    for txn in current:
        value = _unit_cost(txn)
        values = by_key.get((txn.counterparty_id, txn.category), [])
        if value is None or len(values) < 3:
            continue
        center = statistics.median(values)
        mad = statistics.median(abs(item - center) for item in values)
        scale = max(1.4826 * mad, abs(center) * 0.01, 1e-9)
        z = (value - center) / scale
        if z <= 2.5:
            continue
        quantity = abs(float(txn.quantity or 1))
        gap = max(0.0, value - center) * quantity
        flags.append(
            LeakageFlag(
                rule="unit_cost_outlier",
                entity=txn.counterparty or txn.counterparty_id,
                gap_dollars=gap,
                evidence_rows=[txn.txn_id],
                counter_explanation="Check for a product-grade, pack-size, or order-tier change before contacting the supplier.",
                detail=f"Unit cost is {z:.1f} robust standard deviations above this supplier's history.",
            )
        )
    return flags


def _new_vendor_flags(current: list[Transaction], history: list[Transaction]) -> list[LeakageFlag]:
    known = {txn.counterparty_id for txn in history}
    spend: dict[str, float] = {}
    names: dict[str, str] = {}
    rows: dict[str, list[str]] = {}
    for txn in current:
        if txn.txn_type not in {"cogs", "opex"}:
            continue
        spend[txn.counterparty_id] = spend.get(txn.counterparty_id, 0.0) + _cost(txn)
        names[txn.counterparty_id] = txn.counterparty or txn.counterparty_id
        rows.setdefault(txn.counterparty_id, []).append(txn.txn_id)
    total = sum(spend.values()) or 1.0
    return [
        LeakageFlag(
            rule="new_vendor_spike",
            entity=names[key],
            gap_dollars=amount,
            evidence_rows=rows[key],
            counter_explanation="This may be a planned supplier switch or a one-time purchase.",
            detail="A new counterparty represents more than 3% of current-period spend.",
        )
        for key, amount in spend.items()
        if key not in known and key != "unknown" and amount / total > 0.03
    ]


def _supplier_market_gap_flags(
    current: list[Transaction],
    history: list[Transaction],
    market_unit_cost_changes: dict[str, float],
) -> list[LeakageFlag]:
    prior_costs: dict[tuple[str, str], list[float]] = {}
    for txn in history:
        value = _unit_cost(txn)
        if value is not None:
            prior_costs.setdefault((txn.counterparty_id, txn.category), []).append(value)
    flags = []
    for txn in current:
        value = _unit_cost(txn)
        history_values = prior_costs.get((txn.counterparty_id, txn.category), [])
        market_change = market_unit_cost_changes.get(txn.category)
        if value is None or not history_values or market_change is None:
            continue
        prior = statistics.median(history_values)
        if prior <= 0:
            continue
        supplier_change = value / prior - 1.0
        excess = supplier_change - market_change
        if excess < 0.05:
            continue
        quantity = abs(float(txn.quantity or 1))
        gap = max(0.0, value - prior * (1.0 + market_change)) * quantity
        flags.append(
            LeakageFlag(
                rule="supplier_market_gap",
                entity=txn.counterparty or txn.counterparty_id,
                gap_dollars=gap,
                evidence_rows=[txn.txn_id],
                counter_explanation="The difference may reflect a product grade, delivery term, pack size, or lost volume tier.",
                detail="Supplier unit cost increased at least five percentage points beyond the market benchmark.",
            )
        )
    return flags


def _missing_recurring_flags(current: list[Transaction], history: list[Transaction]) -> list[LeakageFlag]:
    current_keys = {txn.recurrence_key for txn in current if txn.recurrence_key}
    historical: dict[str, list[Transaction]] = {}
    for txn in history:
        if txn.recurrence_key:
            historical.setdefault(txn.recurrence_key, []).append(txn)
    flags = []
    current_period = current[0].period if current else ""

    def period_index(value: str) -> int:
        year, month = (int(part) for part in value.split("-", 1))
        return year * 12 + month

    for key, txns in historical.items():
        periods = {txn.period for txn in txns}
        if key in current_keys or len(periods) < 2 or not current_period:
            continue
        expected = period_index(current_period)
        prior_indices = {period_index(period) for period in periods}
        if not {expected - 1, expected - 2}.issubset(prior_indices):
            continue
        latest = max(txns, key=lambda txn: txn.date)
        flags.append(
            LeakageFlag(
                rule="missing_expected_charge",
                entity=latest.counterparty or latest.counterparty_id,
                gap_dollars=_cost(latest),
                evidence_rows=[txn.txn_id for txn in txns[-3:]],
                counter_explanation="The invoice may be late and may appear in the next period.",
                detail="A charge seen on a recurring key in at least two periods is absent.",
            )
        )
    return flags


def scan(
    transactions: Iterable[Transaction],
    *,
    period: str,
    market_unit_cost_changes: dict[str, float] | None = None,
) -> list[LeakageFlag]:
    rows = list(transactions)
    current = [txn for txn in rows if txn.period == period]
    history = [txn for txn in rows if txn.period < period]
    return [
        *_duplicate_flags(current),
        *_unit_cost_flags(current, history),
        *_supplier_market_gap_flags(current, history, market_unit_cost_changes or {}),
        *_new_vendor_flags(current, history),
        *_missing_recurring_flags(current, history),
    ]
