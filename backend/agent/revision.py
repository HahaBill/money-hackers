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
        prior = result.previous
        if not prior:
            continue
        old_verdict = prior.get("verdict")
        if old_verdict == "supported" and result.verdict.label in {"weakening", "rejected"}:
            old_id = prior.get("verdict_node")
            node = store.add(
                type="revision",
                period=period,
                run_id=run_id,
                label=f"{result.leaf}:{result.cls}",
                value={
                    "old": old_id or prior.get("id"),
                    "new": result.verdict_node_id,
                    "from": old_verdict,
                    "to": result.verdict.label,
                    "reason": f"{result.leaf} {result.cls} no longer supported",
                },
                unit=None,
                provenance="inferred",
            )
            if old_id and store.has_node(old_id):
                store.write_edge(
                    Edge(result.verdict_node_id, old_id, "supersedes", period, run_id)
                )
                store.mark_superseded(old_id, result.verdict_node_id)
            revisions.append(
                {
                    "old": old_id or prior.get("id"),
                    "new": result.verdict_node_id,
                    "summary": f"{result.leaf}: {result.cls} {old_verdict} → {result.verdict.label}",
                    "node": node.id,
                }
            )
    return revisions
