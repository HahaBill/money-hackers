from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

TxnType = Literal["revenue", "cogs", "opex", "transfer", "other"]
Basis = Literal["cash", "accrual"]


@dataclass
class Transaction:
    txn_id: str
    date: date
    period: str
    amount: Decimal
    txn_type: TxnType
    category: str
    counterparty: str | None
    product: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    source_row: int
    ingested_at: datetime
    day_of_week: int
    hour_bucket: str | None
    is_recurring: bool
    recurrence_key: str | None
    counterparty_id: str
    basis: Basis
    source_file: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class PeriodSummary:
    period: str
    revenue: Decimal
    expenses: Decimal
    operating_profit: Decimal
    source: str
    basis: Basis = "accrual"
    expenses_by_category: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class OperationalMetric:
    period: str
    foot_traffic: int | None = None
    orders: int | None = None
    opening_hours: Decimal | None = None
