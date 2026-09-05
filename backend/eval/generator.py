"""Seeded transaction-grain scenario generator from PRD §26."""

from __future__ import annotations

import argparse
import csv
import json
import random
from calendar import monthrange
from pathlib import Path
from typing import Any

import yaml

from engine.graph_def import INPUTS, PRODUCTS, RECIPE, attribution_leaves
from engine.ingest import ingest_operational_metrics, ingest_transactions
from engine.reconcile import load_leaf_map
from engine.shapley import shapley
from engine.state_builder import build_leaf_state

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _period_offset(period: str, offset: int) -> str:
    year, month = (int(part) for part in period.split("-", 1))
    absolute = year * 12 + month - 1 + offset
    return f"{absolute // 12:04d}-{absolute % 12 + 1:02d}"


def _periods(start: str, count: int) -> list[str]:
    return [_period_offset(start, offset) for offset in range(count)]


def _weighted_counts(total: int, shares: dict[str, float], rng: random.Random) -> dict[str, int]:
    products = list(shares)
    weights = [max(0.0, shares[name]) for name in products]
    picks = rng.choices(products, weights=weights, k=total)
    return {product: picks.count(product) for product in products}


def _month_injections(config: dict[str, Any], month_number: int) -> list[dict[str, Any]]:
    return [
        item
        for item in config.get("inject", [])
        if int(item.get("month", 0)) == month_number
    ]


def _month_parameters(config: dict[str, Any], month_number: int) -> tuple[float, dict[str, float], dict[str, float]]:
    base = config["base"]
    volume_factor = 1.0
    shares = {name: float(spec["share"]) for name, spec in base["products"].items()}
    input_costs = {
        "milk": 4.10,
        "coffee_beans": 18.50,
        "food": 8.00,
        "packaging": 0.12,
        **{
            ("coffee_beans" if name == "beans" else name): float(spec["unit_cost"])
            for name, spec in base.get("inputs", {}).items()
        },
    }
    for injection in _month_injections(config, month_number):
        leaf = injection["leaf"]
        change = injection["change"]
        if leaf == "volume":
            volume_factor *= 1.0 + float(change)
        elif leaf == "mix":
            for product, delta in change.items():
                shares[product] = shares.get(product, 0.0) + float(delta)
        elif leaf.startswith("unit_cost."):
            input_name = leaf.split(".", 1)[1]
            input_costs[input_name] *= 1.0 + float(change)
    total_share = sum(max(0.0, value) for value in shares.values())
    shares = {name: max(0.0, value) / total_share for name, value in shares.items()}
    return volume_factor, shares, input_costs


def generate(config_path: Path, out_dir: Path, *, seed: int) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text())
    rng = random.Random(seed)
    months = int(config.get("months", 6))
    start = config.get("start_period", "2026-03")
    periods = _periods(start, months)
    base = config["base"]
    products = base["products"]
    order_mean = float(base["daily_orders"]["mean"])
    order_sd = float(base["daily_orders"].get("sd", 0.0))
    cost_noise = float(base.get("noise", {}).get("cost_sd", 0.0))
    transactions: list[dict[str, Any]] = []
    operational: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for month_number, period in enumerate(periods, start=1):
        year, month = (int(part) for part in period.split("-", 1))
        days = monthrange(year, month)[1]
        volume_factor, shares, input_costs = _month_parameters(config, month_number)
        monthly_quantities = {product: 0 for product in products}
        revenue = 0.0
        orders = 0
        for day in range(1, days + 1):
            daily_orders = max(1, round(rng.gauss(order_mean, order_sd) * volume_factor))
            orders += daily_orders
            counts = _weighted_counts(daily_orders, shares, rng)
            for product, quantity in counts.items():
                if not quantity:
                    continue
                price = float(products[product]["price"])
                amount = quantity * price
                monthly_quantities[product] += quantity
                revenue += amount
                transactions.append(
                    {
                        "txn_id": f"rev-{period}-{day:02d}-{product}",
                        "date": f"{period}-{day:02d}T12:00:00",
                        "period": period,
                        "amount": f"{amount:.2f}",
                        "txn_type": "revenue",
                        "category": "sales",
                        "counterparty": "POS customers",
                        "product": product,
                        "quantity": quantity,
                        "unit_price": f"{price:.4f}",
                        "basis": "accrual",
                        "tags": "",
                    }
                )

        expenses = 0.0
        for input_name in INPUTS:
            quantity = sum(
                monthly_quantities.get(product, 0) * RECIPE[product].get(input_name, 0.0)
                for product in PRODUCTS
            )
            if quantity <= 0:
                continue
            unit_cost = input_costs[input_name] * (1.0 + rng.gauss(0.0, cost_noise))
            amount = quantity * unit_cost
            expenses += amount
            supplier_specs = base.get("inputs", {}).get(
                "beans" if input_name == "coffee_beans" else input_name,
                {},
            )
            suppliers = supplier_specs.get("suppliers") or [f"{input_name} supplier"]
            transactions.append(
                {
                    "txn_id": f"cogs-{period}-{input_name}",
                    "date": f"{period}-15",
                    "period": period,
                    "amount": f"{-amount:.2f}",
                    "txn_type": "cogs",
                    "category": input_name,
                    "counterparty": rng.choice(suppliers),
                    "product": "",
                    "quantity": f"{quantity:.6f}",
                    "unit_price": f"{unit_cost:.6f}",
                    "basis": "accrual",
                    "tags": "",
                }
            )

        opex = base.get("opex", {})
        fixed_and_ratio = {
            "labor": revenue * float(opex.get("labor", 0.30)),
            "rent": float(opex.get("rent", 3600.0)),
            "electricity": float((opex.get("electricity") or {}).get("base", 900.0)),
            "other_opex": revenue * float(opex.get("other", 0.07)),
        }
        for category, amount in fixed_and_ratio.items():
            expenses += amount
            transactions.append(
                {
                    "txn_id": f"opex-{period}-{category}",
                    "date": f"{period}-28",
                    "period": period,
                    "amount": f"{-amount:.2f}",
                    "txn_type": "opex",
                    "category": category,
                    "counterparty": f"{category} provider",
                    "product": "",
                    "quantity": "",
                    "unit_price": "",
                    "basis": "accrual",
                    "tags": "",
                }
            )
        summaries.append(
            {
                "period": period,
                "revenue": f"{revenue:.2f}",
                "expenses": f"{expenses:.2f}",
                "operating_profit": f"{revenue - expenses:.2f}",
                "basis": "accrual",
            }
        )
        operational.append(
            {
                "period": period,
                "foot_traffic": round(orders / 0.30),
                "orders": orders,
                "opening_hours": days * 12,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    txn_fields = list(transactions[0])
    with (out_dir / "transactions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=txn_fields)
        writer.writeheader()
        writer.writerows(transactions)
    with (out_dir / "summaries.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    with (out_dir / "operational_metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(operational[0]))
        writer.writeheader()
        writer.writerows(operational)

    ingested = ingest_transactions(out_dir / "transactions.csv")
    operational_by_period = ingest_operational_metrics(out_dir / "operational_metrics.csv")
    category_map = load_leaf_map(BACKEND_ROOT / "data/category_map.yaml")
    previous_period, current_period = periods[-2:]
    previous = build_leaf_state(
        [txn for txn in ingested if txn.period == previous_period],
        category_map=category_map,
        operational=operational_by_period[previous_period],
    )
    current = build_leaf_state(
        [txn for txn in ingested if txn.period == current_period],
        category_map=category_map,
        operational=operational_by_period[current_period],
        fallback=previous,
    )
    attribution = shapley(attribution_leaves(has_traffic=True), previous, current)
    primary = max(attribution, key=lambda leaf: abs(attribution[leaf]))
    truth = {
        "scenario": config.get("scenario", config_path.stem),
        "seed": seed,
        "period": current_period,
        "prior_period": previous_period,
        "primary_leaf": primary,
        "attribution_truth": {leaf: round(value, 6) for leaf, value in attribution.items()},
        "injections": config.get("inject", []),
        "distractors": config.get("distractors", []),
    }
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "config": config_path.name,
                "seed": seed,
                "periods": periods,
                "rows": len(transactions),
                "files": [
                    "transactions.csv",
                    "summaries.csv",
                    "operational_metrics.csv",
                    "truth.json",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    return truth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(generate(args.config, args.out, seed=args.seed), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
