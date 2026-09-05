"""Post-call storage. Unstructured facts remain pending until owner confirmation."""

from __future__ import annotations

import json
import re
from pathlib import Path


FACT_PATTERNS = (
    re.compile(r"\bwe (?:started|stopped|changed|opened|closed|switched|added|removed)\b[^.!?]*", re.I),
    re.compile(r"\b(?:new|different) supplier\b[^.!?]*", re.I),
    re.compile(r"\b(?:raised|lowered|changed) (?:our )?prices?\b[^.!?]*", re.I),
    re.compile(r"\b(?:promotion|discount|construction|road closure)\b[^.!?]*", re.I),
)


def confirmation_candidates(transcript: str) -> list[dict[str, str]]:
    """Extract operational statements without treating them as evidence."""
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in FACT_PATTERNS:
        for match in pattern.finditer(transcript):
            text = match.group(0).strip()
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "text": text,
                    "status": "pending_confirmation",
                    "source": "voice_transcript",
                }
            )
    return found[:10]


def store_transcript(
    run_id: str,
    transcript: str,
    *,
    conversation_id: str,
    dest: Path | None = None,
) -> Path:
    dest = dest or (
        Path(__file__).resolve().parents[1]
        / "runs"
        / "transcripts"
        / f"{conversation_id}.json"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "conversation_id": conversation_id,
                "transcript": transcript,
                "candidates": confirmation_candidates(transcript),
            },
            indent=2,
        )
        + "\n"
    )
    return dest
