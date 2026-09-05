"""Post-call webhook: store the transcript; do not encode unstructured facts as evidence."""

from __future__ import annotations

import json
from pathlib import Path


def store_transcript(run_id: str, transcript: str, dest: Path | None = None) -> Path:
    dest = dest or Path(__file__).resolve().parents[1] / "runs" / f"{run_id}.transcript.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"run_id": run_id, "transcript": transcript, "candidates": []}, indent=2))
    return dest
