# Deploy + Smoke Test Results — AkzoNobel Agent Bricks Apps

**Workspace:** `<your-workspace-host>` (AWS) · profile `<your-profile>`
**Deployed:** 2026-06-26 · **Deployer:** <you@example.com>
**Deploy host:** `<deploy-host>.aws.databricksapps.com`

All three apps are **live, ACTIVE, and SUCCEEDED**, and every read / reason / write
path was exercised against the deployed URL (not just locally). Bottom line: **all green**.

| App | URL | Compute | Deployment | Smoke result |
|---|---|---|---|---|
| **akzo-quote-agent** | https://akzo-quote-agent-<deploy-host>.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — full parse→price→quote→approve incl. Lakebase write |
| **akzo-supervisor** | https://akzo-supervisor-<deploy-host>.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — route→fuse + session/feedback Lakebase writes |
| **akzo-finance-copilot** | https://akzo-finance-copilot-<deploy-host>.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — ask (text2sql)→variance→save→read-back |

> The apps require workspace SSO, so a raw browser `curl` redirects to login. Smoke
> tests below were run by attaching the deployer's OAuth bearer token
> (`databricks auth token -p <your-profile>`) to each request — this is a
> real authenticated round-trip through the app's HTTP surface to the FastAPI backend,
> which then acts under the **app's own service principal** (confirmed: `/api/health`
> reports the SP client_id, not the caller).

---

## Service principals + grants applied

Each app got its own service principal at create time. Grants use the **SP client_id**
(application id) for Unity Catalog, the SQL warehouse, and Lakebase, because that is
exactly the identity `WorkspaceClient().current_user.me().user_name` returns inside a
Databricks App (verified live: each `/api/health` echoes its own client_id).

| App | SP client_id | SP numeric id |
|---|---|---|
| akzo-quote-agent | `60954750-0c12-45eb-8bc4-493590827090` | `75273100893336` |
| akzo-supervisor | `80fff31e-d3f0-470c-92f5-0d10285cbcc7` | `75936088236097` |
| akzo-finance-copilot | `bcae9d4c-d8e5-4308-87cf-26c88ca7e116` | `77178490908661` |

**Grants applied to all three SPs (idempotent):**

1. **Unity Catalog** (via SQL statement-execution on warehouse `<your-warehouse-id>`) — all SUCCEEDED:
   - `GRANT USE CATALOG ON CATALOG <catalog>`
   - `GRANT USE SCHEMA` + `GRANT SELECT ON SCHEMA` for: `akzo_finance`, `akzo_scm`,
     `akzo_commercial`, `akzo_docs`, `akzo_ops`, `akzo_gateway`
2. **SQL warehouse `<your-warehouse-id>`** — `CAN_USE` via
   `PATCH /api/2.0/permissions/warehouses/...` (additive). Confirmed live: governed
   `ai_extract` / `text2sql` queries run on the warehouse under each SP.
3. **Serving endpoint `databricks-claude-opus-4-8`** — see "Known item" below; no
   explicit grant needed (FM API). Confirmed live: each app's LLM narrative / ai_query
   calls succeed under its SP.
4. **Lakebase `<your-lakebase-instance>`** (Postgres, db `databricks_postgres`, schema `akzo`):
   - Registered each SP as a Postgres role via
     `POST /api/2.0/database/instances/<your-lakebase-instance>/roles`
     (`identity_type: SERVICE_PRINCIPAL`, role name = SP client_id).
   - Connected to Postgres as the instance superuser (`<you@example.com>`,
     `DATABRICKS_SUPERUSER`) and granted each role on schema `akzo`:
     `USAGE, CREATE`, `SELECT/INSERT/UPDATE/DELETE ON ALL TABLES`,
     `USAGE, SELECT ON ALL SEQUENCES`, plus matching `ALTER DEFAULT PRIVILEGES`.
   - `CREATE` is required because the apps bootstrap their write tables with
     `CREATE TABLE IF NOT EXISTS` on first write (Postgres evaluates the privilege even
     when the table already exists).

`akzo` write-back tables present and writable: `quotes`, `quote_approvals`,
`agent_sessions`, `agent_feedback`, `saved_analyses`, `forecast_overrides`,
`scm_interventions`, `commercial_actions`.

---

## Per-app smoke detail

### akzo-quote-agent — read → reason → act → write → approve
- `GET /api/health` → **200** `{"status":"ok","identity":"60954750-..."}` (runs as its SP)
- `POST /api/parse` → **200** — `ai_extract` on the warehouse parsed the EMEA RFQ and
  matched product → **SKU DEC-1008** (Textured Exterior Coating, list €38.52 / cost €22.82).
- `POST /api/price` → **200** — governed UC reads: unit margin €15.70 (40.8%), recent
  realized margin 28.0% from `akzo_finance`.
- `POST /api/quote` → **200** — drafted 5,000 units @ 10% discount (net €34.67, margin
  34.2%, total margin €59,250, no guardrail flags) and **wrote `quote_id 4` to Lakebase
  `akzo.quotes` (status `pending`)**.
- `POST /api/approvals/4` → **200** — flipped `pending → approved` with audit trail
  (`approver`, `decided_at`) in `akzo.quotes` + `akzo.quote_approvals`. **Lakebase write confirmed.**
- `GET /` → **200**, serves the built React SPA (`<div id="root">`).

### akzo-supervisor — multi-domain route → fuse
- `GET /api/health` → **200**, identity = SP, personas `[controller, emea_planner, rep]`.
- `POST /api/ask` → **200** — routed a cross-domain question to **FINANCE + SCM** legs and
  returned a fused answer (margin bridge + supply risk), with `session_id`/`session_uuid`
  persisted to `akzo.agent_sessions`. **Lakebase write confirmed.**
- `POST /api/feedback` → **200** — wrote `feedback_id 2` to `akzo.agent_feedback`
  (rating +1). **Second Lakebase write path confirmed.**
- `GET /` → **200**, React SPA served.

### akzo-finance-copilot — variance copilot
- `GET /api/health` → **200**, identity = SP.
- `POST /api/ask` → **200** — text2sql over governed UC returned 6 rows (EMEA Decorative
  Paints 2026 monthly revenue/margin) plus an LLM narrative.
- `POST /api/variance` → **200** — quarter-over-quarter bridge `2026-Q1 → 2026-Q2`
  (periods/bridge/narrative/recommended_action). Note: periods are **quarter-formatted**
  (`2026-Q1`), not month — a month string returns a clear 4xx, this is expected input
  validation, not a bug.
- `POST /api/save` → **200** — wrote `analysis_id 2` to Lakebase `akzo.saved_analyses`
  (`created_by = finance-copilot@service`). **Lakebase write confirmed.**
- `GET /api/saved` → **200** — read back 2 analyses incl. the just-written row.
- `GET /` → **200**, React SPA served.

---

## Issues found and fixed during deploy

1. **`'WorkspaceClient' object has no attribute 'database'` (Lakebase writes broke).**
   The Databricks Apps build image pre-installs `databricks-sdk==0.33.0`, and the original
   `requirements.txt` pinned only `databricks-sdk>=0.30`, so pip kept 0.33.0 — which
   predates `WorkspaceClient.database` (the Lakebase API). Read/reason paths worked, but
   every Lakebase write 500'd.
   **Fix:** bumped all three `requirements.txt` to `databricks-sdk>=0.96` and redeployed;
   the build now upgrades to `0.119.0` and all write paths pass. (Committed in repo.)

2. **`permission denied for schema akzo` on first write.**
   The apps run `CREATE TABLE IF NOT EXISTS akzo.<table>` before inserting; the SP roles
   initially had DML but not `CREATE` on the schema, so the statement was rejected even
   though the table already existed.
   **Fix:** granted `CREATE ON SCHEMA akzo` to all three SP roles. All write paths pass.

3. **`frontend/dist/` excluded by `.gitignore`.**
   `databricks sync` honors `.gitignore`, which excludes `frontend/dist/` — but FastAPI
   serves that directory as the static frontend, so a plain sync would deploy a backend
   with no UI.
   **Fix:** sync with `--include "frontend/dist/**" --exclude "frontend/node_modules/**"`.
   Verified `dist/index.html` + `dist/assets/*` landed in the workspace and `GET /` returns
   the SPA. (`dist/` is prebuilt and committed; node_modules was 64 MB/app and correctly excluded.)

---

## Known items / remediation notes

- **Serving endpoint `databricks-claude-opus-4-8` is a `FOUNDATION_MODEL_API`
  (pay-per-token).** It has no per-endpoint numeric id, so the per-SP `CAN_QUERY`
  permissions API rejects it (`'databricks-claude-opus-4-8' is not a valid Inference
  Endpoint ID`). FM API endpoints are queryable by all workspace principals by default,
  and live smoke tests confirm each app SP can call it (all LLM narratives / `ai_query`
  succeeded). **No action required.** If the workspace ever locks down FM API access,
  grant `CAN_QUERY` via the Serving UI or the AI Gateway (not the CLI).

- **No remaining gaps.** Every Lakebase write that the prompt flagged as a risk
  (quote-agent quotes/approvals, supervisor sessions/feedback, finance-copilot
  saved_analyses) was exercised live and **succeeded under the app service principal.**
  The remediation that would otherwise be needed — adding each SP as a Postgres role on
  `<your-lakebase-instance>` and granting it `USAGE/CREATE/DML` on schema `akzo` — has already been
  applied (see grants above) and is captured idempotently in `deploy/deploy_apps.sh`.

- **Token-expiry resilience:** `lakebase.py` caches the ~1h DB credential and transparently
  refreshes on `OperationalError`, so long-lived app sessions keep writing without restart.

## Re-running

`deploy/deploy_apps.sh` captures every command above, idempotently:
```bash
cd /Users/praneeth.paikray/Documents/Code/agent-bricks-workshop
./deploy/deploy_apps.sh
```
It skips `apps create` when the app exists, re-applies grants (no-ops if held), re-syncs
source (incl. dist), redeploys, waits for SUCCEEDED, and re-checks `/api/health`.
