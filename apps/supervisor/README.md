# Multi-domain Supervisor Agent — Databricks App (React + FastAPI)

AkzoNobel Agent Bricks workshop, the **flagship** showcase. One chat that, given a
cross-domain question, **routes** to the right domain subagents (Finance / SCM / Commercial),
calls each governed Genie space, and **fuses one answer** with a visible routing trace and a
recommended action.

This is a faithful, self-contained reproduction of an **Agent Bricks Multi-Agent Supervisor
(MAS)**. A real MAS endpoint (`mas-f14da7dc-endpoint`) already exists in this workspace as a
reference — see the upgrade path below.

## The loop

1. **Route** — one LLM call reads the question + the per-subagent `ROUTING_DESCRIPTION` lines
   and decides which domains to consult and why. For each chosen domain it also produces a
   subquestion phrased in that domain's own terms (so a domain's Genie space does not decline a
   cross-domain question as out of scope).
2. **Call legs** — each chosen domain runs the shared `text2sql` round trip pointed at its own
   `genie/<domain>_space.md` → NL → governed Spark SQL → rows. Under Databricks Apps the SQL runs
   under the caller's identity (OBO), so per-user UC row filters apply (reads only).
3. **Fuse** — a final LLM call takes the legs' structured rows (not free text) and fuses ONE
   governed answer that explicitly connects the domains, plus ONE recommended action.
4. **Persist** — the turn is logged to Lakebase `akzo.agent_sessions`; thumbs up/down feedback
   writes to `akzo.agent_feedback`.

## The flagship question

> *"Paints EMEA gross margin dropped ~8% in Q2 — is it price, volume, or a supply/service issue,
> and what should I do?"*

The right answer is **not** single-cause. The supervisor routes to **Finance + SCM + Commercial**
and fuses: Finance margin bridge (39.6% → 30.7%, ~8.9pt; price erosion −€1.81/unit + raw-material
+€1.90/unit, volume flat), the SCM Rotterdam-NL→EMEA-DACH OTIF collapse (~88.9% in May, service
90.6%, 2,258 backorder units, DEC-1000/DEC-1004 stockouts), and the Commercial churn fallout (3
EMEA accounts churn_score > 0.7, ~€413k Q2 revenue drop) — concluding it is **both** a cost/price
issue **and** a supply/service issue, with a concrete cross-domain action.

## Layout

```
apps/supervisor/
  backend/
    databricks_client.py   # SHARED: SDK singleton + run_sql() + chat()
    lakebase.py            # SHARED: psycopg3 conn via generated credential, token refresh
    text2sql.py            # SHARED: genie instructions -> SQL -> execute -> {sql, rows, columns}
    agent.py               # the supervisor: route -> call legs -> fuse + Lakebase persistence
    main.py                # FastAPI routes + static frontend mount
    finance_space.md       # bundled copy of genie/finance_space.md (self-contained)
    scm_space.md           # bundled copy of genie/scm_space.md
    commercial_space.md    # bundled copy of genie/commercial_space.md
  frontend/                # React + Vite + TypeScript single chat interface
  app.yaml                 # Databricks Apps manifest (uvicorn on $DATABRICKS_APP_PORT)
  requirements.txt
  .env.example
  run_local.sh
```

`databricks_client.py`, `lakebase.py`, and `text2sql.py` are the shared pattern, copied verbatim
from the sibling `quote-agent` app (with one shared fix: `chat()` omits the `temperature`
parameter, which `databricks-claude-opus-4-7` rejects).

## Run locally

```bash
cd apps/supervisor
cp .env.example .env            # uses CLI profile fe-vm-lakebase-praneeth
./run_local.sh                  # builds frontend, installs deps, serves on :8000
```

Then open http://localhost:8000. Auth is via the Databricks CLI profile
(`DATABRICKS_CONFIG_PROFILE`). For frontend hot-reload during development run the API
(`cd backend && uvicorn main:app --port 8000`) and `cd frontend && npm run dev` (Vite proxies
`/api` to :8000).

### API

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET  | `/api/health` | — | identity + persona list |
| POST | `/api/ask` | `{question, persona?}` | route → call legs → fuse; returns `{routing, legs, answer, recommended_action, session_id, session_uuid, persona_scope}`; logs to `akzo.agent_sessions` |
| POST | `/api/feedback` | `{session_uuid, rating, note?}` | thumbs up/down (+ note) → `akzo.agent_feedback` |

`persona` is one of `controller` / `emea_planner` / `rep`. It sets the **governed data scope** the
trace notes — under OBO at the Genie-call layer (reads only), the same routing runs but each leg's
SQL executes under the caller's identity, so a UC row filter narrows what the persona actually
sees (a controller sees all regions; an EMEA planner sees EMEA only).

## Deploy to Databricks Apps

In Apps the app service principal provides SDK auth automatically (no profile). Build the frontend
first so `frontend/dist` is bundled, then sync + deploy:

```bash
cd apps/supervisor/frontend && npm install && npm run build
cd ..
databricks sync . /Workspace/Users/<you>/supervisor --profile fe-vm-lakebase-praneeth
databricks apps deploy supervisor --source-code-path /Workspace/Users/<you>/supervisor --profile fe-vm-lakebase-praneeth
```

`app.yaml` runs `uvicorn main:app --app-dir backend` on `$DATABRICKS_APP_PORT` and sets the
warehouse / chat endpoint / Lakebase env. The app service principal needs: `CAN USE` on warehouse
`4d39ac2e32b72a3a`, `CAN QUERY` on `databricks-claude-opus-4-7`, SELECT on
`serverless_lakebase_praneeth_catalog.akzo_finance.*`, `.akzo_scm.*`, and `.akzo_commercial.*`,
and a Postgres role on the `graphrag-spike` Lakebase instance for the `akzo` schema.

## Upgrade path: this router → a native Agent Bricks Multi-Agent Supervisor

This app reproduces a MAS in code. To move to the managed product:

1. **Register each Genie space as a subagent** of a Multi-Agent Supervisor (Agent Bricks UI / SDK),
   pasting the same `genie/*_space.md` instructions. The per-subagent **description** field is
   exactly the `ROUTING_DESCRIPTION` lines in `agent.py` — edit one and routing changes.
2. The MAS does the route → call → fuse loop for you, **with OBO and tracing built in** — no
   router/fuser code to maintain.
3. Call the deployed MAS endpoint with the `agent/v1/responses` task. A reference MAS endpoint
   already lives in this workspace: **`mas-f14da7dc-endpoint`** (state READY). Point the backend at
   it by swapping `agent.ask()` for a single `serving_endpoints.query(name="mas-f14da7dc-endpoint", ...)`
   call once your own MAS is registered over the three Akzo Genie spaces.

## Verified

End-to-end against the live workspace (profile `fe-vm-lakebase-praneeth`): the flagship question
routed to **Finance + SCM + Commercial**; each leg returned real governed rows — Finance margin
**39.6% → 30.7%** (price €34.54 → €32.73, raw material €11.47 → €13.37, volume flat), SCM Rotterdam
lane **OTIF 88.9% in May** with service 90.6% / 2,258 backorders / DEC-1000+DEC-1004 stockouts, and
Commercial 3 at-risk EMEA accounts (churn 0.80–0.87, ~€413k Q2 revenue drop). The fused answer
correctly concluded **cost + service (not volume)** with a concrete action. The turn wrote
**session #5** to `akzo.agent_sessions` and a thumbs-up wrote **feedback #1** to
`akzo.agent_feedback`.
