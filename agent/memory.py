"""Carry-forward judgments only. Numbers stay in DuckDB (§18)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MAX_OPEN = 15
MAX_DIRECTIVES = 20
MAX_ANSWERS = 30
MAX_PATTERNS = 10


@dataclass
class Memory:
    version: int = 1
    open_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    closed_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    directives: list[dict[str, Any]] = field(default_factory=list)
    owner_answers: list[dict[str, Any]] = field(default_factory=list)
    learned_patterns: list[dict[str, Any]] = field(default_factory=list)
    feedback: list[dict[str, Any]] = field(default_factory=list)
    baseline_version: str = ""

    def prior_for(self, leaf: str, cls: str) -> dict[str, Any] | None:
        for item in self.open_hypotheses:
            if item.get("leaf") == leaf and item.get("class") == cls:
                return item
        for item in self.closed_hypotheses:
            if item.get("leaf") == leaf and item.get("class") == cls:
                return item
        return None

    def upsert_open(self, item: dict[str, Any]) -> None:
        self.open_hypotheses = [
            h for h in self.open_hypotheses if not (h.get("id") == item["id"])
        ]
        self.open_hypotheses.append(item)
        self.open_hypotheses = self.open_hypotheses[-MAX_OPEN:]

    def close(self, hid: str, verdict: str, period: str) -> dict[str, Any] | None:
        kept = []
        closed = None
        for item in self.open_hypotheses:
            if item.get("id") == hid:
                closed = {**item, "verdict": verdict, "closed": period}
            else:
                kept.append(item)
        self.open_hypotheses = kept
        if closed:
            self.closed_hypotheses.append(closed)
        return closed

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Memory":
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text()))
