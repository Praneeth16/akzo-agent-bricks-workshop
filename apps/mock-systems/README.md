# Mock External Systems (`akzo-mock-systems`)

A small FastAPI app that simulates the external systems the AkzoNobel agents act
on — **the governed external target for the Action Plane**. No real email/PO/ticket is ever sent; every call lands an auditable
receipt in Lakebase `akzo.external_system_log`.

## Endpoints

| Method | Path | JSON payload |
|---|---|---|
| POST | `/email` | `to, subject, body` |
| POST | `/teams` | `channel, message` |
| POST | `/crm/task` | `account, task, due` |
| POST | `/erp/po` | `supplier, sku, qty, amount_eur` |
| POST | `/sharepoint/upload` | `path, title` |
| POST | `/servicenow/ticket` | `summary, priority` |
| GET | `/api/health` | liveness + service-principal identity |
| GET | `/api/log` | recent `external_system_log` rows (`?limit=`, `?system=`) |
| GET | `/` | HTML status page listing the endpoints |

Each POST returns `{ref_id, status, echo}` with a human-readable `ref_id`
(`EMAIL-0001`, `PO-0001`, `SNOW-0001`, ...) derived from the inserted row's identity.

## Data

`akzo.external_system_log` (created on first call):

```
id bigint identity PK · ts timestamptz · system text · ref_id text
request jsonb · created_by text
```

## How it is called

- **Governed path (preferred):** through the UC HTTP connection
  `akzo_external_systems` (see `L200-capabilities/02_agents_that_act.py`) so every
  external call is catalog-governed and logged.
- **Fallback:** the app's connectors call the deployed URL directly under the app
  service principal — still authenticated and still logged in
  `external_system_log` + the Action Plane.

## Run locally

```bash
cd apps/mock-systems/backend
DATABRICKS_CONFIG_PROFILE=<your-profile> uvicorn main:app --reload --port 8000
```

## Deploy

Use `deploy/deploy_mock_systems.sh` (create → grant SP UC + warehouse + Lakebase
Postgres role with DML+CREATE on schema `akzo` → sync → deploy → wait
ACTIVE/SUCCEEDED). The recipe mirrors `deploy/deploy_apps.sh`.
