from engine.materiality import rank


def test_gate_drops_small_items():
    ranked = rank(
        [
            {"leaf": "mix", "dollar_impact": -1420, "z": 2.4, "persistence": 1, "hhi": 0.51},
            {"leaf": "rent", "dollar_impact": -20, "z": 4.0, "persistence": 3, "hhi": 1.0},
        ],
        revenue=70_000,
    )
    assert [r.leaf for r in ranked] == ["mix"]


def test_top_score_is_100():
    ranked = rank(
        [
            {"leaf": "mix", "dollar_impact": -1420, "z": 2.4, "persistence": 1, "hhi": 0.51},
            {"leaf": "unit_cost.milk", "dollar_impact": -930, "z": 3.1, "persistence": 2, "hhi": 0.82},
            {"leaf": "electricity_fixed", "dollar_impact": -760, "z": 2.9, "persistence": 3},
            {"leaf": "conversion", "dollar_impact": -570, "z": 1.8, "persistence": 1},
        ],
        revenue=70_000,
    )
    assert ranked[0].score == 100.0
    # Dollars + concentration beat the most abnormal / persistent line.
    assert ranked[0].leaf in {"mix", "unit_cost.milk"}
    assert "electricity_fixed" in [r.leaf for r in ranked]
    elec = next(r for r in ranked if r.leaf == "electricity_fixed")
    assert elec.score < 100.0
