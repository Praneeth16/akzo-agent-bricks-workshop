# Pricing & Quote Agent — Databricks App (React + FastAPI)

AkzoNobel Agent Bricks workshop, showcase #2. The densest single agent demo: it
**reads → reasons → acts → writes → approves** end to end.

1. **Parse** an inbound RFQ with `ai_extract` (governed, on the SQL warehouse) and
   resolve the free-text product to a real `products` SKU.
2. **Price** it: list price + standard cost from `akzo_finance.products`, recent
   realized margin from `akzo_finance.margin_actuals` (governed Unity Catalog reads).
3. **Draft** a quote — line items, discount, total, post-discount margin — and run a
   **guardrail** (flags discount > 15% or margin < 25%).
4. **Write** the quote to **Lakebase** (`akzo.quotes`, status `pending`) plus a
   `akzo.quote_approvals` ledger row, under the app/service write identity.
5. **Approve** — a human flips the row `pending → approved/rejected` with a full audit
   trail (`approver`, `decided_at`).

The collapsible **"How this works"** panel shows the generated SQL, data sources, and
the exact Lakebase writes for every step.

## Layout

```
apps/quote-agent/
  backend/
    databricks_client.py   # SHARED: SDK singleton + run_sql() + chat() helpers
    lakebase.py            # SHARED: psycopg3 conn via generated credential, token refresh
    text2sql.py            # SHARED: genie instructions -> SQL -> execute -> {sql, rows, columns}
    agent.py               # quote workflow (parse/price/draft/write/approve)
    main.py                # FastAPI routes + static frontend mount
    finance_space.md       # bundled copy of genie/finance_space.md (self-contained)
  frontend/                # React + Vite + TypeScript single-page flow
  app.yaml                 # Databricks Apps manifest (uvicorn on $DATABRICKS_APP_PORT)
  requirements.txt
  .env.example
  run_local.sh
```

`backend/databricks_client.py`, `lakebase.py`, and `text2sql.py` are domain-agnostic and
are the **shared pattern** copied by the sibling Supervisor and Finance apps.

## Run locally

```bash
cd apps/quote-agent
cp .env.example .env            # uses CLI profile <your-profile>
./run_local.sh                  # builds frontend, installs deps, serves on :8000
```

Then open http://localhost:8000. Auth is via the Databricks CLI profile
(`DATABRICKS_CONFIG_PROFILE`). For frontend hot-reload during development run the API
(`cd backend && uvicorn main:app --port 8000`) and `cd frontend && npm run dev` (Vite
proxies `/api` to :8000).

### API

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET  | `/api/health` | — | identity check |
| POST | `/api/parse` | `{rfq_text}` | ai_extract + SKU match |
| POST | `/api/price` | `{sku, region?}` | governed price/cost/margin lookup |
| POST | `/api/quote` | `{account_id, sku, region?, quantity_units, list_price_eur, standard_cost_eur, discount_pct}` | draft + guardrail + Lakebase write |
| GET  | `/api/approvals?status=pending` | — | list staged quotes |
| POST | `/api/approvals/{quote_id}` | `{decision, approver, comment?}` | approve/reject |

## Deploy to Databricks Apps

In Apps, the app service principal provides SDK auth automatically (no profile). Build
the frontend first so `frontend/dist` is bundled, then sync + deploy:

```bash
cd apps/quote-agent/frontend && npm install && npm run build
cd ..
databricks sync . /Workspace/Users/<you>/quote-agent --profile <your-profile>
databricks apps deploy quote-agent --source-code-path /Workspace/Users/<you>/quote-agent --profile <your-profile>
```

`app.yaml` runs `uvicorn main:app --app-dir backend` on `$DATABRICKS_APP_PORT` and sets
the warehouse / chat endpoint / Lakebase env. The app service principal needs: `CAN USE`
on warehouse `<your-warehouse-id>`, `CAN QUERY` on `databricks-claude-opus-4-7`, SELECT on
`<catalog>.akzo_finance.*`, and a Postgres role on the
`<your-lakebase-instance>` Lakebase instance for the `akzo` schema.

## Verified

End-to-end against the live workspace (profile `<your-profile>`): parsed the
sample EMEA RFQ → matched **DEC-1008 Textured Exterior Coating** (list €38.52, cost
€22.82) → drafted 5,000 units @ 10% discount (net €34.67, margin 34.2%, total margin
€59,250) → wrote **quote_id 2** to Lakebase `akzo.quotes` (status `pending`) →
approved it (status flipped to `approved`, `controller@akzo.example` + `decided_at`
stamped in `akzo.quote_approvals`). Guardrail path verified: a 25% discount quote was
flagged (margin 21% < 25% floor) and staged for escalation.
