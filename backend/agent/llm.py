"""OpenAI Responses API. Astra rejects max_tokens; never send it."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from dotenv import load_dotenv
from prism_setup import emit_trace

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
CLASSIFIER_MODEL = os.environ.get("OPENAI_CLASSIFIER_MODEL", DEFAULT_MODEL)
JUDGMENT_MODEL = os.environ.get("OPENAI_JUDGMENT_MODEL", DEFAULT_MODEL)
Route = Literal["classifier", "judgment"]


def model_for(route: Route) -> str:
    return CLASSIFIER_MODEL if route == "classifier" else JUDGMENT_MODEL


def _client():
    from openai import OpenAI

    return OpenAI()


def available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def complete(
    prompt: str,
    *,
    model: str | None = None,
    route: Route = "judgment",
    effort: str = "medium",
    session_id: str | None = None,
) -> str:
    selected_model = model or model_for(route)
    started = perf_counter()
    try:
        response = _client().responses.create(
            model=selected_model,
            input=prompt,
            reasoning={"effort": effort},
        )
    except Exception as exc:
        emit_trace(
            model=selected_model,
            input_messages=[{"role": "user", "content": prompt}],
            output_message="",
            latency_ms=int((perf_counter() - started) * 1000),
            session_id=session_id,
            status="error",
            metadata={
                "route": route,
                "reasoning_effort": effort,
                "error_type": type(exc).__name__,
            },
        )
        raise
    usage = getattr(response, "usage", None)
    output = response.output_text
    emit_trace(
        model=selected_model,
        input_messages=[{"role": "user", "content": prompt}],
        output_message=output,
        latency_ms=int((perf_counter() - started) * 1000),
        session_id=session_id,
        token_count_input=getattr(usage, "input_tokens", 0) or 0,
        token_count_output=getattr(usage, "output_tokens", 0) or 0,
        metadata={"route": route, "reasoning_effort": effort},
    )
    return output


def complete_json(
    prompt: str,
    *,
    model: str | None = None,
    route: Route = "judgment",
    effort: str = "low",
) -> Any:
    text = complete(
        prompt + "\n\nReply with a single JSON object or array. No markdown.",
        model=model,
        route=route,
        effort=effort,
    )
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)
