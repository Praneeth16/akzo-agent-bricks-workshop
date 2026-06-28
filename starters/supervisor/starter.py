# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — Supervisor Agent (route Finance / SCM / Commercial + fuse)
# MAGIC
# MAGIC *Hackathon track #3 — the flagship. Forkable Day-2 starter.*
# MAGIC
# MAGIC This is a **self-contained, forkable** distillation of `notebooks/04_supervisor_agent.py`. It is
# MAGIC the working spine of a Multi-Agent Supervisor: an LLM **router** picks which domain legs to call,
# MAGIC each leg is a Genie-style text2SQL call over governed Unity Catalog tables, and an LLM **fuser**
# MAGIC produces one governed answer with a routing trace. It then **writes the session + feedback to
# MAGIC Lakebase** so the supervisor has memory and an eval loop.
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak → swap → extend*, not build-from-zero. The
# MAGIC three `# TODO (Day-2)` markers below are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** the flagship question routes to **Finance + SCM**;
# MAGIC Finance shows Paints EMEA margin **39.6% (Q1) -> 30.7% (Q2)**, SCM shows the **Rotterdam lane OTIF
# MAGIC dip to 88.9% in May** (recovering to 93.0% in June) — the fuse concludes it is *both* a margin/cost
# MAGIC issue *and* a supply/service issue.
# MAGIC
# MAGIC **Ship target:** a working notebook + a live routing trace + a Lakebase session row. The deployable
# MAGIC React+FastAPI version lives at `apps/supervisor/` (clone, don't author).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, models, Lakebase

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
FIN = f"{CATALOG}.akzo_finance"
SCM = f"{CATALOG}.akzo_scm"
COM = f"{CATALOG}.akzo_commercial"
LLM_ENDPOINT = "databricks-claude-opus-4-7"   # router + fuser. Swap to "databricks-gpt-5-5" to compare.

spark.sql(f"USE CATALOG {CATALOG}")
print("Finance    :", FIN)
print("SCM        :", SCM)
print("Commercial :", COM)
print("LLM        :", LLM_ENDPOINT)

import json

# COMMAND ----------

# MAGIC %md
# MAGIC ## The three domain legs (the Genie text2SQL pattern, in code)
# MAGIC
# MAGIC Each leg is a distilled Genie-space instruction block driving an `ai_query` text2SQL call. The
# MAGIC supervisor treats each leg as a **subagent** it can choose to invoke — exactly how a native Agent
# MAGIC Bricks Multi-Agent Supervisor treats a registered Genie space.

# COMMAND ----------

FINANCE_INSTRUCTIONS = """You are the Akzo Finance text-to-SQL agent. Convert the question into ONE Spark SQL query. Output ONLY SQL.
TABLES (serverless_lakebase_praneeth_catalog.akzo_finance):
- products(sku, product_name, product_line['Decorative Paints'|'Performance Coatings'], region, currency, list_price_eur, standard_cost_eur)
- margin_actuals(sku, region, month DATE, units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct)
- fx_rates(currency, month, rate_to_eur)
- cost_drivers(sku, region, month, raw_material_cost, freight_cost, energy_cost, overhead)
RULES: gross_margin_pct=SUM(gross_margin_eur)/SUM(revenue_eur) (never average row-level). "Paints EMEA":=product_line='Decorative Paints' AND region='EMEA', join margin_actuals.sku=products.sku. Q1=2026-01-01..2026-03-01, Q2=2026-04-01..2026-06-01. month is first-of-month DATE; round % to 1 decimal."""

SCM_INSTRUCTIONS = """You are the Akzo SCM text-to-SQL agent. Convert the question into ONE Spark SQL query. Output ONLY SQL.
TABLES (serverless_lakebase_praneeth_catalog.akzo_scm):
- otif(plant, region, lane, sku, month DATE, orders, on_time, in_full, otif_pct)
- inventory(plant, sku, month, on_hand_units, safety_stock, days_of_supply, stockout_flag)
- lanes(lane_id, origin_plant, dest_region, mode, lead_time_days, cost_per_unit)
- service_levels(region, month, service_pct[fraction], backorder_units)
RULES: OTIF=SUM(ROUND(otif_pct*orders))/SUM(orders) (weight by orders, never average). Narrative lane='Rotterdam-NL->EMEA-DACH'. "Paints EMEA":=region='EMEA' AND sku LIKE 'DEC-%'. Q2=2026-04-01..2026-06-01. service_pct is a fraction; round % to 1 decimal."""

COM_INSTRUCTIONS = """You are the Akzo Commercial text-to-SQL agent. Convert the question into ONE Spark SQL query. Output ONLY SQL.
TABLES (serverless_lakebase_praneeth_catalog.akzo_commercial):
- accounts(account_id, account_name, region, segment, industry, owner_rep)
- sales_actuals(account_id, month DATE, revenue_eur, volume_units, margin_eur)
- churn_signals(account_id, month, churn_score[0-1], last_order_days, complaint_count, nps)
RULES: "at churn risk":=churn_score>0.7 (evaluate on 2026-06-01). "Paints EMEA accounts":=region='EMEA' AND segment='Architectural'. month is first-of-month DATE; round churn_score to 3 decimals."""

LEG_INSTRUCTIONS = {"FINANCE": FINANCE_INSTRUCTIONS, "SCM": SCM_INSTRUCTIONS, "COMMERCIAL": COM_INSTRUCTIONS}

# COMMAND ----------

def _ai_query(prompt: str) -> str:
    return spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS out",
        args={"endpoint": LLM_ENDPOINT, "prompt": prompt},
    ).first()["out"]

def text2sql(question: str, instructions: str) -> str:
    sql = _ai_query(instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def call_leg(domain: str, question: str) -> dict:
    """Invoke one domain subagent under the caller's UC identity; return structured rows for the fuser."""
    sql = text2sql(question, LEG_INSTRUCTIONS[domain])
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(50).collect()]
        err = None
    except Exception as e:
        rows, err = [], str(e)[:300]
    return {"domain": domain, "sql": sql, "rows": rows, "error": err}

# COMMAND ----------

# MAGIC %md
# MAGIC ## The router — `# TODO (Day-2)` SPRINT 1 lives here
# MAGIC
# MAGIC The router is one LLM call given the question + a **routing description** (one line per subagent).
# MAGIC In a native MAS this description IS the per-subagent "description" field. **Routing is
# MAGIC configuration, not code** — edit a line and the same question routes differently.

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — SWAP IN YOUR DOMAIN: edit these description lines to match your data/persona.
#   Narrow one and widen another, then re-run BEAT 1 and watch which legs get called change.
#   To add a 4th subagent (e.g. a DOCS/contracts leg): add a line here AND an entry to LEG_INSTRUCTIONS above.
ROUTING_DESCRIPTION = {
    "FINANCE":    "Gross margin, price/realized price per unit, FX translation, COGS / raw-material / freight / energy cost, budget variance. Use for any 'why did margin/price/cost change' question.",
    "SCM":        "OTIF (on-time-in-full), inventory, stockouts, days of supply, transport lanes, lead times, service levels, backorders. Use for supply, service, delivery, or fulfilment questions.",
    "COMMERCIAL": "Customer accounts, churn risk/score, NPS, complaints, sales/revenue by account, pipeline. Use for customer-risk, retention, or account-impact questions.",
}

def build_router_prompt(question: str, descriptions: dict) -> str:
    lines = "\n".join(f"- {d}: {desc}" for d, desc in descriptions.items())
    return f"""You are the routing controller for an AkzoNobel Multi-Agent Supervisor. Registered domain subagents:
{lines}

Decide which subagent(s) are needed to fully answer the user's question. A cross-domain "why" question
often needs several. Output ONLY a JSON object, no prose:
{{"domains": ["FINANCE"|"SCM"|"COMMERCIAL", ...], "reason": "<one sentence per chosen domain>"}}

Question: {question}"""

def route(question: str, descriptions: dict = ROUTING_DESCRIPTION) -> dict:
    raw = _ai_query(build_router_prompt(question, descriptions)).strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    try:
        decision = json.loads(raw)
    except Exception:
        decision = {"domains": ["FINANCE", "SCM", "COMMERCIAL"], "reason": "router parse fallback: " + raw[:200]}
    decision["domains"] = [d for d in decision.get("domains", []) if d in LEG_INSTRUCTIONS]
    return decision

# COMMAND ----------

# MAGIC %md
# MAGIC ## The fuser — one governed answer from the chosen legs

# COMMAND ----------

def fuse(question: str, decision: dict, leg_results: list) -> str:
    evidence = json.dumps(
        {lr["domain"]: {"sql": lr["sql"], "rows": lr["rows"], "error": lr["error"]} for lr in leg_results},
        default=str,
    )
    prompt = f"""You are the AkzoNobel Multi-Agent Supervisor. You consulted these domain subagents and got governed data.
Routing decision: {json.dumps(decision)}
Retrieved evidence (per domain, as JSON): {evidence}

Fuse ONE answer to the user's question using ONLY the numbers above (do not invent figures). If multiple
domains contributed, explicitly connect them rather than listing them separately. End with ONE concrete
recommended action. If the data cannot answer the question, say so. Keep it under 220 words.

User question: {question}"""
    return _ai_query(prompt)

def supervise(question: str, descriptions: dict = ROUTING_DESCRIPTION, verbose: bool = True) -> dict:
    decision = route(question, descriptions)
    if verbose:
        print("ROUTING TRACE")
        print("  domains :", decision["domains"])
        print("  reason  :", decision.get("reason", ""))
        print()
    leg_results = [call_leg(d, question) for d in decision["domains"]]
    if verbose:
        for lr in leg_results:
            tag = "ERR" if lr["error"] else f"{len(lr['rows'])} rows"
            print(f"  [{lr['domain']}] {tag} :: {lr['sql'][:90].replace(chr(10),' ')}...")
        print()
    answer = fuse(question, decision, leg_results)
    return {"question": question, "decision": decision, "legs": leg_results, "answer": answer}

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — the flagship cross-domain question (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC Watch the routing trace, then the fused answer. Expected: routes to **Finance + SCM** (often +
# MAGIC Commercial); fuses the ~8.9pp margin bridge with the Rotterdam OTIF dip.

# COMMAND ----------

FLAGSHIP = "Paints EMEA gross margin dropped ~8% in Q2 2026 — is it price, volume, or a supply/service issue, and what should I do?"

result = supervise(FLAGSHIP)
print("=" * 80)
print("FUSED ANSWER")
print("=" * 80)
print(result["answer"])

# COMMAND ----------

trace_rows = [
    {"domain": lr["domain"], "rows_returned": len(lr["rows"]),
     "error": lr["error"] or "", "generated_sql": lr["sql"]}
    for lr in result["legs"]
]
display(spark.createDataFrame(trace_rows))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lakebase — write the session + feedback (the supervisor's memory)
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 2 lives here. Reads are governed by OBO/UC. **Writes** go through the
# MAGIC app/service identity into Lakebase Postgres (schema `akzo`) — a separate governance plane. We log
# MAGIC each turn into `agent_sessions` so the app can show history and feed the eval loop.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg
from contextlib import contextmanager

INSTANCE_NAME = "graphrag-spike"
DB_NAME = "databricks_postgres"
PG_SCHEMA = "akzo"

w = WorkspaceClient()
inst = w.database.get_database_instance(name=INSTANCE_NAME)
PG_HOST = inst.read_write_dns
PG_USER = w.current_user.me().user_name

@contextmanager
def pg():
    cred = w.database.generate_database_credential(instance_names=[INSTANCE_NAME])
    conn = psycopg.connect(host=PG_HOST, port=5432, dbname=DB_NAME,
                           user=PG_USER, password=cred.token, sslmode="require", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {PG_SCHEMA}")
        yield conn
    finally:
        conn.close()

# COMMAND ----------

# Tables agent_sessions / agent_feedback already exist (created by notebooks/05_lakebase_memory_action.py).
# TODO (Day-2) SPRINT 2 — EXTEND THE ACTION: instead of only logging the session, have the supervisor
#   stage a governed ACTION when the fuse implies one (e.g. write a row to scm_interventions or
#   commercial_actions with status='pending'), then approve it. See starters/forecast for the full
#   write+approve pattern.
import uuid

session_uuid = str(uuid.uuid4())
with pg() as conn, conn.cursor() as cur:
    cur.execute(
        """INSERT INTO agent_sessions (session_uuid, user_email, question, routed_domains, fused_answer)
           VALUES (%s,%s,%s,%s,%s) RETURNING session_id""",
        (session_uuid, PG_USER, FLAGSHIP, ",".join(result["decision"]["domains"]), result["answer"]))
    sid = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO agent_feedback (session_uuid, user_email, rating, comment)
           VALUES (%s,%s,%s,%s)""",
        (session_uuid, PG_USER, 5, "Routed cross-domain and connected margin to the Rotterdam service shock."))
print("Logged agent_session id =", sid, "uuid =", session_uuid, "routed:", result["decision"]["domains"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Eval judge over the 5 golden questions (the trust gate)
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 3 lives in `eval.yaml`. We run the supervisor on each golden question and
# MAGIC grade the fused answer with an independent judge model (`ai_query`-based, portable across MLflow
# MAGIC versions — same pattern as `notebooks/06_mlflow_eval_judge.py`).

# COMMAND ----------

import os, re, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/supervisor/eval.yaml"]:
        if os.path.exists(c):
            return c
    return None

_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else None
# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add your own golden question to eval.yaml (a new cross-domain
#   "why" that should route to >=2 of YOUR swapped-in domains), then re-run this cell and watch the judge.
QUESTIONS = (GOLDEN or {}).get("golden_questions", [])
JUDGE_ENDPOINT = "databricks-gpt-5-5"
print("Loaded", len(QUESTIONS), "golden questions from", _p)

# COMMAND ----------

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a multi-domain supervisor. Score the ANSWER against the EXPECTED FACTS.
QUESTION: {question}
EXPECTED FACTS (small wording/number rounding is fine):
{expected_str}
GRADING NOTES: {notes}
ANSWER UNDER TEST:
{answer}
Return ONLY JSON: {{"correctness": <0..1>, "groundedness": <0..1>, "pass": <true|false>, "rationale": "<one sentence>"}}
pass=true only if correctness>=0.6 AND groundedness>=0.6."""
    raw = spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": JUDGE_ENDPOINT, "p": prompt}).first()["o"].strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0) if m else raw)
    except Exception:
        v = {"correctness": 0.0, "groundedness": 0.0, "pass": False, "rationale": "unparseable: " + raw[:150]}
    v["correctness"] = float(v.get("correctness", 0.0)); v["groundedness"] = float(v.get("groundedness", 0.0))
    v["pass"] = bool(v.get("pass", False))
    return v

n_pass = 0
for q in QUESTIONS:
    ans = supervise(q["question"], verbose=False)["answer"]
    v = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), ans)
    n_pass += int(v["pass"])
    print(f"[{q['id']}] pass={v['pass']} corr={v['correctness']:.2f} grnd={v['groundedness']:.2f} — {v['rationale']}")
print(f"\nPASS RATE: {n_pass}/{len(QUESTIONS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole + ship
# MAGIC
# MAGIC The supervisor reads -> routes -> calls governed legs -> fuses -> logs to Lakebase -> is graded.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** edit `ROUTING_DESCRIPTION` to your domains; watch routing change.
# MAGIC - **Sprint 2 (swap/act):** stage a governed action to Lakebase, not just a session log.
# MAGIC - **Sprint 3 (extend):** add a golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Upgrade path:** register the three Akzo Genie spaces as subagents of an Agent Bricks
# MAGIC Multi-Agent Supervisor; the per-subagent description field IS `ROUTING_DESCRIPTION`. A reference
# MAGIC MAS endpoint `mas-f14da7dc-endpoint` exists in this workspace. **Deployable app:**
# MAGIC `apps/supervisor/` (React+FastAPI; clone, don't author).
