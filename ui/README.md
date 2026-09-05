# Larry desktop UI

Larry is a desktop-first SvelteKit workbook UI. The main view behaves like a
familiar spreadsheet, while the floating Larry panel answers from validated
backend data and highlights the cited workbook rows.

From the repository root, start the backend:

```bash
.venv/bin/uvicorn --app-dir backend voice.server_tools:app --port 8090
```

Then start the frontend:

```bash
cd ui
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8090`. Set `PUBLIC_API_BASE_URL` only
when the API is hosted elsewhere. OpenAI, ElevenLabs, and PRISM credentials are
server-side variables in `backend/.env`; never expose them through `PUBLIC_*`
variables or frontend source.

The Talk orb records a short audio clip, transcribes it through the backend,
submits the transcript to Larry chat, and speaks the validated reply. The demo
uses `CoffeeshopFinancials.csv` as its tracked mock workbook source.
