"""ElevenLabs server tools. Voice never computes; it only sequences validated text."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.memory import Memory
from rcg.validator import ValidationError, validate_text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUNS = BACKEND_ROOT / "runs"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
app = FastAPI(title="money-talks voice tools")


def _load(run_id: str) -> dict:
    if not SAFE_ID.fullmatch(run_id):
        raise HTTPException(400, "invalid run id")
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
            # Numeric structured data never goes to the voice model. It only
            # receives prose that already passed the backend validator.
            return {"text": data.get("narrative", {}).get("walkthrough", "")}
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
    data = _load(body.run_id)
    question = next(
        (item for item in data.get("questions", []) if item.get("id") == body.question_id),
        None,
    )
    if not question:
        raise HTTPException(404, "question not found")
    if body.option not in question.get("options", []):
        raise HTTPException(422, "option is not valid for this question")
    mem_path = RUNS / "memory.json"
    memory = Memory.load(mem_path)
    memory.add_answer(
        {
            "q": body.question_id,
            "asked": data.get("period"),
            "option": body.option,
            "run_id": body.run_id,
            "encoded": {
                "leaf": question.get("leaf"),
                "class": question.get("class"),
                "support": "strong_for",
            },
        }
    )
    memory.bump_version()
    memory.save(mem_path)
    return {"text": "Noted. I will factor that in next period."}


@app.get("/tools/get_revisions")
def get_revisions(run_id: str):
    data = _load(run_id)
    return {"revisions": data.get("revisions", [])}


class UtteranceIn(BaseModel):
    run_id: str
    text: str
    last_tool_text: str


@app.post("/tools/validate_utterance")
def validate_utterance(body: UtteranceIn):
    _load(body.run_id)
    # Only figures in the most recent validated tool response may be repeated.
    from rcg.validator import extract_numbers

    try:
        validate_text(body.text, {"last_tool_numbers": extract_numbers(body.last_tool_text)})
    except ValidationError as exc:
        return {"valid": False, "retry": True, "reason": str(exc)}
    return {"valid": True, "retry": False}
