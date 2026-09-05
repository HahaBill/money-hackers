from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from engine.leakage import scan
from engine.model import Transaction


def txn(tid: str, when: str, amount: str, *, period: str, unit: str | None = None) -> Transaction:
    day = date.fromisoformat(when)
    return Transaction(
        txn_id=tid,
        date=day,
        period=period,
        amount=Decimal(amount),
        txn_type="cogs",
        category="milk",
        counterparty="Nordic Dairy",
        product="milk",
        quantity=Decimal("10") if unit else None,
        unit_price=Decimal(unit) if unit else None,
        source_row=1,
        ingested_at=datetime.now(timezone.utc),
        day_of_week=day.weekday(),
        hour_bucket=None,
        is_recurring=False,
        recurrence_key=None,
        counterparty_id="nordicdairy",
        basis="accrual",
    )


@pytest.mark.regression
def test_k_duplicate_payment_is_flagged_with_counter_explanation():
    rows = [
        txn("a", "2026-08-02", "-500", period="2026-08"),
        txn("b", "2026-08-04", "-500", period="2026-08"),
    ]
    flags = scan(rows, period="2026-08")
    duplicate = next(flag for flag in flags if flag.rule == "duplicate_payment")
    assert duplicate.gap_dollars == 500
    assert duplicate.counter_explanation


def test_supplier_unit_cost_outlier_uses_own_history():
    history = [
        txn(f"h{i}", f"2026-0{i}-02", "-100", period=f"2026-0{i}", unit="10")
        for i in range(5, 8)
    ]
    current = txn("c", "2026-08-02", "-130", period="2026-08", unit="13")
    flags = scan([*history, current], period="2026-08")
    assert any(flag.rule == "unit_cost_outlier" for flag in flags)


@pytest.mark.regression
def test_f_supplier_gap_is_market_unexplained_and_non_accusatory():
    history = [txn("h", "2026-07-02", "-100", period="2026-07", unit="10")]
    current = txn("c", "2026-08-02", "-122", period="2026-08", unit="12.2")
    flags = scan(
        [*history, current],
        period="2026-08",
        market_unit_cost_changes={"milk": 0.07},
    )
    flag = next(item for item in flags if item.rule == "supplier_market_gap")
    assert round(flag.gap_dollars, 2) == 15.0
    combined = f"{flag.detail} {flag.counter_explanation}".casefold()
    assert not any(word in combined for word in ("fraud", "scam", "cheat", "overcharge"))
