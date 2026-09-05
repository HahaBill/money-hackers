from prism_setup import steps_from_findings


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
    assert by_label["validate_output"]["metrics"]["unsourced_figure_rate"] == 0.0
