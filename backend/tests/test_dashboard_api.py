import json

from fastapi.testclient import TestClient

from rcg.store import GraphStore
from voice import server_tools


def test_run_discovery_and_dashboard_graph(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    monkeypatch.setattr(server_tools, "DEMO_RUNS", tmp_path / "demo-fixtures")
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
    monkeypatch.setattr(server_tools, "DEMO_RUNS", tmp_path / "demo-fixtures")
    (tmp_path / "memory.json").write_text('{"version": 1}')
    (tmp_path / "broken.json").write_text("not-json")
    assert TestClient(server_tools.app).get("/runs").json() == {"runs": []}


def test_csv_demo_is_available_and_reconciles():
    dashboard = TestClient(server_tools.app).get("/dashboard/garden_state_coffee_model").json()
    assert dashboard["report"]["period"] == "2025-08"
    assert dashboard["report"]["source_workbook"] == "CoffeeshopFinancials.csv"
    assert dashboard["attribution_total"] == -13802.0
    assert sum(item["dollars"] for item in dashboard["attributions"]) == -13802.0
    assert dashboard["sheet_rows"][0]["current"] == 116640.0
    assert dashboard["sheet_rows"][-1]["current"] == -38681.0


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
        {"node": "f_001", "driver": "mix", "dollars": -75.0},
        {"node": None, "driver": "everything_else", "dollars": -45.0},
    ]


def test_dashboard_has_only_one_residual_per_attribution_view(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    (tmp_path / "residual.json").write_text(
        json.dumps(
            {
                "run_id": "residual",
                "period": "2026-08",
                "status": "complete",
                "headline": {"change": 100.0},
                "findings": [
                    {"id": "a", "leaf": "volume", "attribution_dollars": 50.0},
                    {"id": "b", "leaf": "mix", "attribution_dollars": 30.0},
                    {"id": "c", "leaf": "price", "attribution_dollars": 20.0},
                    {"id": "d", "leaf": "labor", "attribution_dollars": 10.0},
                    {"id": "e", "leaf": "electricity", "attribution_dollars": 5.0},
                    {"id": "f", "leaf": "everything_else", "attribution_dollars": -15.0},
                ],
            }
        )
    )
    dashboard = TestClient(server_tools.app).get("/dashboard/residual").json()
    assert sum(item["driver"] == "everything_else" for item in dashboard["attributions"]) == 1
    assert sum(item["driver"] == "everything_else" for item in dashboard["attribution_summary"]) == 1
    assert sum(item["dollars"] for item in dashboard["attributions"]) == 100.0
    assert sum(item["dollars"] for item in dashboard["attribution_summary"]) == 100.0


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
        "answer": "Operating profit decreased by $120.",
        "sources": ["headline"],
        "mode": "deterministic",
    }


def test_chat_names_largest_attribution_from_sorted_graph_data(monkeypatch, tmp_path):
    monkeypatch.setattr(server_tools, "RUNS", tmp_path)
    monkeypatch.setattr(server_tools.llm, "available", lambda: False)
    (tmp_path / "drivers.json").write_text(
        json.dumps(
            {
                "run_id": "drivers",
                "period": "2026-08",
                "status": "complete",
                "headline": {"change": 140.0, "node": "headline-node"},
                "findings": [
                    {"id": "mix-node", "leaf": "mix", "attribution_dollars": 40.0},
                    {"id": "volume-node", "leaf": "volume", "attribution_dollars": 100.0},
                ],
            }
        )
    )
    response = TestClient(server_tools.app).post(
        "/chat", json={"run_id": "drivers", "message": "What changed profit?"}
    )
    assert response.json()["answer"] == (
        "Operating profit increased by $140. "
        "The largest verified contribution was more tickets at +$100."
    )
    assert response.json()["sources"] == ["headline-node", "volume-node"]
