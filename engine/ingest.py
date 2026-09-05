from __future__ import annotations

import csv
import hashlib
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from engine.model import Transaction

LEGAL_SUFFIX = re.compile(r"\b(inc|llc|ltd|co|corp|limited|company)\b\.?", re.I)


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


def ingest_transactions(path: Path, *, period: str, basis: str = "cash") -> list[Transaction]:
    now = datetime.now(timezone.utc)
    rows: list[Transaction] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for i, raw in enumerate(reader, start=1):
            txn_id = raw.get("txn_id") or hashlib.sha256(
                f"{path.name}:{i}".encode()
            ).hexdigest()[:16]
            day = date.fromisoformat(raw["date"][:10])
            qty = Decimal(raw["quantity"]) if raw.get("quantity") else None
            price = Decimal(raw["unit_price"]) if raw.get("unit_price") else None
            counterparty = raw.get("counterparty") or None
            rows.append(
                Transaction(
                    txn_id=txn_id,
                    date=day,
                    period=period,
                    amount=Decimal(raw["amount"]),
                    txn_type=raw.get("txn_type") or "other",  # type: ignore[arg-type]
                    category=raw.get("category") or "",
                    counterparty=counterparty,
                    product=raw.get("product") or None,
                    quantity=qty,
                    unit_price=price,
                    source_row=i,
                    ingested_at=now,
                    day_of_week=day.weekday(),
                    hour_bucket=_hour_bucket(raw.get("timestamp") or raw.get("date")),
                    is_recurring=False,
                    recurrence_key=None,
                    counterparty_id=normalize_counterparty(counterparty),
                    basis=basis,  # type: ignore[arg-type]
                    source_file=path.name,
                )
            )
    _mark_recurring(rows)
    return rows


def _mark_recurring(rows: list[Transaction]) -> None:
    by_key: dict[str, list[Transaction]] = {}
    for txn in rows:
        if not txn.counterparty_id:
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
