# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — Forecast Planner (actual-vs-budget delta -> proposed override -> Lakebase + approval)
# MAGIC
# MAGIC *Hackathon adjacent track #6 (MMF, Paints EMEA). Forkable Day-2 starter.*
# MAGIC
# MAGIC A **self-contained, forkable** forecast copilot. It reasons over `akzo_finance.margin_actuals`
# MAGIC vs `akzo_finance.margin_budget` (the Paints EMEA actual-vs-budget margin delta), explains the
# MAGIC miss, proposes a forecast override, and **writes the override to Lakebase `akzo.forecast_overrides`
# MAGIC as `pending`**, then flips it `pending -> approved` through the approval helper. Reads are
# MAGIC governed by OBO/UC; the write is governed by the app/service identity + approval + audit (a
# MAGIC separate plane).
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak -> swap -> extend*. The `# TODO (Day-2)`
# MAGIC markers are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** Paints EMEA (Decorative x EMEA) Q2 2026 **actual
# MAGIC margin 30.7% vs budget 39.9% = -9.2pp miss** (Q1 was on-plan at 39.6% vs 39.9%). The budget
# MAGIC assumed no shocks; actuals hit price erosion, FX, and a raw-material spike.
# MAGIC
# MAGIC **Ship target:** a working notebook + a Lakebase `forecast_overrides` row (pending -> approved) +
# MAGIC a live judge run.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, models

# COMMAND ----------

import os
CATALOG = os.environ.get("AKZO_CATALOG") or spark.sql("SELECT current_catalog()").first()[0]
FIN = f"{CATALOG}.akzo_finance"
SCM = f"{CATALOG}.akzo_scm"
LLM_ENDPOINT = "databricks-claude-opus-4-8"   # reasoning. Swap to "databricks-gpt-5-5" to compare.

spark.sql(f"USE CATALOG {CATALOG}")
print("Finance:", FIN, "| SCM:", SCM, "| LLM:", LLM_ENDPOINT)

import json

def _ai_query(prompt: str, endpoint: str = LLM_ENDPOINT) -> str:
    return spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: the actual-vs-budget delta (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC The forecast planner's core signal: **actual margin vs budget (plan) margin** for Paints EMEA by
# MAGIC quarter. The Q2 gap is the forecast miss the override has to address.

# COMMAND ----------

df_delta = spark.sql(f"""
SELECT m.quarter,
  ROUND(SUM(m.gross_margin_eur)/SUM(m.revenue_eur)*100, 1)         AS actual_margin_pct,
  ROUND(SUM(b.budget_margin_eur)/SUM(b.budget_revenue_eur)*100, 1) AS budget_margin_pct,
  ROUND(SUM(m.gross_margin_eur)/SUM(m.revenue_eur)*100
      - SUM(b.budget_margin_eur)/SUM(b.budget_revenue_eur)*100, 1) AS delta_pp,
  SUM(m.units)                                                     AS actual_units,
  SUM(b.budget_units)                                              AS budget_units
FROM (SELECT *, CASE WHEN month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN '2026-Q1'
                     WHEN month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN '2026-Q2' END AS quarter
      FROM {FIN}.margin_actuals) m
JOIN {FIN}.products p     ON m.sku = p.sku
JOIN {FIN}.margin_budget b ON b.sku = m.sku AND b.region = m.region AND b.month = m.month
WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA' AND m.quarter IS NOT NULL
GROUP BY m.quarter ORDER BY m.quarter
""")
display(df_delta)
# Expected: 2026-Q1 actual 39.6 vs budget 39.9 (~on plan, -0.3pp); 2026-Q2 actual 30.7 vs budget 39.9 (-9.2pp miss).

# COMMAND ----------

# MAGIC %md
# MAGIC **Supporting evidence for the override.** Cost-driver + FX trend (price erosion, raw-material
# MAGIC spike, FX headwind) and the SCM service shock that constrained deliverable volume.

# COMMAND ----------

df_drivers = spark.sql(f"""
WITH base AS (
  SELECT CASE WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
              WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
         m.units, m.revenue_eur, c.raw_material_cost
  FROM {FIN}.margin_actuals m
  JOIN {FIN}.products p ON m.sku = p.sku
  LEFT JOIN {FIN}.cost_drivers c ON c.sku=m.sku AND c.region=m.region AND c.month=m.month
  WHERE p.product_line='Decorative Paints' AND p.region='EMEA'
    AND m.month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
)
SELECT qtr, ROUND(SUM(revenue_eur)/SUM(units),2) AS price_per_unit,
       ROUND(SUM(raw_material_cost)/SUM(units),2) AS raw_mat_per_unit, SUM(units) AS units
FROM base GROUP BY qtr ORDER BY qtr
""")
display(df_drivers)

df_service = spark.sql(f"""
SELECT month, ROUND(service_pct*100,1) AS service_pct, backorder_units
FROM {SCM}.service_levels WHERE region='EMEA' AND month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01'
ORDER BY month
""")
display(df_service)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — REASON: explain the miss, propose an override
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 1 lives here. The reasoning step turns the actual-vs-budget delta + the
# MAGIC drivers into a forecast explanation and a concrete, quantified override **proposal** (not applied).

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — TWEAK THE OVERRIDE LOGIC: edit the reasoning prompt to fit YOUR planning
#   metric (units, revenue, margin %, or a service-constrained volume). Change what the override
#   proposes and how it is justified, then re-run. The proposal feeds the Lakebase write below.
delta_rows = [r.asDict() for r in df_delta.collect()]
driver_rows = [r.asDict() for r in df_drivers.collect()]
service_rows = [r.asDict() for r in df_service.collect()]

REASON_PROMPT = f"""You are an AkzoNobel MMF forecast planner copilot for Paints EMEA (Decorative Paints x EMEA).
ACTUAL vs BUDGET margin by quarter (JSON): {json.dumps(delta_rows, default=str)}
COST/PRICE drivers by quarter (JSON): {json.dumps(driver_rows, default=str)}
EMEA service levels Q2 (JSON): {json.dumps(service_rows, default=str)}

Using ONLY these numbers (do not invent figures):
1) State the Q2 forecast miss (actual vs budget margin %, the pp gap).
2) Attribute it to demand/volume, price, cost, and FX — note volume was service-constrained, not weak demand.
3) Propose ONE forecast override for the next period (2026-07): give a concrete new margin-% assumption
   (range is fine) and a revised raw-material/FX stance, with a one-line rationale.
4) State explicitly that this override is STAGED for human review, not auto-applied.
Keep under 200 words."""

forecast_reasoning = _ai_query(REASON_PROMPT)
print(forecast_reasoning)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — ACT: write the override to Lakebase, then approve
# MAGIC
# MAGIC The override lands in `akzo.forecast_overrides` as `pending` under the service identity, then a
# MAGIC human flips it to `approved` with audit. Table already exists (created by
# MAGIC `L200-capabilities/05_lakebase_memory_action.py`). This is the read -> reason -> **act -> write -> approve**
# MAGIC loop.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg
from contextlib import contextmanager

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE", "<your-lakebase-instance>")
DB_NAME = "databricks_postgres"
PG_SCHEMA = "akzo"
SERVICE_IDENTITY = "forecast-agent@service"

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

def approve_override(override_id, approver) -> tuple:
    """APPROVAL FLOW: flip an override pending -> approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE forecast_overrides SET status='approved', approved_by=%s, approved_at=now()
               WHERE override_id=%s AND status='pending'
               RETURNING status, approved_by, approved_at""",
            (approver, override_id))
        return cur.fetchone()

# COMMAND ----------

# TODO (Day-2) SPRINT 2 — SWAP THE WRITE: change what the override stages (your SKU/region/period and
#   override quantity), and have the `reason` carry the LLM rationale above. Then approve as your persona.
# Narrative: the May service shock constrained deliverable EMEA volume -> trim the July build below plan
# until the Rotterdam lane fully recovers; hold the cost/FX adjustment.
oid = write_forecast_override(
    sku="DEC-1000", region="EMEA", month="2026-07-01",
    baseline_units=4200, override_units=3600,
    reason="Q2 actual margin 30.7% vs budget 39.9% (-9.2pp): price erosion + TiO2/resin spike + FX. "
           "Volume was service-constrained (May Rotterdam stockout/backorders), not weak demand. "
           "Trim July EMEA build to 3600u and hold the raised raw-material/FX assumption until the lane recovers.",
)
print("Wrote forecast_override id =", oid, "(status=pending)")

print("Approve:", approve_override(oid, approver="planner.emea@akzo.example"))

with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT override_id, sku, region, month, baseline_units, override_units, status,
                          created_by, approved_by, approved_at
                   FROM forecast_overrides WHERE override_id=%s""", (oid,))
    print("Audited override row:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Eval judge over the 5 golden questions
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 3 lives in `eval.yaml`. We run the planner reasoning against each golden
# MAGIC question and grade with an independent judge (`ai_query`-based, portable — same pattern as
# MAGIC `L200-capabilities/06_mlflow_eval_judge.py`).

# COMMAND ----------

import os, re, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/forecast/eval.yaml"]:
        if os.path.exists(c):
            return c
    return None

_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else {"golden_questions": []}
QUESTIONS = GOLDEN.get("golden_questions", [])
JUDGE_ENDPOINT = "databricks-gpt-5-5"
print("Loaded", len(QUESTIONS), "golden questions from", _p)

# Shared evidence block the planner reasons over for any forecast question.
EVIDENCE = (f"ACTUAL_VS_BUDGET={json.dumps(delta_rows, default=str)} "
            f"DRIVERS={json.dumps(driver_rows, default=str)} SERVICE={json.dumps(service_rows, default=str)}")

def planner_answer(question: str) -> str:
    return _ai_query(
        "You are an AkzoNobel MMF forecast planner copilot for Paints EMEA. Using ONLY this governed "
        f"data (do not invent figures):\n{EVIDENCE}\n\nAnswer concisely for a planner. Frame overrides as "
        f"staged for human review, never auto-applied.\n\nQUESTION: {question}\n\nANSWER:")

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a forecast planner copilot. Score the ANSWER against the EXPECTED FACTS.
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

# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add a golden question to eval.yaml (e.g. "propose an override
#   for Performance Coatings APAC") and re-run. Watch the judge grade your new case.
n_pass = 0
for q in QUESTIONS:
    v = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), planner_answer(q["question"]))
    n_pass += int(v["pass"])
    print(f"[{q['id']}] pass={v['pass']} corr={v['correctness']:.2f} grnd={v['groundedness']:.2f} — {v['rationale']}")
print(f"\nPASS RATE: {n_pass}/{len(QUESTIONS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole + ship
# MAGIC
# MAGIC The planner reads the actual-vs-budget delta -> reasons the miss -> proposes a quantified
# MAGIC override -> writes it to Lakebase pending -> approves -> is graded.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** edit the override reasoning prompt for your planning metric.
# MAGIC - **Sprint 2 (swap):** change what the Lakebase write stages and who approves.
# MAGIC - **Sprint 3 (extend):** add a golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Upgrade path:** point the actual-vs-budget read at the real Akzo Finance Genie space (Genie
# MAGIC Conversation API) and back the planner with MMF version tables instead of `margin_budget`.
