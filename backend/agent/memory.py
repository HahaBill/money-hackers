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
MAX_FEEDBACK = 30


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
        for item in reversed(self.open_hypotheses):
            if item.get("leaf") == leaf and item.get("class") == cls:
                return item
        for item in reversed(self.closed_hypotheses):
            if item.get("leaf") == leaf and item.get("class") == cls:
                return item
        return None

    def upsert_open(self, item: dict[str, Any]) -> None:
        self.open_hypotheses = [
            h
            for h in self.open_hypotheses
            if not (
                h.get("id") == item["id"]
                or (h.get("leaf") == item.get("leaf") and h.get("class") == item.get("class"))
            )
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

    def add_answer(self, answer: dict[str, Any]) -> None:
        self.owner_answers.append(answer)
        self.owner_answers = self.owner_answers[-MAX_ANSWERS:]

    def add_directive(self, directive: dict[str, Any]) -> None:
        self.directives = [
            item for item in self.directives if item.get("driver") != directive.get("driver")
        ]
        self.directives.append(directive)
        self.directives = self.directives[-MAX_DIRECTIVES:]

    def add_feedback(self, item: dict[str, Any]) -> None:
        self.feedback.append(item)
        self.feedback = self.feedback[-MAX_FEEDBACK:]

    def adjusted_prior(self, leaf: str, cls: str, default: float) -> float:
        """Apply deterministic owner-feedback multipliers to a class prior."""
        prior = default
        for item in self.feedback:
            if item.get("leaf") != leaf or item.get("class") != cls:
                continue
            rating = item.get("rating")
            if rating == "right":
                prior *= 1.15
            elif rating == "wrong":
                prior *= 0.70
            elif rating == "incomplete":
                prior *= 0.90
        return max(0.05, min(0.80, prior))

    def bump_version(self) -> None:
        self.version += 1

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Memory":
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text()))
