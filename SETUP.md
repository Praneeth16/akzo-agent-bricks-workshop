# Provision Once — Workshop Setup Checklist

Everything in this workshop reads its catalog, warehouse, endpoints, and IDs from widgets or
environment variables. Nothing is tied to one workspace. This page is the **one ordered checklist**
to provision your own workspace before you start the ladder.

Work top to bottom. Steps 1–3 get you into L100; **L100 chapter 3 (short-term memory) also needs
Lakebase (step 5)**, and the no-code Agent Bricks lab uses a Genie space (step 4). Steps 4–7 unlock
the rest of L200/L300 and the apps.

---

## At a glance

| # | Provision | Needed for | How |
|---|---|---|---|
| 1 | Unity Catalog + SQL warehouse | everything | you create / are granted them |
| 2 | Load the data | everything | `data/load_to_uc.py` |
| 3 | A Foundation Model endpoint | every LLM call | enable FM API; note the endpoint name |
| 4 | Genie spaces (3) | L100 no-code lab, L200 ch1, supervisor app | `genie/create_genie_spaces.py` or the UI |
| 5 | Lakebase instance | L100 ch3, L200 ch2–3, apps | enable Lakebase; note the instance name |
| 6 | Vector Search endpoint | L200 ch5 | enable Vector Search; note the endpoint name |
| 7 | Mock Systems app + UC HTTP connection | L200 ch2–3, action apps | `deploy/deploy_mock_systems.sh` |

Optional, only if you reach them: an **AI Gateway** endpoint (L200 ch4 Part B) and **Model
Serving** (L200 ch7). Both degrade gracefully — the notebooks run without them.

---

## 1. Unity Catalog + SQL warehouse

You need a Unity Catalog you can write to and a **serverless** SQL warehouse.

- Pick (or create) a catalog. The workshop creates `akzo_*` schemas inside it — it does not need a
  dedicated catalog, just write access.
- Note your **warehouse id**: Compute → SQL Warehouses → your warehouse → copy the id from the URL
  or the **Connection details** tab.

Hold onto two values — you will reuse them everywhere:

```bash
export AKZO_CATALOG=<your_catalog>
export DATABRICKS_WAREHOUSE_ID=<your_warehouse_id>
# optional, if you use a named CLI profile:
export DATABRICKS_CONFIG_PROFILE=<your_profile>
```

**Permissions:** `USE CATALOG` + `USE SCHEMA` + `SELECT` on the `akzo_*` schemas, and
`CREATE SCHEMA` / `CREATE VOLUME` to run the loader. `CAN_USE` on the warehouse.

---

## 2. Load the data

```bash
python3 data/load_to_uc.py
```

(`AKZO_CATALOG` and `DATABRICKS_WAREHOUSE_ID` from step 1 must be set.) This creates 6 schemas, 13
tables, 2 volumes, and uploads 14 PDFs. Idempotent — safe to re-run. Full detail and the column
docs are in [`data/README.md`](data/README.md).

---

## 3. A Foundation Model endpoint

Every agent calls a chat model. Enable the **Foundation Model API** and note an endpoint name you
are entitled to query. The notebooks default to widgets you can override:

- L100 notebooks default `llm_endpoint` to `databricks-meta-llama-3-3-70b-instruct`.
- L200 notebooks default `llm_endpoint` / `chat_endpoint` to `databricks-claude-opus-4-8`.
- Apps read `DATABRICKS_CHAT_ENDPOINT` (default `databricks-claude-opus-4-8`).

Set the widget / env var to whatever endpoint your workspace has. **Permission:** `CAN_QUERY` on
the endpoint (FM API endpoints are usually queryable by all workspace users by default).

---

## 4. Genie spaces (3)

The L200 supervisor (chapter 1) and the supervisor app route to three Genie spaces — Finance, SCM,
Commercial. Two ways to create them:

- **From code (recommended):**
  ```bash
  python3 genie/create_genie_spaces.py            # uses AKZO_CATALOG + DATABRICKS_WAREHOUSE_ID
  # add --profile <your_profile> if you use a named CLI profile (env vars still required)
  ```
  It creates all three, seeds them with the prebuilt configs, and writes the ids to
  `genie/space_ids.json`.
- **By hand in the UI:** New → Genie space, attach the `akzo_finance` / `akzo_scm` /
  `akzo_commercial` tables, paste the instructions from `genie/<domain>_space.md`.

Either way, you then copy each **space id** into the notebook widgets (`finance_space_id`,
`scm_space_id`, `commercial_space_id`) or the app's env vars. The id is the last URL segment of
`/genie/rooms/<space_id>`. Leave a widget blank to use the in-code `ai_query` fallback. Full
walkthrough: [`genie/README.md`](genie/README.md).

---

## 5. Lakebase instance

Agent memory (L100 ch3), the action plane (L200 ch2–3), and the apps persist to a **Lakebase**
managed Postgres instance.

- Enable Lakebase and create an instance. Note its **name**.
- Set it where prompted: the `lakebase_instance` widget (notebooks) or `LAKEBASE_INSTANCE` env var
  (apps, deploy scripts). The workshop uses database `databricks_postgres` and schema `akzo`.

**Permissions:** the running identity (you, or an app's service principal) needs a Postgres role on
the instance with `USAGE, CREATE` on the `akzo` schema. The deploy scripts wire this for app
service principals automatically.

---

## 6. Vector Search endpoint

L200 chapter 5 (document intelligence) embeds the PDFs and builds an index.

- Enable Vector Search and note your endpoint name.
- Set the `vs_endpoint` widget (default `akzo_workshop_vs`) and `embed_endpoint` (default
  `databricks-qwen3-embedding-0-6b`) to what your workspace has.

---

## 7. Mock Systems app (+ the UC HTTP connection)

The "agents that act" labs (L200 ch2–3) and the action apps POST to a **Mock External Systems**
app through a governed Unity Catalog HTTP connection. The deploy script below stands up the **app**
and its grants; the **UC HTTP connection** `akzo_external_systems` is created inside L200 chapter 2.

- Deploy the app:
  ```bash
  DATABRICKS_CONFIG_PROFILE=<profile> WORKSPACE_USER=<you@example.com> \
  DATABRICKS_WAREHOUSE_ID=<id> AKZO_CATALOG=<catalog> LAKEBASE_INSTANCE=<instance> \
  ./deploy/deploy_mock_systems.sh
  ```
- Copy its URL into the `mock_app_url` widget (notebooks) or the `AKZO_MOCK_SYSTEMS_URL` env var (apps).
- The UC HTTP connection `akzo_external_systems` is created inside L200 chapter 2; the notebooks and
  apps reference it by the `connection_name` widget / `AKZO_HTTP_CONNECTION` env var.

See [`apps/mock-systems/README.md`](apps/mock-systems/README.md) for endpoints and grants.

---

## Where each material reads its config

| Material | Reads config from |
|---|---|
| `data/load_to_uc.py`, `genie/create_genie_spaces.py` | env vars (`AKZO_CATALOG`, `DATABRICKS_WAREHOUSE_ID`, `DATABRICKS_CONFIG_PROFILE`) |
| L100 / L200 notebooks | `dbutils.widgets` at the top of each notebook (catalog defaults to `current_catalog()`) |
| `apps/*` | env vars in `app.yaml` / `.env.example` (see each app's README) |
| `deploy/*.sh` | env vars with `<placeholder>` fallbacks (see the header of each script) |

Once steps 1–3 are done you can start `L100-foundations/`. Climb the ladder from there — each tier
README ([L100](L100-foundations/README.md), [L200](L200-capabilities/README.md)) lists exactly
which of the above it needs.
