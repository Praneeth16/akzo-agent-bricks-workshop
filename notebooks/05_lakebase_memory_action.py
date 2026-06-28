# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 5 — Memory + action (Lakebase)
# MAGIC
# MAGIC *The "agents that act" layer — shared by use cases #1/#2/#5/#6.*
# MAGIC
# MAGIC Every layer so far has the agent **answering**. This layer is where it starts **acting**: it
# MAGIC writes a recommended SCM intervention and a forecast override into **Lakebase** (managed
# MAGIC Postgres), the write lands in a governed table, and a human **approval flow flips the row from
# MAGIC `pending` → `approved`** with a full audit trail. The supervisor now reads → reasons → acts →
# MAGIC writes → routes to approval.
# MAGIC
# MAGIC This notebook is the **reference build** behind the Layer-5 hands-on block. In the room you do not
# MAGIC stand up Lakebase, roles, the schema, or the approval app — they are pre-staged. You **write one
# MAGIC row through the prepared path OR change one action definition**, then watch it land and surface
# MAGIC in the approval flow.
# MAGIC
# MAGIC **3-beat rhythm:**
# MAGIC 1. **See** — connect to Lakebase, see the write-back schema and the audit columns.
# MAGIC 2. **Tweak** — change one action definition, re-run, watch the new row land in Lakebase.
# MAGIC 3. **Return** — the approval flow flips `pending → approved`; the supervisor's recommendation is
# MAGIC    now a governed, audited action.
# MAGIC
# MAGIC ### Write governance — say it plainly (this is the honest 2,000-user story)
# MAGIC OBO + UC/RLS (Layer 2) govern **reads**. They do **not** govern these writes. The write path is a
# MAGIC **separate governance plane**:
# MAGIC - **Lakebase (Postgres) writes use Postgres roles**, not UC RLS. **UC-registered Lakebase is
# MAGIC   read-only** — you cannot write through the UC mirror.
# MAGIC - The agent writes through an **app/service identity**, every row carries **`created_by` +
# MAGIC   `created_at` + `status`** (the audit trail), and nothing takes effect until a human flips the
# MAGIC   status in the **approval flow**.
# MAGIC - So "who can see what" (OBO, Layer 2) and "who can change what" (Postgres roles + approval +
# MAGIC   audit, here) are two distinct planes. Keeping them distinct is the point.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — connect to the Lakebase Postgres instance
# MAGIC
# MAGIC We reuse the existing Lakebase instance **`graphrag-spike`** (state AVAILABLE, native Postgres
# MAGIC login enabled). The connection recipe (verified on this workspace):
# MAGIC
# MAGIC | Field | Value |
# MAGIC |---|---|
# MAGIC | host | `ep-spring-block-d2tu1slg.database.us-east-1.cloud.databricks.com` (the instance `read_write_dns`) |
# MAGIC | port | `5432` |
# MAGIC | dbname | `databricks_postgres` |
# MAGIC | user | your email — `praneeth.paikray@databricks.com` (the OAuth principal) |
# MAGIC | password | a **short-lived DB credential token** generated via the SDK/CLI |
# MAGIC | sslmode | `require` |
# MAGIC
# MAGIC The token is the app/service **write identity**. We use `psycopg` (psycopg3, preinstalled on
# MAGIC serverless); `psycopg2-binary` works identically if you prefer it.

# COMMAND ----------

# Get the instance DNS from the SDK so the notebook is self-locating (no hard-coded host drift).
from databricks.sdk import WorkspaceClient

INSTANCE_NAME = "graphrag-spike"
DB_NAME = "databricks_postgres"   # write into schema `akzo` within this database
PG_SCHEMA = "akzo"

w = WorkspaceClient()
inst = w.database.get_database_instance(name=INSTANCE_NAME)
PG_HOST = inst.read_write_dns
PG_USER = w.current_user.me().user_name   # your email — the OAuth principal / write identity
print("Lakebase instance :", INSTANCE_NAME, "(", inst.state, ")")
print("Host (read_write) :", PG_HOST)
print("Database / schema :", DB_NAME, "/", PG_SCHEMA)
print("Write identity    :", PG_USER)

# COMMAND ----------

# MAGIC %md
# MAGIC The DB credential is a short-lived token (≈1h). We generate it via the SDK and wrap the whole
# MAGIC connect-and-run flow in a helper so every cell gets a fresh token if needed. **This token is the
# MAGIC service/app write identity** — distinct from the UC/OBO read identity in Layer 2.

# COMMAND ----------

import psycopg
from contextlib import contextmanager

def _db_token() -> str:
    """Generate a short-lived Lakebase credential (the app/service write identity)."""
    cred = w.database.generate_database_credential(instance_names=[INSTANCE_NAME])
    return cred.token

@contextmanager
def pg():
    """Open an autocommit psycopg connection to Lakebase with search_path set to the akzo schema."""
    conn = psycopg.connect(
        host=PG_HOST, port=5432, dbname=DB_NAME,
        user=PG_USER, password=_db_token(), sslmode="require", autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {PG_SCHEMA}")
        yield conn
    finally:
        conn.close()

# Smoke test the connection.
with pg() as conn, conn.cursor() as cur:
    cur.execute("SELECT current_user, current_database()")
    print("Connected as:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: create the write-back schema + tables (with audit trail)
# MAGIC
# MAGIC The pre-staged schema is the agent's **memory + action surface**. Every action table carries the
# MAGIC audit trio — **`created_by`, `created_at`, `status`** — and an `approved_by` / `approved_at` pair
# MAGIC where a human decision applies. `quote_approvals` is the explicit approval ledger for quotes.
# MAGIC
# MAGIC | Table | What the agent writes | Audit / approval |
# MAGIC |---|---|---|
# MAGIC | `quotes` | a drafted quote (price, discount, rationale) | `status`, `created_by`, `created_at` |
# MAGIC | `quote_approvals` | the approval decision ledger for a quote | `decision`, `approver`, `decided_at` |
# MAGIC | `forecast_overrides` | an override to a demand forecast | `status`, `created_by`, `approved_by/at` |
# MAGIC | `scm_interventions` | a recommended supply-chain intervention | `status`, `created_by`, `approved_by/at` |
# MAGIC | `commercial_actions` | a next-best-action / save play | `status`, `created_by`, `approved_by/at` |
# MAGIC | `agent_sessions` | the agent's memory of a Q&A turn (routing + answer) | `created_at` |
# MAGIC | `agent_feedback` | human feedback on a session | `rating`, `comment`, `created_at` |
# MAGIC
# MAGIC The DDL is idempotent (`CREATE ... IF NOT EXISTS`) so re-running is safe.

# COMMAND ----------

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}",
    """CREATE TABLE IF NOT EXISTS quotes (
        quote_id         BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        account_id       TEXT NOT NULL,
        sku              TEXT NOT NULL,
        region           TEXT,
        quantity_units   INTEGER NOT NULL,
        list_price_eur   NUMERIC(12,2),
        quoted_price_eur NUMERIC(12,2) NOT NULL,
        discount_pct     NUMERIC(5,2),
        rationale        TEXT,
        status           TEXT NOT NULL DEFAULT 'pending',
        created_by       TEXT NOT NULL,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS quote_approvals (
        approval_id  BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        quote_id     BIGINT NOT NULL REFERENCES quotes(quote_id),
        decision     TEXT NOT NULL DEFAULT 'pending',
        approver     TEXT,
        comment      TEXT,
        decided_at   TIMESTAMPTZ,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS forecast_overrides (
        override_id    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        sku            TEXT NOT NULL,
        region         TEXT NOT NULL,
        month          DATE NOT NULL,
        baseline_units INTEGER,
        override_units INTEGER NOT NULL,
        reason         TEXT,
        status         TEXT NOT NULL DEFAULT 'pending',
        created_by     TEXT NOT NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        approved_by    TEXT,
        approved_at    TIMESTAMPTZ)""",
    """CREATE TABLE IF NOT EXISTS scm_interventions (
        intervention_id   BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        lane              TEXT,
        plant             TEXT,
        sku               TEXT,
        region            TEXT,
        intervention_type TEXT NOT NULL,
        detail            TEXT,
        expected_impact   TEXT,
        status            TEXT NOT NULL DEFAULT 'pending',
        created_by        TEXT NOT NULL,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        approved_by       TEXT,
        approved_at       TIMESTAMPTZ)""",
    """CREATE TABLE IF NOT EXISTS commercial_actions (
        action_id    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        account_id   TEXT NOT NULL,
        action_type  TEXT NOT NULL,
        detail       TEXT,
        owner_rep    TEXT,
        status       TEXT NOT NULL DEFAULT 'pending',
        created_by   TEXT NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        approved_by  TEXT,
        approved_at  TIMESTAMPTZ)""",
    """CREATE TABLE IF NOT EXISTS agent_sessions (
        session_id     BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        session_uuid   TEXT NOT NULL,
        user_email     TEXT NOT NULL,
        question       TEXT,
        routed_domains TEXT,
        fused_answer   TEXT,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS agent_feedback (
        feedback_id  BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        session_uuid TEXT NOT NULL,
        user_email   TEXT NOT NULL,
        rating       INTEGER,
        comment      TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now())""",
]

with pg() as conn, conn.cursor() as cur:
    for stmt in DDL:
        cur.execute(stmt)
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema = %s ORDER BY table_name""", (PG_SCHEMA,))
    tables = [r[0] for r in cur.fetchall()]
print("Lakebase write-back tables ready:", tables)

# COMMAND ----------

# MAGIC %md
# MAGIC ## The action layer — the agent's write helpers
# MAGIC
# MAGIC These are the **action definitions**: the small, audited write functions the agent calls instead
# MAGIC of just printing a recommendation. Each stamps the audit columns and returns the new row id with
# MAGIC `status='pending'`. **`write_scm_intervention` is the one you tweak** in Beat 2.

# COMMAND ----------

SERVICE_IDENTITY = "supervisor-agent@service"   # the app/service write identity in the audit trail

def write_scm_intervention(lane, plant, sku, region, intervention_type, detail, expected_impact,
                           created_by=SERVICE_IDENTITY) -> int:
    """ACTION: stage a recommended SCM intervention as a pending, audited row."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scm_interventions
               (lane, plant, sku, region, intervention_type, detail, expected_impact, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING intervention_id""",
            (lane, plant, sku, region, intervention_type, detail, expected_impact, created_by))
        return cur.fetchone()[0]

def write_forecast_override(sku, region, month, baseline_units, override_units, reason,
                            created_by=SERVICE_IDENTITY) -> int:
    """ACTION: stage a forecast override as a pending, audited row."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO forecast_overrides
               (sku, region, month, baseline_units, override_units, reason, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING override_id""",
            (sku, region, month, baseline_units, override_units, reason, created_by))
        return cur.fetchone()[0]

def approve_intervention(intervention_id, approver) -> tuple:
    """APPROVAL FLOW: flip an intervention pending -> approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE scm_interventions
               SET status='approved', approved_by=%s, approved_at=now()
               WHERE intervention_id=%s AND status='pending'
               RETURNING status, approved_by, approved_at""",
            (approver, intervention_id))
        return cur.fetchone()

def approve_override(override_id, approver) -> tuple:
    """APPROVAL FLOW: flip a forecast override pending -> approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE forecast_overrides
               SET status='approved', approved_by=%s, approved_at=now()
               WHERE override_id=%s AND status='pending'
               RETURNING status, approved_by, approved_at""",
            (approver, override_id))
        return cur.fetchone()

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: the agent acts; the row lands in Lakebase
# MAGIC
# MAGIC The supervisor's SCM leg (Layer 4) recommended fixing the Rotterdam lane. Now the agent **acts**:
# MAGIC it writes that intervention plus a forecast override. They land as `pending` rows.
# MAGIC
# MAGIC > **The tweak:** edit the `intervention_type` / `detail` / `expected_impact` below (e.g. change
# MAGIC > `"expedite_reroute"` to `"safety_stock_increase"` and rewrite the detail), re-run this cell, and
# MAGIC > watch a *new* pending row land with your action definition.

# COMMAND ----------

# >>> THIS IS THE ACTION YOU TWEAK <<< — change the intervention definition and re-run.
iid = write_scm_intervention(
    lane="Rotterdam-NL->EMEA-DACH",
    plant="Rotterdam-NL",
    sku="DEC-1000",
    region="EMEA",
    intervention_type="expedite_reroute",
    detail="Switch DEC-1000/DEC-1004 to air freight for 2 weeks and raise safety stock 20% to absorb the lead-time blowout.",
    expected_impact="Restore Rotterdam lane OTIF ~89% -> 95%+, clear ~2,258 EMEA backorders.",
)
print("Wrote scm_intervention id =", iid, "(status=pending)")

oid = write_forecast_override(
    sku="DEC-1000", region="EMEA", month="2026-07-01",
    baseline_units=4200, override_units=3600,
    reason="Demand softening after the May service disruption; trim EMEA July build to avoid overstock.",
)
print("Wrote forecast_override  id =", oid, "(status=pending)")

# COMMAND ----------

# MAGIC %md
# MAGIC **See it land.** Read the pending rows straight back from Lakebase — including the audit columns.
# MAGIC This is the same query the approval app runs to populate its pending queue.

# COMMAND ----------

with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT intervention_id, intervention_type, status, created_by, created_at
                   FROM scm_interventions WHERE status='pending' ORDER BY intervention_id DESC LIMIT 5""")
    interv = cur.fetchall()
    cur.execute("""SELECT override_id, sku, region, override_units, status, created_by
                   FROM forecast_overrides WHERE status='pending' ORDER BY override_id DESC LIMIT 5""")
    overr = cur.fetchall()

print("PENDING interventions:")
for r in interv:
    print("  ", r)
print("PENDING overrides:")
for r in overr:
    print("  ", r)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: the approval flow flips pending → approved
# MAGIC
# MAGIC A human (planner / controller) reviews the pending action and approves it. The `UPDATE` is
# MAGIC guarded by `status='pending'`, stamps `approved_by` + `approved_at`, and is the exact operation
# MAGIC the approval app's "Approve" button performs. Reads stay governed by OBO; this **write** is
# MAGIC governed by Postgres role + approval + audit — a different plane.

# COMMAND ----------

print("Approve intervention:", approve_intervention(iid, approver="planner.emea@akzo.example"))
print("Approve override    :", approve_override(oid, approver="controller@akzo.example"))

# Read the full audited row back — created_by (agent) AND approved_by (human) both recorded.
with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT intervention_id, intervention_type, status, created_by, approved_by, approved_at
                   FROM scm_interventions WHERE intervention_id=%s""", (iid,))
    print("Audited intervention:", cur.fetchone())
    cur.execute("""SELECT override_id, sku, override_units, status, created_by, approved_by, approved_at
                   FROM forecast_overrides WHERE override_id=%s""", (oid,))
    print("Audited override    :", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## The supervisor's memory: log the session (read → reason → act → write)
# MAGIC
# MAGIC Lakebase is also the agent's **memory**. We log the supervisor turn into `agent_sessions` so the
# MAGIC app can show history, support feedback (`agent_feedback`), and tie an action back to the question
# MAGIC that produced it.

# COMMAND ----------

import uuid

session_uuid = str(uuid.uuid4())
with pg() as conn, conn.cursor() as cur:
    cur.execute(
        """INSERT INTO agent_sessions (session_uuid, user_email, question, routed_domains, fused_answer)
           VALUES (%s,%s,%s,%s,%s) RETURNING session_id""",
        (session_uuid, PG_USER,
         "Paints EMEA gross margin dropped ~8% in Q2 — price, volume, or supply/service?",
         "FINANCE,SCM,COMMERCIAL",
         "Both a margin/cost issue (price/FX/raw-material ~8.9pp) and a supply/service issue "
         "(Rotterdam OTIF ~89% May, stockout). Action: expedite/reroute + review TiO2 contract + protect at-risk accounts."))
    sid = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO agent_feedback (session_uuid, user_email, rating, comment)
           VALUES (%s,%s,%s,%s)""",
        (session_uuid, "planner.emea@akzo.example", 5, "Correctly connected margin to the Rotterdam service shock."))
print("Logged agent_session id =", sid, "uuid =", session_uuid)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify everything from one place
# MAGIC
# MAGIC A final read across the action tables — what the approval app surfaces.

# COMMAND ----------

with pg() as conn, conn.cursor() as cur:
    for t in ("scm_interventions", "forecast_overrides", "agent_sessions", "agent_feedback"):
        cur.execute(f"SELECT count(*) FROM {t}")
        n = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {t}" + (" WHERE status='approved'" if t in ("scm_interventions","forecast_overrides") else ""))
        extra = f", approved={cur.fetchone()[0]}" if t in ("scm_interventions","forecast_overrides") else ""
        print(f"  {t}: rows={n}{extra}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole
# MAGIC
# MAGIC The supervisor now **reads → reasons → acts → writes → routes to approval**. **Verified on this
# MAGIC workspace (Lakebase `graphrag-spike`, schema `akzo`):** the agent wrote a `scm_intervention` and a
# MAGIC `forecast_override` as `pending` rows under the service identity, then the approval flow flipped
# MAGIC each to `approved` with `approved_by` + `approved_at` stamped. The tables persist — the Day-2
# MAGIC Quote/Pricing app and the Supervisor app read and write the same `akzo` schema.
# MAGIC
# MAGIC **The honest write-governance recap (the answer to the 2,000-user rollout question):**
# MAGIC - **Reads** are governed by OBO + UC/RLS (Layer 2) — per-user truth, enforced under the caller's
# MAGIC   identity.
# MAGIC - **Writes** are governed independently: **Postgres roles** on the Lakebase instance + an
# MAGIC   **app/service write identity** + an **approval flow** + an **audit trail** (`created_by`,
# MAGIC   `created_at`, `status`, `approved_by`, `approved_at`). **UC-registered Lakebase is read-only**;
# MAGIC   you write through Postgres, not the UC mirror.
# MAGIC - Two planes, not one. That separation is the governance story, not a limitation to hide.
# MAGIC
# MAGIC **Next:** `06_mlflow_eval_judge.py` — make the agent *measurable*.
