# Deploy + Smoke Test Results — "Agents That Act" (U10)

**Workspace:** `fevm-serverless-lakebase-praneeth` (AWS) · profile `fe-vm-lakebase-praneeth`
**Deployed:** 2026-06-27 · **Deployer:** praneeth.paikray@databricks.com
**Deploy host:** `7474654904882204.aws.databricksapps.com`
**Driver script:** `deploy/deploy_action_apps.sh` (idempotent, re-runnable)

The "Agents That Act" expansion is **live and all-green**. The new Action Center app,
the 3 deepened domain apps, the redeployed mock-systems app, and the autonomous Job are
all deployed; the L1→L4 action ladder is exercisable end-to-end against the live URLs,
including a fresh L3 execute that lands a real `external_system_log` receipt through the
governed UC HTTP connection.

| App | URL | Compute | Deployment | Smoke |
|---|---|---|---|---|
| **akzo-action-center** (NEW) | https://akzo-action-center-7474654904882204.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — health/ladder/actions + SoD guard + serves SPA |
| **akzo-supervisor** | https://akzo-supervisor-7474654904882204.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — health + `/api/act` stages a cross-agent action |
| **akzo-finance-copilot** | https://akzo-finance-copilot-7474654904882204.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — health + own action queue |
| **akzo-quote-agent** | https://akzo-quote-agent-7474654904882204.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — health + own action queue (8) |
| **akzo-mock-systems** | https://akzo-mock-systems-7474654904882204.aws.databricksapps.com | ACTIVE | SUCCEEDED | GREEN — health + receives governed calls, lands receipts |

**Autonomous Job:** `akzo-autonomous-scm` · **job_id `957865596190448`** · **PAUSED** ·
serverless (no cluster) · cron `0 0 * * * ?` Europe/Amsterdam · notebook
`/Workspace/Users/praneeth.paikray@databricks.com/akzo-apps/notebooks/10_autonomous_closed_loop`
(synced + recognized as a PYTHON notebook). Safe — paused; never auto-runs.

> Databricks Apps require workspace SSO, so a raw browser hit 302-redirects to login.
> Every smoke call below attached the deployer's OAuth bearer token
> (`databricks auth token -p fe-vm-lakebase-praneeth`) — a real authenticated round-trip
> through each app's HTTP surface to its FastAPI backend, which then acts under the
> **app's own service principal** (each `/api/health` echoes its SP client_id, not the caller).

---

## Service principals + grants applied

Each app runs as its own service principal. Grants use the **SP client_id** (application id)
for Unity Catalog, the SQL warehouse, the UC HTTP connection, and Lakebase — exactly the
identity `WorkspaceClient().current_user.me().user_name` returns inside a Databricks App
(verified live: each `/api/health` echoes its own client_id).

| App | SP client_id | SP numeric id |
|---|---|---|
| akzo-action-center | `0b196b6e-292d-462c-9cb3-807d2848089c` | `74130439864527` |
| akzo-supervisor | `80fff31e-d3f0-470c-92f5-0d10285cbcc7` | `75936088236097` |
| akzo-finance-copilot | `bcae9d4c-d8e5-4308-87cf-26c88ca7e116` | `77178490908661` |
| akzo-quote-agent | `60954750-0c12-45eb-8bc4-493590827090` | `75273100893336` |
| akzo-mock-systems | `99ba0349-8260-4815-8fe7-ecf6df3fc3f6` | `70488120352789` |

**Grants applied to every executor SP (idempotent):**

1. **Unity Catalog** (SQL statement-execution on warehouse `4d39ac2e32b72a3a`) — all SUCCEEDED:
   - `GRANT USE CATALOG ON CATALOG serverless_lakebase_praneeth_catalog`
   - `GRANT USE SCHEMA` + `GRANT SELECT ON SCHEMA` for: `akzo_finance`, `akzo_scm`,
     `akzo_commercial`, `akzo_docs`, `akzo_ops`, `akzo_gateway`.
2. **SQL warehouse `4d39ac2e32b72a3a`** — `CAN_USE` (additive PATCH). The executor runs
   `http_request(...)` on the warehouse, so warehouse access is required.
3. **UC HTTP connection `akzo_external_systems`** — `GRANT USE CONNECTION` to the four
   **executor** SPs (action-center, supervisor, finance-copilot, quote-agent). This is the
   grant that makes the **primary** governed path work: without it the
   `http_request(conn => 'akzo_external_systems', ...)` call 403s and the connector silently
   falls back to the SP-direct path. Confirmed live: the fresh L3 execute below ran
   `via=uc_connection` (not the fallback). The mock-systems SP intentionally does NOT get this
   grant — it is the *target*, not a caller.
4. **Lakebase `graphrag-spike`** (Postgres, db `databricks_postgres`, schema `akzo`):
   - Registered each SP as a Postgres role (`identity_type: SERVICE_PRINCIPAL`, role name = SP client_id).
   - Connected as the instance superuser and granted each role on schema `akzo`:
     `USAGE, CREATE`, `SELECT/INSERT/UPDATE/DELETE ON ALL TABLES`,
     `USAGE, SELECT ON ALL SEQUENCES`, + matching `ALTER DEFAULT PRIVILEGES`.
   - `CREATE` is required because the apps bootstrap their write tables with
     `CREATE TABLE IF NOT EXISTS` (Postgres evaluates the privilege even when the table exists).
   - **DML on schema `akzo` confirmed for all** — the deepened apps + action-center read/write
     `akzo.actions` / `akzo.action_events`; mock-systems writes `akzo.external_system_log`.

Action-plane tables present + writable in `akzo`: `actions`, `action_events`,
`action_policies` (7 seeded policy rows), `external_system_log`, plus the pre-existing
`quotes`, `quote_approvals`, `agent_sessions`, `agent_feedback`, `saved_analyses`,
`forecast_overrides`, `scm_interventions`, `commercial_actions`.

---

## What was smoke-tested GREEN

### akzo-action-center (the exec's single screen)
- `GET /api/health` → **200** `{"status":"ok","identity":"0b196b6e-..."}` (runs as its SP).
- `GET /api/ladder` → **200** — live level counts:
  **L1** 0 · **L2** 3 (executed) · **L3** 16 (10 executed, 5 escalated, 1 proposed) ·
  **L4** 10 (4 executed, 6 escalated).
- `GET /api/actions` → **200** — the cross-agent queue (27+ actions across all agents).
- `GET /api/actions/{id}` → **200** — action row + ordered `events` lineage + live guardrail verdict.
- `GET /` → **200** — serves the built React SPA (`<div id="root">`).
- **Clean boot** (from `databricks apps logs`): build upgraded `databricks-sdk` 0.33.0 → 0.119.0
  (the Lakebase fix), `psycopg 3.3.4` installed, "Application startup complete", "Deployment successful".

### Separation-of-duties guard (verified live)
- An action staged via the supervisor (`/api/act`) gets `requested_by = praneeth.paikray@databricks.com`
  (derived from the `X-Forwarded-Email` Apps header, never the request body).
- `POST /api/actions/30/approve` as the **same** identity → **403**
  `"separation of duties: you cannot approve an action you requested"`. The guard works.
- The task notes this is expected and must not fail the smoke — and it didn't; the 403 is the guard firing.

### L1→L4 cross-agent story (exercisable)
- **Cross-agent visibility:** an action staged from a **domain app** (supervisor `/api/act`,
  id=30, `quote_send`, guardrail passed) **immediately appears in the action-center queue**
  (`GET /api/actions/30` from action-center returns it, agent `supervisor-agent`, status `proposed`).
- **L3 execute → external receipt (fresh, this deploy):** drove the same `action_plane` the apps
  run (proposer `finance-copilot-agent`, approver `praneeth...` → SoD satisfied) — action **id=31**
  `quote_send` → route `email, crm`:
  - `proposed → approved → executing → connector(email) → connector(crm) → executed`
  - `external_ref = EMAIL-0031`; both connectors ran **`via=uc_connection`** (the governed UC HTTP path)
  - **Fresh receipts landed in `akzo.external_system_log`:** `EMAIL-0031` + `CRM-0032`,
    `created_by = 99ba0349-...` (the **mock-systems** SP) — proof the call traveled through the
    mock app via the connection. Log grew 30 → 32 rows.
  - action-center `GET /api/actions/31` shows it `executed`, level 3, external_ref EMAIL-0031.
- **Guardrail gate on execute (verified):** `POST /api/actions/24/execute` on an over-cap
  `scm_reorder` (€205k > €100k cap) → the executor's final guardrail re-check **escalated**
  instead of acting → status `escalated`, `external_ref` null, **no external call made**.
- **L4 autonomous loop:** notebook 10 (`10_autonomous_closed_loop.py`) was already verified
  end-to-end on its local run (it seeded the existing `external_system_log` rows + the L4 `actions`):
  PATH A in-policy `scm_reorder` auto-approved (`autonomous-loop`, no human) + executed (PO on mock ERP);
  PATH B over-cap reorder escalated (no execution); PATH C re-fire deduped by `breach_key`.
  The `akzo-autonomous-scm` Job wraps that notebook (PAUSED). The ladder shows the L4 evidence
  live (4 executed + 6 escalated at level 4).

### Deepened domain apps + mock-systems
- `akzo-supervisor` / `akzo-finance-copilot` / `akzo-quote-agent`: `/api/health` → **200** (each as its SP);
  `/api/actions` → **200** returning each app's **own** agent-scoped queue (2 / 2 / 8 actions) —
  confirms `build_actions_router("<agent>")` scoping.
- `akzo-mock-systems`: `/api/health` → **200**; receives governed calls and lands receipts
  (verified by the EMAIL-0031 / CRM-0032 rows above, attributed to its SP).

---

## Guards demonstrated (the governance story)

- **Separation of duties** — the proposer of an action may not approve it; the approver is the
  authenticated user from `X-Forwarded-Email` (Apps-injected), never the request body. 403 verified live.
- **Guardrail gate before execute** — the executor re-runs `evaluate()` against `akzo.action_policies`
  as a final gate; a breach (e.g. spend > cap) **escalates** to a human gate instead of executing.
  Verified live on the €205k over-cap reorder (action 24).
- **Idempotency** — the L4 loop de-dupes on `payload.breach_key`; a re-fired scheduled run finds the
  already-handled breach and skips (no duplicate PO). Verified in notebook 10 PATH C.
- **Governed external path** — every connector call goes through the UC HTTP connection
  `akzo_external_systems` (the four executor SPs now hold `USE CONNECTION`), so the path is
  catalog-governed + lineage-traced; the SP-direct path is only a documented fallback. The fresh
  L3 execute confirmed `via=uc_connection`.

---

## Issues found + fixed during deploy

1. **`declare -A` not supported (macOS bash 3.2).** The first run of the consolidated deploy
   script failed (`supervisor: unbound variable`) because macOS ships bash 3.2, which has no
   associative arrays. **Fix:** rewrote the app map as parallel indexed arrays
   (`REDEPLOY_DIRS` / `REDEPLOY_NAMES`). Script now runs clean on the stock shell.

2. **`USE CONNECTION` was missing on the connection.** `akzo_external_systems` had no explicit
   grants (owner-only), so the executor SPs' primary `http_request(conn => ...)` path would 403
   and silently fall back to SP-direct. **Fix:** added `GRANT USE CONNECTION` to the four executor
   SPs (now also baked into the script's `grant_sp`). The action-center SP's grant was applied
   manually after the run because the script edit landed mid-run (after that SP's grant block had
   already executed); a fresh re-run grants it automatically. All four executor SPs now hold
   `USE_CONNECTION`; the live L3 execute ran `via=uc_connection`.

---

## Gaps + remediation

- **End-to-end approve→execute in the UI needs two identities.** The SoD guard means a single
  signed-in user cannot both propose and approve. For the API smoke this surfaced as a 403 on a
  self-proposed action (the guard working). The fresh L3 execute was therefore proven by driving
  the shared `action_plane` with a distinct proposer/approver (proposer `finance-copilot-agent`,
  approver `praneeth...`) — same code path the app runs. **Remediation for the live demo:** show
  the approve→execute as two browser identities (e.g. a "rep" proposes, a "controller" approves),
  which the X-Forwarded-Email header makes automatic in the deployed app.
- **Autonomous Job left PAUSED and not run via `run-now`.** Per the task, the notebook-10 local
  run is already verified (it produced the L4 actions + receipts visible in the ladder), so the
  paused serverless job was created but not triggered — the safe choice. **To run it live:**
  `databricks jobs run-now 957865596190448 -p fe-vm-lakebase-praneeth` (serverless; it acts only
  on the mock systems and escalates over-cap, so it is safe to trigger for a demo).
- **FM API serving endpoint** `databricks-claude-opus-4-7` needs no per-SP grant (queryable by all
  workspace principals; live `ai_query`/`chat` calls succeed under each SP). Unchanged from the
  original deploy. No action required.

---

## Re-running

`deploy/deploy_action_apps.sh` captures everything idempotently:
```bash
cd /Users/praneeth.paikray/Documents/Code/agent-bricks-workshop
./deploy/deploy_action_apps.sh
```
It creates `akzo-action-center` (skips if it exists), applies the full grant recipe
(UC read + warehouse CAN_USE + **USE CONNECTION** + Lakebase role/DML on `akzo`), syncs each app
source (incl. `frontend/dist/**`, excluding `node_modules`), redeploys the 3 deepened apps +
mock-systems, syncs `notebooks/` + `apps/_shared` to the workspace paths the Job/notebook import,
creates the `akzo-autonomous-scm` Job if absent, waits for all deployments SUCCEEDED, and
re-checks `/api/health` on all five apps.
