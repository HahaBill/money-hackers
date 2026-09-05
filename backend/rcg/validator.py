"""Numeric-token validator. Unmatched numbers fail the run (§21)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

CURRENCY = re.compile(
    r"(?<![\w.])([+-]?)\s*(?:USD|US\$|\$)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"
)
PERCENT = re.compile(r"(?<![\w.])([+-]?[0-9]+(?:\.[0-9]+)?)\s*%")
NUMBER = re.compile(
    r"(?<![\w.$])([+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?)(?![\w%])"
)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")

BANNED = ("fraud", "scam", "cheat", "overcharge")


class ValidationError(AssertionError):
    pass


@dataclass(frozen=True)
class NumericToken:
    value: float
    kind: str  # currency | percent | number


def _parse(num: str) -> float:
    return float(num.replace(",", ""))


def _numeric_tokens(text: str) -> list[NumericToken]:
    # Reporting periods are identifiers, not asserted quantities.
    scrubbed = ISO_DATE.sub(lambda m: " " * len(m.group(0)), text)
    occupied: list[tuple[int, int]] = []
    found: list[NumericToken] = []
    for kind, rx in (("currency", CURRENCY), ("percent", PERCENT), ("number", NUMBER)):
        for match in rx.finditer(scrubbed):
            if any(start < match.end() and match.start() < end for start, end in occupied):
                continue
            if kind == "currency":
                sign = -1.0 if match.group(1) == "-" else 1.0
                value = sign * _parse(match.group(2))
            else:
                value = _parse(match.group(1))
            occupied.append(match.span())
            found.append(NumericToken(value, kind))
    return found


def extract_numbers(text: str) -> list[float]:
    return [token.value for token in _numeric_tokens(text)]


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


def matches(token: float, allowed: list[float], *, kind: str = "number") -> bool:
    for candidate in allowed:
        # Narrative may state the magnitude of a negative variance after words
        # such as "fell" or "lost", so compare both signed and absolute forms.
        candidates = (candidate, abs(candidate))
        abs_tol = 0.15 if kind == "percent" else 1.0 if kind == "currency" else 0.01
        if any(math.isclose(token, value, rel_tol=0.03, abs_tol=abs_tol) for value in candidates):
            return True
        # "about $4,800" for $4,820. Never apply dollar-style rounding to a
        # percentage or a generic count.
        if kind in {"currency", "number"} and abs(candidate) >= 100 and abs(round(abs(candidate), -2) - abs(token)) <= 50:
            return True
    return False


def validate_text(text: str, node_values: dict[str, Any]) -> None:
    lowered = text.lower()
    for word in BANNED:
        if word in lowered:
            raise ValidationError(f"banned word '{word}' in output")
    allowed = flatten_values(node_values.values())
    missing = [
        token.value
        for token in _numeric_tokens(text)
        if not matches(token.value, allowed, kind=token.kind)
    ]
    if missing:
        raise ValidationError(f"unsourced_figure: {missing}")
