# Action Center (U6)

The exec's single screen for **"agents act, governed."** A React + FastAPI Databricks
App that is a thin read/act layer over the shared **Action Plane**
(`apps/_shared/action_plane`): the cross-agent action queue, the Action Maturity
Ladder counts, the per-action audit lineage + guardrail verdict, and the
approve / reject / execute controls.

## What it shows

- **LadderMeter** — L1 Recommend → L2 Stage & approve → L3 Execute → L4 Autonomous,
  with live counts per level (click a step to filter the queue to that level).
- **Action queue** — a dense, sortable DataTable of every action across all agents
  (status badge, agent, type, subject, level, region, created), filterable by
  status and level.
- **Detail panel** — click a row for the full story: **GuardrailChips** (the live
  policy verdict from `evaluate`), the external effect (connector refs + the
  `external_ref` returned by email/PO/etc.), a vertical **Timeline** of
  `action_events` (the audit lineage), the action payload, and the
  approve / reject / execute controls (2-step confirm; the guardrail verdict is
  shown before execute).

## Backend

FastAPI under `backend/`. The Action Plane package + the shared
`databricks_client.py` / `lakebase.py` are **bundled into `backend/`** so the app is
self-contained for deployment (no `sys.path` juggling).

Routes:

| Route | Purpose |
|---|---|
| `GET /api/health` | identity + liveness |
| `GET /api/ladder` | counts per level/status → LadderMeter |
| `GET /api/actions?status=&level=&agent=` | the filtered queue |
| `GET /api/actions/{id}` | row + `events` + live guardrail verdict |
| `POST /api/actions/{id}/approve` | `{approver}` → approved |
| `POST /api/actions/{id}/reject` | `{approver, reason}` → rejected |
| `POST /api/actions/{id}/execute` | run the L3 executor → executed / failed / escalated |

## Run locally

```bash
cp .env.example .env          # uses CLI profile <your-profile>
./run_local.sh                # builds the frontend, serves API + static on :8000
```

Or for frontend dev with hot reload:

```bash
# terminal 1 — backend
cd backend && DATABRICKS_CONFIG_PROFILE=<your-profile> \
  python3 -m uvicorn main:app --reload --port 8000
# terminal 2 — frontend (proxies /api → :8000)
cd frontend && npm install && npm run dev
```

## Deploy

Deployed as a Databricks App (see `app.yaml`). The app service principal auths the
SDK automatically; it needs the Lakebase `akzo` schema roles + the
`akzo_external_systems` UC HTTP connection grant (see `deploy/` in repo root).
Deployment is the central step **U10** — do not deploy from here.
