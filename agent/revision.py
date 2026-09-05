"""Cross-period revision. A change of mind is a graph write, not a prompt trick."""

from __future__ import annotations

from agent.investigate import HypothesisResult
from agent.memory import Memory
from rcg.store import Edge, GraphStore


def apply_revisions(
    results: list[HypothesisResult],
    *,
    store: GraphStore,
    period: str,
    run_id: str,
    memory: Memory,
) -> list[dict]:
    revisions = []
    for result in results:
        prior = memory.prior_for(result.leaf, result.cls)
        if not prior:
            continue
        old_verdict = prior.get("verdict")
        if old_verdict == "supported" and result.verdict.label in {"weakening", "rejected"}:
            old_id = prior.get("verdict_node") or prior.get("id")
            node = store.add(
                type="revision",
                period=period,
                run_id=run_id,
                label=f"{result.leaf}:{result.cls}",
                value={
                    "old": old_id,
                    "new": result.id,
                    "from": old_verdict,
                    "to": result.verdict.label,
                    "reason": f"{result.leaf} {result.cls} no longer supported",
                },
                unit=None,
                provenance="inferred",
            )
            store.write_edge(Edge(str(old_id), node.id, "supersedes", period, run_id))
            revisions.append(
                {
                    "old": old_id,
                    "new": result.id,
                    "summary": f"{result.leaf}: {result.cls} {old_verdict} → {result.verdict.label}",
                }
            )
    return revisions
