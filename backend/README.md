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

The frontend can read `/runs/{run_id}`, post `/feedback`, and request
`/voice/session?run_id=...`. The last endpoint mints an ElevenLabs signed URL;
the API key remains server-side. Deploy or update the ElevenLabs agent only
after the frontend proxy or FastAPI service has a public HTTPS URL:

```bash
.venv/bin/python backend/voice/deploy_agent.py --base-url https://api.example.com
```

Generated graph, memory, finding, transcript, and PRISM files are written under
`backend/runs/` regardless of the caller's working directory.
