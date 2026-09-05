"""Post-call webhook: store the transcript; do not encode unstructured facts as evidence."""

from __future__ import annotations

import json
from pathlib import Path


def store_transcript(run_id: str, transcript: str, dest: Path | None = None) -> Path:
    dest = dest or Path("runs") / f"{run_id}.transcript.json"
    dest.write_text(json.dumps({"run_id": run_id, "transcript": transcript, "candidates": []}, indent=2))
    return dest
