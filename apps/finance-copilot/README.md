# Finance Controlling Copilot — Databricks App (React + FastAPI)

AkzoNobel Agent Bricks workshop, showcase #1 (the Finance leg). A controller asks
*"Paints EMEA gross margin dropped ~8% in Q2 — is it price, volume, FX, or cost, and what
should I do?"* This app answers it two ways, both grounded in governed Unity Catalog data:

1. **Variance analysis** — pick a product line / region / from-period / to-period and the app
   computes a quantified **price / volume / FX / cost** bridge for the gross-margin-% change off
   governed numbers (`margin_actuals` + `cost_drivers` + `fx_rates`, certified `gross_margin_pct`
   rule from the metric view `akzo_finance.mv_gross_margin`). An LLM reasoning step turns the
   bridge into a controller-ready **variance narrative + one recommended action**. The UI renders a
   waterfall-style bridge, a driver table, the narrative, and the action.
2. **Ask a question** — free-text NL → governed SQL (the **Genie-space pattern**: `genie/finance_space.md`
   is the system prompt) → run on the warehouse → an LLM reasoning step writes a grounded answer.

The collapsible **"How this works"** panel shows the generated SQL, the certified metric view, and
the exact source tables used.

## Layout

```
apps/finance-copilot/
  backend/
    databricks_client.py   # SHARED: SDK singleton + run_sql() + chat() helpers
    lakebase.py            # SHARED: psycopg3 conn via generated credential, token refresh
    text2sql.py            # SHARED: genie instructions -> SQL -> execute -> {sql, rows, columns}
    agent.py               # finance workflow (ask / variance-decomposition / reasoning / save)
    main.py                # FastAPI routes + static frontend mount
    finance_space.md       # bundled copy of genie/finance_space.md (self-contained)
  frontend/                # React + Vite + TypeScript (variance + ask, waterfall bridge, trace panel)
  app.yaml                 # Databricks Apps manifest (uvicorn on $DATABRICKS_APP_PORT)
  requirements.txt
  .env.example
  run_local.sh
```

`backend/databricks_client.py`, `lakebase.py`, and `text2sql.py` are the **shared pattern** copied
from the sibling Quote agent. The only shared-module change vs. the quote-agent copy: `chat()` now
omits the `temperature` parameter unless explicitly set, because `databricks-claude-opus-4-7`
rejects that parameter.

## Run locally

```bash
cd apps/finance-copilot
cp .env.example .env            # uses CLI profile <your-profile>
./run_local.sh                  # builds frontend, installs deps, serves on :8000
```

Then open http://localhost:8000. Auth is via the Databricks CLI profile
(`DATABRICKS_CONFIG_PROFILE`). For frontend hot-reload during development run the API
(`cd backend && uvicorn main:app --port 8000`) and `cd frontend && npm run dev` (Vite proxies
`/api` to :8000).

### API

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET  | `/api/health` | — | identity check |
| POST | `/api/ask` | `{question}` | text2SQL → run → grounded answer; returns `{sql, rows, columns, answer, trace}` |
| POST | `/api/variance` | `{product_line, region, from_period, to_period}` | quantified price/volume/FX/cost bridge + narrative + recommended action + the SQL |
| POST | `/api/save` | `{kind, title, summary, payload, product_line?, region?, from_period?, to_period?, question?}` | save an analysis to Lakebase `akzo.saved_analyses` |
| GET  | `/api/saved` | — | list saved analyses |

Periods are `2026-Q1 .. 2026-Q4`.

## Deploy to Databricks Apps

In Apps, the app service principal provides SDK auth automatically (no profile). Build the
frontend first so `frontend/dist` is bundled, then sync + deploy:

```bash
cd apps/finance-copilot/frontend && npm install && npm run build
cd ..
databricks sync . /Workspace/Users/<you>/finance-copilot --profile <your-profile>
databricks apps deploy finance-copilot --source-code-path /Workspace/Users/<you>/finance-copilot --profile <your-profile>
```

`app.yaml` runs `uvicorn main:app --app-dir backend` on `$DATABRICKS_APP_PORT` and sets the
warehouse / chat endpoint / Lakebase env. The app service principal needs: `CAN USE` on warehouse
`<your-warehouse-id>`, `CAN QUERY` on `databricks-claude-opus-4-7`, SELECT on
`<catalog>.akzo_finance.*`, and a Postgres role on the `<your-lakebase-instance>`
Lakebase instance for the `akzo` schema.

## Verified

End-to-end against the live workspace (profile `<your-profile>`):

- **`/api/variance`** for `{Decorative Paints, EMEA, 2026-Q1 → 2026-Q2}` returned the certified
  bridge: gross margin **39.6% → 30.7% = −8.9pp**, decomposed as **cost −3.8pp** (raw-material/unit
  €11.47 → €13.37, +16.6%), **price −3.3pp** (realized price/unit €34.54 → €32.73, −5.2%), **FX
  −1.8pp** (USD `rate_to_eur` 0.9289 → 0.8880, −4.4%), **volume ~flat 0.0pp** (57,980 → 57,602
  units). The four legs sum exactly to −8.9pp. Recommended action: convene procurement + treasury
  to lock Q3 raw-material volumes and layer USD/EUR forward hedges before Q3 pricing.
- **`/api/ask`** with *"Why did Paints EMEA gross margin drop in Q2 2026?"* generated governed SQL
  over `margin_actuals` + `cost_drivers` and returned a grounded answer: 39.6% → 30.7% (−8.9pp) on
  flat volume, price erosion −5.2% and raw-material inflation +16.6% as the two dominant drivers.
- **`/api/save`** wrote analysis **#1** to Lakebase `akzo.saved_analyses` under
  `finance-copilot@service` and `/api/saved` reads it back.
