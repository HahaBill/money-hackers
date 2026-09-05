import pytest

from agent import llm
from agent.investigate import investigate_leaf
from agent.memory import Memory
from agent.tavily_tool import SearchResult, TavilyResearcher, build_request, source_tier
from rcg.store import GraphStore


def test_query_builder_is_template_only_and_period_scoped():
    request = build_request("weather", {"city": "Boston", "period": "2026-08"})
    assert request["start_date"] == "2026-08-01"
    assert request["end_date"] == "2026-09-01"
    assert request["include_answer"] is False
    with pytest.raises(ValueError):
        build_request("free_form", {"period": "2026-08"})


def test_source_tiers_keep_unknown_sites_at_tier_four():
    assert source_tier("https://www.weather.gov/example") == 2
    assert source_tier("https://random-blog.example/post") == 4


def test_call_budget_fails_closed(monkeypatch):
    researcher = TavilyResearcher("test", max_calls=0)
    with pytest.raises(RuntimeError, match="budget"):
        researcher.search("weather", {"city": "Boston", "period": "2026-08"})


def test_investigation_uses_bounded_external_evidence_without_causal_promotion(monkeypatch):
    class FakeResearcher:
        available = True

        def __init__(self):
            self.calls = 0

        def search(self, template, context):
            self.calls += 1
            assert template == "weather"
            assert context["city"] == "Boston"
            return [
                SearchResult(
                    url="https://www.weather.gov/example",
                    title="August weather",
                    content="Boston recorded unusually heavy rain in August.",
                    score=0.9,
                    published_date="2026-09-01",
                    tier=2,
                )
            ]

    def fake_complete(prompt, **kwargs):
        if "Pick the two" in prompt:
            return {"classes": ["weather"]}
        return {"assessments": [{"index": 0, "support": "strong_for", "note": "same month"}]}

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete_json", fake_complete)
    researcher = FakeResearcher()
    results = investigate_leaf(
        leaf="traffic",
        phi=-1000,
        store=GraphStore(),
        period="2026-08",
        run_id="tavily_integration",
        memory=Memory(),
        facts=[{"label": "traffic_down", "tier": 1, "support": "neutral"}],
        entity=None,
        use_llm=True,
        budget_left=2,
        researcher=researcher,  # type: ignore[arg-type]
        research_context={"city": "Boston"},
    )
    assert researcher.calls == 1
    assert results[0].cls == "weather"
    assert results[0].verdict.label != "supported"
    assert any(update.temporal_cap_applied for update in results[0].updates)
