import pytest

from agent.memory import Memory
from agent.templates import templates_for


@pytest.mark.regression
def test_o_repeated_wrong_feedback_lowers_class_prior_and_reorders_candidates():
    memory = Memory()
    for period in ("2026-07", "2026-08"):
        memory.add_feedback(
            {
                "leaf": "unit_cost.milk",
                "class": "supplier_specific",
                "rating": "wrong",
                "period": period,
            }
        )
    supplier = next(item for item in templates_for("unit_cost.milk") if item.cls == "supplier_specific")
    market = next(item for item in templates_for("unit_cost.milk") if item.cls == "market_inflation")
    assert memory.adjusted_prior("unit_cost.milk", supplier.cls, supplier.prior) < supplier.prior
    assert memory.adjusted_prior("unit_cost.milk", market.cls, market.prior) > memory.adjusted_prior(
        "unit_cost.milk", supplier.cls, supplier.prior
    )
