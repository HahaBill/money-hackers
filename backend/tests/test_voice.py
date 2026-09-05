import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from voice.server_tools import app


def test_briefing_404():
    client = TestClient(app)
    assert client.get("/tools/get_briefing", params={"run_id": "missing"}).status_code == 404


def test_run_id_cannot_escape_runs_directory():
    client = TestClient(app)
    assert client.get("/tools/get_briefing", params={"run_id": "../secret"}).status_code == 400


@pytest.mark.regression
def test_m_voice_guard_rejects_new_figure():
    from voice import server_tools

    path = server_tools.RUNS / "voice_guard_test.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"run_id":"voice_guard_test"}')
    try:
        client = TestClient(app)
        response = client.post(
            "/tools/validate_utterance",
            json={
                "run_id": "voice_guard_test",
                "text": "Profit changed $900.",
                "last_tool_text": "Profit changed $800.",
            },
        )
        assert response.json()["retry"] is True
    finally:
        path.unlink(missing_ok=True)


def _signed_body(payload: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(),
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return body, f"t={timestamp},v0={digest}"


def test_post_call_requires_signature(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", "test-secret")
    response = TestClient(app).post(
        "/webhooks/elevenlabs/post-call",
        content=b"{}",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401


def test_post_call_is_idempotent_and_keeps_facts_pending(monkeypatch):
    from voice import server_tools

    secret = "test-secret"
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", secret)
    run_path = server_tools.RUNS / "postcall_test.json"
    transcript_path = server_tools.RUNS / "transcripts" / "conv_postcall_test.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text('{"run_id":"postcall_test"}')
    payload = {
        "type": "post_call_transcription",
        "data": {
            "conversation_id": "conv_postcall_test",
            "conversation_initiation_client_data": {
                "dynamic_variables": {"run_id": "postcall_test"}
            },
            "transcript": [
                {"role": "user", "message": "We started opening Sundays."},
                {"role": "agent", "message": "I will ask you to confirm that next period."},
            ],
        },
    }
    body, signature = _signed_body(payload, secret)
    try:
        client = TestClient(app)
        first = client.post(
            "/webhooks/elevenlabs/post-call",
            content=body,
            headers={
                "content-type": "application/json",
                "ElevenLabs-Signature": signature,
            },
        )
        assert first.status_code == 200
        assert first.json()["confirmation_candidates"] == 1
        stored = json.loads(transcript_path.read_text())
        assert stored["candidates"][0]["status"] == "pending_confirmation"
        second = client.post(
            "/webhooks/elevenlabs/post-call",
            content=body,
            headers={
                "content-type": "application/json",
                "ElevenLabs-Signature": signature,
            },
        )
        assert second.json()["status"] == "duplicate"
    finally:
        run_path.unlink(missing_ok=True)
        transcript_path.unlink(missing_ok=True)


def test_record_answer_encodes_negative_option(monkeypatch, tmp_path):
    from voice import server_tools

    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    (tmp_path / "answer_test.json").write_text(
        json.dumps(
            {
                "period": "2026-08",
                "questions": [
                    {
                        "id": "q_1",
                        "text": "Did the contract change?",
                        "options": ["yes", "no", "not sure"],
                        "leaf": "unit_cost.milk",
                        "class": "order_tier",
                    }
                ],
            }
        )
    )
    response = TestClient(app).post(
        "/tools/record_answer",
        json={"run_id": "answer_test", "question_id": "q_1", "option": "no"},
    )
    assert response.status_code == 200
    saved = json.loads((tmp_path / "memory.json").read_text())
    assert saved["owner_answers"][0]["encoded"]["support"] == "strong_against"


def test_frontend_voice_session_keeps_api_key_server_side(monkeypatch, tmp_path):
    from voice import server_tools

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"signed_url": "wss://api.elevenlabs.io/conversation?signature=test"}

    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    monkeypatch.setattr(server_tools.httpx, "get", fake_get)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "server-only-key")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_test")
    (tmp_path / "session_test.json").write_text(
        json.dumps(
            {
                "period": "2026-08",
                "findings": [{"title": "Mix changed"}],
                "narrative": {"briefing": "Validated briefing."},
            }
        )
    )
    response = TestClient(app).get("/voice/session", params={"run_id": "session_test"})
    assert response.status_code == 200
    assert response.json()["dynamic_variables"]["run_id"] == "session_test"
    assert "server-only-key" not in response.text
    assert captured["headers"]["xi-api-key"] == "server-only-key"


def test_direct_voice_transcribes_browser_audio(monkeypatch, tmp_path):
    from voice import server_tools

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"text": "What changed in August?"}

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    monkeypatch.setattr(server_tools, "DEMO_RUNS", tmp_path / "demo-fixtures")
    monkeypatch.setattr(server_tools.httpx, "post", fake_post)
    monkeypatch.setattr(server_tools, "emit_trace", lambda **_kwargs: None)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "server-only-key")
    (tmp_path / "voice_direct.json").write_text('{"run_id":"voice_direct"}')

    response = TestClient(app).post(
        "/voice/transcribe",
        params={"run_id": "voice_direct"},
        content=b"webm-audio",
        headers={"content-type": "audio/webm"},
    )
    assert response.status_code == 200
    assert response.json() == {"text": "What changed in August?"}
    assert captured["url"] == server_tools.SPEECH_TO_TEXT_ENDPOINT
    assert captured["headers"]["xi-api-key"] == "server-only-key"
    assert captured["data"]["model_id"] == "scribe_v2"


def test_direct_voice_speaks_only_validated_chat_text(monkeypatch, tmp_path):
    from voice import server_tools

    class Response:
        content = b"mp3-audio"
        headers = {"content-type": "audio/mpeg"}

        def raise_for_status(self):
            return None

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    monkeypatch.setattr(server_tools, "DEMO_RUNS", tmp_path / "demo-fixtures")
    monkeypatch.setattr(server_tools.httpx, "post", fake_post)
    monkeypatch.setattr(server_tools, "emit_trace", lambda **_kwargs: None)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "server-only-key")
    (tmp_path / "voice_speak.json").write_text(
        json.dumps(
            {
                "run_id": "voice_speak",
                "headline": {"metric": "operating_profit", "change": -120.0},
                "findings": [],
            }
        )
    )

    response = TestClient(app).post(
        "/voice/speak",
        json={"run_id": "voice_speak", "text": "Operating profit decreased by $120."},
    )
    assert response.status_code == 200
    assert response.content == b"mp3-audio"
    assert captured["headers"]["xi-api-key"] == "server-only-key"
    assert captured["json"]["text"] == "Operating profit decreased by $120."

    rejected = TestClient(app).post(
        "/voice/speak",
        json={"run_id": "voice_speak", "text": "Operating profit decreased by $999."},
    )
    assert rejected.status_code == 400
