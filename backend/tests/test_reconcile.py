from datetime import date, datetime, timezone
from decimal import Decimal

from engine.ingest import IngestError, ingest_transactions
from engine.model import PeriodSummary, Transaction
from engine.reconcile import load_leaf_map, reconcile
from rcg.store import GraphStore


def make_txn(
    tid: str,
    amount: str,
    txn_type: str,
    category: str,
    *,
    when: str = "2026-08-10",
    basis: str = "accrual",
) -> Transaction:
    day = date.fromisoformat(when)
    return Transaction(
        txn_id=tid,
        date=day,
        period="2026-08",
        amount=Decimal(amount),
        txn_type=txn_type,  # type: ignore[arg-type]
        category=category,
        counterparty="Example",
        product=None,
        quantity=None,
        unit_price=None,
        source_row=2,
        ingested_at=datetime.now(timezone.utc),
        day_of_week=day.weekday(),
        hour_bucket=None,
        is_recurring=False,
        recurrence_key=None,
        counterparty_id="example",
        basis=basis,  # type: ignore[arg-type]
    )


def test_reconcile_checks_revenue_expenses_and_basis():
    rows = [
        make_txn("r", "1000", "revenue", "sales"),
        make_txn("c", "-300", "cogs", "milk"),
    ]
    summary = PeriodSummary(
        period="2026-08",
        revenue=Decimal("1000"),
        expenses=Decimal("300"),
        operating_profit=Decimal("700"),
        source="summary.csv",
        basis="accrual",
    )
    mapping = load_leaf_map(__import__("pathlib").Path(__file__).parents[1] / "data/category_map.yaml")
    result = reconcile(
        rows,
        summary,
        store=GraphStore(),
        period="2026-08",
        run_id="test",
        category_map=mapping,
    )
    assert result.status == "passed"


def test_reconcile_uses_transaction_dates_for_boundaries():
    row = make_txn("r", "1000", "revenue", "sales", when="2026-07-31")
    summary = PeriodSummary("2026-08", Decimal("1000"), Decimal("0"), Decimal("1000"), "s", "accrual")
    mapping = load_leaf_map(__import__("pathlib").Path(__file__).parents[1] / "data/category_map.yaml")
    result = reconcile(
        [row], summary, store=GraphStore(), period="2026-08", run_id="test", category_map=mapping
    )
    assert result.status == "blocked"
    assert any(check.name == "period_boundaries" and check.status == "block" for check in result.checks)


def test_ingest_reports_missing_required_columns(tmp_path):
    source = tmp_path / "transactions.csv"
    source.write_text("date,amount\n2026-08-01,10\n")
    try:
        ingest_transactions(source, period="2026-08")
    except IngestError as exc:
        assert "required columns" in str(exc)
    else:
        raise AssertionError("expected IngestError")
