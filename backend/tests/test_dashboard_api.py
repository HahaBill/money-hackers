import json

from fastapi.testclient import TestClient

from rcg.store import GraphStore
from voice import server_tools


def test_run_discovery_and_dashboard_graph(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    (tmp_path / "demo.json").write_text(
        json.dumps(
            {
                "run_id": "demo",
                "period": "2026-08",
                "status": "complete",
                "headline": {"change": -120.0},
                "findings": [{"id": "f_001"}],
            }
        )
    )
    store = GraphStore(tmp_path / "rcg.duckdb")
    data = store.add(
        type="data",
        period="2026-08",
        run_id="demo",
        label="leaf_states",
        value={"prior_profit": 1_000, "curr_profit": 880},
    )
    variance = store.add(
        type="variance",
        period="2026-08",
        run_id="demo",
        label="operating_profit_delta",
        value=-120,
        inputs=[data.id],
    )
    store.add(
        type="attribution",
        period="2026-08",
        run_id="demo",
        label="unit_cost.milk",
        value=-120,
        inputs=[variance.id],
    )
    store.con.close()

    client = TestClient(server_tools.app)
    runs = client.get("/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == "demo"
    assert runs.json()["runs"][0]["graph_node_count"] == 3

    graph = client.get("/runs/demo/graph").json()
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 2

    dashboard = client.get("/dashboard/demo").json()
    assert dashboard["business"]["name"] == "Garden State Coffee"
    assert dashboard["metrics"]["curr_profit"] == 880
    assert dashboard["attribution_total"] == -120
    assert dashboard["attributions"][0]["driver"] == "unit_cost.milk"
    assert dashboard["attribution_summary"] == dashboard["attributions"]
    assert dashboard["sheet_rows"][1]["label"] == "Operating profit"


def test_runs_ignores_memory_and_invalid_json(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    (tmp_path / "memory.json").write_text('{"version": 1}')
    (tmp_path / "broken.json").write_text("not-json")
    assert TestClient(server_tools.app).get("/runs").json() == {"runs": []}


def test_dashboard_falls_back_to_report_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    (tmp_path / "report_only.json").write_text(
        json.dumps(
            {
                "run_id": "report_only",
                "period": "2026-08",
                "status": "complete",
                "reconciliation": "passed",
                "headline": {"change": -120.0},
                "findings": [
                    {"id": "f_001", "leaf": "mix", "attribution_dollars": -75.0}
                ],
                "narrative": {"briefing": "Profit changed by $120."},
            }
        )
    )
    dashboard = TestClient(server_tools.app).get("/dashboard/report_only").json()
    assert dashboard["attribution_total"] == -120
    assert dashboard["attributions"] == [
        {"node": None, "driver": "mix", "dollars": -75.0},
        {"node": None, "driver": "everything_else", "dollars": -45.0},
    ]


def test_chat_uses_validated_deterministic_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    monkeypatch.setattr(server_tools.llm, "available", lambda: False)
    (tmp_path / "chat_demo.json").write_text(
        json.dumps(
            {
                "run_id": "chat_demo",
                "period": "2026-08",
                "status": "complete",
                "reconciliation": "passed",
                "headline": {"change": -120.0},
                "findings": [],
                "narrative": {"briefing": "Operating profit changed -120."},
            }
        )
    )
    response = TestClient(server_tools.app).post(
        "/chat", json={"run_id": "chat_demo", "message": "How did profit change?"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "answer": "Operating profit changed -120.",
        "sources": ["headline"],
        "mode": "deterministic",
    }
