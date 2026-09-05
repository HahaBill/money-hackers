"""ElevenLabs server tools. Voice never computes; it only sequences validated text."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

RUNS = Path("runs")
app = FastAPI(title="money-talks voice tools")


def _load(run_id: str) -> dict:
    path = RUNS / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, f"run {run_id} not found")
    return json.loads(path.read_text())


@app.get("/tools/get_briefing")
def get_briefing(run_id: str):
    data = _load(run_id)
    return {"text": data.get("narrative", {}).get("briefing", "")}


@app.get("/tools/get_finding")
def get_finding(run_id: str, finding_id: str):
    data = _load(run_id)
    for item in data.get("findings", []):
        if item["id"] == finding_id:
            return {"text": data.get("narrative", {}).get("walkthrough", ""), "finding": item}
    raise HTTPException(404, "finding not found")


@app.get("/tools/get_recommendations")
def get_recommendations(run_id: str):
    data = _load(run_id)
    return {"text": data.get("narrative", {}).get("recommendations", "")}


@app.get("/tools/get_verify_items")
def get_verify_items(run_id: str):
    data = _load(run_id)
    return {"text": data.get("narrative", {}).get("verify", ""), "items": data.get("verify", [])}


@app.get("/tools/get_questions")
def get_questions(run_id: str):
    data = _load(run_id)
    return {"questions": data.get("questions", [])}


class AnswerIn(BaseModel):
    run_id: str
    question_id: str
    option: str


@app.post("/tools/record_answer")
def record_answer(body: AnswerIn):
    mem_path = Path("runs/memory.json")
    blob = json.loads(mem_path.read_text()) if mem_path.exists() else {"owner_answers": []}
    blob.setdefault("owner_answers", []).append(
        {"q": body.question_id, "option": body.option, "run_id": body.run_id}
    )
    mem_path.write_text(json.dumps(blob, indent=2))
    return {"text": "Noted. I will factor that in next period."}


@app.get("/tools/get_revisions")
def get_revisions(run_id: str):
    data = _load(run_id)
    return {"revisions": data.get("revisions", [])}
