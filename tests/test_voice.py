from fastapi.testclient import TestClient

from voice.server_tools import app


def test_briefing_404():
    client = TestClient(app)
    assert client.get("/tools/get_briefing", params={"run_id": "missing"}).status_code == 404
