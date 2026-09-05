from agent.belief import lr_for, posterior_from
from agent.verdict import decide


def test_temporal_cap():
    ratio, capped = lr_for("strong_for", temporal_only=True)
    assert capped
    assert ratio == 1.5


def test_supported_requires_tier2():
    v = decide(posterior=0.9, has_tier2_nontemporal=False, has_strong_against_internal=False)
    assert v.label == "unresolved"
    v2 = decide(posterior=0.9, has_tier2_nontemporal=True, has_strong_against_internal=False)
    assert v2.label == "supported"


def test_posterior_moves():
    p = posterior_from(0.3, [8.0])
    assert p > 0.7
