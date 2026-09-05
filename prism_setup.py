"""PRISM Observe → Improve → Prove. Trajectories mirror RCG writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

AGENT_NAME = "money-talks"
AGENT_ID = "moneytalks-1"


def _local(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def submit_run(
    *,
    run_id: str,
    period: str,
    agent_version: str,
    steps: list[dict[str, Any]],
    out_dir: Path = Path("runs/prism"),
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
    key = os.environ.get("PRISM_API_KEY")
    host = os.environ.get("PRISM_HOST", "https://prismtrace.blockconvey.com")
    project = os.environ.get("PRISM_PROJECT_ID")
    if not (key and project):
        return payload
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
    return [
        {"step_type": "reasoning", "label": "reconcile", "output_summary": findings.get("reconciliation"), "status": "success"},
        {
            "step_type": "reasoning",
            "label": "decompose_shapley",
            "output_summary": f"sum={sum(phi.values()):.2f} leaves={len(phi)}",
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "rank_materiality",
            "output_summary": ",".join(f["leaf"] for f in findings.get("findings", [])),
            "status": "success",
        },
        {
            "step_type": "reasoning",
            "label": "investigate",
            "output_summary": f"findings={len(findings.get('findings', []))}",
            "status": "success",
        },
        {
            "step_type": "final_answer",
            "label": "generate_findings",
            "output_summary": findings.get("headline", {}).get("change"),
            "status": "success",
        },
    ]
