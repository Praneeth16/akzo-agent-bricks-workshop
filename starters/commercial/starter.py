# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — Commercial action assistant (churn signals -> next-best-action)
# MAGIC
# MAGIC *Hackathon track #5. Forkable Day-2 starter — a slim distillation of `L200-capabilities/01_governed_supervisor.py` (Commercial leg).*
# MAGIC
# MAGIC A **self-contained, forkable** Commercial assistant: a governed **text2SQL** call over
# MAGIC `<catalog>.akzo_commercial` (the Akzo Commercial Genie-space pattern in
# MAGIC code), a **reasoning step** that ranks at-risk accounts, ties the churn to its upstream cause, and
# MAGIC proposes ONE next-best-action, a **Lakebase write** that stages the save play for human approval, and an
# MAGIC **`ai_query` judge** over the 5 golden questions. Reads governed by OBO/UC; the write governed by
# MAGIC app/service identity + approval + audit.
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak -> swap -> extend*. The four `# TODO (Day-2)`
# MAGIC markers are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** three at-risk EMEA Decorative accounts in Jun 2026 —
# MAGIC **ACC0001 Rhine Valley Decor Distributors (0.865), ACC0002 Benelux PaintPro (0.827), ACC0003 Nordic
# MAGIC Coatings Supply (0.80)** — all churn_score > 0.7, all with rising complaints and negative NPS.
# MAGIC
# MAGIC **Ship target:** a working notebook + a live trace + a Lakebase `commercial_actions` row. The Commercial
# MAGIC leg also ships inside **`apps/supervisor/`** (clone, don't author); this notebook is the distilled logic.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, schema, models

# COMMAND ----------

import os
CATALOG = os.environ.get("AKZO_CATALOG") or spark.sql("SELECT current_catalog()").first()[0]
COM = f"{CATALOG}.akzo_commercial"
LLM_ENDPOINT = "databricks-claude-opus-4-8"   # text2SQL + reasoning. Swap to "databricks-gpt-5-5" to compare.
JUDGE_ENDPOINT = "databricks-gpt-5-5"          # an independent grader

spark.sql(f"USE CATALOG {CATALOG}")
print("Commercial:", COM, "| LLM:", LLM_ENDPOINT, "| Judge:", JUDGE_ENDPOINT)

import json, re

def _ai_query(prompt: str, endpoint: str = LLM_ENDPOINT) -> str:
    return spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Commercial Genie instructions (the agent's system prompt)
# MAGIC
# MAGIC Distilled *Instructions* from `genie/commercial_space.md`. **`# TODO (Day-2) SPRINT 1` lives here.**

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — TWEAK THE INSTRUCTION: edit one CERTIFIED RULE (e.g. the churn_score>0.7
#   threshold) or add one EXAMPLE Q:/SQL: pair, re-run BEAT 1, and watch the generated SQL / answer change.
COM_INSTRUCTIONS = f"""You are the Akzo Commercial text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no fences.

TABLES (all under {CATALOG}.akzo_commercial):
- accounts(account_id, account_name, region['EMEA'|'Americas'|'APAC'|'China'], segment['Architectural'|'Industrial'|'Marine & Protective'|'Automotive Refinish'], industry, owner_rep)
- pipeline(opp_id, account_id, stage, amount_eur, close_month DATE, product_line['Decorative Paints'|'Performance Coatings'])
- sales_actuals(account_id, month DATE, revenue_eur, volume_units, margin_eur)
- churn_signals(account_id, month, churn_score[0-1], last_order_days, complaint_count, nps)

CERTIFIED RULES:
- "at churn risk" := churn_score > 0.7 (evaluate on month=2026-06-01 unless told otherwise).
- "Paints EMEA accounts" := accounts.region='EMEA' AND accounts.segment='Architectural' (Decorative Paints buyers).
- When asked WHY an account is at risk, also return last_order_days, complaint_count, nps and the revenue trend.
- "open pipeline" := pipeline.stage NOT IN ('ClosedWon','ClosedLost').
- month/close_month are first-of-month DATEs; current=2026-06. Round churn_score to 3 decimals, EUR to whole euros.

EXAMPLE:
Q: "Which accounts have churn_score above 0.7 in June 2026?"
SQL: SELECT a.account_id, a.account_name, a.region, a.segment, ROUND(c.churn_score,3) AS churn_score
FROM {CATALOG}.akzo_commercial.churn_signals c
JOIN {CATALOG}.akzo_commercial.accounts a ON c.account_id=a.account_id
WHERE c.month=DATE'2026-06-01' AND c.churn_score>0.7 ORDER BY c.churn_score DESC;"""

def text2sql(question: str, instructions: str = COM_INSTRUCTIONS) -> str:
    sql = _ai_query(instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def ask_commercial(question: str, instructions: str = COM_INSTRUCTIONS):
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    return sql, spark.sql(sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE/ASK: the governed text2SQL call (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC Ask the golden question; the LLM writes governed SQL, we run it on serverless. This is the exact call
# MAGIC the supervisor's Commercial leg makes.

# COMMAND ----------

sql, df_risk = ask_commercial(
    "Which Paints EMEA accounts are at churn risk in June 2026 and why? Include owner_rep, last_order_days, "
    "complaint_count, nps.")
display(df_risk)
# Expected: ACC0001 Rhine Valley Decor Distributors (0.865), ACC0002 Benelux PaintPro (0.827),
# ACC0003 Nordic Coatings Supply (0.800) — all >0.7.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The structured evidence (revenue-at-risk trend + upstream context)
# MAGIC
# MAGIC The reasoner needs the revenue consequence and the link to the upstream service shock.

# COMMAND ----------

risk_rows = [r.asDict() for r in df_risk.collect()]
rev_trend = spark.sql(f"""
  SELECT month, ROUND(SUM(revenue_eur)) AS combined_revenue_eur
  FROM {COM}.sales_actuals WHERE account_id IN ('ACC0001','ACC0002','ACC0003') AND month>=DATE'2026-01-01'
  GROUP BY month ORDER BY month""").collect()

evidence = json.dumps({
    "at_risk_accounts_jun2026": risk_rows,
    "combined_revenue_trend": [r.asDict() for r in rev_trend],
    "upstream_context": "Paints EMEA OTIF/service collapsed in May 2026 (Rotterdam lane, stockouts); these "
                        "are Decorative Paints (Architectural EMEA) buyers.",
}, default=str)
print(evidence)
# Combined revenue falls ~EUR 375k (Jan) -> ~EUR 169k (Jun).

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — REASON: signals -> next-best-action (tied to the real root cause)
# MAGIC
# MAGIC The assistant confirms the at-risk accounts, frames the churn as a DOWNSTREAM consequence of the EMEA
# MAGIC service shock (not pricing), and proposes ONE save play. It recommends; it does not approve discounts.

# COMMAND ----------

com_answer = _ai_query(f"""You are an Akzo Commercial action assistant. Verified governed data (JSON):
{evidence}

Task: in under 170 words, (1) confirm the three at-risk accounts and cite each one's churn_score and the
driving signals; (2) state that the churn is a DOWNSTREAM consequence of the EMEA service/OTIF shock, not a
pricing failure; (3) recommend ONE concrete next-best-action (save play) for the top account's owner rep,
framed around fixing the service issue, and note it would be logged as a commercial_action for human
approval (the assistant recommends, it does not approve discounts or send email). Use ONLY the data above.
Format:
- At-risk accounts: ...
- Root cause: ...
- Next-best-action for ACC0001: ...""")
print(com_answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ACT: write the save play to Lakebase (pending -> approved)
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 2` lives here. The save play is staged as an audited `pending` row in Lakebase
# MAGIC `akzo.commercial_actions` under the service identity, then a human approves it. Reads stay governed by
# MAGIC OBO; this **write** is governed by Postgres role + approval + audit. The `commercial_actions` table
# MAGIC already exists (created by `L200-capabilities/05_lakebase_memory_action.py`).

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg
from contextlib import contextmanager

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE", "<your-lakebase-instance>")
DB_NAME = "databricks_postgres"
PG_SCHEMA = "akzo"
SERVICE_IDENTITY = "commercial-assistant@service"

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

def stage_action(account_id, action_type, detail, owner_rep, created_by=SERVICE_IDENTITY) -> int:
    """ACTION: stage a commercial next-best-action as a pending, audited row. Returns action_id."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO commercial_actions (account_id, action_type, detail, owner_rep, created_by)
               VALUES (%s,%s,%s,%s,%s) RETURNING action_id""",
            (account_id, action_type, detail, owner_rep, created_by))
        return cur.fetchone()[0]

def approve_action(action_id, approver) -> tuple:
    """APPROVAL FLOW: flip a commercial action pending -> approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE commercial_actions SET status='approved', approved_by=%s, approved_at=now()
               WHERE action_id=%s AND status='pending' RETURNING status, approved_by, approved_at""",
            (approver, action_id))
        return cur.fetchone()

# COMMAND ----------

# TODO (Day-2) SPRINT 2 — SWAP THE ACTION: change the action_type / detail / which account it targets (e.g.
#   "retention_outreach" -> "service_recovery_QBR"), re-run, and watch the new pending row land.
aid = stage_action(
    account_id="ACC0001", action_type="retention_outreach",
    detail="Proactive save call for Rhine Valley Decor Distributors (churn 0.865): acknowledge the May "
           "service disruption, confirm restored Rotterdam supply + expedited backorders, offer a service "
           "credit. NOT a price discount — the root cause is service, not pricing.",
    owner_rep="Sofie Maes")
print("Wrote commercial_action id =", aid, "(status=pending)")

# A human sales manager releases it (the assistant stages, it does not self-approve).
print("Approve:", approve_action(aid, approver="sales.manager.emea@akzo.example"))

with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT action_id, account_id, action_type, status, created_by, approved_by, approved_at
                   FROM commercial_actions WHERE action_id=%s""", (aid,))
    print("Audited action:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — MEASURE: the LLM judge over the 5 golden questions
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 3` lives in `eval.yaml`. Same portable `ai_query` judge as
# MAGIC `L200-capabilities/06_mlflow_eval_judge.py`: the agent answers each golden question from text2SQL evidence, an
# MAGIC independent judge scores correctness + groundedness.

# COMMAND ----------

import os, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/commercial/eval.yaml"]:
        if os.path.exists(c):
            return c
    return None

_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else {"golden_questions": []}
QUESTIONS = GOLDEN.get("golden_questions", [])
print("Loaded", len(QUESTIONS), "golden questions from", _p)

# Shared upstream context so the assistant can connect churn to the service root cause (golden q4).
UPSTREAM = ("Context: Paints EMEA OTIF/service collapsed in May 2026 (Rotterdam-NL->EMEA-DACH lane, "
            "stockouts of Decorative SKUs). The at-risk accounts ACC0001-0003 are Architectural EMEA "
            "(Decorative Paints) buyers — their churn is downstream of that service shock, not pricing.")

def agent_answer(question: str) -> str:
    """The agent under test: text2SQL -> run on serverless -> reason over the labeled rows."""
    sql = text2sql(question)
    try:
        ev = json.dumps([r.asDict() for r in spark.sql(sql).limit(50).collect()], default=str)
    except Exception as e:
        ev = f"(SQL failed: {e}). SQL was: {sql}"
    return _ai_query(
        "You are an Akzo Commercial action assistant. Using ONLY the data below (do not invent figures), "
        "answer the question concisely for a sales rep. Cite churn_score and the driving signals "
        f"(last_order_days, complaints, NPS, revenue) where relevant.\n{UPSTREAM}\nSQL: {sql}\n"
        f"DATA (rows as JSON): {ev}\n\nQUESTION: {question}\n\nANSWER:")

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a commercial assistant. Score the ANSWER against the EXPECTED FACTS.
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

# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add a golden question to eval.yaml (e.g. pipeline-at-risk by
#   product line, or a churn-vs-NPS correlation) and re-run this cell.
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
# MAGIC The assistant reads governed churn/sales/pipeline data -> reasons into a ranked at-risk list + a
# MAGIC root-caused next-best-action -> writes a `commercial_action` to Lakebase -> a human approves -> is graded.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** edit one `COM_INSTRUCTIONS` rule/example (e.g. the churn threshold); re-run BEAT 1.
# MAGIC - **Sprint 2 (swap):** change the staged action (`stage_action`); re-run, watch the row land.
# MAGIC - **Sprint 3 (extend):** add a golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Measurable value:** churn-risk account review 30 min of manual CRM/sales-report cross-checking per
# MAGIC account -> 5-10 min ranked at-risk list with root cause and a recommended next action.
# MAGIC
# MAGIC **Deployable app:** the Commercial leg ships inside **`apps/supervisor/`** (clone, don't author).
# MAGIC Upgrade path: point `text2sql` at the real Akzo Commercial Genie space via the Genie Conversation API
# MAGIC (the system prompt above is the space's Instructions block).
