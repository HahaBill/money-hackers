from fastapi.testclient import TestClient

from voice.server_tools import app


def test_briefing_404():
    client = TestClient(app)
    assert client.get("/tools/get_briefing", params={"run_id": "missing"}).status_code == 404


def test_run_id_cannot_escape_runs_directory():
    client = TestClient(app)
    assert client.get("/tools/get_briefing", params={"run_id": "../secret"}).status_code == 400


def test_voice_guard_rejects_new_figure():
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
