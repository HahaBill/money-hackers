#!/usr/bin/env python3
"""P0 entry point. Arithmetic in engine/; Astra only for judgment and prose."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent import llm
from agent.memory import Memory
from engine.pipeline import analyze, persist
from prism_setup import steps_from_findings, submit_run
from rcg.store import GraphStore
from tests.cafe_states import cafe_curr, cafe_prior


def _scenario(sid: str):
    from eval.scenarios import load

    return load(sid)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="2026-08")
    parser.add_argument("--run-id", default="r_001")
    parser.add_argument("--db", default="runs/rcg.duckdb")
    parser.add_argument("--scenario", help="A, B, C, D, E, or I")
    parser.add_argument("--llm", action="store_true", help="use OpenAI gpt-6-astra for classify/narrative")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--memory", default="runs/memory.json")
    args = parser.parse_args()

    use_llm = args.llm or (llm.available() and not args.no_llm)
    Path("runs").mkdir(exist_ok=True)
    store = GraphStore(args.db)
    memory = Memory.load(Path(args.memory))

    if args.scenario:
        sc = _scenario(args.scenario)
        period, prior, curr = sc.period, sc.prior, sc.curr
        if sc.previous_memory:
            memory = Memory(**{k: v for k, v in sc.previous_memory.items() if k in Memory.__dataclass_fields__})
        facts, entities, history_n = sc.facts, sc.entities, sc.history_n
    else:
        period, prior, curr = args.period, cafe_prior(), cafe_curr()
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
    )
    persist(result, Path("runs") / f"{args.run_id}.json")
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
