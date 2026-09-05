import json

from voice.deploy_agent import ROOT, _public_https
from voice.tool_specs import webhook_tools


def test_agent_uses_standalone_tool_ids_not_deprecated_inline_tools():
    config = json.loads((ROOT / "voice/agent_config.json").read_text())
    prompt = config["conversation_config"]["agent"]["prompt"]
    assert "tool_ids" in prompt
    assert "tools" not in prompt
    assert "end_call" in prompt["built_in_tools"]


def test_deploy_requires_public_https_webhook():
    assert _public_https("https://api.example.com")
    assert not _public_https("http://localhost:8090")


def test_every_webhook_tool_points_at_backend_and_has_schema():
    tools = webhook_tools("https://api.example.com")
    assert {tool["name"] for tool in tools} >= {"get_briefing", "record_answer"}
    assert all(tool["api_schema"]["url"].startswith("https://api.example.com/tools/") for tool in tools)
