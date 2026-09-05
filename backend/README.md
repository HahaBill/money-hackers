# Money Hackers backend

The backend owns deterministic financial calculations, the reasoning graph,
investigation/memory, regression scenarios, PRISM submission, and ElevenLabs
server tools. Frontend code can live at the repository root without importing
backend internals.

From the repository root:

```bash
.venv/bin/python -m pytest backend
.venv/bin/python backend/run.py --scenario B --run-id demo_b --no-llm
.venv/bin/uvicorn --app-dir backend voice.server_tools:app --port 8090
```

To use the configured OpenAI model, add credentials to `backend/.env` and pass
`--llm`. Without `--llm`, runs are deterministic and do not make network calls.

Generated graph, memory, finding, transcript, and PRISM files are written under
`backend/runs/` regardless of the caller's working directory.
