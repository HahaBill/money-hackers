from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

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
    mapping = load_leaf_map(Path(__file__).parents[1] / "data/category_map.yaml")
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
    mapping = load_leaf_map(Path(__file__).parents[1] / "data/category_map.yaml")
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


@pytest.mark.regression
def test_p_cash_rows_reconcile_to_accrual_summary_with_tagged_cutoff_adjustment():
    revenue = make_txn("rev", "1000", "revenue", "sales", basis="cash")
    expense = make_txn("expense", "-200", "cogs", "milk", basis="cash")
    shifted_out = make_txn(
        "shifted_out",
        "-50",
        "cogs",
        "milk",
        when="2026-08-31",
        basis="cash",
    )
    shifted_out.tags.append("accrual_period:2026-09")
    shifted_in = make_txn(
        "shifted_in",
        "-100",
        "cogs",
        "milk",
        when="2026-09-01",
        basis="cash",
    )
    shifted_in.period = "2026-09"
    shifted_in.tags.append("accrual_period:2026-08")
    rows = [revenue, expense, shifted_out]
    all_rows = [*rows, shifted_in]
    summary = PeriodSummary(
        "2026-08",
        Decimal("1000"),
        Decimal("300"),
        Decimal("700"),
        "summary.csv",
        "accrual",
    )
    mapping = load_leaf_map(Path(__file__).parents[1] / "data/category_map.yaml")
    result = reconcile(
        rows,
        summary,
        store=GraphStore(),
        period="2026-08",
        run_id="basis_adjustment",
        category_map=mapping,
        adjacent_txns=all_rows,
    )
    assert result.status == "passed"
    assert {txn.txn_id for txn in result.analysis_rows} == {"rev", "expense", "shifted_in"}
    assert "basis_adjusted" in shifted_in.tags
    assert "basis_adjusted" in shifted_out.tags


@pytest.mark.regression
def test_l_five_percent_revenue_gap_blocks_analysis():
    rows = [make_txn("r", "9500", "revenue", "sales")]
    summary = PeriodSummary(
        "2026-08",
        Decimal("10000"),
        Decimal("0"),
        Decimal("10000"),
        "summary.csv",
        "accrual",
    )
    mapping = load_leaf_map(Path(__file__).parents[1] / "data/category_map.yaml")
    result = reconcile(
        rows,
        summary,
        store=GraphStore(),
        period="2026-08",
        run_id="reconcile_block",
        category_map=mapping,
    )
    assert result.status == "blocked"
    assert any(
        check.name == "revenue_reconciles" and check.status == "block"
        for check in result.checks
    )
