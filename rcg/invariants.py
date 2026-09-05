"""Graph invariants from PRD §9. Fail the run if any break."""

from __future__ import annotations

import json
from collections import defaultdict, deque

from rcg.store import GraphStore

TOLERANCE = 0.01


class InvariantError(AssertionError):
    pass


def _parents(store: GraphStore) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in store.edges():
        if edge["type"] == "derives_from":
            incoming[edge["dst"]].append(edge["src"])
    return incoming


def reachable(store: GraphStore, start: str, pred) -> bool:
    parents = _parents(store)
    nodes = {n["id"]: n for n in store.nodes()}
    seen = set()
    q = deque([start])
    while q:
        nid = q.popleft()
        if nid in seen:
            continue
        seen.add(nid)
        node = nodes.get(nid)
        if node and pred(node):
            return True
        q.extend(parents.get(nid, []))
    return False


def check_findings_reach_attribution(store: GraphStore) -> None:
    for node in store.nodes():
        if node["type"] != "finding":
            continue
        if not reachable(store, node["id"], lambda n: n["type"] == "attribution"):
            raise InvariantError(f"finding {node['id']} has no path to an attribution")


def check_attributions_reach_data(store: GraphStore) -> None:
    for node in store.nodes():
        if node["type"] != "attribution":
            continue
        if not reachable(store, node["id"], lambda n: n["type"] == "data"):
            raise InvariantError(f"attribution {node['id']} has no path to data")


def check_attribution_sum(store: GraphStore, period: str) -> None:
    attrs = [n for n in store.nodes() if n["type"] == "attribution" and n["period"] == period]
    vars_ = [n for n in store.nodes() if n["type"] == "variance" and n["period"] == period]
    if not attrs or not vars_:
        return
    total = 0.0
    for node in attrs:
        val = json.loads(node["value"]) if isinstance(node["value"], str) else node["value"]
        if isinstance(val, (int, float)):
            total += float(val)
    parent = vars_[0]
    parent_val = json.loads(parent["value"]) if isinstance(parent["value"], str) else parent["value"]
    if abs(total - float(parent_val)) >= TOLERANCE:
        raise InvariantError(
            f"attributions sum to {total:.4f}, variance is {parent_val} (period {period})"
        )


def check_supported_verdict_tier(store: GraphStore) -> None:
    evidence_by_id = {n["id"]: n for n in store.nodes() if n["type"] == "evidence"}
    supports: dict[str, list[str]] = defaultdict(list)
    for edge in store.edges():
        if edge["type"] == "supports":
            supports[edge["dst"]].append(edge["src"])
    for node in store.nodes():
        if node["type"] != "verdict":
            continue
        val = json.loads(node["value"]) if isinstance(node["value"], str) else node["value"]
        if not (isinstance(val, dict) and val.get("verdict") == "supported"):
            continue
        ok = False
        for eid in supports.get(node["id"], []):
            ev = evidence_by_id.get(eid)
            if not ev:
                continue
            payload = json.loads(ev["payload"]) if isinstance(ev["payload"], str) else ev["payload"]
            if payload.get("tier", 99) <= 2 and not payload.get("temporal_only"):
                ok = True
        if not ok:
            raise InvariantError(f"supported verdict {node['id']} lacks tier≤2 non-temporal evidence")


def check_supersedes(store: GraphStore) -> None:
    incoming = defaultdict(int)
    for edge in store.edges():
        if edge["type"] == "supersedes":
            incoming[edge["dst"]] += 1
    for node in store.nodes():
        if node["status"] != "superseded":
            continue
        if incoming.get(node["id"], 0) != 1:
            raise InvariantError(f"superseded node {node['id']} must have exactly one supersedes edge")


def check_all(store: GraphStore, period: str | None = None) -> None:
    check_findings_reach_attribution(store)
    check_attributions_reach_data(store)
    if period:
        check_attribution_sum(store, period)
    check_supported_verdict_tier(store)
    check_supersedes(store)
