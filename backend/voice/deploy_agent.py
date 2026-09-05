#!/usr/bin/env python3
"""Deploy the versioned ElevenLabs agent and standalone webhook tools."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from voice.tool_specs import webhook_tools

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.elevenlabs.io/v1/convai"
STATE_PATH = ROOT / "voice/deployment.json"


def _public_https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname not in {None, "localhost", "127.0.0.1"}


def deploy(base_url: str, *, api_key: str, agent_id: str | None = None) -> str:
    if not _public_https(base_url):
        raise ValueError("--base-url must be a public HTTPS endpoint reachable by ElevenLabs")
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"tools": {}}
    tool_ids = []
    with httpx.Client(base_url=API, headers=headers, timeout=30.0) as client:
        for tool in webhook_tools(base_url):
            existing_id = state.get("tools", {}).get(tool["name"])
            if existing_id:
                response = client.patch(f"/tools/{existing_id}", json={"tool_config": tool})
            else:
                response = client.post("/tools", json={"tool_config": tool})
            response.raise_for_status()
            tool_id = existing_id or response.json()["id"]
            state.setdefault("tools", {})[tool["name"]] = tool_id
            tool_ids.append(tool_id)

        config = json.loads((ROOT / "voice/agent_config.json").read_text())
        config["conversation_config"]["agent"]["prompt"]["tool_ids"] = tool_ids
        if agent_id:
            response = client.patch(f"/agents/{agent_id}", json=config)
        else:
            response = client.post("/agents/create", json=config)
        response.raise_for_status()
        deployed_id = agent_id or response.json()["agent_id"]
    state["agent_id"] = deployed_id
    state["base_url"] = base_url.rstrip("/")
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    return deployed_id


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("ELEVENLABS_AGENT_ID") or state.get("agent_id"),
    )
    args = parser.parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        parser.error("ELEVENLABS_API_KEY is not configured")
    agent_id = deploy(args.base_url, api_key=key, agent_id=args.agent_id)
    print(json.dumps({"agent_id": agent_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
