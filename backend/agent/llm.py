"""OpenAI Responses API. Astra rejects max_tokens; never send it."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

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
) -> str:
    response = _client().responses.create(
        model=model or model_for(route),
        input=prompt,
        reasoning={"effort": effort},
    )
    return response.output_text


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
