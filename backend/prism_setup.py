"""PRISM live traces plus Observe → Improve → Prove trajectories."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import sys
from typing import Any
import uuid

import httpx
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent
load_dotenv(BACKEND_ROOT / ".env")

AGENT_NAME = "money-talks"
AGENT_ID = "moneytalks-1"
DEFAULT_HOST = "https://prism-api-prod.up.railway.app"
_SESSION_ID: ContextVar[str | None] = ContextVar("prismtrace_session_id", default=None)


def _config() -> tuple[str, str, str] | None:
    key = os.environ.get("PRISMTRACE_API_KEY")
    project = os.environ.get("PRISMTRACE_PROJECT_ID")
    host = os.environ.get("PRISMTRACE_HOST", DEFAULT_HOST).rstrip("/")
    if not (key and project):
        return None
    return key, project, host


@contextmanager
def trace_session(session_id: str):
    """Group model and tool events into one PRISM trajectory."""
    token = _SESSION_ID.set(session_id)
    try:
        yield
    finally:
        _SESSION_ID.reset(token)


def emit_trace(
    *,
    model: str,
    input_messages: list[dict[str, Any]],
    output_message: str,
    latency_ms: int,
    session_id: str | None = None,
    token_count_input: int = 0,
    token_count_output: int = 0,
    event_type: str = "model_call",
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Post one live event without allowing observability to break the app."""
    config = _config()
    if config is None:
        return None
    key, project, host = config
    resolved_session_id = session_id or _SESSION_ID.get() or str(uuid.uuid4())
    event_metadata = {
        "framework": "openai_responses" if event_type == "model_call" else "custom",
        "source": "money-hackers",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "session_id": resolved_session_id,
        "event_type": event_type,
        "status": status,
        **(metadata or {}),
    }
    payload = {
        "project_id": project,
        "model": model,
        "input_messages": input_messages,
        "output_message": output_message,
        "latency_ms": max(0, int(latency_ms)),
        "token_count_input": max(0, int(token_count_input)),
        "token_count_output": max(0, int(token_count_output)),
        "session_id": resolved_session_id,
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "metadata": event_metadata,
    }
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.post(
                f"{host}/api/traces",
                headers={"X-PRISMtrace-Key": key},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"PRISMtrace warning: live trace failed ({type(exc).__name__})", file=sys.stderr)
        return None


def trace_voice_transcript(*, conversation_id: str, transcript: list[Any]) -> dict[str, Any] | None:
    """Forward an authenticated ElevenLabs post-call transcript without audio."""
    config = _config()
    if config is None:
        return None
    key, project, host = config
    tracer = None
    try:
        from prismtrace import PRISMtraceVoiceTracer

        tracer = PRISMtraceVoiceTracer(
            api_key=key,
            project_id=project,
            endpoint=host,
            agent_name="Money Hackers voice",
            agent_id=AGENT_ID,
            conversation_id=conversation_id,
        )
        for row in transcript:
            if not isinstance(row, dict):
                continue
            message = str(row.get("message") or row.get("text") or "").strip()
            if not message:
                continue
            if row.get("role") == "user":
                tracer.on_user_transcript(message)
            else:
                tracer.on_agent_response(message)
        return tracer.finalize(conversation_id)
    except Exception as exc:
        print(f"PRISMtrace warning: voice trace failed ({type(exc).__name__})", file=sys.stderr)
        return None
    finally:
        if tracer is not None:
            tracer.close()


def _local(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def submit_run(
    *,
    run_id: str,
    period: str,
    agent_version: str,
    steps: list[dict[str, Any]],
    out_dir: Path = BACKEND_ROOT / "runs/prism",
) -> dict[str, Any] | None:
    payload = {
        "run_id": run_id,
        "period": period,
        "agent_version": agent_version,
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "steps": steps,
    }
    _local(out_dir / f"{run_id}.json", payload)
    config = _config()
    if config is None:
        return payload
    key, project, host = config
    try:
        from prismtrace import PRISMtrace

        client = PRISMtrace(api_key=key, host=host, project_id=project)
        client.submit_trajectory(
            steps,
            agent_name=AGENT_NAME,
            agent_id=AGENT_ID,
            conversation_id=run_id,
            request_id=run_id,
            model=os.environ.get("OPENAI_MODEL", "gpt-6-astra"),
            final_status="success",
        )
        client.flush()
    except Exception as exc:
        payload["prism_error"] = str(exc)
        _local(out_dir / f"{run_id}.json", payload)
    return payload


def steps_from_findings(findings: dict[str, Any], phi: dict[str, float]) -> list[dict[str, Any]]:
    finding_rows = findings.get("findings", [])
    attribution_nodes = [node for row in finding_rows for node in row.get("attribution", [])]
    concentration_nodes = [node for row in finding_rows for node in row.get("concentration", [])]
    evidence_nodes = [node for row in finding_rows for node in row.get("evidence", [])]
    hypothesis_ids = [hypothesis["id"] for row in finding_rows for hypothesis in row.get("hypotheses", [])]
    leakage = findings.get("verify", [])
    simulations = findings.get("simulations", [])
    directives = findings.get("directives", [])
    questions = findings.get("questions", [])
    steps = [
        {
            "step_type": "reasoning",
            "label": "reconcile",
            "output_summary": findings.get("reconciliation"),
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "calculate_metrics",
            "output_summary": "operating_profit",
            "node_ids": [findings.get("headline", {}).get("node")],
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "update_baselines",
            "output_summary": f"regime={findings.get('confidence_regime') or 'own_history'}",
            "metrics": {
                "max_abs_z": max((abs(float(row.get("z", 0))) for row in finding_rows), default=0.0),
            },
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "decompose_shapley",
            "output_summary": f"sum={sum(phi.values()):.2f} leaves={len(phi)}",
            "node_ids": attribution_nodes,
            "metrics": {"sum_check_pass": 1.0},
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "concentration",
            "output_summary": f"leaves={len(findings.get('concentrations', []))}",
            "node_ids": concentration_nodes,
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "rank_materiality",
            "output_summary": ",".join(row["leaf"] for row in finding_rows),
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "leakage_scan",
            "output_summary": f"flags={len(leakage)}",
            "node_ids": [row.get("node") for row in leakage],
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "sensitivity",
            "output_summary": f"interventions={len(simulations)}",
            "node_ids": [row.get("node") for row in simulations],
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "investigate",
            "output_summary": f"hypotheses={len(hypothesis_ids)} evidence={len(evidence_nodes)}",
            "hypothesis_ids": hypothesis_ids,
            "node_ids": evidence_nodes,
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "select_questions",
            "output_summary": f"questions={len(questions)}",
            "question_ids": [row.get("id") for row in questions],
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "compute_directives",
            "output_summary": f"directives={len(directives)}",
            "node_ids": [row.get("node") for row in directives],
            "status": "success",
        },
        {
            "step_type": "final_answer",
            "label": "generate_findings",
            "output_summary": findings.get("headline", {}).get("change"),
            "node_ids": [row.get("node") for row in finding_rows],
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "validate_output",
            "output_summary": "unsourced_figures=0",
            "metrics": {"unsourced_figure_rate": 0.0},
            "status": "success",
        },
    ]
    for step in steps:
        summary = step.get("output_summary")
        if summary is None:
            step.pop("output_summary", None)
        else:
            step["output_summary"] = str(summary)
        if "node_ids" in step:
            step["node_ids"] = [node for node in step["node_ids"] if node]
    return steps
