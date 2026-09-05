from __future__ import annotations

from dataclasses import dataclass
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


def reconcile(
    txns: list[Transaction],
    summary: PeriodSummary,
    *,
    store: GraphStore,
    period: str,
    run_id: str,
    category_map: dict[str, str],
) -> ReconcileResult:
    checks: list[CheckResult] = []

    ids = [t.txn_id for t in txns]
    dup = len(ids) != len(set(ids))
    checks.append(
        CheckResult(
            "no_duplicate_txn_id",
            "block" if dup else "pass",
            "duplicate txn_id" if dup else "unique ids",
            {"duplicate": dup},
        )
    )

    outside = [t for t in txns if t.period != period]
    checks.append(
        CheckResult(
            "period_boundaries",
            "block" if outside else "pass",
            f"{len(outside)} rows outside {period}" if outside else "all dates in period",
            {"outside": len(outside)},
        )
    )

    unmapped = [t.category for t in txns if map_category(t.category, category_map) is None]
    checks.append(
        CheckResult(
            "categories_mapped",
            "block" if unmapped else "pass",
            f"unmapped: {sorted(set(unmapped))}" if unmapped else "all mapped",
            {"unmapped": sorted(set(unmapped))},
        )
    )

    rev = sum((t.amount for t in txns if t.txn_type == "revenue"), Decimal("0"))
    gap = abs(rev - summary.revenue)
    checks.append(
        CheckResult(
            "revenue_reconciles",
            "block" if gap > _tol(summary.revenue, TOL_REV) else "pass",
            f"txns={rev} summary={summary.revenue} gap={gap}",
            {"txns": float(rev), "summary": float(summary.revenue), "gap": float(gap)},
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
        return ReconcileResult(status="blocked", checks=checks, message=msg)
    return ReconcileResult(status="passed", checks=checks)
