from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from engine.model import PeriodSummary, Transaction
from rcg.store import GraphStore

TOL_ABS = Decimal("50")
TOL_REV = Decimal("0.005")
TOL_EXP = Decimal("0.01")


@dataclass
class CheckResult:
    name: str
    status: str  # pass | warn | block
    detail: str
    value: dict


@dataclass
class ReconcileResult:
    status: str  # passed | blocked
    checks: list[CheckResult]
    message: str | None = None
    analysis_rows: list[Transaction] = field(default_factory=list)


def load_leaf_map(path: Path) -> dict[str, str]:
    spec = yaml.safe_load(path.read_text())
    mapping: dict[str, str] = {}
    for leaf, aliases in spec["leaves"].items():
        for alias in aliases:
            mapping[alias.casefold()] = leaf
        mapping[leaf.casefold()] = leaf
    return mapping


def map_category(category: str, mapping: dict[str, str]) -> str | None:
    return mapping.get(category.casefold())


def _tol(amount: Decimal, pct: Decimal) -> Decimal:
    return max(TOL_ABS, abs(amount) * pct)


def _tagged_period(txn: Transaction, basis: str) -> str | None:
    prefix = f"{basis}_period:"
    return next((tag[len(prefix) :] for tag in txn.tags if tag.startswith(prefix)), None)


def _near_period_boundary(txn: Transaction, tagged_period: str, days: int = 3) -> bool:
    year, month = (int(part) for part in tagged_period.split("-", 1))
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return min(abs((txn.date - start).days), abs((txn.date - end).days)) <= days


def _basis_adjusted_rows(
    current: list[Transaction],
    adjacent: list[Transaction] | None,
    *,
    period: str,
    target_basis: str,
) -> tuple[list[Transaction], int, bool]:
    if not adjacent:
        return list(current), 0, False
    deduped = {txn.txn_id: txn for txn in adjacent}
    explicit = [txn for txn in deduped.values() if _tagged_period(txn, target_basis)]
    if not explicit or any(
        not _near_period_boundary(txn, _tagged_period(txn, target_basis) or period)
        for txn in explicit
    ):
        return list(current), 0, False
    effective = []
    adjusted = 0
    for txn in deduped.values():
        target_period = _tagged_period(txn, target_basis)
        include = target_period == period if target_period else txn.period == period
        if target_period and target_period != txn.period:
            if "basis_adjusted" not in txn.tags:
                txn.tags.append("basis_adjusted")
            adjusted += 1
        if include:
            effective.append(txn)
    return effective, adjusted, adjusted > 0


def reconcile(
    txns: list[Transaction],
    summary: PeriodSummary,
    *,
    store: GraphStore,
    period: str,
    run_id: str,
    category_map: dict[str, str],
    adjacent_txns: list[Transaction] | None = None,
) -> ReconcileResult:
    checks: list[CheckResult] = []
    source_bases = {txn.basis for txn in txns}
    basis_matches_before = source_bases == {summary.basis}
    effective_txns, adjusted_count, basis_adjusted = _basis_adjusted_rows(
        txns,
        adjacent_txns if not basis_matches_before else None,
        period=period,
        target_basis=summary.basis,
    )

    ids = [t.txn_id for t in effective_txns]
    dup = len(ids) != len(set(ids))
    checks.append(
        CheckResult(
            "no_duplicate_txn_id",
            "block" if dup else "pass",
            "duplicate txn_id" if dup else "unique ids",
            {"duplicate": dup},
        )
    )

    outside = [
        txn
        for txn in effective_txns
        if (txn.period != period or txn.date.strftime("%Y-%m") != period)
        and _tagged_period(txn, summary.basis) != period
    ]
    checks.append(
        CheckResult(
            "period_boundaries",
            "block" if outside else "pass",
            f"{len(outside)} rows outside {period}" if outside else "all dates in period",
            {"outside": len(outside)},
        )
    )

    unmapped = [
        txn.category
        for txn in effective_txns
        if txn.txn_type in {"cogs", "opex"}
        and map_category(txn.category, category_map) is None
    ]
    checks.append(
        CheckResult(
            "categories_mapped",
            "block" if unmapped else "pass",
            f"unmapped: {sorted(set(unmapped))}" if unmapped else "all mapped",
            {"unmapped": sorted(set(unmapped))},
        )
    )

    rev = sum((t.amount for t in effective_txns if t.txn_type == "revenue"), Decimal("0"))
    gap = abs(rev - summary.revenue)
    checks.append(
        CheckResult(
            "revenue_reconciles",
            "block" if gap > _tol(summary.revenue, TOL_REV) else "pass",
            f"txns={rev} summary={summary.revenue} gap={gap}",
            {"txns": float(rev), "summary": float(summary.revenue), "gap": float(gap)},
        )
    )

    expense_total = abs(
        sum((t.amount for t in effective_txns if t.txn_type in {"cogs", "opex"}), Decimal("0"))
    )
    expense_gap = abs(expense_total - abs(summary.expenses))
    checks.append(
        CheckResult(
            "expenses_reconcile",
            "block" if expense_gap > _tol(summary.expenses, TOL_EXP) else "pass",
            f"txns={expense_total} summary={summary.expenses} gap={expense_gap}",
            {
                "txns": float(expense_total),
                "summary": float(summary.expenses),
                "gap": float(expense_gap),
            },
        )
    )

    calculated_profit = summary.revenue - abs(summary.expenses)
    profit_gap = abs(calculated_profit - summary.operating_profit)
    checks.append(
        CheckResult(
            "summary_profit_consistency",
            "block" if profit_gap > _tol(summary.operating_profit, TOL_REV) else "pass",
            f"revenue-expenses={calculated_profit} operating_profit={summary.operating_profit} gap={profit_gap}",
            {
                "calculated": float(calculated_profit),
                "reported": float(summary.operating_profit),
                "gap": float(profit_gap),
            },
        )
    )

    for raw_category, expected in summary.expenses_by_category.items():
        leaf = map_category(raw_category, category_map) or raw_category
        actual = abs(
            sum(
                (
                    txn.amount
                    for txn in effective_txns
                    if txn.txn_type in {"cogs", "opex"}
                    and map_category(txn.category, category_map) == leaf
                ),
                Decimal("0"),
            )
        )
        category_gap = abs(actual - abs(expected))
        checks.append(
            CheckResult(
                f"expense_category:{leaf}",
                "block" if category_gap > _tol(expected, TOL_EXP) else "pass",
                f"txns={actual} summary={expected} gap={category_gap}",
                {"txns": float(actual), "summary": float(expected), "gap": float(category_gap)},
            )
        )

    suspected = []
    ordered = sorted(effective_txns, key=lambda txn: txn.date)
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if right.date - left.date > timedelta(days=1):
                break
            if left.txn_id == right.txn_id or left.counterparty_id != right.counterparty_id:
                continue
            largest = max(abs(left.amount), abs(right.amount), Decimal("1"))
            if abs(abs(left.amount) - abs(right.amount)) / largest <= Decimal("0.01"):
                suspected.append((left.txn_id, right.txn_id))
    checks.append(
        CheckResult(
            "suspected_duplicate",
            "warn" if suspected else "pass",
            f"{len(suspected)} possible duplicate pairs" if suspected else "none found",
            {"pairs": suspected},
        )
    )

    quantity_mismatches = []
    for txn in effective_txns:
        if txn.quantity is None or txn.unit_price is None:
            continue
        expected_amount = abs(txn.quantity * txn.unit_price)
        actual_amount = abs(txn.amount)
        if abs(expected_amount - actual_amount) > max(Decimal("0.01"), actual_amount * Decimal("0.01")):
            quantity_mismatches.append(txn.txn_id)
    checks.append(
        CheckResult(
            "quantity_price_consistency",
            "warn" if quantity_mismatches else "pass",
            f"{len(quantity_mismatches)} inconsistent rows" if quantity_mismatches else "consistent",
            {"txn_ids": quantity_mismatches},
        )
    )

    txn_bases = {txn.basis for txn in effective_txns}
    basis_matches = txn_bases == {summary.basis} or basis_adjusted
    checks.append(
        CheckResult(
            "cash_accrual_basis",
            "pass" if basis_matches else "block",
            "bases match"
            if txn_bases == {summary.basis}
            else f"cutoff-window adjustment applied to {adjusted_count} rows"
            if basis_adjusted
            else "basis mismatch requires tagged adjacent-period rows for cutoff-window adjustment",
            {
                "transaction_bases": sorted(txn_bases),
                "summary_basis": summary.basis,
                "basis_adjusted_rows": adjusted_count,
            },
        )
    )

    for chk in checks:
        store.add(
            type="check",
            period=period,
            run_id=run_id,
            label=chk.name,
            value=chk.status,
            unit=None,
            payload=chk.value,
        )

    blocked = [c for c in checks if c.status == "block"]
    if blocked:
        first = blocked[0]
        msg = (
            f"ANALYSIS_BLOCKED  period={period}\n"
            f"{first.name}: {first.detail}"
        )
        return ReconcileResult(
            status="blocked",
            checks=checks,
            message=msg,
            analysis_rows=effective_txns,
        )
    return ReconcileResult(status="passed", checks=checks, analysis_rows=effective_txns)
