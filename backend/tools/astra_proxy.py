"""Local shim that lets GIDE 2.3.56 drive gpt-6-astra.

GIDE speaks Chat Completions and sends `max_tokens`, which Astra rejects with
HTTP 400 ("use `max_completion_tokens` instead"). 2.3.56 is the latest release,
so the fix has to sit between GIDE and OpenAI.

Point GIDE here:
    python tools/astra_proxy.py
    gide connect --endpoint http://127.0.0.1:8787/v1 --kind openai --model gpt-6-astra

The caller's Authorization header is forwarded untouched; this process never
reads or stores a key.
"""

import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

UPSTREAM = "https://api.openai.com"

# Astra's API default reasoning effort is `low`, which is too weak to drive an
# agent through multi-step file edits. Override unless the caller asked.
DEFAULT_EFFORT = os.environ.get("ASTRA_PROXY_EFFORT", "high")
PORT = int(os.environ.get("ASTRA_PROXY_PORT", "8787"))

# Reasoning models reject the sampling knobs older clients send by habit.
UNSUPPORTED = ("temperature", "top_p", "frequency_penalty", "presence_penalty")

app = FastAPI()
# trust_env=False: macOS/conda often inject HTTP_PROXY; OpenAI then 403s
# and GIDE's probe reports "nothing is listening".
client = httpx.AsyncClient(
    base_url=UPSTREAM,
    timeout=httpx.Timeout(900.0, connect=15.0),
    trust_env=False,
)


@app.get("/health")
async def health():
    return {"ok": True}


def adapt(body: dict) -> dict:
    if not str(body.get("model", "")).startswith("gpt-6"):
        return body
    if "max_tokens" in body:
        body["max_completion_tokens"] = body.pop("max_tokens")
    body.setdefault("reasoning_effort", DEFAULT_EFFORT)
    for key in UNSUPPORTED:
        body.pop(key, None)
    return body


@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() in ("authorization", "content-type", "openai-organization")
    }

    body = await request.body()
    if body and request.headers.get("content-type", "").startswith("application/json"):
        import json

        try:
            body = json.dumps(adapt(json.loads(body))).encode()
        except json.JSONDecodeError:
            pass

    try:
        req = client.build_request(
            request.method, f"/{path}", headers=headers, content=body or None
        )
        upstream = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        return Response(
            content=f'{{"error":{{"message":"astra_proxy upstream: {exc}"}}}}',
            status_code=502,
            media_type="application/json",
        )

    if "text/event-stream" in upstream.headers.get("content-type", ""):
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            media_type="text/event-stream",
            background=upstream.aclose,
        )

    payload = await upstream.aread()
    await upstream.aclose()
    return Response(
        content=payload,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
