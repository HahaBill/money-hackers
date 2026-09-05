from __future__ import annotations

import csv
import hashlib
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from engine.model import Basis, OperationalMetric, PeriodSummary, Transaction

LEGAL_SUFFIX = re.compile(r"\b(inc|llc|ltd|co|corp|limited|company)\b\.?", re.I)
REQUIRED_COLUMNS = {"date", "amount", "txn_type", "category"}
TXN_TYPES = {"revenue", "cogs", "opex", "transfer", "other"}
BASES = {"cash", "accrual"}


class IngestError(ValueError):
    pass


def normalize_counterparty(name: str | None) -> str:
    if not name:
        return "unknown"
    folded = LEGAL_SUFFIX.sub("", name).casefold()
    return re.sub(r"[^a-z0-9]+", "", folded) or "unknown"


def _hour_bucket(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        hour = int(raw.split("T")[1][:2]) if "T" in raw else int(raw[11:13])
    except (ValueError, IndexError):
        return None
    if hour < 11:
        return "open"
    if hour < 15:
        return "peak"
    return "close"


def ingest_transactions(
    path: Path,
    *,
    period: str | None = None,
    basis: Basis = "cash",
) -> list[Transaction]:
    now = datetime.now(timezone.utc)
    rows: list[Transaction] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise IngestError(f"{path.name} is missing required columns: {sorted(missing)}")
        for i, raw in enumerate(reader, start=1):
            txn_id = raw.get("txn_id") or hashlib.sha256(
                f"{path.name}:{i}".encode()
            ).hexdigest()[:16]
            day = date.fromisoformat(raw["date"][:10])
            qty = Decimal(raw["quantity"]) if raw.get("quantity") else None
            price = Decimal(raw["unit_price"]) if raw.get("unit_price") else None
            counterparty = raw.get("counterparty") or None
            txn_type = raw.get("txn_type") or "other"
            if txn_type not in TXN_TYPES:
                raise IngestError(f"row {i}: invalid txn_type {txn_type!r}")
            row_basis = raw.get("basis") or basis
            if row_basis not in BASES:
                raise IngestError(f"row {i}: invalid basis {row_basis!r}")
            row_period = period or raw.get("period") or day.strftime("%Y-%m")
            rows.append(
                Transaction(
                    txn_id=txn_id,
                    date=day,
                    period=row_period,
                    amount=Decimal(raw["amount"]),
                    txn_type=txn_type,  # type: ignore[arg-type]
                    category=raw.get("category") or "",
                    counterparty=counterparty,
                    product=raw.get("product") or None,
                    quantity=qty,
                    unit_price=price,
                    source_row=i + 1,
                    ingested_at=now,
                    day_of_week=day.weekday(),
                    hour_bucket=_hour_bucket(raw.get("timestamp") or raw.get("date")),
                    is_recurring=False,
                    recurrence_key=None,
                    counterparty_id=normalize_counterparty(counterparty),
                    basis=row_basis,  # type: ignore[arg-type]
                    source_file=path.name,
                )
            )
    _mark_recurring(rows)
    return rows


def _mark_recurring(rows: list[Transaction]) -> None:
    by_key: dict[str, list[Transaction]] = {}
    for txn in rows:
        if not txn.counterparty_id or txn.counterparty_id == "unknown":
            continue
        key = txn.counterparty_id
        by_key.setdefault(key, []).append(txn)
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        amounts = [abs(t.amount) for t in group]
        mid = amounts[0]
        close = [t for t in group if mid == 0 or abs(abs(t.amount) - mid) / mid <= 0.03]
        if len(close) >= 2:
            rk = f"rec:{key}:{mid}"
            for txn in close:
                txn.is_recurring = True
                txn.recurrence_key = rk


def ingest_summary(path: Path, *, period: str | None = None) -> PeriodSummary:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise IngestError(f"{path.name} contains no summary rows")
    selected = next((row for row in rows if not period or row.get("period") == period), None)
    if not selected:
        raise IngestError(f"{path.name} has no summary for {period}")
    required = {"period", "revenue", "expenses", "operating_profit"}
    missing = required - set(selected)
    if missing:
        raise IngestError(f"{path.name} is missing required columns: {sorted(missing)}")
    basis = selected.get("basis") or "accrual"
    if basis not in BASES:
        raise IngestError(f"invalid summary basis {basis!r}")
    by_category = {
        key.removeprefix("expense_"): Decimal(value)
        for key, value in selected.items()
        if key.startswith("expense_") and value not in {None, ""}
    }
    return PeriodSummary(
        period=selected["period"],
        revenue=Decimal(selected["revenue"]),
        expenses=Decimal(selected["expenses"]),
        operating_profit=Decimal(selected["operating_profit"]),
        source=path.name,
        basis=basis,  # type: ignore[arg-type]
        expenses_by_category=by_category,
    )


def ingest_operational_metrics(path: Path) -> dict[str, OperationalMetric]:
    if not path.exists():
        return {}
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    metrics: dict[str, OperationalMetric] = {}
    for i, row in enumerate(rows, start=2):
        period = row.get("period")
        if not period:
            raise IngestError(f"{path.name} row {i}: period is required")
        metrics[period] = OperationalMetric(
            period=period,
            foot_traffic=int(row["foot_traffic"]) if row.get("foot_traffic") else None,
            orders=int(row["orders"]) if row.get("orders") else None,
            opening_hours=Decimal(row["opening_hours"]) if row.get("opening_hours") else None,
        )
    return metrics
