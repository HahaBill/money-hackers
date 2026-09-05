"""ElevenLabs server tools. Voice never computes; it only sequences validated text."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.memory import Memory
from agent.questions import support_for_option
from rcg.validator import ValidationError, validate_text
from voice.postcall import store_transcript

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")
RUNS = BACKEND_ROOT / "runs"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
WEBHOOK_MAX_AGE_SECONDS = 30 * 60
SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
app = FastAPI(title="money-talks backend")
frontend_origins = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]
if frontend_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


def _load(run_id: str) -> dict:
    if not SAFE_ID.fullmatch(run_id):
        raise HTTPException(400, "invalid run id")
    path = RUNS / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, f"run {run_id} not found")
    return json.loads(path.read_text())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    return _load(run_id)


def _dynamic_variables(data: dict, run_id: str) -> dict[str, str]:
    findings = data.get("findings") or []
    headline_text = data.get("narrative", {}).get("briefing", "")
    return {
        "business_name": os.environ.get("BUSINESS_NAME", "the café"),
        "period": str(data.get("period") or "the latest period"),
        "headline_text": headline_text,
        "finding_count": str(len(findings)),
        "top_finding_title": str(findings[0].get("title") if findings else "No material finding"),
        "run_id": run_id,
    }


@app.get("/voice/session")
def create_voice_session(run_id: str):
    """Mint a short-lived browser URL without exposing the ElevenLabs key."""
    data = _load(run_id)
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID")
    if not api_key or not agent_id:
        raise HTTPException(503, "ElevenLabs agent is not configured")
    try:
        response = httpx.get(
            SIGNED_URL_ENDPOINT,
            params={"agent_id": agent_id, "include_conversation_id": "true"},
            headers={"xi-api-key": api_key},
            timeout=15.0,
        )
        response.raise_for_status()
        signed_url = response.json()["signed_url"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(502, "ElevenLabs session creation failed") from exc
    return {
        "signed_url": signed_url,
        "dynamic_variables": _dynamic_variables(data, run_id),
    }


def _verify_elevenlabs_signature(
    body: bytes,
    signature_header: str | None,
    secret: str,
    *,
    now: float | None = None,
) -> bool:
    if not signature_header or not secret:
        return False
    fields = {}
    for part in signature_header.split(","):
        key, separator, value = part.partition("=")
        if separator:
            fields[key.strip()] = value.strip()
    try:
        timestamp = int(fields["t"])
    except (KeyError, ValueError):
        return False
    current = time.time() if now is None else now
    if timestamp > current + 60 or current - timestamp > WEBHOOK_MAX_AGE_SECONDS:
        return False
    expected = hmac.new(
        secret.encode(),
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, fields.get("v0", ""))


def _post_call_fields(payload: dict) -> tuple[str, str, str]:
    data = payload.get("data") or {}
    conversation_id = str(data.get("conversation_id") or "")
    initiation = data.get("conversation_initiation_client_data") or {}
    dynamic = initiation.get("dynamic_variables") or {}
    run_id = str(dynamic.get("run_id") or data.get("run_id") or "")
    transcript_rows = data.get("transcript") or []
    parts = []
    for row in transcript_rows:
        if isinstance(row, dict):
            message = row.get("message") or row.get("text")
            if message:
                parts.append(f"{row.get('role', 'unknown')}: {message}")
        elif isinstance(row, str):
            parts.append(row)
    return conversation_id, run_id, "\n".join(parts)


@app.post("/webhooks/elevenlabs/post-call")
async def elevenlabs_post_call(request: Request):
    body = await request.body()
    secret = os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(503, "post-call webhook secret is not configured")
    if not _verify_elevenlabs_signature(
        body,
        request.headers.get("ElevenLabs-Signature"),
        secret,
    ):
        raise HTTPException(401, "invalid ElevenLabs signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "invalid JSON payload") from exc
    if payload.get("type") != "post_call_transcription":
        return {"status": "ignored"}
    conversation_id, run_id, transcript = _post_call_fields(payload)
    if not SAFE_ID.fullmatch(conversation_id) or not SAFE_ID.fullmatch(run_id):
        raise HTTPException(400, "invalid conversation or run id")
    _load(run_id)
    path = RUNS / "transcripts" / f"{conversation_id}.json"
    if path.exists():
        return {"status": "duplicate", "conversation_id": conversation_id}
    stored = store_transcript(
        run_id,
        transcript,
        conversation_id=conversation_id,
        dest=path,
    )
    record = json.loads(stored.read_text())
    return {
        "status": "stored",
        "conversation_id": conversation_id,
        "confirmation_candidates": len(record["candidates"]),
    }


@app.get("/tools/get_briefing")
def get_briefing(run_id: str):
    data = _load(run_id)
    return {
        "text": data.get("narrative", {}).get("briefing", ""),
        "finding_ids": [item.get("id") for item in data.get("findings", [])],
    }


@app.get("/tools/get_finding")
def get_finding(run_id: str, finding_id: str):
    data = _load(run_id)
    for item in data.get("findings", []):
        if item["id"] == finding_id:
            # Numeric structured data never goes to the voice model. It only
            # receives prose that already passed the backend validator.
            narrative = data.get("narrative", {})
            return {
                "text": narrative.get("finding_texts", {}).get(
                    finding_id,
                    narrative.get("walkthrough", ""),
                )
            }
    raise HTTPException(404, "finding not found")


@app.get("/tools/get_recommendations")
def get_recommendations(run_id: str):
    data = _load(run_id)
    return {"text": data.get("narrative", {}).get("recommendations", "")}


@app.get("/tools/get_verify_items")
def get_verify_items(run_id: str):
    data = _load(run_id)
    return {"text": data.get("narrative", {}).get("verify", "")}


@app.get("/tools/get_questions")
def get_questions(run_id: str):
    data = _load(run_id)
    return {
        "questions": [
            {"id": item["id"], "text": item["text"], "options": item.get("options", [])}
            for item in data.get("questions", [])
        ]
    }


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
                "support": support_for_option(body.option),
            },
        }
    )
    memory.bump_version()
    memory.save(mem_path)
    return {"text": "Noted. I will factor that in next period."}


class FeedbackIn(BaseModel):
    run_id: str
    finding_id: str
    rating: str
    hypothesis_id: str | None = None


@app.post("/feedback")
def record_feedback(body: FeedbackIn):
    if body.rating not in {"right", "wrong", "incomplete"}:
        raise HTTPException(422, "rating must be right, wrong, or incomplete")
    data = _load(body.run_id)
    finding = next(
        (item for item in data.get("findings", []) if item.get("id") == body.finding_id),
        None,
    )
    if not finding:
        raise HTTPException(404, "finding not found")
    hypotheses = finding.get("hypotheses") or []
    hypothesis = next(
        (
            item
            for item in hypotheses
            if not body.hypothesis_id or item.get("id") == body.hypothesis_id
        ),
        None,
    )
    if not hypothesis:
        raise HTTPException(404, "hypothesis not found")
    memory = Memory.load(RUNS / "memory.json")
    memory.add_feedback(
        {
            "run_id": body.run_id,
            "finding_id": body.finding_id,
            "hypothesis_id": hypothesis.get("id"),
            "leaf": finding.get("leaf"),
            "class": hypothesis.get("class"),
            "rating": body.rating,
            "period": data.get("period"),
        }
    )
    memory.bump_version()
    memory.save(RUNS / "memory.json")
    return {"status": "recorded"}


@app.get("/tools/get_revisions")
def get_revisions(run_id: str):
    data = _load(run_id)
    revisions = [item.get("summary", "") for item in data.get("revisions", [])]
    return {"text": " ".join(item for item in revisions if item)}


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
