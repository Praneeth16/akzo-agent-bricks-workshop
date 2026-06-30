# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — Finance controlling copilot (variance decomposition -> recommended action)
# MAGIC
# MAGIC *Hackathon track #1. Forkable Day-2 starter — a slim distillation of `L200-capabilities/01_governed_supervisor.py` (Finance leg).*
# MAGIC
# MAGIC A **self-contained, forkable** Finance copilot: a governed **text2SQL** call over
# MAGIC `<catalog>.akzo_finance` (the Akzo Finance Genie-space pattern in code),
# MAGIC a **reasoning step** that turns the numbers into a four-way **price/volume/FX/cost** bridge plus a
# MAGIC recommended action, a **Lakebase write** that stages the recommendation as a saved analysis / forecast
# MAGIC override for human approval, and an **`ai_query` judge** over the 5 golden questions. Reads governed by
# MAGIC OBO/UC; the write governed by app/service identity + approval + audit.
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak -> swap -> extend*. The four `# TODO (Day-2)`
# MAGIC markers are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** Paints EMEA (Decorative Paints x EMEA) gross margin
# MAGIC **39.6% (Q1 2026) -> 30.7% (Q2 2026)** — a **~8.9pp** drop; realized price/unit erodes **34.54 -> 32.73**.
# MAGIC
# MAGIC **Ship target:** a working notebook + a live trace + a Lakebase `forecast_overrides` row. The deployable
# MAGIC React+FastAPI version is the full app at **`apps/finance-copilot/`** (clone, don't author) — this
# MAGIC notebook is the distilled logic behind it.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, schema, models

# COMMAND ----------

import os
CATALOG = os.environ.get("AKZO_CATALOG") or spark.sql("SELECT current_catalog()").first()[0]
FIN = f"{CATALOG}.akzo_finance"
LLM_ENDPOINT = "databricks-claude-opus-4-8"   # text2SQL + reasoning. Swap to "databricks-gpt-5-5" to compare.
JUDGE_ENDPOINT = "databricks-gpt-5-5"          # an independent grader (not marking its own homework)

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql("USE SCHEMA akzo_finance")
print("Finance:", FIN, "| LLM:", LLM_ENDPOINT, "| Judge:", JUDGE_ENDPOINT)

import json, re

def _ai_query(prompt: str, endpoint: str = LLM_ENDPOINT) -> str:
    return spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Finance Genie instructions (the agent's system prompt)
# MAGIC
# MAGIC This is the distilled *Instructions* block from `genie/finance_space.md` — the same text you paste
# MAGIC into the real Genie space. **`# TODO (Day-2) SPRINT 1` lives here.**

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — TWEAK THE INSTRUCTION: edit one CERTIFIED RULE or add one EXAMPLE Q:/SQL: pair
#   to match your tables/persona, then re-run BEAT 1 and watch the generated SQL (and the answer) change.
FINANCE_INSTRUCTIONS = f"""You are the Akzo Finance text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no markdown fences.

TABLES (all under {CATALOG}.akzo_finance):
- products(sku, product_name, product_line['Decorative Paints'|'Performance Coatings'], region['EMEA'|'Americas'|'APAC'|'China'], currency, list_price_eur, standard_cost_eur)
- margin_actuals(sku, region, month DATE, units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct)
- margin_budget(sku, region, month, budget_units, budget_revenue_eur, budget_margin_eur)
- fx_rates(currency['EUR'|'USD'|'GBP'|'CNY'], month, rate_to_eur)
- cost_drivers(sku, region, month, raw_material_cost, freight_cost, energy_cost, overhead)

CERTIFIED RULES (always follow):
- gross_margin_pct = SUM(gross_margin_eur)/SUM(revenue_eur). NEVER average row-level gross_margin_pct.
- "Paints EMEA" := products.product_line='Decorative Paints' AND products.region='EMEA'. Join margin_actuals.sku=products.sku.
- Quarters 2026: Q1 = months 2026-01-01..2026-03-01 ; Q2 = months 2026-04-01..2026-06-01.
- month is a DATE at first-of-month; compare against 'YYYY-MM-01' literals; current month is 2026-06.
- Currency is EUR. Round percentages to 1 decimal in SELECT. Give every selected column a descriptive alias.

EXAMPLE:
Q: "Show Paints EMEA gross margin % by month for 2026."
SQL: SELECT m.month, ROUND(SUM(m.gross_margin_eur)/SUM(m.revenue_eur)*100,1) AS gross_margin_pct
FROM {CATALOG}.akzo_finance.margin_actuals m
JOIN {CATALOG}.akzo_finance.products p ON m.sku=p.sku
WHERE p.product_line='Decorative Paints' AND p.region='EMEA' AND m.month>=DATE'2026-01-01'
GROUP BY m.month ORDER BY m.month;"""

def text2sql(question: str, instructions: str = FINANCE_INSTRUCTIONS) -> str:
    sql = _ai_query(instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def ask_finance(question: str, instructions: str = FINANCE_INSTRUCTIONS):
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    return sql, spark.sql(sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE/ASK: the governed text2SQL call (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC Ask the golden question; the LLM writes governed SQL from the instructions, we run it on serverless.
# MAGIC This is the exact call the supervisor's Finance leg makes.

# COMMAND ----------

sql, df = ask_finance("Why did Paints EMEA gross margin drop in Q2 2026 versus Q1 — show both quarters' margin %?")
display(df)
# Expected: Q1 ~39.6%, Q2 ~30.7% -> ~8.9pp drop.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The structured variance evidence (price / volume / FX / cost)
# MAGIC
# MAGIC The reasoning step needs structured evidence, not one number. This deterministic query pulls the four
# MAGIC drivers for Q1 vs Q2 so the LLM can build the bridge from facts.

# COMMAND ----------

df_decomp = spark.sql(f"""
WITH base AS (
  SELECT CASE WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
              WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    m.units, m.revenue_eur, m.gross_margin_eur,
    c.raw_material_cost, c.freight_cost, c.energy_cost, c.overhead
  FROM {FIN}.margin_actuals m
  JOIN {FIN}.products p ON m.sku = p.sku
  LEFT JOIN {FIN}.cost_drivers c ON c.sku=m.sku AND c.region=m.region AND c.month=m.month
  WHERE p.product_line='Decorative Paints' AND p.region='EMEA'
    AND m.month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
),
fx AS (
  SELECT CASE WHEN month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
              WHEN month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    AVG(rate_to_eur) AS usd_rate
  FROM {FIN}.fx_rates WHERE currency='USD' AND month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
  GROUP BY 1
)
SELECT b.qtr, SUM(b.units) AS units,
  ROUND(SUM(b.revenue_eur)/SUM(b.units),2)            AS price_per_unit_eur,
  ROUND(SUM(b.gross_margin_eur)/SUM(b.revenue_eur)*100,1) AS gross_margin_pct,
  ROUND(SUM(b.raw_material_cost)/SUM(b.units),2)      AS raw_mat_per_unit,
  ROUND(SUM(b.freight_cost)/SUM(b.units),2)           AS freight_per_unit,
  ROUND(SUM(b.energy_cost)/SUM(b.units),2)            AS energy_per_unit,
  ROUND(MAX(fx.usd_rate),4)                           AS usd_rate_to_eur
FROM base b JOIN fx ON fx.qtr=b.qtr
GROUP BY b.qtr ORDER BY b.qtr
""")
display(df_decomp)
# Q1->Q2: price/unit ~34.5 -> ~32.7, raw_mat/unit up ~11.5 -> ~13.4, USD rate 0.926 -> 0.879 (EUR strengthened).

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — REASON: number -> four-way bridge -> recommended action
# MAGIC
# MAGIC The copilot turns the structured numbers into a controller-ready bridge and ONE concrete action,
# MAGIC grounded only in the data (no invented figures).

# COMMAND ----------

evidence = json.dumps([r.asDict() for r in df_decomp.collect()])
recommendation = _ai_query(f"""You are a finance controlling copilot for AkzoNobel coatings.
Verified Paints EMEA (Decorative Paints x EMEA) 2026 data, Q1 vs Q2, as JSON:
{evidence}
FX note: USD rate_to_eur fell ~0.926 (Jan) -> ~0.879 (Jun) — EUR strengthened, a translation headwind.

Task: explain the gross-margin-% change Q1->Q2 as a four-way bridge — PRICE, VOLUME, FX, COST — that
roughly sums to the total margin-% change. Use ONLY the numbers above. Then give ONE concrete recommended
action for the controller. Under 180 words. Format:
- Headline: <one line with the pp drop>
- Price: ...
- Volume: ...
- FX: ...
- Cost: ...
- Recommended action: ...""")
print(recommendation)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ACT: write the recommendation to Lakebase as a forecast override (pending -> approved)
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 2` lives here. The copilot's recommendation is staged as an audited `pending`
# MAGIC row in Lakebase `akzo.forecast_overrides` under the service identity, then a human approves it. Reads
# MAGIC stay governed by OBO; this **write** is governed by Postgres role + approval + audit — a different
# MAGIC plane. The `forecast_overrides` table already exists (created by `L200-capabilities/05_lakebase_memory_action.py`).

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg
from contextlib import contextmanager

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE", "<your-lakebase-instance>")
DB_NAME = "databricks_postgres"
PG_SCHEMA = "akzo"
SERVICE_IDENTITY = "finance-copilot@service"

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

def stage_override(sku, region, month, baseline_units, override_units, reason,
                   created_by=SERVICE_IDENTITY) -> int:
    """ACTION: stage a forecast override as a pending, audited row. Returns override_id."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO forecast_overrides (sku, region, month, baseline_units, override_units, reason, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING override_id""",
            (sku, region, month, baseline_units, override_units, reason, created_by))
        return cur.fetchone()[0]

def approve_override(override_id, approver) -> tuple:
    """APPROVAL FLOW: flip a forecast override pending -> approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE forecast_overrides SET status='approved', approved_by=%s, approved_at=now()
               WHERE override_id=%s AND status='pending' RETURNING status, approved_by, approved_at""",
            (approver, override_id))
        return cur.fetchone()

# COMMAND ----------

# TODO (Day-2) SPRINT 2 — SWAP THE ACTION: change what the copilot stages — e.g. a price-floor review, a
#   margin-recovery target, or a different override magnitude. Re-run and watch the new pending row land.
oid = stage_override(
    sku="DEC-1000", region="EMEA", month="2026-07-01",
    baseline_units=4200, override_units=3600,
    reason="Q2 margin shock (~8.9pp): price erosion + TiO2/resin cost spike + EUR FX headwind. "
           "Trim EMEA July build to protect margin while raw-material contract is re-negotiated.")
print("Wrote forecast_override id =", oid, "(status=pending)")

# A human controller releases it (the agent stages, it does not self-approve).
print("Approve:", approve_override(oid, approver="controller.emea@akzo.example"))

with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT override_id, sku, region, override_units, status, created_by, approved_by, approved_at
                   FROM forecast_overrides WHERE override_id=%s""", (oid,))
    print("Audited override:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — MEASURE: the LLM judge over the 5 golden questions
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 3` lives in `eval.yaml`. Same portable `ai_query` judge as
# MAGIC `L200-capabilities/06_mlflow_eval_judge.py`: the agent answers each golden question from text2SQL + reasoning,
# MAGIC an independent judge scores correctness + groundedness.

# COMMAND ----------

import os, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/finance/eval.yaml"]:
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
        evidence = json.dumps([r.asDict() for r in spark.sql(sql).limit(50).collect()], default=str)
    except Exception as e:
        evidence = f"(SQL failed: {e}). SQL was: {sql}"
    return _ai_query(
        "You are a finance controlling copilot for AkzoNobel coatings. Using ONLY the data below (do not "
        "invent figures), answer the question concisely for a controller. Include the relevant margin %s, "
        "the pp change, the named product line/region, and any price/volume/FX/cost drivers the data "
        f"supports.\nSQL: {sql}\nDATA (rows as JSON): {evidence}\n\nQUESTION: {question}\n\nANSWER:")

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a finance copilot. Score the ANSWER against the EXPECTED FACTS.
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

# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add a golden question to eval.yaml (e.g. a budget-vs-actual
#   variance, or a Performance Coatings comparison) and re-run this cell.
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
# MAGIC The copilot reads governed margin/cost/FX data -> reasons into a four-way bridge + recommended action
# MAGIC -> writes a forecast override to Lakebase -> a human approves -> is graded by the judge.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** edit one `FINANCE_INSTRUCTIONS` rule/example; re-run BEAT 1.
# MAGIC - **Sprint 2 (swap):** change the staged action (`stage_override`); re-run, watch the row land.
# MAGIC - **Sprint 3 (extend):** add a golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Measurable value:** margin-variance root-cause investigation 20-30 min of manual cube slicing ->
# MAGIC 5-10 min copilot answer with a cited four-way price/volume/FX/cost decomposition.
# MAGIC
# MAGIC **Deployable app:** the full React+FastAPI finance copilot lives at **`apps/finance-copilot/`** —
# MAGIC clone and deploy it, don't author it. Upgrade path: point `text2sql` at the real Akzo Finance Genie
# MAGIC space via the Genie Conversation API (the system prompt above is the space's Instructions block).
