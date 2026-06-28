# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — SCM control-tower copilot (OTIF diagnosis -> recommended intervention)
# MAGIC
# MAGIC *Hackathon track #2. Forkable Day-2 starter — a slim distillation of `notebooks/03_scm_commercial_legs.py` (SCM leg).*
# MAGIC
# MAGIC A **self-contained, forkable** SCM copilot: a governed **text2SQL** call over
# MAGIC `serverless_lakebase_praneeth_catalog.akzo_scm` (the Akzo SCM Genie-space pattern in code), a
# MAGIC **reasoning step** that ties lead-time + stockout + service/backorder evidence into a root cause and
# MAGIC ONE concrete intervention, a **Lakebase write** that stages the intervention for human approval, and an
# MAGIC **`ai_query` judge** over the 5 golden questions. Reads governed by OBO/UC; the write governed by
# MAGIC app/service identity + approval + audit.
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak -> swap -> extend*. The four `# TODO (Day-2)`
# MAGIC markers are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** the `Rotterdam-NL->EMEA-DACH` lane OTIF
# MAGIC **96.0% (Jan-Mar) -> 88.9% (May 2026) -> 93.0% (Jun)** — the disrupted EMEA lane (lead time 5->9 days,
# MAGIC key Decorative SKUs stocked out).
# MAGIC
# MAGIC **Ship target:** a working notebook + a live trace + a Lakebase `scm_interventions` row. There is no
# MAGIC dedicated deployable SCM app — the SCM leg ships inside **`apps/supervisor/`** (clone, don't author);
# MAGIC this notebook is the distilled SCM logic.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, schema, models

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
SCM = f"{CATALOG}.akzo_scm"
LLM_ENDPOINT = "databricks-claude-opus-4-7"   # text2SQL + reasoning. Swap to "databricks-gpt-5-5" to compare.
JUDGE_ENDPOINT = "databricks-gpt-5-5"          # an independent grader

spark.sql(f"USE CATALOG {CATALOG}")
print("SCM:", SCM, "| LLM:", LLM_ENDPOINT, "| Judge:", JUDGE_ENDPOINT)

import json, re

def _ai_query(prompt: str, endpoint: str = LLM_ENDPOINT) -> str:
    return spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## The SCM Genie instructions (the agent's system prompt)
# MAGIC
# MAGIC Distilled *Instructions* from `genie/scm_space.md`. **`# TODO (Day-2) SPRINT 1` lives here.**

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — TWEAK THE INSTRUCTION: edit one CERTIFIED RULE or add one EXAMPLE Q:/SQL: pair
#   (e.g. normalize lead time by transport mode so sea lanes don't dominate), re-run BEAT 1, watch the SQL change.
SCM_INSTRUCTIONS = """You are the Akzo SCM text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no fences.

TABLES (all under serverless_lakebase_praneeth_catalog.akzo_scm):
- otif(plant, region['EMEA'|'Americas'|'APAC'|'China'], lane, sku, month DATE, orders, on_time, in_full, otif_pct)
- inventory(plant, sku, month, on_hand_units, safety_stock, days_of_supply, stockout_flag[1=stockout])
- lanes(lane_id, origin_plant, dest_region, mode['road'|'sea'|'air'], lead_time_days, cost_per_unit)
- service_levels(region, month, service_pct[fraction, 0.906=90.6%], backorder_units)

CERTIFIED RULES:
- OTIF (aggregated) = SUM(ROUND(otif_pct*orders))/SUM(orders). NEVER average otif_pct; weight by orders.
- "Paints EMEA" := region='EMEA' AND sku LIKE 'DEC-%' (Decorative Paints SKUs).
- The narrative EMEA lane is 'Rotterdam-NL->EMEA-DACH'. EMEA plants: Rotterdam-NL, Felling-UK.
- Quarters 2026: Q1=2026-01-01..2026-03-01 ; Q2=2026-04-01..2026-06-01. month is first-of-month DATE; current=2026-06.
- service_pct is a fraction; multiply by 100 only when presenting a percentage. Round percentages to 1 decimal.

EXAMPLE:
Q: "Show monthly OTIF for the Rotterdam-NL->EMEA-DACH lane in 2026."
SQL: SELECT month, ROUND(SUM(ROUND(otif_pct*orders))/SUM(orders)*100,1) AS lane_otif_pct, SUM(orders) AS orders
FROM serverless_lakebase_praneeth_catalog.akzo_scm.otif
WHERE lane='Rotterdam-NL->EMEA-DACH' AND month>=DATE'2026-01-01'
GROUP BY month ORDER BY month;"""

def text2sql(question: str, instructions: str = SCM_INSTRUCTIONS) -> str:
    sql = _ai_query(instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def ask_scm(question: str, instructions: str = SCM_INSTRUCTIONS):
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    return sql, spark.sql(sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE/ASK: the governed text2SQL call (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC Ask the golden question; the LLM writes governed SQL, we run it on serverless. This is the exact call
# MAGIC the supervisor's SCM leg makes.

# COMMAND ----------

sql, df = ask_scm("Show monthly OTIF for the Rotterdam-NL to EMEA-DACH lane in 2026.")
display(df)
# Expected: ~96% Jan-Mar -> 88.9% May -> ~93.0% June: the disrupted EMEA lane.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The structured root-cause evidence (lead time + stockout + service/backorder)
# MAGIC
# MAGIC Deterministic queries that give the reasoner the three pieces of evidence behind the OTIF dip.

# COMMAND ----------

lane_trend = spark.sql(f"""
  SELECT month, ROUND(SUM(ROUND(otif_pct*orders))/SUM(orders)*100,1) AS lane_otif_pct
  FROM {SCM}.otif WHERE lane='Rotterdam-NL->EMEA-DACH' AND month>=DATE'2026-03-01'
  GROUP BY month ORDER BY month""").collect()
stockouts = spark.sql(f"""
  SELECT plant, sku, ROUND(days_of_supply,1) AS days_of_supply
  FROM {SCM}.inventory WHERE month=DATE'2026-05-01' AND stockout_flag=1
    AND plant IN ('Rotterdam-NL','Felling-UK')""").collect()
service = spark.sql(f"""
  SELECT month, ROUND(service_pct*100,1) AS service_pct, backorder_units
  FROM {SCM}.service_levels WHERE region='EMEA' AND month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01'
  ORDER BY month""").collect()

evidence = json.dumps({
    "lane_otif_pct_by_month": [r.asDict() for r in lane_trend],
    "may_stockouts": [r.asDict() for r in stockouts],
    "emea_service_and_backorders": [r.asDict() for r in service],
    "lane_lead_time": "Rotterdam-NL->EMEA-DACH road lane stepped from 5 to 9 days in Q2 2026",
})
print(evidence)
# May stockouts: DEC-1000, DEC-1004 at Rotterdam-NL (days_of_supply ~1). EMEA service 0.906 May, ~2,258 backorders.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — REASON: root cause -> one concrete intervention
# MAGIC
# MAGIC The copilot ties the evidence into a root-cause read plus ONE intervention a planner can action — the
# MAGIC SCM analogue of the finance recommended action. It recommends; it does not execute the reroute.

# COMMAND ----------

scm_answer = _ai_query(f"""You are an Akzo SCM control-tower copilot. Verified governed data (JSON):
{evidence}

Task: in under 160 words, (1) state the root cause of the May 2026 EMEA service drop tying together lead
time, stockout, and the OTIF/service/backorder numbers; (2) recommend ONE concrete intervention for a
supply planner. Use ONLY the numbers above. Note this is a diagnostic copilot — it recommends, it does not
execute the reroute (that is a governed write in the scm_interventions queue). Format:
- Root cause: ...
- Evidence: OTIF ..., stockout ..., service/backorders ...
- Recommended intervention: ...""")
print(scm_answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ACT: write the intervention to Lakebase (pending -> approved)
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 2` lives here. The intervention is staged as an audited `pending` row in
# MAGIC Lakebase `akzo.scm_interventions` under the service identity, then a human approves it. Reads stay
# MAGIC governed by OBO; this **write** is governed by Postgres role + approval + audit. The
# MAGIC `scm_interventions` table already exists (created by `notebooks/05_lakebase_memory_action.py`).

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg
from contextlib import contextmanager

INSTANCE_NAME = "graphrag-spike"
DB_NAME = "databricks_postgres"
PG_SCHEMA = "akzo"
SERVICE_IDENTITY = "scm-copilot@service"

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

def stage_intervention(lane, plant, sku, region, intervention_type, detail, expected_impact,
                       created_by=SERVICE_IDENTITY) -> int:
    """ACTION: stage a recommended SCM intervention as a pending, audited row. Returns intervention_id."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scm_interventions
               (lane, plant, sku, region, intervention_type, detail, expected_impact, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING intervention_id""",
            (lane, plant, sku, region, intervention_type, detail, expected_impact, created_by))
        return cur.fetchone()[0]

def approve_intervention(intervention_id, approver) -> tuple:
    """APPROVAL FLOW: flip an intervention pending -> approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE scm_interventions SET status='approved', approved_by=%s, approved_at=now()
               WHERE intervention_id=%s AND status='pending' RETURNING status, approved_by, approved_at""",
            (approver, intervention_id))
        return cur.fetchone()

# COMMAND ----------

# TODO (Day-2) SPRINT 2 — SWAP THE ACTION: change the intervention_type / detail / expected_impact (e.g.
#   "expedite_reroute" -> "safety_stock_increase"), re-run, and watch the new pending row land.
iid = stage_intervention(
    lane="Rotterdam-NL->EMEA-DACH", plant="Rotterdam-NL", sku="DEC-1000", region="EMEA",
    intervention_type="expedite_reroute",
    detail="Switch DEC-1000/DEC-1004 to air freight for 2 weeks and raise safety stock 20% to absorb the "
           "lead-time blowout (5->9 days).",
    expected_impact="Restore Rotterdam lane OTIF ~89% -> 95%+, clear ~2,258 EMEA backorders.")
print("Wrote scm_intervention id =", iid, "(status=pending)")

# A human planner releases it (the agent stages, it does not self-approve).
print("Approve:", approve_intervention(iid, approver="planner.emea@akzo.example"))

with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT intervention_id, intervention_type, status, created_by, approved_by, approved_at
                   FROM scm_interventions WHERE intervention_id=%s""", (iid,))
    print("Audited intervention:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — MEASURE: the LLM judge over the 5 golden questions
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 3` lives in `eval.yaml`. Same portable `ai_query` judge as
# MAGIC `notebooks/06_mlflow_eval_judge.py`: the agent answers each golden question from text2SQL evidence, an
# MAGIC independent judge scores correctness + groundedness.

# COMMAND ----------

import os, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/scm/eval.yaml"]:
        if os.path.exists(c):
            return c
    return None

_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else {"golden_questions": []}
QUESTIONS = GOLDEN.get("golden_questions", [])
print("Loaded", len(QUESTIONS), "golden questions from", _p)

def agent_answer(question: str) -> str:
    """The agent under test: text2SQL -> run on serverless -> reason over the labeled rows."""
    sql = text2sql(question)
    try:
        ev = json.dumps([r.asDict() for r in spark.sql(sql).limit(50).collect()], default=str)
    except Exception as e:
        ev = f"(SQL failed: {e}). SQL was: {sql}"
    return _ai_query(
        "You are an Akzo SCM control-tower copilot. Using ONLY the data below (do not invent figures), "
        "answer the question concisely for a supply planner. Cite OTIF/service %s, the named lane/plant/SKU, "
        f"and the lead-time/stockout cause where the data supports it.\nSQL: {sql}\nDATA (rows as JSON): {ev}"
        f"\n\nQUESTION: {question}\n\nANSWER:")

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for an SCM copilot. Score the ANSWER against the EXPECTED FACTS.
QUESTION: {question}
EXPECTED FACTS (small wording/number rounding is fine):
{expected_str}
GRADING NOTES: {notes}
ANSWER UNDER TEST:
{answer}
Return ONLY JSON: {{"correctness": <0..1>, "groundedness": <0..1>, "pass": <true|false>, "rationale": "<one sentence>"}}
pass=true only if correctness>=0.6 AND groundedness>=0.6."""
    raw = _ai_query(prompt, endpoint=JUDGE_ENDPOINT).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0) if m else raw)
    except Exception:
        v = {"correctness": 0.0, "groundedness": 0.0, "pass": False, "rationale": "unparseable: " + raw[:150]}
    v["correctness"] = float(v.get("correctness", 0.0)); v["groundedness"] = float(v.get("groundedness", 0.0))
    v["pass"] = bool(v.get("pass", False))
    return v

# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add a golden question to eval.yaml (e.g. a lane cost-per-unit
#   comparison or a multi-region OTIF ranking) and re-run this cell.
n_pass = 0
for q in QUESTIONS:
    v = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), agent_answer(q["question"]))
    n_pass += int(v["pass"])
    print(f"[{q['id']}] pass={v['pass']} corr={v['correctness']:.2f} grnd={v['groundedness']:.2f} — {v['rationale']}")
print(f"\nPASS RATE: {n_pass}/{len(QUESTIONS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole + ship
# MAGIC
# MAGIC The copilot reads governed OTIF/lane/inventory/service data -> reasons into a root cause + one
# MAGIC intervention -> writes a `scm_intervention` to Lakebase -> a human approves -> is graded.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** edit one `SCM_INSTRUCTIONS` rule/example; re-run BEAT 1.
# MAGIC - **Sprint 2 (swap):** change the staged intervention (`stage_intervention`); re-run, watch the row land.
# MAGIC - **Sprint 3 (extend):** add a golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Measurable value:** service-disruption root-cause triage 30-45 min of cross-referencing OTIF, lane,
# MAGIC and inventory reports -> 5-10 min copilot answer linking lead-time, stockout, and service-level evidence.
# MAGIC
# MAGIC **Deployable app:** the SCM leg ships inside **`apps/supervisor/`** (clone, don't author). Upgrade path:
# MAGIC point `text2sql` at the real Akzo SCM Genie space via the Genie Conversation API (the system prompt
# MAGIC above is the space's Instructions block).
