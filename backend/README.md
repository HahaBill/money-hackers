# Money Hackers backend

The backend owns deterministic financial calculations, the reasoning graph,
investigation/memory, regression scenarios, PRISM submission, and ElevenLabs
server tools. Frontend code can live at the repository root without importing
backend internals.

From the repository root:

```bash
.venv/bin/python -m pytest backend
.venv/bin/python -m pytest -c backend/pytest.ini -m regression
.venv/bin/python backend/run.py --scenario B --run-id demo_b --no-llm
.venv/bin/uvicorn --app-dir backend voice.server_tools:app --port 8090
```

Generate and analyze seeded transaction data:

```bash
PYTHONPATH=backend .venv/bin/python -m eval.generator backend/data/scenarios/b_product_mix.yaml --out /tmp/generated-b --seed 7
.venv/bin/python backend/run.py --data /tmp/generated-b --period 2026-08 --run-id generated_b --no-llm
```

To use the configured OpenAI model, add credentials to `backend/.env` and pass
`--llm`. Without `--llm`, runs are deterministic and do not make network calls.
Classifier and judgment routes are separate, but intentionally default to
`gpt-6-astra` as the product-level override to the PRD's original model names.
Add `--research --research-context context.json` to permit at most four
template-bound Tavily calls.

The Larry frontend discovers reports through `/runs`, loads the workbook shape
from `/dashboard/{run_id}`, traverses `/runs/{run_id}/graph`, and posts grounded
questions to `/chat`. Arithmetic remains in Python; the browser only renders
validated figures and source node IDs.

Larry's demo orb records in the browser, posts audio to `/voice/transcribe`,
sends the transcript through the same grounded `/chat` path, and plays the
validated answer from `/voice/speak`. These direct ElevenLabs speech endpoints
require `ELEVENLABS_API_KEY`; `ELEVENLABS_VOICE_ID` is optional. The key never
reaches the browser.

`/voice/session?run_id=...` remains available for the full ElevenLabs Agents
Platform flow. That optional flow also requires `ELEVENLABS_AGENT_ID`. Deploy or
update the agent only after the frontend proxy or FastAPI service has a public
HTTPS URL:

```bash
.venv/bin/python backend/voice/deploy_agent.py --base-url https://api.example.com
```

Generated graph, memory, finding, transcript, and PRISM files are written under
`backend/runs/` regardless of the caller's working directory.
