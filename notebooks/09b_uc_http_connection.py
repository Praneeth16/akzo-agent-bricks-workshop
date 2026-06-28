# Databricks notebook source
# MAGIC %md
# MAGIC # 09b — Governed UC HTTP connection to the Mock External Systems app
# MAGIC
# MAGIC *Agents That Act — Architecture §3/§4, unit U2.*
# MAGIC
# MAGIC The Action Plane never sends real email/PO. Its connectors call a **Mock External
# MAGIC Systems** Databricks App (`akzo-mock-systems`), and the call goes **through a Unity
# MAGIC Catalog HTTP connection** (`akzo_external_systems`) so every external action is
# MAGIC catalog-governed and auditable. Each call also lands a receipt row in Lakebase
# MAGIC `akzo.external_system_log`.
# MAGIC
# MAGIC This notebook:
# MAGIC 1. creates the UC HTTP connection pointing at the deployed mock app,
# MAGIC 2. makes a **governed call** through it with `http_request(...)`,
# MAGIC 3. reads the receipt back from `akzo.external_system_log`,
# MAGIC 4. documents the auth constraint + the graceful fallback.
# MAGIC
# MAGIC **What you'll learn:** why routing external side effects through a UC HTTP connection
# MAGIC (instead of a raw `requests.post`) is the difference between an ungoverned script and an
# MAGIC auditable Action Plane — and how `http_request` turns a SQL statement into a governed,
# MAGIC logged external action.
# MAGIC
# MAGIC **Prerequisites:** the mock app must already be deployed (`deploy/deploy_mock_systems.sh`)
# MAGIC and you need permission to `CREATE CONNECTION` in this catalog. **How to run:** top to
# MAGIC bottom, ~2 min. Set `MOCK_APP_URL` in cell 0 to your deployment first; everything else
# MAGIC flows from there.
# MAGIC
# MAGIC **Verified live** on workspace `fevm-serverless-lakebase-praneeth` (2026-06-27):
# MAGIC the connection was created, `http_request` POSTs to `/email` and `/erp/po`
# MAGIC returned ref ids `EMAIL-0003` / `PO-0004`, and both rows were read back from
# MAGIC `akzo.external_system_log` under the mock app's service principal.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Config — the deployed mock app base URL
# MAGIC
# MAGIC The mock app is deployed by `deploy/deploy_mock_systems.sh`. Its URL has the form
# MAGIC `https://akzo-mock-systems-<workspace-id>.<cloud>.databricksapps.com`. Set it here.

# COMMAND ----------

MOCK_APP_URL = "https://akzo-mock-systems-7474654904882204.aws.databricksapps.com"
CONNECTION_NAME = "akzo_external_systems"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The auth constraint (read this before creating the connection)
# MAGIC
# MAGIC Databricks Apps sit behind **workspace SSO** — every request needs an
# MAGIC `Authorization: Bearer <token>` header. A UC HTTP connection has two ways to attach
# MAGIC credentials:
# MAGIC
# MAGIC - **OAuth (`auth_type 'OAuth'`)** — UC dynamically registers a client with the
# MAGIC   authorization server (DCR). The workspace's OIDC endpoint
# MAGIC   (`.../oidc`) **does not advertise a `registration_endpoint`**, so DCR fails:
# MAGIC   `Authorization server ... does not support DCR`. OAuth is therefore **not usable**
# MAGIC   for an Apps target on this workspace.
# MAGIC - **Bearer token (`bearer_token '...'`)** — UC attaches a static bearer token to
# MAGIC   every request. This **works** against the Apps SSO gate and is what we use below.
# MAGIC
# MAGIC **Token lifetime caveat:** a workspace OAuth access token is short-lived (~1h). For a
# MAGIC long-lived governed connection, mint the bearer from a **service principal OAuth
# MAGIC client** (M2M) and rotate it, *or* use the documented fallback (§5) where the app's
# MAGIC own connectors call the mock URL under the app service principal. For the workshop /
# MAGIC demo, a freshly minted token is sufficient and the governance shape is identical.

# COMMAND ----------

# MAGIC %md
# MAGIC The next cell mints the bearer token. We reuse the notebook's own API token via
# MAGIC `dbutils` so the workshop needs no extra setup — this is the credential UC will attach
# MAGIC to every request through the connection. In production you would swap this for a
# MAGIC service-principal M2M token (see the caveat above); the rest of the notebook is unchanged.

# COMMAND ----------

# Mint a bearer token for the connection. In the workshop this is your interactive
# OAuth token; in production use an SP OAuth (M2M) token and rotate.
#   databricks auth token -p fe-vm-lakebase-praneeth   ->  .access_token
#
# dbutils gives us the notebook's API token directly:
BEARER_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create the UC HTTP connection
# MAGIC
# MAGIC `host` is the full https base URL, `port '443'`, `base_path '/'` (the mock app's
# MAGIC action routes — `/email`, `/erp/po`, ... — are mounted at root). `bearer_token`
# MAGIC carries the SSO credential. The connection is created **read-only** by UC; that does
# MAGIC not block POSTs made via `http_request`.

# COMMAND ----------

# Use CREATE OR REPLACE so re-running the notebook always installs a FRESH token.
# `CREATE ... IF NOT EXISTS` would keep a stale (expired) bearer token on a re-run
# while we mint a new one above — the connection would then 401 silently.
spark.sql(f"""
  CREATE OR REPLACE CONNECTION {CONNECTION_NAME}
  TYPE HTTP
  OPTIONS (
    host '{MOCK_APP_URL}',
    port '443',
    base_path '/',
    bearer_token '{BEARER_TOKEN}'
  )
""")
display(spark.sql(f"DESCRIBE CONNECTION {CONNECTION_NAME}"))

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** the `DESCRIBE` output shows `connection_type = HTTP` and the `host`
# MAGIC pointing at your mock app. The bearer token is **not** echoed (UC redacts secrets) — that
# MAGIC is expected and correct.

# COMMAND ----------

# MAGIC %md
# MAGIC If the connection already exists with a now-expired token, refresh it:
# MAGIC
# MAGIC ```sql
# MAGIC -- ALTER CONNECTION akzo_external_systems OPTIONS (bearer_token '<fresh token>');
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Governed call — POST /email through the connection
# MAGIC
# MAGIC `http_request(conn => ..., method => 'POST', path => '/email', json => ...)` returns a
# MAGIC struct; `.text` is the response body. The mock app allocates a `ref_id` and logs a
# MAGIC receipt to Lakebase. This is the **catalog-governed external action**.

# COMMAND ----------

email_resp = spark.sql(f"""
  SELECT http_request(
    conn   => '{CONNECTION_NAME}',
    method => 'POST',
    path   => '/email',
    json   => to_json(named_struct(
      'to',      'exec@akzonobel.com',
      'subject', 'Governed UC call',
      'body',    'Sent through the akzo_external_systems UC HTTP connection'
    ))
  ).text AS response
""").collect()[0]["response"]
print(email_resp)   # -> {"ref_id":"EMAIL-000N","status":"accepted","echo":{...}}

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** a JSON body with `"status":"accepted"` and a fresh `ref_id` such as
# MAGIC `EMAIL-0003`. That `ref_id` is your handle into the audit log (§5). A `401` here means the
# MAGIC bearer token expired — re-run the mint cell and `CREATE OR REPLACE` the connection.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Governed call — POST /erp/po through the connection
# MAGIC
# MAGIC Same pattern, different action route. The point is that **every** external side effect
# MAGIC the Action Plane needs (email, purchase order, ...) flows through this one governed
# MAGIC connection, so there is no ungoverned escape hatch.

# COMMAND ----------

po_resp = spark.sql(f"""
  SELECT http_request(
    conn   => '{CONNECTION_NAME}',
    method => 'POST',
    path   => '/erp/po',
    json   => to_json(named_struct(
      'supplier',   'TiO2 Supplier NL',
      'sku',        'DEC-1008',
      'qty',        5000,
      'amount_eur', 114100.0
    ))
  ).text AS response
""").collect()[0]["response"]
print(po_resp)      # -> {"ref_id":"PO-000N","status":"accepted","echo":{...}}

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** another `"accepted"` response with a `PO-000N` ref id and your
# MAGIC supplier/sku/qty echoed back. Two governed actions are now on record.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Read the receipts back — the audit trail in Lakebase
# MAGIC
# MAGIC The mock app logs each call to `akzo.external_system_log` (managed Postgres /
# MAGIC Lakebase). We read it back via the app's own `/api/log` endpoint, or directly from
# MAGIC Lakebase. Here we hit `/api/log` *through the same governed connection* (a GET), so
# MAGIC even the audit read is catalog-governed.

# COMMAND ----------

log_resp = spark.sql(f"""
  SELECT http_request(
    conn   => '{CONNECTION_NAME}',
    method => 'GET',
    path   => '/api/log'
  ).text AS response
""").collect()[0]["response"]
print(log_resp)     # recent external_system_log rows, including the two calls above

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** the two `ref_id`s you just created (`EMAIL-000N`, `PO-000N`) appear
# MAGIC in the returned rows, each attributed to the mock app's service principal. This is the
# MAGIC closed loop: action issued → receipt logged → audit read, all through one governed path.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Documented fallback (if `http_request` / HTTP connections are unavailable)
# MAGIC
# MAGIC If a workspace lacks the connection-HTTP feature, or the bearer-token auth path is
# MAGIC closed, the Action Plane **degrades gracefully without losing auditability**:
# MAGIC
# MAGIC > The connectors in `apps/_shared/action_plane/connectors/` call the mock app's URL
# MAGIC > **directly under the app service principal** (the SP's SDK/OAuth credential), still
# MAGIC > writing the `external_ref` + result to the Action Plane and a row to
# MAGIC > `akzo.external_system_log`. The governance story shifts from "catalog-governed HTTP
# MAGIC > connection" to "identity + audit", but every external action stays logged and
# MAGIC > attributable.
# MAGIC
# MAGIC On **this** workspace neither fallback is needed: the connection + governed
# MAGIC `http_request` path is live and verified (§3/§4 above).

# COMMAND ----------

# MAGIC %md
# MAGIC ### Summary (verified live, 2026-06-27)
# MAGIC
# MAGIC | Step | Result |
# MAGIC |---|---|
# MAGIC | `CREATE CONNECTION akzo_external_systems TYPE HTTP` (bearer_token) | **SUCCEEDED** |
# MAGIC | `http_request` POST `/email` | `EMAIL-0003` accepted |
# MAGIC | `http_request` POST `/erp/po` | `PO-0004` accepted |
# MAGIC | Receipts in `akzo.external_system_log` | both rows present, `created_by` = mock-app SP |
# MAGIC | OAuth (`auth_type 'OAuth'`) | **not usable** — workspace OIDC lacks DCR `registration_endpoint` |
# MAGIC
# MAGIC **What you built & where it goes next:** you now have a catalog-governed, audited path for
# MAGIC external side effects — the foundation the Action Plane connectors
# MAGIC (`apps/_shared/action_plane/connectors/`) sit on. The next layer wires these governed calls
# MAGIC into the agent itself, so when the supervisor decides to send an email or cut a PO, it does
# MAGIC so through exactly this connection — governed, logged, and attributable end to end.
