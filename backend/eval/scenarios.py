"""Leaf-state scenarios A–E and I from PRD §24."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.graph_def import INPUTS, LeafState
from engine.demo_states import cafe_prior


@dataclass
class Scenario:
    id: str
    period: str
    prior_period: str
    prior: LeafState
    curr: LeafState
    facts: dict[str, list[dict[str, Any]]]
    entities: dict[str, str] = field(default_factory=dict)
    truth: dict[str, Any] = field(default_factory=dict)
    history_n: int = 4
    previous_memory: dict[str, Any] | None = None


def _base() -> LeafState:
    return cafe_prior()


def scenario_a() -> Scenario:
    prior = _base()
    curr = prior.copy()
    for inp in INPUTS:
        curr.unit_cost[inp] = prior.unit_cost[inp] * 1.18
    facts = {
        f"unit_cost.{inp}": [
            {
                "label": "all_suppliers_up",
                "tier": 1,
                "support": "strong_for",
                "classes": ["market_inflation"],
                "extract": "all suppliers of this input rose 15 to 20%",
            },
            {
                "label": "market_dairy_beans",
                "tier": 2,
                "support": "strong_for",
                "classes": ["market_inflation"],
                "source": "tavily",
                "extract": "commodity markets corroborate a 15 to 18% rise",
            },
        ]
        for inp in INPUTS
    }
    return Scenario(
        "A",
        "2026-08",
        "2026-07",
        prior,
        curr,
        facts,
        truth={"primary_leaf_prefix": "unit_cost", "supported_class": "market_inflation"},
    )


def scenario_b() -> Scenario:
    prior = _base()
    curr = prior.copy()
    curr.mix = {
        "espresso": 0.18,
        "latte": 0.22,
        "iced_latte": 0.24,
        "cold_brew": 0.12,
        "drip": 0.14,
        "pastry": 0.10,
        "sandwich": 0.00,
    }
    curr.volume = prior.volume * 1.11
    return Scenario(
        "B",
        "2026-08",
        "2026-07",
        prior,
        curr,
        {
            "mix": [
                {
                    "label": "iced_share",
                    "tier": 1,
                    "support": "strong_for",
                    "classes": ["seasonal"],
                    "extract": "iced_latte share 16% to 24%",
                }
            ]
        },
        truth={"primary_leaf": "mix"},
    )


def scenario_c() -> Scenario:
    prior = _base()
    prior.traffic = 10_000.0
    prior.conversion = 0.30
    prior.volume = 0.0
    curr = prior.copy()
    curr.traffic = 8_200.0
    return Scenario(
        "C",
        "2026-08",
        "2026-07",
        prior,
        curr,
        {
            "traffic": [
                {
                    "label": "traffic_down",
                    "tier": 1,
                    "support": "strong_for",
                    "classes": ["traffic"],
                    "extract": "foot traffic fell 18%",
                }
            ],
            "volume": [
                {
                    "label": "no_competitor_signal",
                    "tier": 1,
                    "support": "strong_against",
                    "classes": ["competitor"],
                    "extract": "decline appeared in one step, not gradual",
                }
            ],
        },
        truth={"primary_leaf": "traffic", "supported_class": "traffic", "not_supported": "competitor"},
    )


def scenario_d() -> Scenario:
    prior = _base()
    prior.traffic = 10_000.0
    prior.conversion = 0.30
    prior.volume = 0.0
    curr = prior.copy()
    curr.traffic = 8_600.0
    return Scenario(
        "D",
        "2026-08",
        "2026-07",
        prior,
        curr,
        {
            "traffic": [
                {
                    "label": "dry_day_traffic",
                    "tier": 1,
                    "support": "strong_for",
                    "classes": ["traffic"],
                    "extract": "dry-day traffic also fell 14%",
                },
                {
                    "label": "rain_article",
                    "tier": 3,
                    "support": "strong_for",
                    "classes": ["weather"],
                    "temporal_only": True,
                    "source": "tavily",
                    "extract": "it rained that month",
                },
            ],
            "electricity_fixed": [
                {
                    "label": "rain_article",
                    "tier": 3,
                    "support": "strong_for",
                    "temporal_only": True,
                    "extract": "it rained that month",
                }
            ],
        },
        truth={"no_supported_weather": True, "temporal_cap": True, "primary_leaf": "traffic"},
    )


def scenario_e() -> Scenario:
    prior = _base()
    curr = prior.copy()
    for inp in INPUTS:
        curr.unit_cost[inp] = prior.unit_cost[inp] * 1.10
    curr.electricity_fixed = prior.electricity_fixed + 200
    return Scenario(
        "E",
        "2026-08",
        "2026-07",
        prior,
        curr,
        {
            "unit_cost.milk": [
                {"label": "inputs_up", "tier": 1, "support": "strong_for", "extract": "ingredient unit costs +10%"}
            ],
            "electricity_fixed": [
                {"label": "bill_up", "tier": 1, "support": "weak_for", "extract": "electricity +200"}
            ],
        },
        truth={"primary_leaf_prefix": "unit_cost"},
    )


def scenario_i() -> Scenario:
    """September: weather normalized, electricity still high → revise July weather verdict."""
    prior = _base()
    curr = prior.copy()
    curr.electricity_fixed = prior.electricity_fixed + 800
    return Scenario(
        "I",
        "2026-09",
        "2026-08",
        prior,
        curr,
        {
            "electricity_fixed": [
                {
                    "label": "weather_normal",
                    "tier": 1,
                    "support": "strong_against",
                    "classes": ["weather"],
                    "extract": "cooling degree days back to normal",
                },
                {
                    "label": "kwh_per_order_up",
                    "tier": 1,
                    "support": "strong_for",
                    "classes": ["equipment"],
                    "extract": "kWh per order still elevated",
                },
            ]
        },
        previous_memory={
            "version": 2,
            "open_hypotheses": [
                {
                    "id": "h_electricity_weather_2026-07",
                    "leaf": "electricity_fixed",
                    "class": "weather",
                    "posterior": 0.78,
                    "verdict": "supported",
                    "first_seen": "2026-07",
                }
            ],
            "closed_hypotheses": [],
            "directives": [],
            "owner_answers": [],
            "learned_patterns": [],
            "feedback": [],
            "baseline_version": "2026-07",
        },
        truth={"revision": True, "leading_class": "equipment"},
    )


REGISTRY = {
    "A": scenario_a,
    "B": scenario_b,
    "C": scenario_c,
    "D": scenario_d,
    "E": scenario_e,
    "I": scenario_i,
}


def load(sid: str) -> Scenario:
    return REGISTRY[sid]()
