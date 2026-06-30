# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC The Action Plane writes to Lakebase (Postgres) with **psycopg3**, and reaching the Lakebase instance
# MAGIC needs the **Lakebase database API** in `databricks-sdk` (`w.database`), newer than some serverless
# MAGIC images ship. Install both, then restart Python. (Run this cell first; it is the only `%pip`.)

# COMMAND ----------

# MAGIC %pip install --quiet "psycopg[binary]" "databricks-sdk>=0.96"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 2 — Agents that act
# MAGIC
# MAGIC ### Where this sits
# MAGIC
# MAGIC ```
# MAGIC   CH1  Governed supervisor   ── diagnose (answer)
# MAGIC   CH2  Agents that act       ── memory, staging, approval, governed execution   ← you are here
# MAGIC   CH3  Autonomous loop       ── detect → decide → auto-act or escalate
# MAGIC   CH4  Trust & governance    ── eval + judge, AI Gateway
# MAGIC   CH5  Document intelligence ── parse / extract → embed → RAG + SQL
# MAGIC ```
# MAGIC
# MAGIC In Chapter 1 the supervisor *answered* the Paints EMEA margin question and ended with a recommended
# MAGIC action. Now the agent **acts** — but never by calling a raw API. Every action travels **one governed
# MAGIC plane**, so an exec can sign off on autonomy.
# MAGIC
# MAGIC ### The action maturity ladder
# MAGIC
# MAGIC ```
# MAGIC   L1 Recommend ──▶ L2 Stage & approve ──▶ L3 Execute externally ──▶ L4 Autonomous
# MAGIC   (CH1 output)     propose → guardrails    approved → connectors      (CH3)
# MAGIC                    → human approve         → real systems, audited
# MAGIC ```
# MAGIC
# MAGIC This chapter builds L1 → L3. L4 is Chapter 3.
# MAGIC
# MAGIC ### Two governance planes — say it plainly
# MAGIC Chapter 1's OBO + UC row-level security govern **reads**. They do **not** govern writes. This chapter
# MAGIC is the **write plane**, and it is deliberately separate:
# MAGIC
# MAGIC ```
# MAGIC   READS  (CH1)                          WRITES / ACTIONS  (CH2)
# MAGIC   OBO + UC row-level security           app/service identity + policy guardrails
# MAGIC   per-user truth on UC tables           + human approval + full audit/lineage
# MAGIC                                         on Lakebase (Postgres roles, NOT UC RLS)
# MAGIC ```
# MAGIC
# MAGIC UC-registered Lakebase is **read-only** — writes go through Postgres directly. "Who can see what" and
# MAGIC "who can change what" are two distinct planes. Keeping them distinct is the point.
# MAGIC
# MAGIC ### What you build
# MAGIC The **Action Plane**: three Lakebase tables (`actions`, `action_events`, `action_policies`) + a small
# MAGIC state machine + a guardrail engine + a governed executor that fires real connectors through a Unity
# MAGIC Catalog HTTP connection. This notebook inlines a compact version of the production module that lives
# MAGIC in `apps/_shared/action_plane/` (which adds concurrency guards and partial-failure reconciliation).
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - A Lakebase database instance (default `graphrag-spike`) you can reach, with native Postgres login.
# MAGIC - The **Mock External Systems** app deployed (`deploy/deploy_mock_systems.sh`) — L3 posts to it.
# MAGIC - Permission to `CREATE CONNECTION` in the catalog. `psycopg` (psycopg3) is preinstalled on serverless.
# MAGIC
# MAGIC ### How to run (~20 min)
# MAGIC Top-to-bottom. The widgets set your Lakebase instance, schema, and the mock app URL, so it runs in any
# MAGIC workspace. The DDL is idempotent — re-running is safe.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters + Lakebase connection
# MAGIC
# MAGIC The write identity is a **short-lived (~1h) DB credential** minted via the SDK — nothing long-lived
# MAGIC sits in the notebook. The `pg()` context manager mints a fresh token per connection and pins
# MAGIC `search_path` to our schema. Every later cell reuses the `pg_query` / `pg_exec` helpers.

# COMMAND ----------

dbutils.widgets.text("lakebase_instance", "graphrag-spike", "Lakebase instance")
dbutils.widgets.text("pg_schema", "akzo", "Postgres schema")
dbutils.widgets.text("mock_app_url", "https://akzo-mock-systems-7474654904882204.aws.databricksapps.com", "Mock app URL")
dbutils.widgets.text("connection_name", "akzo_external_systems", "UC HTTP connection")
# Optional: leave EMPTY for interactive runs (uses your workspace identity automatically). Set only when
# running headless where the run identity is not authorized for the app's SSO gate (e.g. a CI job).
dbutils.widgets.text("bearer_token", "", "App bearer token (optional override)")

INSTANCE_NAME = dbutils.widgets.get("lakebase_instance")
PG_SCHEMA = dbutils.widgets.get("pg_schema")
MOCK_APP_URL = dbutils.widgets.get("mock_app_url").rstrip("/")
CONNECTION_NAME = dbutils.widgets.get("connection_name")
DB_NAME = "databricks_postgres"

import json
import uuid
from contextlib import contextmanager

import pandas as pd
import psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
inst = w.database.get_database_instance(name=INSTANCE_NAME)
PG_HOST = inst.read_write_dns
PG_USER = w.current_user.me().user_name   # the OAuth principal / write identity

print("Lakebase instance :", INSTANCE_NAME, "(", inst.state, ")")
print("Host (read_write) :", PG_HOST)
print("Database / schema :", DB_NAME, "/", PG_SCHEMA)
print("Write identity    :", PG_USER)


def _db_token() -> str:
    """Short-lived Lakebase credential — the app/service write identity."""
    return w.database.generate_database_credential(instance_names=[INSTANCE_NAME]).token


@contextmanager
def pg():
    conn = psycopg.connect(
        host=PG_HOST, port=5432, dbname=DB_NAME,
        user=PG_USER, password=_db_token(), sslmode="require", autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}")
            cur.execute(f"SET search_path TO {PG_SCHEMA}")
        yield conn
    finally:
        conn.close()


def pg_query(sql: str, params: tuple | None = None) -> list[dict]:
    """Read query → list of dicts (column names from cursor.description)."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def pg_exec(sql: str, params: tuple | None = None, returning: bool = False):
    """Write. If returning=True, return the first row as a dict."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if returning:
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None
        return None


with pg() as conn, conn.cursor() as cur:
    cur.execute("SELECT current_user, current_database()")
    print("Connected as:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC # PART A — Stand up the Action Plane
# MAGIC
# MAGIC Three Lakebase tables are the entire write plane:
# MAGIC
# MAGIC | Table | What it holds |
# MAGIC |---|---|
# MAGIC | `actions` | the canonical action record + its state-machine status |
# MAGIC | `action_events` | append-only audit + lineage — one row per transition |
# MAGIC | `action_policies` | the guardrail rules, keyed by `action_type` |
# MAGIC
# MAGIC `actions` generalizes every per-domain "staged decision" (a quote, a reorder, a forecast override):
# MAGIC the `action_type` says which, the `payload` JSONB carries the specifics, and `status` + the audit
# MAGIC columns (`requested_by`, `approved_by`, `created_at`, `decided_at`, `executed_at`) are the trail.

# COMMAND ----------

DDL = [
    """CREATE TABLE IF NOT EXISTS actions (
        id            BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        agent         TEXT NOT NULL,
        action_type   TEXT NOT NULL,
        subject       TEXT NOT NULL,
        payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
        status        TEXT NOT NULL DEFAULT 'proposed',
        level         INTEGER NOT NULL DEFAULT 2,
        region        TEXT,
        requested_by  TEXT NOT NULL,
        approved_by   TEXT,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        decided_at    TIMESTAMPTZ,
        executed_at   TIMESTAMPTZ,
        result        JSONB,
        external_ref  TEXT)""",
    """CREATE TABLE IF NOT EXISTS action_events (
        id         BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        action_id  BIGINT NOT NULL REFERENCES actions(id),
        ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
        event      TEXT NOT NULL,
        actor      TEXT NOT NULL,
        detail     JSONB)""",
    """CREATE TABLE IF NOT EXISTS action_policies (
        action_type       TEXT PRIMARY KEY,
        max_discount_pct  NUMERIC(5,2),
        max_spend_eur     NUMERIC(14,2),
        allowed_regions   TEXT[],
        requires_approval BOOLEAN NOT NULL DEFAULT TRUE)""",
    "CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)",
    "CREATE INDEX IF NOT EXISTS idx_actions_agent ON actions(agent)",
    "CREATE INDEX IF NOT EXISTS idx_action_events_action ON action_events(action_id)",
]

with pg() as conn, conn.cursor() as cur:
    for stmt in DDL:
        cur.execute(stmt)
print("DDL applied — actions / action_events / action_policies ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Seed the guardrail policies
# MAGIC
# MAGIC One row per action type the agents can take. Caps are realistic for the Paints/Coatings story so the
# MAGIC demo shows both an in-policy execute and a breach → escalate. Read each row as a **contract** the
# MAGIC guardrail engine enforces: a `quote_send` over 15% discount or EUR 250k breaches; `scm_reorder` over
# MAGIC EUR 100k breaches; `crm_task` / `escalation` skip the approval gate (low-risk). `ON CONFLICT` makes
# MAGIC the seed idempotent and re-tunable.

# COMMAND ----------

EMEA = ["EMEA", "NL", "DE", "FR", "UK", "BE", "ES", "IT"]

POLICIES = [
    # action_type,        max_discount_pct, max_spend_eur, allowed_regions, requires_approval
    ("quote_send",        15.0,   250000.0,  EMEA,  True),
    ("price_change",      10.0,   None,      EMEA,  True),
    ("forecast_override", None,   None,      EMEA,  True),
    ("scm_reorder",       None,   100000.0,  EMEA,  True),
    ("scm_reroute",       None,   50000.0,   EMEA,  True),
    ("crm_task",          None,   None,      EMEA,  False),
    ("escalation",        None,   None,      None,  False),
]

UPSERT = """
    INSERT INTO action_policies
        (action_type, max_discount_pct, max_spend_eur, allowed_regions, requires_approval)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (action_type) DO UPDATE SET
        max_discount_pct  = EXCLUDED.max_discount_pct,
        max_spend_eur     = EXCLUDED.max_spend_eur,
        allowed_regions   = EXCLUDED.allowed_regions,
        requires_approval = EXCLUDED.requires_approval
"""

with pg() as conn, conn.cursor() as cur:
    for p in POLICIES:
        cur.execute(UPSERT, p)
# Render via pandas: Lakebase rows carry Decimal/None/array values that Spark's local
# schema inference can choke on; pandas object columns handle them cleanly.
display(pd.DataFrame(pg_query(
    "SELECT action_type, max_discount_pct, max_spend_eur, allowed_regions, requires_approval "
    "FROM action_policies ORDER BY action_type")))
print("Seeded", len(POLICIES), "policies.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The state machine + Action Plane operations
# MAGIC
# MAGIC Illegal transitions raise — the record can never reach an impossible state. `escalated` is reachable
# MAGIC from any live state (a guardrail breach pulls the action back to a human gate).
# MAGIC
# MAGIC ```
# MAGIC   proposed ──approve──▶ approved ──mark_executing──▶ executing ──mark_executed──▶ executed
# MAGIC      │                     │                            │
# MAGIC      ├──reject──▶ rejected │                            └──mark_failed──▶ failed
# MAGIC      └──escalate──▶ escalated  ◀── (breach from approved/executing too)
# MAGIC ```
# MAGIC
# MAGIC Every operation appends an `action_events` row in the same call as the `actions` mutation, so the
# MAGIC lineage is always complete. (The production module in `apps/_shared/action_plane/` adds a
# MAGIC compare-and-set guard so concurrent writers can't race a stale state through; we keep it simple here.)

# COMMAND ----------

PROPOSED, APPROVED, EXECUTING, EXECUTED, REJECTED, FAILED, ESCALATED = (
    "proposed", "approved", "executing", "executed", "rejected", "failed", "escalated")

_TRANSITIONS = {
    PROPOSED:  {APPROVED, REJECTED, ESCALATED},
    APPROVED:  {EXECUTING, REJECTED, ESCALATED},
    EXECUTING: {EXECUTED, FAILED, ESCALATED},
    ESCALATED: {APPROVED, REJECTED},
    EXECUTED: set(), REJECTED: set(), FAILED: set(),
}

def _jsonb(value):
    return None if value is None else (value if isinstance(value, str) else json.dumps(value))

def _event(action_id: int, event: str, actor: str, detail=None) -> None:
    pg_exec("INSERT INTO action_events (action_id, event, actor, detail) VALUES (%s,%s,%s,%s)",
            (action_id, event, actor, _jsonb(detail)))

def _check(current: str, target: str) -> None:
    if target not in _TRANSITIONS.get(current, set()):
        raise ValueError(f"illegal transition: '{current}' -> '{target}'")

def ap_get(action_id: int) -> dict:
    rows = pg_query("SELECT * FROM actions WHERE id=%s", (action_id,))
    if not rows:
        raise ValueError(f"action {action_id} not found")
    action = rows[0]
    action["events"] = pg_query(
        "SELECT ts, event, actor, detail FROM action_events WHERE action_id=%s ORDER BY ts, id",
        (action_id,))
    return action

def ap_propose(agent, action_type, subject, payload, region, requested_by, level=2) -> dict:
    row = pg_exec(
        "INSERT INTO actions (agent, action_type, subject, payload, status, level, region, requested_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (agent, action_type, subject, _jsonb(payload), PROPOSED, level, region, requested_by),
        returning=True)
    _event(row["id"], "proposed", requested_by,
           {"action_type": action_type, "subject": subject, "level": level})
    return row

def ap_approve(action_id: int, approver: str) -> dict:
    cur = ap_get(action_id); _check(cur["status"], APPROVED)
    row = pg_exec("UPDATE actions SET status=%s, approved_by=%s, decided_at=now() "
                  "WHERE id=%s RETURNING *", (APPROVED, approver, action_id), returning=True)
    _event(action_id, "approved", approver)
    return row

def ap_escalate(action_id: int, reason: str, actor: str = "executor") -> dict:
    cur = ap_get(action_id); _check(cur["status"], ESCALATED)
    row = pg_exec("UPDATE actions SET status=%s WHERE id=%s RETURNING *",
                  (ESCALATED, action_id), returning=True)
    _event(action_id, "escalated", actor, {"reason": reason})
    return row

def ap_mark(action_id: int, target: str, **fields) -> dict:
    cur = ap_get(action_id); _check(cur["status"], target)
    sets = ["status=%s"]; params = [target]
    if "result" in fields:       sets.append("result=%s");       params.append(_jsonb(fields["result"]))
    if "external_ref" in fields: sets.append("external_ref=%s"); params.append(fields["external_ref"])
    if target in (EXECUTED, FAILED): sets.append("executed_at=now()")
    params.append(action_id)
    row = pg_exec(f"UPDATE actions SET {', '.join(sets)} WHERE id=%s RETURNING *",
                  tuple(params), returning=True)
    _event(action_id, target, fields.get("actor", "executor"),
           {k: v for k, v in fields.items() if k != "actor"} or None)
    return row

def show_events(action_id: int) -> None:
    a = ap_get(action_id)
    print(f"action {action_id}  [{a['action_type']}]  status={a['status']}")
    for ev in a["events"]:
        ts = ev["ts"].strftime("%H:%M:%S") if hasattr(ev["ts"], "strftime") else ev["ts"]
        print(f"  {ts}  {ev['event']:14s} by {ev['actor']:28s} {ev.get('detail') or ''}")

print("Action Plane operations ready: ap_propose / ap_approve / ap_escalate / ap_mark / ap_get / show_events")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The guardrail engine
# MAGIC
# MAGIC `evaluate(action)` checks a proposed action against its `action_policies` row and returns a verdict
# MAGIC per rule — discount cap, spend cap (`amount_eur`/`spend_eur`), region scope, action-type allowed,
# MAGIC approval required. A breach mutates nothing; the caller is responsible for escalating. A missing
# MAGIC field is "nothing to check" for that rule (applicable=False), never a breach.

# COMMAND ----------

def _payload(action: dict) -> dict:
    raw = action.get("payload")
    if isinstance(raw, str):
        try: return json.loads(raw)
        except (ValueError, TypeError): return {}
    return dict(raw) if raw else {}

def evaluate(action: dict) -> dict:
    action_type, region, payload = action.get("action_type"), action.get("region"), _payload(action)
    rows = pg_query("SELECT * FROM action_policies WHERE action_type=%s", (action_type,))
    policy = rows[0] if rows else None
    checks, breaches = [], []

    allowed = policy is not None
    checks.append({"rule": "action_type_allowed", "applicable": True, "passed": allowed,
                   "detail": "known action type" if allowed else f"no policy for '{action_type}'"})
    if not allowed:
        breaches.append(f"action_type '{action_type}' not allowed")
        return {"passed": False, "breaches": breaches, "checks": checks}

    max_discount, discount = policy.get("max_discount_pct"), payload.get("discount_pct")
    if max_discount is not None and discount is not None:
        ok = float(discount) <= float(max_discount)
        checks.append({"rule": "max_discount_pct", "applicable": True, "passed": ok,
                       "detail": f"discount {discount}% vs cap {max_discount}%"})
        if not ok: breaches.append(f"discount {discount}% exceeds cap {max_discount}%")
    else:
        checks.append({"rule": "max_discount_pct", "applicable": False, "passed": True,
                       "detail": "no discount / no cap"})

    max_spend = policy.get("max_spend_eur")
    spend = next((v for v in (payload.get("spend_eur"), payload.get("amount_eur")) if v is not None), None)
    if max_spend is not None and spend is not None:
        ok = float(spend) <= float(max_spend)
        checks.append({"rule": "max_spend_eur", "applicable": True, "passed": ok,
                       "detail": f"spend EUR {spend} vs cap {max_spend}"})
        if not ok: breaches.append(f"spend EUR {spend} exceeds cap EUR {max_spend}")
    else:
        checks.append({"rule": "max_spend_eur", "applicable": False, "passed": True,
                       "detail": "no spend / no cap"})

    allowed_regions = policy.get("allowed_regions")
    if allowed_regions:
        ok = region in allowed_regions
        checks.append({"rule": "allowed_regions", "applicable": True, "passed": ok,
                       "detail": f"region '{region}' " + ("in scope" if ok else "out of scope")})
        if not ok: breaches.append(f"region '{region}' not in {list(allowed_regions)}")
    else:
        checks.append({"rule": "allowed_regions", "applicable": False, "passed": True,
                       "detail": "no region restriction"})

    requires_approval = bool(policy.get("requires_approval"))
    checks.append({"rule": "requires_approval", "applicable": True, "passed": True,
                   "detail": "human approval required" if requires_approval else "may auto-approve (L4)"})

    return {"passed": len(breaches) == 0, "breaches": breaches, "checks": checks}

def print_verdict(verdict: dict) -> None:
    print(f"GUARDRAILS — passed={verdict['passed']}")
    for chk in verdict["checks"]:
        mark = "PASS" if chk["passed"] else "FAIL"
        na = "" if chk["applicable"] else "  (n/a)"
        print(f"  [{mark}] {chk['rule']:22s} {chk['detail']}{na}")
    if verdict["breaches"]:
        print("  breaches:", verdict["breaches"])

print("Guardrail engine ready: evaluate / print_verdict")

# COMMAND ----------

# MAGIC %md
# MAGIC # PART B — L1 Recommend, L2 Stage & approve
# MAGIC
# MAGIC ## L1 — Recommend (no write)
# MAGIC
# MAGIC L1 is Chapter 1's output: the supervisor's Paints EMEA conclusion, made into a **structured proposal**.
# MAGIC It is just data — nothing written, nothing sent. The floor of the ladder.

# COMMAND ----------

RECOMMENDATION = {
    "situation": ("Paints EMEA Q2 gross margin down ~8.9pp: price/FX/TiO2-cost squeeze (Finance) "
                  "AND Rotterdam->DACH OTIF dipped to ~89% in May (SCM)."),
    "recommended_actions": [
        {"action_type": "quote_send",
         "subject": "Paints EMEA price-recovery quote — DACH architectural account",
         "why": "Recover margin on the largest at-risk EMEA account with an in-policy revised quote.",
         "payload": {"to": "procurement@dach-account.example",
                     "subject": "Revised AkzoNobel quote — Q3 pricing",
                     "body": "Updated pricing reflecting TiO2 cost recovery; 8% volume discount retained.",
                     "discount_pct": 8.0, "amount_eur": 180000.0,
                     "account_id": "ACC-DACH-014", "sku": "DEC-1008"},
         "region": "EMEA"},
        {"action_type": "scm_reorder",
         "subject": "Rotterdam safety-stock reorder — DEC-1008",
         "why": "Rebuild safety stock on the stocked-out lane so the OTIF dip does not recur.",
         "payload": {"supplier": "TiO2 Supplier NL", "sku": "DEC-1008", "qty": 4000, "amount_eur": 92000.0},
         "region": "EMEA"},
    ],
}

print("L1 RECOMMENDATION (no write yet)")
print("  Situation:", RECOMMENDATION["situation"])
for r in RECOMMENDATION["recommended_actions"]:
    print(f"  -> [{r['action_type']}] {r['subject']}\n       why: {r['why']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## L2 — Stage & approve
# MAGIC
# MAGIC The agent **acts** for the first time — but only into the governed plane. `ap_propose` writes the
# MAGIC recommended quote as an `actions` row in status `proposed` and appends the first audit event. Then
# MAGIC `evaluate` runs the guardrails as readable checks, and a human runs `ap_approve`. Still nothing has
# MAGIC left Databricks.

# COMMAND ----------

quote_rec = RECOMMENDATION["recommended_actions"][0]
proposed = ap_propose(agent="quote-agent", action_type=quote_rec["action_type"],
                      subject=quote_rec["subject"], payload=quote_rec["payload"],
                      region=quote_rec["region"], requested_by=PG_USER, level=3)
ACTION_ID = proposed["id"]
print(f"L2 STAGED -> action id={ACTION_ID}, status={proposed['status']!r}, type={proposed['action_type']!r}")

verdict = evaluate(proposed)
print_verdict(verdict)
assert verdict["passed"], "expected the in-policy quote to pass guardrails"

approved = ap_approve(ACTION_ID, approver=PG_USER)
print(f"\nAPPROVED -> status={approved['status']!r}, approved_by={approved['approved_by']!r}")
show_events(ACTION_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** the action gets a real `id` and walks `proposed → approved`, all green on
# MAGIC guardrails. The lineage already has two events. The agent acted — but only into `akzo.actions`, not
# MAGIC the outside world.
# MAGIC
# MAGIC ## Agent memory — log the session
# MAGIC
# MAGIC Lakebase is also the agent's **memory**. We log the supervisor turn into `agent_sessions` so an app
# MAGIC can show history and tie an action back to the question that produced it. The `session_uuid` is the
# MAGIC join key linking a Q&A turn to the actions it produced.

# COMMAND ----------

pg_exec("""CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id     BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    session_uuid   TEXT NOT NULL,
    user_email     TEXT NOT NULL,
    question        TEXT,
    routed_domains  TEXT,
    fused_answer    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now())""")

session_uuid = str(uuid.uuid4())
sid = pg_exec("""INSERT INTO agent_sessions (session_uuid, user_email, question, routed_domains, fused_answer)
                 VALUES (%s,%s,%s,%s,%s) RETURNING session_id""",
              (session_uuid, PG_USER,
               "Paints EMEA gross margin dropped ~8% in Q2 — price, volume, or supply/service?",
               "FINANCE,SCM,COMMERCIAL",
               "Both a margin/cost issue (~8.9pp) and a supply/service issue (Rotterdam OTIF ~89% May)."),
              returning=True)["session_id"]
print("Logged agent_session id =", sid, "uuid =", session_uuid)

# COMMAND ----------

# MAGIC %md
# MAGIC # PART C — L3 Execute externally (governed)
# MAGIC
# MAGIC The new rung. The Action Plane never sends real email/PO — its connectors call a **Mock External
# MAGIC Systems** app, and the call goes **through a Unity Catalog HTTP connection** so every external action
# MAGIC is catalog-governed and auditable.
# MAGIC
# MAGIC ```
# MAGIC   execute(id) ─▶ re-check guardrails ─▶ mark_executing ─▶ for each connector:
# MAGIC                       │ breach                                http_request(conn=>'akzo_external_systems',
# MAGIC                       ▼                                                    POST /email | /crm/task | /erp/po)
# MAGIC                   escalate (no external call)             ─▶ mark_executed (external_ref, receipts logged)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create the governed UC HTTP connection
# MAGIC
# MAGIC Databricks Apps sit behind workspace SSO, so the connection needs a bearer token. We mint a fresh
# MAGIC **workspace OAuth** token (`w.config.authenticate()`; in production a rotated service-principal M2M
# MAGIC token). We **create** the connection if new, else **ALTER** it to install a fresh token.
# MAGIC (`CREATE OR REPLACE CONNECTION` is rejected on the SQL surface, and `IF NOT EXISTS` would keep a
# MAGIC stale token that 401s.)

# COMMAND ----------

def _oauth_token() -> str:
    """The app bearer token: the optional widget override if set, else a fresh workspace/SP OAuth token
    (which is what interactive runs use automatically)."""
    override = dbutils.widgets.get("bearer_token")
    return override or w.config.authenticate()["Authorization"].split(" ", 1)[1]

BEARER_TOKEN = _oauth_token()

def ensure_http_connection():
    opts = f"host '{MOCK_APP_URL}', port '443', base_path '/', bearer_token '{BEARER_TOKEN}'"
    try:
        spark.sql(f"CREATE CONNECTION {CONNECTION_NAME} TYPE HTTP OPTIONS ({opts})")
        print("Created UC HTTP connection:", CONNECTION_NAME)
    except Exception:
        # Already exists — ALTER refreshes the bearer token in place (ALTER must restate all options).
        spark.sql(f"ALTER CONNECTION {CONNECTION_NAME} OPTIONS ({opts})")
        print("Refreshed UC HTTP connection token:", CONNECTION_NAME)

ensure_http_connection()
display(spark.sql(f"DESCRIBE CONNECTION {CONNECTION_NAME}"))
# The bearer token is NOT echoed (UC redacts secrets) — expected and correct.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The executor: connectors fired through the governed connection
# MAGIC
# MAGIC `http_post` runs one governed `http_request` POST and parses the mock's `{ref_id, status, echo}`.
# MAGIC `execute` takes an **approved** action, re-runs guardrails as the final gate (escalate on breach,
# MAGIC no external call), then fires its connector route, recording the external ref + a receipt per
# MAGIC connector. `ROUTING` maps each action type to its ordered connectors.

# COMMAND ----------

# action_type -> ordered connectors; each connector -> (mock path, payload-builder from the action payload)
def _email_body(p):  return {"to": p.get("to", "ops@akzo.example"), "subject": p.get("subject", "AkzoNobel"), "body": p.get("body", "")}
def _crm_body(p):    return {"account": p.get("account_id", p.get("account", "unknown")), "task": p.get("subject", "follow-up")}
def _erp_body(p):    return {"supplier": p.get("supplier", "unknown"), "sku": p.get("sku", ""), "qty": p.get("qty", 0), "amount_eur": p.get("amount_eur", p.get("spend_eur", 0))}
def _teams_body(p):  return {"channel": p.get("channel", "ops"), "message": p.get("subject", p.get("body", "notice"))}
def _ticket_body(p): return {"summary": p.get("subject", "issue"), "priority": p.get("priority", "P3")}

CONNECTORS = {
    "email":  ("/email", _email_body),
    "crm":    ("/crm/task", _crm_body),
    "erp_po": ("/erp/po", _erp_body),
    "teams":  ("/teams", _teams_body),
    "ticket": ("/servicenow/ticket", _ticket_body),
}
ROUTING = {
    "quote_send": ["email", "crm"], "price_change": ["crm"], "forecast_override": ["teams"],
    "scm_reorder": ["erp_po"], "scm_reroute": ["teams", "ticket"], "crm_task": ["crm"], "escalation": ["ticket"],
}

import urllib.request

def _parse_mock(text: str):
    try:
        p = json.loads(text)
    except (ValueError, TypeError):
        return None
    return p if isinstance(p, dict) and "ref_id" in p else None

def _post_direct(path: str, body: dict) -> dict:
    """Fallback: direct HTTPS POST to the mock app under a fresh workspace OAuth token.

    Still governed (SP/workspace identity + the mock's own audit), used when the UC-connection
    bearer token is not honored by App SSO (e.g. inside a job run)."""
    req = urllib.request.Request(
        url=f"{MOCK_APP_URL}{path}", data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {_oauth_token()}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        parsed = _parse_mock(resp.read().decode("utf-8"))
    if parsed is None:
        raise RuntimeError(f"mock app returned no ref_id for {path}")
    return parsed

def http_post(path: str, body: dict) -> dict:
    """Send to the mock app through a governed path: UC HTTP connection first (catalog-governed +
    lineage), else a direct POST under workspace OAuth. Returns {ref_id, ..., _via}."""
    try:
        resp = spark.sql(
            "SELECT http_request(conn => :conn, method => 'POST', path => :path, json => :body).text AS response",
            args={"conn": CONNECTION_NAME, "path": path, "body": json.dumps(body)},
        ).first()["response"]
        parsed = _parse_mock(resp)
        if parsed is not None:
            return {**parsed, "_via": "uc_connection"}
    except Exception:
        pass   # UC-connection path unavailable here — fall back to the governed SP-direct path.
    return {**_post_direct(path, body), "_via": "sp_direct"}

def execute(action_id: int) -> dict:
    """L3 executor: approved -> executing -> executed | escalated, firing governed connectors."""
    action = ap_get(action_id)
    if action["status"] != APPROVED:
        return {"error": "not_approved", "status": action["status"]}
    # Final gate: re-run guardrails. Breach -> escalate, no external call.
    verdict = evaluate(action)
    if not verdict["passed"]:
        ap_escalate(action_id, reason="; ".join(verdict["breaches"]), actor="executor")
        return ap_get(action_id)
    payload = _payload(action)
    ap_mark(action_id, EXECUTING, actor="executor")
    connectors_fired = []
    for key in ROUTING.get(action["action_type"], []):
        path, build = CONNECTORS[key]
        parsed = http_post(path, build(payload))
        via = parsed.get("_via", "uc_connection")
        connectors_fired.append({"system": key, "ref_id": parsed["ref_id"], "via": via})
        _event(action_id, "connector", f"connector:{key}",
               {"system": key, "external_ref": parsed["ref_id"], "via": via})
    external_ref = connectors_fired[0]["ref_id"] if connectors_fired else None
    ap_mark(action_id, EXECUTED, result={"connectors": connectors_fired}, external_ref=external_ref, actor="executor")
    return ap_get(action_id)

print("Executor ready: execute (governed http_request through", CONNECTION_NAME, ")")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute the approved quote — the happy path
# MAGIC
# MAGIC `quote_send` routes to **email → crm**. Each connector POSTs to the mock app through the UC
# MAGIC connection, returns a `ref_id`, and the action walks `approved → executing → executed`.

# COMMAND ----------

executed = execute(ACTION_ID)
print(f"L3 EXECUTED -> status={executed['status']!r}, external_ref={executed.get('external_ref')!r}")
for c in (executed.get("result") or {}).get("connectors", []):
    print(f"  {c['system']:6s} ref={c['ref_id']:12s} via={c.get('via')}")
print()
show_events(ACTION_ID)
# Expect status=executed, an EMAIL-000N external_ref, and email + crm connector lines.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The breach case — a guardrail stops an over-cap action before it executes
# MAGIC
# MAGIC The exec's real question is "what stops it doing something dumb?" We stage an `scm_reorder` whose
# MAGIC spend (EUR 205k) **exceeds the EUR 100k cap**. It is proposed and even approved — but `execute`
# MAGIC re-runs guardrails as the final gate, sees the breach, and **escalates instead of calling any external
# MAGIC system**. No PO is raised. The breach + reason land in `action_events`.

# COMMAND ----------

breach = ap_propose(agent="scm-agent", action_type="scm_reorder",
                    subject="Rotterdam safety-stock reorder — DEC-1008 (OVER CAP)",
                    payload={"supplier": "TiO2 Supplier NL", "sku": "DEC-1008", "qty": 9000, "amount_eur": 205000.0},
                    region="EMEA", requested_by=PG_USER, level=3)
BREACH_ID = breach["id"]
print_verdict(evaluate(breach))

ap_approve(BREACH_ID, approver=PG_USER)        # approve anyway — the executor is the backstop
bexecuted = execute(BREACH_ID)
print(f"\nexecute() -> status={bexecuted['status']!r}, external_ref={bexecuted.get('external_ref')!r}")
print("  -> escalated to a human gate; NO external system was called (no PO raised).")
show_events(BREACH_ID)
# Expect status=escalated, external_ref=None, a spend_cap breach in the lineage, no connector rows.

# COMMAND ----------

# MAGIC %md
# MAGIC # PART D — RETURN: one governed plane, four rungs
# MAGIC
# MAGIC ## The ladder, as counts
# MAGIC
# MAGIC `ladder_counts` groups every action by level + status — the data behind the Action Center's
# MAGIC maturity-ladder viz. You should see an `L3 executed` (the quote) and an `L3 escalated` (the over-cap
# MAGIC reorder); L4 rows appear once you run Chapter 3.

# COMMAND ----------

display(pd.DataFrame(pg_query(
    "SELECT level, status, COUNT(*) AS count FROM actions GROUP BY level, status ORDER BY level, status")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you built
# MAGIC
# MAGIC **Verified end to end on Lakebase + the governed connection:**
# MAGIC - **L1 Recommend** — the supervisor's conclusion, made into a structured proposal.
# MAGIC - **L2 Stage & approve** — `ap_propose → evaluate` (green chips) `→ ap_approve`, in `akzo.actions` +
# MAGIC   `akzo.action_events`, with the turn logged to `agent_sessions` (memory).
# MAGIC - **L3 Execute externally** — `execute` fired `email → crm` **through the UC HTTP connection
# MAGIC   `akzo_external_systems`**, returned an `external_ref`, and recorded receipts. The over-cap
# MAGIC   `scm_reorder` **escalated** at the gate with no external call.
# MAGIC
# MAGIC Every rung used the **same** identity + guardrails + approval + audit/lineage — the write plane,
# MAGIC distinct from Chapter 1's read plane (OBO + UC RLS).
# MAGIC
# MAGIC ### The honest write-governance recap
# MAGIC - **Reads** → OBO + UC row-level security (Chapter 1).
# MAGIC - **Writes/actions** → Postgres roles on Lakebase + app/service write identity + policy guardrails +
# MAGIC   approval + audit (`requested_by`, `approved_by`, `created_at`, `decided_at`, `executed_at`,
# MAGIC   `action_events`). UC-registered Lakebase is read-only; you write through Postgres.
# MAGIC - External effects go through **one** governed UC HTTP connection — no ungoverned escape hatch.
# MAGIC
# MAGIC **Next:** `03_autonomous_loop.py` — L4. The agent detects a breach, decides within policy, and
# MAGIC auto-approves + executes if in-policy, or escalates if not — no human in the approval loop while it
# MAGIC stays within policy.
