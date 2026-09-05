"""Persistent Reasoning & Calculation Graph. Content-addressed node ids."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


def node_id(
    type_: str,
    period: str,
    label: str,
    inputs: list[str],
    *,
    content: Any | None = None,
) -> str:
    address = {"type": type_, "period": period, "label": label, "inputs": inputs}
    if content is not None:
        # Raw data has no upstream node id, so its own content must participate
        # in addressing. Downstream ids then change naturally.
        address["content"] = content
    payload = json.dumps(
        address,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "n_" + hashlib.sha256(payload.encode()).hexdigest()[:6]


@dataclass
class Node:
    id: str
    type: str
    period: str
    run_id: str
    agent_version: str
    label: str
    value: Any
    unit: str | None
    method: str | None
    formula: str | None
    inputs: list[str]
    confidence: float
    status: str = "active"
    supersedes: str | None = None
    provenance: str = "deterministic"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    type: str
    period: str
    run_id: str


class GraphStore:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.con = duckdb.connect(self.path)
        self._init()

    def _init(self) -> None:
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id VARCHAR PRIMARY KEY,
                type VARCHAR,
                period VARCHAR,
                run_id VARCHAR,
                agent_version VARCHAR,
                label VARCHAR,
                value JSON,
                unit VARCHAR,
                method VARCHAR,
                formula VARCHAR,
                inputs JSON,
                confidence DOUBLE,
                status VARCHAR,
                supersedes VARCHAR,
                provenance VARCHAR,
                payload JSON,
                created_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS edges (
                src VARCHAR,
                dst VARCHAR,
                type VARCHAR,
                period VARCHAR,
                run_id VARCHAR
            );
            """
        )

    def write_node(self, node: Node) -> Node:
        self.con.execute(
            """
            INSERT OR REPLACE INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                node.id,
                node.type,
                node.period,
                node.run_id,
                node.agent_version,
                node.label,
                json.dumps(node.value),
                node.unit,
                node.method,
                node.formula,
                json.dumps(node.inputs),
                node.confidence,
                node.status,
                node.supersedes,
                node.provenance,
                json.dumps(node.payload),
                datetime.now(timezone.utc),
            ],
        )
        return node

    def write_edge(self, edge: Edge) -> Edge:
        exists = self.con.execute(
            "SELECT 1 FROM edges WHERE src=? AND dst=? AND type=? AND period=? AND run_id=?",
            [edge.src, edge.dst, edge.type, edge.period, edge.run_id],
        ).fetchone()
        if not exists:
            self.con.execute(
                "INSERT INTO edges VALUES (?, ?, ?, ?, ?)",
                [edge.src, edge.dst, edge.type, edge.period, edge.run_id],
            )
        return edge

    def has_node(self, nid: str) -> bool:
        return bool(self.con.execute("SELECT 1 FROM nodes WHERE id = ?", [nid]).fetchone())

    def mark_superseded(self, old_id: str, new_id: str) -> None:
        self.con.execute(
            "UPDATE nodes SET status = 'superseded', supersedes = ? WHERE id = ?",
            [new_id, old_id],
        )

    def add(
        self,
        *,
        type: str,
        period: str,
        run_id: str,
        label: str,
        value: Any,
        inputs: list[str] | None = None,
        agent_version: str = "v0.3.1",
        unit: str | None = "USD",
        method: str | None = None,
        formula: str | None = None,
        confidence: float = 1.0,
        provenance: str = "deterministic",
        payload: dict[str, Any] | None = None,
        derives_from: list[str] | None = None,
    ) -> Node:
        inputs = inputs or []
        nid = node_id(type, period, label, inputs, content=value if type == "data" else None)
        node = Node(
            id=nid,
            type=type,
            period=period,
            run_id=run_id,
            agent_version=agent_version,
            label=label,
            value=value,
            unit=unit,
            method=method,
            formula=formula,
            inputs=inputs,
            confidence=confidence,
            payload=payload or {},
            provenance=provenance,
        )
        self.write_node(node)
        for parent in derives_from or inputs:
            self.write_edge(Edge(parent, nid, "derives_from", period, run_id))
        return node

    def nodes(self, **filters) -> list[dict[str, Any]]:
        sql = "SELECT * FROM nodes"
        clauses = []
        params: list[Any] = []
        for key, val in filters.items():
            clauses.append(f"{key} = ?")
            params.append(val)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        cur = self.con.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def edges(self) -> list[dict[str, Any]]:
        cur = self.con.execute("SELECT * FROM edges")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def node_values(
        self,
        ids: list[str] | None = None,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        rows = self.nodes(run_id=run_id) if run_id else self.nodes()
        out = {}
        for row in rows:
            if ids is not None and row["id"] not in ids:
                continue
            raw = row["value"]
            out[row["id"]] = json.loads(raw) if isinstance(raw, str) else raw
        return out

    def append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
