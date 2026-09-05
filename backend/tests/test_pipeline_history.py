import json

from agent.memory import Memory
from engine.pipeline import analyze
from eval.scenarios import load
from rcg.store import GraphStore


def _value(row):
    return json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]


def test_baselines_and_recurrence_use_prior_run_history():
    scenario = load("A")
    store = GraphStore()
    memory = Memory()
    first = analyze(
        period="2026-08",
        run_id="history_aug",
        prior=scenario.prior,
        curr=scenario.curr,
        store=store,
        memory=memory,
        facts_by_leaf=scenario.facts,
        entities=scenario.entities,
        history_n=0,
        use_llm=False,
    )
    second = analyze(
        period="2026-09",
        run_id="history_sep",
        prior=scenario.prior,
        curr=scenario.curr,
        store=store,
        memory=memory,
        facts_by_leaf=scenario.facts,
        entities=scenario.entities,
        history_n=1,
        use_llm=False,
    )

    baselines = sorted(
        store.nodes(type="baseline", label="unit_cost.milk"),
        key=lambda row: row["period"],
    )
    assert _value(baselines[0])["n"] == 0
    assert _value(baselines[1])["n"] == 1
    assert next(item for item in second.ranking if item.leaf == "unit_cost.milk").persistence == 2
    recurrences = [edge for edge in store.edges() if edge["type"] == "recurs_from"]
    assert any(edge["src"] == baselines[0]["id"] and edge["dst"] == baselines[1]["id"] for edge in recurrences)
    assert first.findings["confidence_regime"] == "prior_dominant"
