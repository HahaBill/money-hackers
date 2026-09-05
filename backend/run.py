#!/usr/bin/env python3
"""P0 entry point. Arithmetic in engine/; Astra only for judgment and prose."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import re
from pathlib import Path

from agent import llm
from agent.memory import Memory
from engine.demo_states import cafe_current, cafe_prior
from engine.ingest import ingest_operational_metrics, ingest_summary, ingest_transactions
from engine.pipeline import analyze, persist
from engine.reconcile import load_leaf_map, reconcile
from engine.state_builder import build_leaf_state
from prism_setup import steps_from_findings, submit_run
from rcg.store import GraphStore

BACKEND_ROOT = Path(__file__).resolve().parent
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _scenario(sid: str):
    from eval.scenarios import load

    return load(sid)


def _previous_period(period: str, available: set[str]) -> str:
    candidates = sorted(item for item in available if item < period)
    if not candidates:
        raise ValueError(f"no period before {period} exists in the transaction history")
    return candidates[-1]


def _blocked_payload(period: str, run_id: str, results) -> dict:
    return {
        "period": period,
        "run_id": run_id,
        "status": "blocked",
        "reconciliation": "blocked",
        "checks": [asdict(check) for result in results for check in result.checks],
        "findings": [],
        "narrative": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="2026-08")
    parser.add_argument("--run-id", default="r_001")
    parser.add_argument("--db", default=str(BACKEND_ROOT / "runs/rcg.duckdb"))
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--scenario", help="deterministic regression scenario id")
    source.add_argument("--data", type=Path, help="directory containing transactions.csv and summaries.csv")
    parser.add_argument("--prior-period", help="comparison period; defaults to the latest period before --period")
    parser.add_argument(
        "--category-map",
        type=Path,
        default=BACKEND_ROOT / "data/category_map.yaml",
    )
    parser.add_argument("--llm", action="store_true", help="use OpenAI gpt-6-astra for classify/narrative")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--memory", default=str(BACKEND_ROOT / "runs/memory.json"))
    args = parser.parse_args()

    if not SAFE_RUN_ID.fullmatch(args.run_id):
        parser.error("--run-id may contain only letters, numbers, dot, underscore, and dash")
    if args.llm and not llm.available():
        parser.error("--llm requires OPENAI_API_KEY in backend/.env or the environment")
    use_llm = args.llm and not args.no_llm
    (BACKEND_ROOT / "runs").mkdir(exist_ok=True)
    store = GraphStore(args.db)
    memory = Memory.load(Path(args.memory))

    data_payload = None
    if args.scenario:
        sc = _scenario(args.scenario)
        period, prior, curr = sc.period, sc.prior, sc.curr
        if sc.previous_memory:
            memory = Memory(**{k: v for k, v in sc.previous_memory.items() if k in Memory.__dataclass_fields__})
        facts, entities, history_n = sc.facts, sc.entities, sc.history_n
    elif args.data:
        transactions = ingest_transactions(args.data / "transactions.csv")
        periods = {txn.period for txn in transactions}
        period = args.period
        prior_period = args.prior_period or _previous_period(period, periods)
        summaries_path = args.data / "summaries.csv"
        current_summary = ingest_summary(summaries_path, period=period)
        prior_summary = ingest_summary(summaries_path, period=prior_period)
        category_map = load_leaf_map(args.category_map)
        current_rows = [txn for txn in transactions if txn.period == period]
        prior_rows = [txn for txn in transactions if txn.period == prior_period]
        checks = [
            reconcile(
                prior_rows,
                prior_summary,
                store=store,
                period=prior_period,
                run_id=args.run_id,
                category_map=category_map,
            ),
            reconcile(
                current_rows,
                current_summary,
                store=store,
                period=period,
                run_id=args.run_id,
                category_map=category_map,
            ),
        ]
        if any(result.status == "blocked" for result in checks):
            payload = _blocked_payload(period, args.run_id, checks)
            output = BACKEND_ROOT / "runs" / f"{args.run_id}.json"
            output.write_text(json.dumps(payload, indent=2))
            print(json.dumps(payload, indent=2))
            return 2
        operational = ingest_operational_metrics(args.data / "operational_metrics.csv")
        prior = build_leaf_state(
            prior_rows,
            category_map=category_map,
            operational=operational.get(prior_period),
        )
        curr = build_leaf_state(
            current_rows,
            category_map=category_map,
            operational=operational.get(period),
            fallback=prior,
        )
        facts, entities = {}, {}
        history_n = len([item for item in periods if item < period])
        data_payload = {
            "transaction_ids": [txn.txn_id for txn in current_rows],
            "summary_source": current_summary.source,
            "analysis_basis": current_summary.basis,
        }
    else:
        period, prior, curr = args.period, cafe_prior(), cafe_current()
        facts, entities, history_n = {}, {}, 4

    result = analyze(
        period=period,
        run_id=args.run_id,
        prior=prior,
        curr=curr,
        store=store,
        memory=memory,
        facts_by_leaf=facts,
        entities=entities,
        history_n=history_n,
        use_llm=use_llm,
        data_payload=data_payload,
    )
    persist(result, BACKEND_ROOT / "runs" / f"{args.run_id}.json")
    memory.save(Path(args.memory))
    submit_run(
        run_id=args.run_id,
        period=period,
        agent_version="v0.3.1",
        steps=steps_from_findings(result.findings, result.phi),
    )
    print(json.dumps(result.findings, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
