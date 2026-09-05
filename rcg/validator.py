"""Numeric-token validator. Unmatched numbers fail the run (§21)."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

CURRENCY = re.compile(r"(?<![\w.])(?:USD|US\$|\$)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)")
PERCENT = re.compile(r"(?<![\w.])([0-9]+(?:\.[0-9]+)?)\s*%")
NUMBER = re.compile(r"(?<![\w.$])(-?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|-?[0-9]+\.[0-9]+)(?![\w%])")

BANNED = ("fraud", "scam", "cheat", "overcharge")


class ValidationError(AssertionError):
    pass


def _parse(num: str) -> float:
    return float(num.replace(",", ""))


def extract_numbers(text: str) -> list[float]:
    found: list[float] = []
    for rx in (CURRENCY, PERCENT, NUMBER):
        for match in rx.finditer(text):
            found.append(_parse(match.group(1) if match.lastindex else match.group(0)))
    return found


def flatten_values(values: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for val in values:
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            out.append(float(val))
        elif isinstance(val, dict):
            out.extend(flatten_values(val.values()))
        elif isinstance(val, (list, tuple)):
            out.extend(flatten_values(val))
    return out


def matches(token: float, allowed: list[float]) -> bool:
    for candidate in allowed:
        if math.isclose(token, candidate, rel_tol=0.03, abs_tol=25.0):
            return True
        # "about $4,800" for $4,820
        if abs(candidate) >= 100 and abs(round(candidate, -2) - token) <= 50:
            return True
    return False


def validate_text(text: str, node_values: dict[str, Any]) -> None:
    lowered = text.lower()
    for word in BANNED:
        if word in lowered:
            raise ValidationError(f"banned word '{word}' in output")
    allowed = flatten_values(node_values.values())
    missing = [n for n in extract_numbers(text) if not matches(n, allowed)]
    if missing:
        raise ValidationError(f"unsourced_figure: {missing}")
