from agent import llm


def test_classifier_and_judgment_routes_are_explicit():
    assert llm.model_for("classifier") == llm.CLASSIFIER_MODEL
    assert llm.model_for("judgment") == llm.JUDGMENT_MODEL
    assert llm.CLASSIFIER_MODEL
    assert llm.JUDGMENT_MODEL
