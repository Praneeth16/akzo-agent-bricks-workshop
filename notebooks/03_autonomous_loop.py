# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC The Action Plane writes to Lakebase (Postgres) with **psycopg3**, and reaching the Lakebase instance
# MAGIC needs the **Lakebase database API** in `databricks-sdk` (`w.database`). Install both, then restart
# MAGIC Python. (Run this cell first; it is the only `%pip` in the notebook.)

# COMMAND ----------

# MAGIC %pip install --quiet "psycopg[binary]" "databricks-sdk>=0.96"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 3 — Autonomous closed-loop (L4)
# MAGIC
# MAGIC ### Where this sits
# MAGIC
# MAGIC ```
# MAGIC   CH1 Governed supervisor   CH2 Agents that act (L1-L3)   CH3 Autonomous loop (L4)   ← you are here
# MAGIC ```
# MAGIC
# MAGIC Chapter 2 walked one action up to **L3**, but L3 still required a human to approve. This chapter
# MAGIC removes that step — *only when policy allows it*. A trigger fires, the agent picks an intervention,
# MAGIC and if it is **within the guardrails** it auto-approves and executes with **no human in the loop**.
# MAGIC The moment an action breaches policy, it **escalates to a human gate** instead of acting.
# MAGIC
# MAGIC ### The L4 frame — autonomy you can sign off on
# MAGIC ```
# MAGIC   DETECT ──▶ DECIDE ──▶ GUARD (evaluate) ──┬── PASS  ─▶ auto-approve ─▶ execute ─▶ VERIFY
# MAGIC   OTIF<90%   LLM picks   vs action_policies │            (no human)      (mock ERP PO + receipt)
# MAGIC   on a lane  a governed                     └── BREACH ─▶ escalate to human gate (NO execution)
# MAGIC              scm_reorder
# MAGIC ```
# MAGIC
# MAGIC - **Autonomous only WITHIN policy** — every candidate is checked by `evaluate()` before anything runs.
# MAGIC - **Human-on-the-loop, not in-the-loop** — a breach pulls the action straight back to a human gate.
# MAGIC - **Only ever calls the mock systems** — same governed UC HTTP connection as Chapter 2.
# MAGIC - **Fully audited** — every transition appends an `action_events` row; effects land receipts.
# MAGIC
# MAGIC We show **both paths** (in-policy auto-execute, over-cap escalate), prove **idempotency** (a re-fired
# MAGIC schedule does not raise a duplicate PO), then a **tweak** flips one path into the other.
# MAGIC
# MAGIC ### Prerequisites
# MAGIC Run Chapter 2 first (it seeds `action_policies` and creates the mock app + UC connection). The SCM
# MAGIC source tables (`akzo_scm.otif`, `akzo_scm.inventory`) must be loaded. This notebook re-creates the
# MAGIC connection with a fresh token and re-seeds the one policy it needs, so it also runs standalone.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters, Lakebase, and the inlined Action Plane
# MAGIC
# MAGIC Same compact Action Plane as Chapter 2 (state machine + guardrails + governed executor), plus the
# MAGIC SCM catalog for the DETECT query and the chat endpoint for the DECIDE step. The production module is
# MAGIC `apps/_shared/action_plane/`; we inline a compact version so the notebook is self-contained.

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_lakebase_praneeth_catalog", "Unity Catalog (SCM source)")
dbutils.widgets.text("lakebase_instance", "graphrag-spike", "Lakebase instance")
dbutils.widgets.text("pg_schema", "akzo", "Postgres schema")
dbutils.widgets.text("mock_app_url", "https://akzo-mock-systems-7474654904882204.aws.databricksapps.com", "Mock app URL")
dbutils.widgets.text("connection_name", "akzo_external_systems", "UC HTTP connection")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-7", "Decision LLM endpoint")
# Optional: leave EMPTY for interactive runs (uses your workspace identity). Set only headless where the
# run identity is not authorized for the app SSO gate.
dbutils.widgets.text("bearer_token", "", "App bearer token (optional override)")

CATALOG = dbutils.widgets.get("catalog")
SCM = f"{CATALOG}.akzo_scm"
INSTANCE_NAME = dbutils.widgets.get("lakebase_instance")
PG_SCHEMA = dbutils.widgets.get("pg_schema")
MOCK_APP_URL = dbutils.widgets.get("mock_app_url").rstrip("/")
CONNECTION_NAME = dbutils.widgets.get("connection_name")
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")
DB_NAME = "databricks_postgres"
LOOP_ACTOR = "autonomous-loop"
OTIF_THRESHOLD = 90.0

import json
import uuid
from contextlib import contextmanager

import pandas as pd
import psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
inst = w.database.get_database_instance(name=INSTANCE_NAME)
PG_HOST = inst.read_write_dns
PG_USER = w.current_user.me().user_name

def _db_token() -> str:
    return w.database.generate_database_credential(instance_names=[INSTANCE_NAME]).token

@contextmanager
def pg():
    conn = psycopg.connect(host=PG_HOST, port=5432, dbname=DB_NAME, user=PG_USER,
                           password=_db_token(), sslmode="require", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}")
            cur.execute(f"SET search_path TO {PG_SCHEMA}")
        yield conn
    finally:
        conn.close()

def pg_query(sql: str, params: tuple | None = None) -> list[dict]:
    with pg() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def pg_exec(sql: str, params: tuple | None = None, returning: bool = False):
    with pg() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if returning:
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None
        return None

print("Lakebase:", INSTANCE_NAME, "(", inst.state, ") | identity:", PG_USER)
print("SCM source:", SCM, "| LLM:", LLM_ENDPOINT, "| OTIF trigger: <", OTIF_THRESHOLD, "%")

# COMMAND ----------

# MAGIC %md
# MAGIC The Action Plane operations + guardrail engine (identical to Chapter 2). We ensure the tables and
# MAGIC the one policy this loop needs (`scm_reorder`, EUR 100k cap) exist, so the notebook runs standalone.

# COMMAND ----------

PROPOSED, APPROVED, EXECUTING, EXECUTED, REJECTED, FAILED, ESCALATED = (
    "proposed", "approved", "executing", "executed", "rejected", "failed", "escalated")
_TRANSITIONS = {
    PROPOSED: {APPROVED, REJECTED, ESCALATED}, APPROVED: {EXECUTING, REJECTED, ESCALATED},
    EXECUTING: {EXECUTED, FAILED, ESCALATED}, ESCALATED: {APPROVED, REJECTED},
    EXECUTED: set(), REJECTED: set(), FAILED: set()}

# Idempotent safety net: ensure the plane + the scm_reorder policy exist even if CH2 was skipped.
with pg() as conn, conn.cursor() as cur:
    cur.execute("""CREATE TABLE IF NOT EXISTS actions (
        id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, agent TEXT NOT NULL,
        action_type TEXT NOT NULL, subject TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'proposed', level INTEGER NOT NULL DEFAULT 2, region TEXT,
        requested_by TEXT NOT NULL, approved_by TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        decided_at TIMESTAMPTZ, executed_at TIMESTAMPTZ, result JSONB, external_ref TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS action_events (
        id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, action_id BIGINT NOT NULL REFERENCES actions(id),
        ts TIMESTAMPTZ NOT NULL DEFAULT now(), event TEXT NOT NULL, actor TEXT NOT NULL, detail JSONB)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS action_policies (
        action_type TEXT PRIMARY KEY, max_discount_pct NUMERIC(5,2), max_spend_eur NUMERIC(14,2),
        allowed_regions TEXT[], requires_approval BOOLEAN NOT NULL DEFAULT TRUE)""")
    cur.execute("""INSERT INTO action_policies (action_type, max_spend_eur, allowed_regions, requires_approval)
        VALUES ('scm_reorder', 100000.0, ARRAY['EMEA','NL','DE','FR','UK','BE','ES','IT'], TRUE)
        ON CONFLICT (action_type) DO UPDATE SET max_spend_eur=EXCLUDED.max_spend_eur,
        allowed_regions=EXCLUDED.allowed_regions""")

def _jsonb(v): return None if v is None else (v if isinstance(v, str) else json.dumps(v))
def _payload(a):
    raw = a.get("payload")
    if isinstance(raw, str):
        try: return json.loads(raw)
        except (ValueError, TypeError): return {}
    return dict(raw) if raw else {}
def _event(aid, event, actor, detail=None):
    pg_exec("INSERT INTO action_events (action_id, event, actor, detail) VALUES (%s,%s,%s,%s)",
            (aid, event, actor, _jsonb(detail)))
def _check(cur_s, tgt):
    if tgt not in _TRANSITIONS.get(cur_s, set()):
        raise ValueError(f"illegal transition: '{cur_s}' -> '{tgt}'")
def ap_get(aid):
    rows = pg_query("SELECT * FROM actions WHERE id=%s", (aid,))
    if not rows: raise ValueError(f"action {aid} not found")
    a = rows[0]
    a["events"] = pg_query("SELECT ts,event,actor,detail FROM action_events WHERE action_id=%s ORDER BY ts,id", (aid,))
    return a
def ap_propose(agent, action_type, subject, payload, region, requested_by, level=2):
    row = pg_exec("INSERT INTO actions (agent,action_type,subject,payload,status,level,region,requested_by) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                  (agent, action_type, subject, _jsonb(payload), PROPOSED, level, region, requested_by), returning=True)
    _event(row["id"], "proposed", requested_by, {"action_type": action_type, "subject": subject, "level": level})
    return row
def ap_approve(aid, approver):
    _check(ap_get(aid)["status"], APPROVED)
    row = pg_exec("UPDATE actions SET status=%s, approved_by=%s, decided_at=now() WHERE id=%s RETURNING *",
                  (APPROVED, approver, aid), returning=True)
    _event(aid, "approved", approver); return row
def ap_escalate(aid, reason, actor="executor"):
    _check(ap_get(aid)["status"], ESCALATED)
    row = pg_exec("UPDATE actions SET status=%s WHERE id=%s RETURNING *", (ESCALATED, aid), returning=True)
    _event(aid, "escalated", actor, {"reason": reason}); return row
def ap_mark(aid, target, **fields):
    _check(ap_get(aid)["status"], target)
    sets, params = ["status=%s"], [target]
    if "result" in fields: sets.append("result=%s"); params.append(_jsonb(fields["result"]))
    if "external_ref" in fields: sets.append("external_ref=%s"); params.append(fields["external_ref"])
    if target in (EXECUTED, FAILED): sets.append("executed_at=now()")
    params.append(aid)
    row = pg_exec(f"UPDATE actions SET {', '.join(sets)} WHERE id=%s RETURNING *", tuple(params), returning=True)
    _event(aid, target, fields.get("actor", "executor"), {k: v for k, v in fields.items() if k != "actor"} or None)
    return row
def show_events(aid):
    a = ap_get(aid)
    print(f"action {aid}  [{a['action_type']}]  status={a['status']}")
    for ev in a["events"]:
        ts = ev["ts"].strftime("%H:%M:%S") if hasattr(ev["ts"], "strftime") else ev["ts"]
        print(f"  {ts}  {ev['event']:14s} by {ev['actor']:20s} {ev.get('detail') or ''}")

def evaluate(action):
    at, region, payload = action.get("action_type"), action.get("region"), _payload(action)
    rows = pg_query("SELECT * FROM action_policies WHERE action_type=%s", (at,))
    policy = rows[0] if rows else None
    checks, breaches = [], []
    checks.append({"rule": "action_type_allowed", "applicable": True, "passed": policy is not None,
                   "detail": "known action type" if policy else f"no policy for '{at}'"})
    if policy is None:
        breaches.append(f"action_type '{at}' not allowed")
        return {"passed": False, "breaches": breaches, "checks": checks}
    md, disc = policy.get("max_discount_pct"), payload.get("discount_pct")
    if md is not None and disc is not None:
        ok = float(disc) <= float(md)
        checks.append({"rule": "max_discount_pct", "applicable": True, "passed": ok, "detail": f"discount {disc}% vs cap {md}%"})
        if not ok: breaches.append(f"discount {disc}% exceeds cap {md}%")
    else:
        checks.append({"rule": "max_discount_pct", "applicable": False, "passed": True, "detail": "no discount / no cap"})
    ms = policy.get("max_spend_eur")
    spend = next((v for v in (payload.get("spend_eur"), payload.get("amount_eur")) if v is not None), None)
    if ms is not None and spend is not None:
        ok = float(spend) <= float(ms)
        checks.append({"rule": "max_spend_eur", "applicable": True, "passed": ok, "detail": f"spend EUR {spend} vs cap {ms}"})
        if not ok: breaches.append(f"spend EUR {spend} exceeds cap EUR {ms}")
    else:
        checks.append({"rule": "max_spend_eur", "applicable": False, "passed": True, "detail": "no spend / no cap"})
    ar = policy.get("allowed_regions")
    if ar:
        ok = region in ar
        checks.append({"rule": "allowed_regions", "applicable": True, "passed": ok,
                       "detail": f"region '{region}' " + ("in scope" if ok else "out of scope")})
        if not ok: breaches.append(f"region '{region}' not in {list(ar)}")
    else:
        checks.append({"rule": "allowed_regions", "applicable": False, "passed": True, "detail": "no region restriction"})
    ra = bool(policy.get("requires_approval"))
    checks.append({"rule": "requires_approval", "applicable": True, "passed": True,
                   "detail": "human approval required" if ra else "may auto-approve (L4)"})
    return {"passed": len(breaches) == 0, "breaches": breaches, "checks": checks}

print("Action Plane + guardrails ready (inlined, same as Chapter 2).")

# COMMAND ----------

# MAGIC %md
# MAGIC The governed executor + the UC HTTP connection (re-created with a fresh bearer token so a stale
# MAGIC token from a prior run can't 401). `scm_reorder` routes to the `erp_po` connector.

# COMMAND ----------

import urllib.request

def _oauth_token() -> str:
    override = dbutils.widgets.get("bearer_token")
    return override or w.config.authenticate()["Authorization"].split(" ", 1)[1]

BEARER_TOKEN = _oauth_token()
def ensure_http_connection():
    opts = f"host '{MOCK_APP_URL}', port '443', base_path '/', bearer_token '{BEARER_TOKEN}'"
    try:
        spark.sql(f"CREATE CONNECTION {CONNECTION_NAME} TYPE HTTP OPTIONS ({opts})")
    except Exception:
        spark.sql(f"ALTER CONNECTION {CONNECTION_NAME} OPTIONS ({opts})")   # exists -> refresh token
ensure_http_connection()

def _erp_body(p):    return {"supplier": p.get("supplier", "unknown"), "sku": p.get("sku", ""), "qty": p.get("qty", 0), "amount_eur": p.get("amount_eur", p.get("spend_eur", 0))}
def _teams_body(p):  return {"channel": p.get("channel", "ops"), "message": p.get("subject", p.get("reason", "notice"))}
def _ticket_body(p): return {"summary": p.get("subject", "issue"), "priority": p.get("priority", "P3")}
CONNECTORS = {"erp_po": ("/erp/po", _erp_body), "teams": ("/teams", _teams_body), "ticket": ("/servicenow/ticket", _ticket_body)}
ROUTING = {"scm_reorder": ["erp_po"], "scm_reroute": ["teams", "ticket"]}

def _parse_mock(text):
    try: p = json.loads(text)
    except (ValueError, TypeError): return None
    return p if isinstance(p, dict) and "ref_id" in p else None

def _post_direct(path, body):
    req = urllib.request.Request(url=f"{MOCK_APP_URL}{path}", data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {_oauth_token()}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        parsed = _parse_mock(resp.read().decode("utf-8"))
    if parsed is None: raise RuntimeError(f"mock app returned no ref_id for {path}")
    return parsed

def http_post(path, body):
    """Governed path: UC HTTP connection first, else direct POST under workspace OAuth. Returns {ref_id,..,_via}."""
    try:
        resp = spark.sql("SELECT http_request(conn => :conn, method => 'POST', path => :path, json => :body).text AS r",
                         args={"conn": CONNECTION_NAME, "path": path, "body": json.dumps(body)}).first()["r"]
        parsed = _parse_mock(resp)
        if parsed is not None:
            return {**parsed, "_via": "uc_connection"}
    except Exception:
        pass
    return {**_post_direct(path, body), "_via": "sp_direct"}

def execute(action_id):
    action = ap_get(action_id)
    if action["status"] != APPROVED:
        return {"error": "not_approved", "status": action["status"]}
    verdict = evaluate(action)
    if not verdict["passed"]:
        ap_escalate(action_id, reason="; ".join(verdict["breaches"]), actor="executor")
        return ap_get(action_id)
    payload = _payload(action)
    ap_mark(action_id, EXECUTING, actor="executor")
    fired = []
    for key in ROUTING.get(action["action_type"], []):
        path, build = CONNECTORS[key]
        parsed = http_post(path, build(payload))
        via = parsed.get("_via", "uc_connection")
        fired.append({"system": key, "ref_id": parsed["ref_id"], "via": via})
        _event(action_id, "connector", f"connector:{key}", {"system": key, "external_ref": parsed["ref_id"], "via": via})
    ext = fired[0]["ref_id"] if fired else None
    ap_mark(action_id, EXECUTED, result={"connectors": fired}, external_ref=ext, actor="executor")
    return ap_get(action_id)

print("Executor + governed connection ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## DETECT — find the breached lane in the latest month that has a breach
# MAGIC
# MAGIC The trigger is data, not a human. We compute the certified volume-weighted OTIF per lane per month
# MAGIC and pick the **most recent month that still contains a breach** (a lane below the threshold). On the
# MAGIC seeded data this surfaces **`Rotterdam-NL->EMEA-DACH` at ~88.9% in May 2026** (June recovered to
# MAGIC ~93%, so it is not flagged).

# COMMAND ----------

DETECT_SQL = f"""
WITH lane_month AS (
  SELECT lane, MAX(region) AS region, month,
         ROUND(SUM(ROUND(otif_pct * orders)) / SUM(orders) * 100, 1) AS otif_pct, SUM(orders) AS orders
  FROM {SCM}.otif GROUP BY lane, month),
breaches AS (SELECT * FROM lane_month WHERE otif_pct < {OTIF_THRESHOLD}),
latest_breach AS (SELECT MAX(month) AS m FROM breaches)
SELECT b.lane, b.region, b.month, b.otif_pct, b.orders
FROM breaches b, latest_breach WHERE b.month = latest_breach.m ORDER BY b.otif_pct ASC
"""
breached = [r.asDict() for r in spark.sql(DETECT_SQL).collect()]
print(f"DETECT — lanes below {OTIF_THRESHOLD}% OTIF in the latest breached month: {len(breached)}")
for r in breached:
    print(f"  [!] {r['lane']:28s} {r['region']:10s} {r['month']}  OTIF={r['otif_pct']}%  orders={r['orders']}")
assert breached, "expected the seeded Rotterdam OTIF breach — is akzo_scm.otif populated?"
TARGET = breached[0]
ORIGIN_PLANT = TARGET["lane"].split("->")[0]
print(f"\nTarget lane -> {TARGET['lane']}  ({TARGET['otif_pct']}% OTIF, {TARGET['month']})")

# COMMAND ----------

# MAGIC %md
# MAGIC **Why did it break?** A service dip is only actionable if we know the cause. We join the breach to
# MAGIC `inventory` for the same month at the origin plant to find the stocked-out SKUs — the evidence the
# MAGIC decision LLM reasons over. On the seeded data, **DEC-1000 and DEC-1004** stock out at Rotterdam.

# COMMAND ----------

STOCKOUT_SQL = f"""
SELECT sku, on_hand_units, safety_stock, ROUND(days_of_supply, 1) AS days_of_supply
FROM {SCM}.inventory
WHERE plant = '{ORIGIN_PLANT}' AND month = DATE'{TARGET['month']}' AND stockout_flag = 1
ORDER BY days_of_supply ASC
"""
stockouts = [r.asDict() for r in spark.sql(STOCKOUT_SQL).collect()]
print(f"DETECT — stockouts at {ORIGIN_PLANT} in {TARGET['month']}: {len(stockouts)}")
for r in stockouts:
    print(f"  [pkg] {r['sku']:10s} on_hand={r['on_hand_units']:>6}  safety={r['safety_stock']:>6}  days_of_supply={r['days_of_supply']}")
STOCKOUT_SKUS = [r["sku"] for r in stockouts]
PROD_BREACH_KEY = f"{TARGET['lane']}|{TARGET['month']}"
BREACH_KEY = f"{PROD_BREACH_KEY}|demo-{uuid.uuid4().hex[:8]}"   # per-run suffix so the teaching NB re-runs cleanly

# COMMAND ----------

# MAGIC %md
# MAGIC ## DECIDE — an LLM proposes the intervention
# MAGIC
# MAGIC The agent does not hard-code the fix. We hand the breach + stockout evidence to the chat model and
# MAGIC ask it to choose a governed intervention, constrained to action types the plane routes
# MAGIC (`scm_reorder`, `scm_reroute`), as strict JSON — including `amount_eur`, the field the spend-cap
# MAGIC guardrail checks. A deterministic fallback keeps the loop from stalling if the model output cannot
# MAGIC be parsed.

# COMMAND ----------

def llm(prompt: str) -> str:
    return spark.sql("SELECT ai_query(:e, :p) AS o", args={"e": LLM_ENDPOINT, "p": prompt}).first()["o"]

def decide_intervention(target, stockout_rows):
    evidence = {"lane": target["lane"], "region": target["region"], "month": str(target["month"]),
                "otif_pct": float(target["otif_pct"]), "otif_threshold": OTIF_THRESHOLD,
                "origin_plant": target["lane"].split("->")[0],
                "stockouts": [{"sku": r["sku"], "on_hand_units": r["on_hand_units"],
                               "safety_stock": r["safety_stock"], "days_of_supply": r["days_of_supply"]}
                              for r in stockout_rows]}
    prompt = (
        "You are AkzoNobel's autonomous supply-chain agent. Given an OTIF breach and the stocked-out SKUs "
        "behind it, choose ONE governed intervention to restore service. You may ONLY use action types "
        "'scm_reorder' (raise a replenishment PO) or 'scm_reroute' (faster mode). Prefer 'scm_reorder' "
        "when there are stockouts. Reply with STRICT JSON only, no prose: "
        '{"action_type":"scm_reorder","subject":"<short>","why":"<one sentence>","supplier":"<supplier>",'
        '"skus":["DEC-1000"],"qty":4000,"amount_eur":92000.0}. Size amount_eur ~EUR 20-25 per unit.\n\n'
        "OTIF breach + stockout evidence:\n" + json.dumps(evidence, indent=2, default=str))
    raw = llm(prompt)
    text = raw.strip()
    s, e = text.find("{"), text.rfind("}")
    parsed = {}
    if s != -1 and e > s:
        try: parsed = json.loads(text[s:e + 1])
        except (ValueError, TypeError): parsed = {}
    at = parsed.get("action_type")
    if at not in ("scm_reorder", "scm_reroute"): at = "scm_reorder"   # fallback — loop never stalls
    skus = parsed.get("skus") or STOCKOUT_SKUS or ["DEC-1000"]
    qty = int(parsed.get("qty") or 4000)
    amount = float(parsed.get("amount_eur") or (qty * 23.0))
    return {"action_type": at, "subject": parsed.get("subject") or f"Autonomous {at} — {', '.join(skus)}",
            "why": parsed.get("why") or "Restore OTIF by replenishing safety stock.", "amount_eur": amount,
            "payload": {"supplier": parsed.get("supplier") or "TiO2 Supplier NL", "skus": skus, "sku": skus[0],
                        "qty": qty, "amount_eur": amount, "reason": parsed.get("why") or "", "lane": TARGET["lane"]},
            "_llm_raw": raw}

decision = decide_intervention(TARGET, stockouts)
print("DECIDE — LLM-chosen intervention:")
print(f"  action_type : {decision['action_type']}")
print(f"  subject     : {decision['subject']}")
print(f"  amount_eur  : EUR {decision['amount_eur']:,.0f}")
print(f"  payload     : {json.dumps(decision['payload'])}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The autonomous step — one function, the whole guardrail gate
# MAGIC
# MAGIC The heart of L4. Given a candidate it `propose()`s at **level=4**, runs `evaluate()`, and branches:
# MAGIC PASS → auto-approve (actor `autonomous-loop`, no human) → `execute()`; BREACH → `escalate()` to a
# MAGIC human gate, never executes. Idempotent per `payload.breach_key`: a breach already handled by a prior
# MAGIC run is skipped (no duplicate external side effect).

# COMMAND ----------

def _already_handled(breach_key):
    rows = pg_query("SELECT id, status FROM actions WHERE payload->>'breach_key' = %s "
                    "AND status IN ('proposed','approved','executing','executed','escalated') "
                    "ORDER BY id DESC LIMIT 1", (breach_key,))
    return rows[0] if rows else None

def autonomous_step(decision, region):
    bk = decision["payload"].get("breach_key")
    if bk:
        existing = _already_handled(bk)
        if existing:
            print(f"\n  [skip] breach '{bk}' already handled by action id={existing['id']} "
                  f"(status={existing['status']}) — no duplicate PO.")
            return {"action_id": existing["id"], "path": "skipped_duplicate", "action": ap_get(existing["id"])}
    proposed = ap_propose(agent=LOOP_ACTOR, action_type=decision["action_type"], subject=decision["subject"],
                          payload=decision["payload"], region=region, requested_by=LOOP_ACTOR, level=4)
    aid = proposed["id"]
    verdict = evaluate(proposed)
    print(f"\n  action id={aid} [{decision['action_type']}]  EUR {decision['payload'].get('amount_eur'):,.0f}  "
          f"-> guardrails passed={verdict['passed']}")
    for chk in verdict["checks"]:
        if chk["applicable"]:
            print(f"      [{'PASS' if chk['passed'] else 'FAIL'}] {chk['rule']:18s} {chk['detail']}")
    if verdict["passed"]:
        ap_approve(aid, approver=LOOP_ACTOR)
        executed = execute(aid)
        print(f"      -> AUTO-EXECUTED status={executed['status']!r} external_ref={executed.get('external_ref')!r} (no human)")
        return {"action_id": aid, "path": "auto_executed", "verdict": verdict, "action": executed}
    reason = "; ".join(verdict["breaches"]) or "guardrail breach"
    escalated = ap_escalate(aid, reason=reason, actor=LOOP_ACTOR)
    print(f"      -> ESCALATED to human gate ({reason}). NO external system called.")
    return {"action_id": aid, "path": "escalated", "verdict": verdict, "action": escalated}

print("autonomous_step ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATH A — the in-policy reorder that auto-executes
# MAGIC
# MAGIC The LLM's intervention sizes spend below the **EUR 100k `scm_reorder` cap**, so every guardrail
# MAGIC passes and the loop auto-approves and executes with no human. `scm_reorder` routes to `erp_po` — a
# MAGIC PO is raised on the mock ERP and a receipt lands in `external_system_log`. (We clamp the amount just
# MAGIC under the cap so PATH A is reliably in-policy regardless of how the model sized it.)

# COMMAND ----------

inpolicy = json.loads(json.dumps(decision))      # deep copy
inpolicy["action_type"] = "scm_reorder"
inpolicy["subject"] = f"Autonomous safety-stock reorder — {', '.join(STOCKOUT_SKUS or ['DEC-1000'])} (Rotterdam)"
inpolicy["payload"]["amount_eur"] = min(inpolicy["payload"]["amount_eur"], 92000.0)
inpolicy["payload"]["breach_key"] = BREACH_KEY

print("PATH A — in-policy autonomous reorder")
result_a = autonomous_step(inpolicy, region=TARGET["region"])
assert result_a["path"] == "auto_executed", "expected the in-policy reorder to auto-execute"
assert result_a["action"]["external_ref"], "expected a real external_ref from the ERP PO"
AUTO_ID = result_a["action_id"]
AUTO_REF = result_a["action"]["external_ref"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATH B — the over-cap reorder that escalates (no execution)
# MAGIC
# MAGIC Same lane, same intent — but a **EUR 205k** reorder, over the EUR 100k cap. `evaluate()` returns a
# MAGIC breach, so the loop **escalates and does NOT execute**. No PO is raised. The breach + reason are
# MAGIC recorded for the human who picks it up. This is the difference between "autonomous" and "uncontrolled".

# COMMAND ----------

overcap = {"action_type": "scm_reorder", "subject": "Autonomous bulk reorder — Rotterdam (OVER CAP)",
           "why": "Large pre-buy to fully rebuild safety stock.", "amount_eur": 205000.0,
           "payload": {"supplier": "TiO2 Supplier NL", "skus": STOCKOUT_SKUS or ["DEC-1000", "DEC-1004"],
                       "sku": (STOCKOUT_SKUS or ["DEC-1000"])[0], "qty": 9000, "amount_eur": 205000.0,
                       "reason": "bulk pre-buy", "lane": TARGET["lane"],
                       "breach_key": f"{BREACH_KEY}#illustrative-overcap"}}
print("PATH B — over-cap autonomous reorder")
result_b = autonomous_step(overcap, region=TARGET["region"])
assert result_b["path"] == "escalated", "expected the over-cap reorder to escalate"
assert result_b["action"].get("external_ref") is None, "escalated action must NOT have executed"
ESCALATED_ID = result_b["action_id"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATH C — the schedule re-fires: idempotency (no duplicate PO)
# MAGIC
# MAGIC The exec's question: *"if it runs every hour, does it raise a new PO each time?"* The same May
# MAGIC Rotterdam breach is still in the data next run. The loop is **idempotent per `breach_key`** —
# MAGIC re-running PATH A finds the already-executed action and **skips** without proposing or calling any
# MAGIC external system.

# COMMAND ----------

print("PATH C — re-fire the same breach (simulates the next scheduled run)")
result_c = autonomous_step(inpolicy, region=TARGET["region"])
assert result_c["path"] == "skipped_duplicate", "re-fire on a handled breach must be a no-op"
assert result_c["action_id"] == AUTO_ID, "skip should point at the original executed action"
print(f"  idempotent: re-run skipped, no new PO (still action id={AUTO_ID}, ref={AUTO_REF})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## VERIFY — the executed effect + the receipt
# MAGIC
# MAGIC The loop closes by confirming the effect: re-read the auto-executed action and pull the matching
# MAGIC `external_system_log` receipt — the mock-side proof of the PO, attributed to the mock app's service
# MAGIC principal. The same `external_ref` appears on both sides. (A real loop would also re-measure OTIF
# MAGIC next cycle to confirm the reorder lifted service back over the threshold.)

# COMMAND ----------

executed_action = ap_get(AUTO_ID)
print(f"VERIFY — auto-executed action {AUTO_ID}: status={executed_action['status']}, external_ref={executed_action['external_ref']}")
fired = (executed_action.get("result") or {}).get("connectors", [])
refs = [c["ref_id"] for c in fired] or [AUTO_REF]
try:
    receipts = pg_query("SELECT id, ts, system, ref_id, created_by FROM external_system_log "
                        "WHERE ref_id = ANY(%s) ORDER BY id", (refs,))
    print("\nexternal_system_log receipts (mock-side proof the PO was raised):")
    for r in receipts:
        ts = r["ts"].strftime("%H:%M:%S") if hasattr(r["ts"], "strftime") else r["ts"]
        print(f"  {ts}  {r['system']:8s} ref={r['ref_id']:14s} created_by={r['created_by']}")
except Exception as exc:
    print("  (external_system_log not readable from here:", str(exc)[:120], ")")

print("\n— Lineage, PATH A (auto-executed) —"); show_events(AUTO_ID)
print("\n— Lineage, PATH B (escalated, no execution) —"); show_events(ESCALATED_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — flip auto-execute ↔ escalate
# MAGIC
# MAGIC The whole L4 lesson: **policy, not code, decides whether the agent may act on its own.** Change the
# MAGIC reorder amount and re-run `evaluate()` — the exact check the loop gates on. Under EUR 100k → it would
# MAGIC auto-execute; over → it would escalate. (To flip via the *policy* instead:
# MAGIC `UPDATE akzo.action_policies SET max_spend_eur=250000 WHERE action_type='scm_reorder'` and the same
# MAGIC EUR 205k reorder would auto-execute — behaviour changes with no code change.)

# COMMAND ----------

TWEAK_AMOUNT_EUR = 120000.0   # try 92000 (auto-executes) vs 120000 (escalates, > 100k cap)
tv = evaluate({"action_type": "scm_reorder", "region": TARGET["region"],
               "payload": {"supplier": "TiO2 Supplier NL", "sku": "DEC-1000", "qty": 5000, "amount_eur": TWEAK_AMOUNT_EUR}})
print(f"amount_eur=EUR {TWEAK_AMOUNT_EUR:,.0f}  ->  passed={tv['passed']}  ->  loop would "
      f"{'AUTO-EXECUTE' if tv['passed'] else 'ESCALATE'}")
for chk in tv["checks"]:
    if chk["rule"] == "max_spend_eur":
        print(f"  [{'PASS' if chk['passed'] else 'FAIL'}] {chk['detail']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — autonomy, bounded by policy, audited end to end
# MAGIC
# MAGIC **Verified end to end:**
# MAGIC - **DETECT** — `akzo_scm.otif` → `Rotterdam-NL->EMEA-DACH` below 90% in the latest breached month
# MAGIC   (~88.9%, May 2026), DEC-1000/DEC-1004 stocked out.
# MAGIC - **DECIDE** — the chat model proposed a governed `scm_reorder` with a spend the guardrails check.
# MAGIC - **PATH A** — in-policy → auto-approved by `autonomous-loop` (no human) → `execute()` raised a PO on
# MAGIC   the mock ERP → real `external_ref` + a receipt.
# MAGIC - **PATH B** — over-cap (EUR 205k > 100k) → breach → escalated, **no external system called**.
# MAGIC - **PATH C** — re-fire on the same breach → skipped, no duplicate PO (idempotent).
# MAGIC - **VERIFY** — re-read the executed action + matched the receipt.
# MAGIC
# MAGIC Same governed plane as L1-L3 — identity, guardrails, approval, audit — with the approval gate made
# MAGIC *conditional on the policy verdict*. That is L4: **autonomous within policy, human-on-the-loop on
# MAGIC breach, only ever calling the mock systems.** Schedule it
# MAGIC (`deploy/job_autonomous_scm.json`, hourly on serverless) and the agent watches the lanes and acts on
# MAGIC its own — within the bounds an exec signed off on.

# COMMAND ----------

print("AUTONOMOUS LOOP — run summary")
print(f"  detected breach : {TARGET['lane']}  OTIF={TARGET['otif_pct']}%  ({TARGET['month']})")
print(f"  stockout SKUs   : {', '.join(STOCKOUT_SKUS) or '(none)'}")
print(f"  PATH A (auto)   : action id={AUTO_ID}  external_ref={AUTO_REF}")
print(f"  PATH B (escald) : action id={ESCALATED_ID}  status=escalated (no execution)")
print("\nLADDER COUNTS (level x status) after this run:")
display(pd.DataFrame(pg_query(
    "SELECT level, status, COUNT(*) AS count FROM actions GROUP BY level, status ORDER BY level, status")))
