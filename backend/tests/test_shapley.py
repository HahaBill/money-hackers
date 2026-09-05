from engine.graph_def import attribution_leaves, profit_fn
from engine.demo_states import cafe_current, cafe_prior, cafe_traffic_gap
from engine.shapley import shapley


def test_shapley_sums_to_delta():
    prior = cafe_prior()
    curr = cafe_current()
    leaves = attribution_leaves(has_traffic=False)
    phi = shapley(leaves, prior, curr)
    assert abs(sum(phi.values()) - (profit_fn(curr) - profit_fn(prior))) < 0.01


def test_mix_is_not_residual():
    prior = cafe_prior()
    curr = cafe_current(mix_shift=True, volume_up=False)
    leaves = attribution_leaves(has_traffic=False)
    phi = shapley(leaves, prior, curr)
    delta = profit_fn(curr) - profit_fn(prior)
    # Mix is the only structural change; it must own most of Δprofit.
    assert abs(phi["mix"]) >= 0.80 * abs(delta)
    assert abs(phi["volume"]) < 1.0


def test_null_player_unchanged_leaf():
    prior = cafe_prior()
    curr = cafe_current()
    curr.rent = prior.rent
    leaves = attribution_leaves(has_traffic=False)
    phi = shapley(leaves, prior, curr)
    assert abs(phi["rent"]) < 0.01


def test_traffic_conversion_split():
    prior, curr = cafe_traffic_gap()
    leaves = attribution_leaves(has_traffic=True)
    phi = shapley(leaves, prior, curr)
    assert phi["traffic"] > 0
    assert phi["conversion"] < 0
    assert abs(sum(phi.values()) - (profit_fn(curr) - profit_fn(prior))) < 0.01
