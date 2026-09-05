"""Deterministic café states used by the CLI demo and regression generator."""

from engine.graph_def import INPUTS, LeafState

PRICES = {
    "espresso": 3.20,
    "latte": 5.00,
    "iced_latte": 5.50,
    "cold_brew": 4.80,
    "drip": 2.80,
    "pastry": 3.75,
    "sandwich": 4.50,
}

COSTS = {
    "coffee_beans": 18.50,
    "milk": 4.10,
    "food": 1.70,
    "packaging": 0.08,
}

EFF = {item: 1.0 for item in INPUTS}

PRIOR_MIX = {
    "espresso": 0.18,
    "latte": 0.26,
    "iced_latte": 0.16,
    "cold_brew": 0.09,
    "drip": 0.21,
    "pastry": 0.10,
    "sandwich": 0.00,
}

CURRENT_MIX = {
    "espresso": 0.18,
    "latte": 0.22,
    "iced_latte": 0.22,
    "cold_brew": 0.12,
    "drip": 0.16,
    "pastry": 0.10,
    "sandwich": 0.00,
}


def cafe_prior() -> LeafState:
    return LeafState(
        volume=30_000,
        items_per_order=1.4,
        price=dict(PRICES),
        mix=dict(PRIOR_MIX),
        unit_cost=dict(COSTS),
        usage_efficiency=dict(EFF),
        variable_labor=6_300,
        fixed_labor=11_700,
        electricity_variable=225,
        electricity_fixed=675,
        rent=3_600,
        other_variable=1_260,
        other_fixed=2_940,
    )


def cafe_current(*, mix_shift: bool = True, volume_up: bool = True) -> LeafState:
    state = cafe_prior().copy()
    if volume_up:
        state.volume *= 1.11
    if mix_shift:
        state.mix = dict(CURRENT_MIX)
    return state


def cafe_traffic_gap() -> tuple[LeafState, LeafState]:
    prior = cafe_prior()
    prior.traffic = 10_000
    prior.conversion = 0.30
    prior.volume = 0.0
    current = prior.copy()
    current.traffic = 11_500
    current.conversion = 0.30 * (1.11 / 1.15)
    return prior, current
