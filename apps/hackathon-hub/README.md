# Hackathon-in-the-Box — unified hub (Databricks AppKit)

One light-theme app that combines everything in this repo — the 10 reference
notebooks, 8 forkable starter tracks, the 5 deployed agent apps, the demo data —
and runs the event end to end (Register → Teams → Submit → Judge → Leaderboard).
Built **on Databricks AppKit**, so the app itself dogfoods the stack.

Project dir: `apps/hackathon-hub/akzo-hackathon-hub`. Plan: `HACKATHON_IN_A_BOX_PLAN.md`.

## Stack
- **AppKit** (`@databricks/appkit`) + `@databricks/appkit-ui` (Shadcn/Radix/Tailwind) — React 19, react-router 7, Vite.
- Server: Express via the AppKit `server` plugin + `analytics` plugin (live charts over `akzo_*`).
- Hackathon state: **Lakebase** (classic instance `graphrag-spike`, db `databricks_postgres`, schema `akzo`, `hack_*` tables) — accessed with `pg` + a short-lived OAuth db credential (`POST /api/2.0/database/credentials`), the Node port of `apps/_shared/lakebase.py`.

## Layout
- `client/src/pages/*` — Overview, Challenges, How-to-run, Register, Teams, Submit, Judge, Leaderboard, **Live** (live `akzo_*` analytics + links to the 5 agent apps), Resources, Materials, Organizer.
- `client/src/content.ts` — static inventory (tracks, notebooks, apps, agenda).
- `client/src/api.ts` — typed client for `/api/hack/*`.
- `server/lakebase.ts` — Lakebase pool + credential refresh. `server/schema.ts` — `hack_*` DDL + seed (idempotent). `server/routes.ts` — CRUD + judging (separation of duties: a judge cannot score their own team; identity from `X-Forwarded-*`, never the body).
- `config/queries/*.sql` — `margin_trend`, `otif_trend`, `churn_top` over the warehouse.

## Local dev
```bash
cd apps/hackathon-hub/akzo-hackathon-hub
DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth npm run dev   # http://localhost:8000
```
Verified locally: all pages render (light theme), Register→Teams→Submit→Judge→Leaderboard round-trips on live Lakebase, separation-of-duties returns 403, and the Live analytics panels return real data (24 months margin, Rotterdam OTIF, at-risk EMEA accounts).

## Deploy
```bash
databricks apps deploy --force -p fe-vm-lakebase-praneeth
```
App name `akzo-hackathon-hub`. URL: https://akzo-hackathon-hub-7474654904882204.aws.databricksapps.com

### Service-principal grants (run once after first deploy; SP = `service_principal_client_id` from `databricks apps get`)
- UC: `GRANT USE CATALOG` + per-schema `USE SCHEMA`/`SELECT` on `akzo_finance`, `akzo_scm`, `akzo_commercial`.
- Warehouse `4d39ac2e32b72a3a`: `CAN_USE` (permissions PATCH).
- Lakebase: register the SP as a Postgres role on `graphrag-spike` (`POST /api/2.0/database/instances/graphrag-spike/roles`), then `GRANT USAGE,CREATE ON SCHEMA akzo` + `SELECT,INSERT,UPDATE,DELETE ON ALL TABLES` + sequence + default privileges to the role.
All grants were applied for SP `bc541e2f-0809-46db-8b9a-678ee3f9e804`. Recipe mirrors `deploy/deploy_apps.sh` §3.

## Status: LIVE
Deployed + verified: https://akzo-hackathon-hub-7474654904882204.aws.databricksapps.com (compute ACTIVE, deploy SUCCEEDED). Live-smoked: root 200, `/api/hack/*` over Lakebase (teams/leaderboard), analytics over the warehouse (margin_trend 24 rows), all under the app SP.

## Deploy gotchas (resolved — keep in mind for redeploys)
- **npm tarball 404s in the build container.** The Apps build container fetches from `npm-proxy.cloud.databricks.com`, whose mirror 404s many tarballs (pg tree, even `@opentelemetry/resources`) — but it CAN reach **public npm**. A corporate dev machine is the opposite (public npm blocked; `~/.npmrc` forces the proxy), so a locally-generated lock has proxy URLs the container can't fetch. **Fix:** generate `package-lock.json` (via the proxy locally), then rewrite every `resolved` host `npm-proxy.cloud.databricks.com` → `registry.npmjs.org` (same path + integrity hash, validates). Don't add a project `.npmrc` pinning the proxy (it broke `@opentelemetry` resolution). Don't pin pg to old versions — it's host/path-specific, not version-specific.
- **Build-time typegen.** `prebuild`/`postinstall` run `appkit generate-types`, which DESCRIBEs the queries against the warehouse — made non-fatal (`npm run typegen || true`); the committed `shared/appkit-types/*.d.ts` is sufficient.
- **SP rotates across redeploys.** Re-read `service_principal_client_id` from `databricks apps get` and re-grant UC SELECT + warehouse CAN_USE + Lakebase role + `akzo` DML before runtime data works.

## Upgrade path
Native Genie: create the 3 Akzo Genie spaces, add the AppKit `genie()` plugin, and swap the Live analytics panels for `<GenieChat alias="finance|scm|commercial" />` — the same move the workshop teaches.
