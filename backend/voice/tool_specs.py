"""ElevenLabs standalone webhook-tool definitions."""

from __future__ import annotations


def _params(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


RUN_ID = {
    "type": "string",
    "description": "The run_id dynamic variable. Copy it exactly; never invent one.",
}


def webhook_tools(base_url: str) -> list[dict]:
    base = base_url.rstrip("/")
    read_tools = [
        ("get_briefing", "Read the pre-rendered validated briefing and get valid finding ids for this run."),
        ("get_recommendations", "Read ranked pre-rendered recommendations and their assumptions."),
        ("get_verify_items", "Read pre-rendered items the owner should verify."),
        ("get_questions", "Get unresolved owner questions and their allowed answer options."),
        ("get_revisions", "Read what the analyst revised since the prior period."),
    ]
    tools = []
    for name, description in read_tools:
        tools.append(
            {
                "type": "webhook",
                "name": name,
                "description": description + " Speak returned text verbatim when it contains figures.",
                "api_schema": {
                    "url": f"{base}/tools/{name}",
                    "method": "GET",
                    "query_params_schema": _params({"run_id": RUN_ID}, ["run_id"]),
                },
                "response_timeout_secs": 10,
                "interruption_mode": "allow",
            }
        )
    tools.append(
        {
            "type": "webhook",
            "name": "get_finding",
            "description": "Read the validated walkthrough for one finding. Speak returned text verbatim.",
            "api_schema": {
                "url": f"{base}/tools/get_finding",
                "method": "GET",
                "query_params_schema": _params(
                    {
                        "run_id": RUN_ID,
                        "finding_id": {"type": "string", "description": "A finding id returned by get_briefing."},
                    },
                    ["run_id", "finding_id"],
                ),
            },
            "response_timeout_secs": 10,
            "interruption_mode": "allow",
        }
    )
    tools.append(
        {
            "type": "webhook",
            "name": "record_answer",
            "description": "Store one allowed answer to an open owner question.",
            "api_schema": {
                "url": f"{base}/tools/record_answer",
                "method": "POST",
                "request_body_schema": _params(
                    {
                        "run_id": RUN_ID,
                        "question_id": {"type": "string", "description": "Question id from get_questions."},
                        "option": {"type": "string", "description": "One exact allowed option from get_questions."},
                    },
                    ["run_id", "question_id", "option"],
                ),
            },
            "response_timeout_secs": 10,
            "interruption_mode": "disable_during_tool",
        }
    )
    return tools
