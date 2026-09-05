from prism_setup import emit_trace, steps_from_findings, trace_session


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True}


class _Client:
    def __init__(self, sent, **_kwargs):
        self.sent = sent

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, url, *, headers, json):
        self.sent.append((url, headers, json))
        return _Response()


def test_emit_trace_uses_prismtrace_env_and_shared_session(monkeypatch):
    sent = []
    monkeypatch.setenv("PRISMTRACE_API_KEY", "pt-sk-test")
    monkeypatch.setenv("PRISMTRACE_PROJECT_ID", "project-test")
    monkeypatch.setenv("PRISMTRACE_HOST", "https://prism.example/")
    monkeypatch.setattr(
        "prism_setup.httpx.Client",
        lambda **kwargs: _Client(sent, **kwargs),
    )

    with trace_session("run-123"):
        result = emit_trace(
            model="gpt-test",
            input_messages=[{"role": "user", "content": "hello"}],
            output_message="hi",
            latency_ms=12,
        )

    assert result == {"ok": True}
    url, headers, payload = sent[0]
    assert url == "https://prism.example/api/traces"
    assert headers == {"X-PRISMtrace-Key": "pt-sk-test"}
    assert payload["project_id"] == "project-test"
    assert payload["session_id"] == "run-123"
    assert payload["metadata"]["session_id"] == "run-123"


def test_prism_steps_carry_graph_node_ids_and_validation_metric():
    findings = {
        "reconciliation": "passed",
        "confidence_regime": "prior_assisted",
        "headline": {"node": "n_var", "change": -100},
        "findings": [
            {
                "id": "f_1",
                "leaf": "mix",
                "z": 2.1,
                "node": "n_find",
                "attribution": ["n_attr"],
                "concentration": ["n_conc"],
                "evidence": ["n_ev"],
                "hypotheses": [{"id": "h_1"}],
            }
        ],
        "verify": [],
        "simulations": [],
        "directives": [],
        "questions": [],
        "concentrations": [{}],
    }
    steps = steps_from_findings(findings, {"mix": -100})
    by_label = {step["label"]: step for step in steps}
    assert by_label["decompose_shapley"]["node_ids"] == ["n_attr"]
    assert by_label["generate_findings"]["node_ids"] == ["n_find"]
    assert by_label["generate_findings"]["output_summary"] == "-100"
    assert by_label["validate_output"]["metrics"]["unsourced_figure_rate"] == 0.0
