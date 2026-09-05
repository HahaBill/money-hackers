"""pytest -m regression — scenarios A–E and I."""

from __future__ import annotations

import pytest

from agent.memory import Memory
from engine.pipeline import analyze
from eval.scenarios import load
from rcg.store import GraphStore

pytestmark = pytest.mark.regression


def _run(sid: str):
    sc = load(sid)
    memory = Memory()
    if sc.previous_memory:
        memory = Memory(**{k: v for k, v in sc.previous_memory.items() if k in Memory.__dataclass_fields__})
    store = GraphStore()
    return analyze(
        period=sc.period,
        run_id=f"reg_{sid}",
        prior=sc.prior,
        curr=sc.curr,
        store=store,
        memory=memory,
        facts_by_leaf=sc.facts,
        entities=sc.entities,
        history_n=sc.history_n,
        use_llm=False,
    ), sc


def test_a_ingredient_inflation():
    result, sc = _run("A")
    assert result.ranking[0].leaf.startswith(sc.truth["primary_leaf_prefix"])
    classes = {h.cls: h.verdict.label for h in result.investigation.results if h.leaf.startswith("unit_cost")}
    assert classes.get("market_inflation") == "supported"


def test_b_mix_primary():
    result, _ = _run("B")
    assert result.ranking[0].leaf == "mix"


def test_c_traffic():
    result, _ = _run("C")
    assert result.ranking[0].leaf == "traffic"
    by_cls = {h.cls: h.verdict.label for h in result.investigation.results}
    assert by_cls.get("competitor") != "supported"


def test_d_temporal_cap_blocks_weather():
    result, _ = _run("D")
    assert result.ranking[0].leaf == "traffic"
    weather = [h for h in result.investigation.results if h.cls == "weather"]
    assert all(h.verdict.label != "supported" for h in weather)
    capped = [u for h in result.investigation.results for u in h.updates if u.temporal_cap_applied]
    assert capped


def test_e_dollars_beat_distractor():
    result, _ = _run("E")
    assert result.ranking[0].leaf.startswith("unit_cost")
    elec = [r for r in result.ranking if "electricity" in r.leaf]
    assert not elec or result.ranking[0].score > elec[0].score


def test_i_revision():
    result, _ = _run("I")
    assert result.revisions
    equipment = [h for h in result.investigation.results if h.cls == "equipment"]
    assert equipment
    weather = [h for h in result.investigation.results if h.cls == "weather"]
    assert weather
    assert weather[0].verdict.label in {"weakening", "rejected"}
