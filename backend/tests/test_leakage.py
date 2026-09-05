from datetime import date, datetime, timezone
from decimal import Decimal

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


def test_duplicate_payment_is_flagged_with_counter_explanation():
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
