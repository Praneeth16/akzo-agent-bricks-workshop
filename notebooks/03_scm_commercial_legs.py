# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 3 — More domain legs: SCM + Commercial
# MAGIC
# MAGIC *Reveals use case #2 (SCM control tower) and use case #5 (Commercial action assistant).*
# MAGIC
# MAGIC Layer 1 built the Finance leg. The point of this layer is that the **recipe repeats**: a Genie
# MAGIC space over governed UC tables + an LLM-text2SQL call + a reasoning step that turns numbers into a
# MAGIC recommended action. We apply that identical recipe to two more domains and watch the pattern
# MAGIC click into place. That repetition *is* the lesson.
# MAGIC
# MAGIC **The connected narrative:** the Paints-EMEA margin shock (Layer 1) has a supply-side cause and a
# MAGIC commercial consequence.
# MAGIC - **SCM:** the `Rotterdam-NL->EMEA-DACH` lane's OTIF fell ~96% → **88.9% in May 2026** (lead time
# MAGIC   5→9 days, key SKUs stocked out, service dipped, backorders spiked).
# MAGIC - **Commercial:** three EMEA Decorative accounts crossed churn-risk **>0.7** — the *downstream*
# MAGIC   consequence of that service shock, not a pricing failure.
# MAGIC
# MAGIC **3-beat rhythm (per domain):** See the leg → Tweak one example/instruction and run one query →
# MAGIC Return it to the supervisor.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
SCM = f"{CATALOG}.akzo_scm"
COM = f"{CATALOG}.akzo_commercial"
LLM_ENDPOINT = "databricks-claude-opus-4-7"   # or "databricks-gpt-5-5"

spark.sql(f"USE CATALOG {CATALOG}")
print("SCM        :", SCM)
print("Commercial :", COM)
print("LLM        :", LLM_ENDPOINT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## The reusable text2SQL helper
# MAGIC
# MAGIC Same helper as Layer 1, parameterized by a domain instruction block (the Genie space's
# MAGIC *Instructions*). This is the Genie-space pattern in code; the upgrade path is to call the real
# MAGIC Genie Conversation API with each space's `space_id` (created in the UI from `genie/scm_space.md`
# MAGIC and `genie/commercial_space.md`).

# COMMAND ----------

def text2sql(question: str, instructions: str) -> str:
    """Turn an NL question into governed Spark SQL using a domain's Genie-space instructions."""
    prompt = instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:"
    sql = spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS sql",
        args={"endpoint": LLM_ENDPOINT, "prompt": prompt},
    ).first()["sql"].strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def ask(question: str, instructions: str):
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    return sql, spark.sql(sql)

def reason(prompt: str) -> str:
    return spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS answer",
        args={"endpoint": LLM_ENDPOINT, "prompt": prompt},
    ).first()["answer"]

import json

# COMMAND ----------

# MAGIC %md
# MAGIC # Domain A — SCM control tower
# MAGIC
# MAGIC ## SCM instructions (the Genie space, distilled from `genie/scm_space.md`)
# MAGIC
# MAGIC >>> THIS IS A LAYER YOU TWEAK <<< — edit one rule / add one example, re-run one SCM question.

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: the Rotterdam OTIF dip the SCM leg explains

# COMMAND ----------

sql, df = ask("Show monthly OTIF for the Rotterdam-NL to EMEA-DACH lane in 2026.", SCM_INSTRUCTIONS)
display(df)
# Expect ~96% Jan-Mar -> 88.9% May -> ~93.0% June: the disrupted EMEA lane.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: run a golden question; then change one example
# MAGIC
# MAGIC The golden question asks *why* OTIF fell. The root cause is a lead-time blowout **plus** a
# MAGIC stockout. Run it, then try the tweak below.

# COMMAND ----------

sql, df = ask("Which EMEA SKUs stocked out at Rotterdam in May 2026, with days of supply?", SCM_INSTRUCTIONS)
display(df)
# Expect DEC-1000 and DEC-1004 at Rotterdam-NL, stockout_flag=1, days_of_supply ~1.

# COMMAND ----------

# Service level + backorder spike — the customer-facing symptom:
sql, df_svc = ask("Show EMEA service level and backorder units by month in Q2 2026.", SCM_INSTRUCTIONS)
display(df_svc)
# Expect service_pct ~0.96 (Apr) -> 0.906 (May) -> 0.946 (Jun); backorder_units ~2,258 in May.

# COMMAND ----------

# MAGIC %md
# MAGIC **Your turn — one tweak.** Add the example below to the SCM instructions (it teaches a
# MAGIC lane-vs-mode comparison) and ask *"which lanes had rising lead times in Q2?"* — the model now
# MAGIC normalizes by transport mode so the road lane, not the naturally-long sea lanes, is flagged.

# COMMAND ----------

SCM_TWEAKED = SCM_INSTRUCTIONS + """

EXAMPLE (added by tweak — normalize lead time by mode so sea lanes don't dominate):
Q: "Which lanes had rising lead times in Q2 2026?"
SQL: WITH mode_norm AS (SELECT mode, AVG(lead_time_days) AS mode_avg FROM serverless_lakebase_praneeth_catalog.akzo_scm.lanes GROUP BY mode)
SELECT l.lane_id, l.mode, l.lead_time_days, ROUND(n.mode_avg,1) AS mode_avg_days,
ROUND(l.lead_time_days - n.mode_avg,1) AS days_above_mode_avg
FROM serverless_lakebase_praneeth_catalog.akzo_scm.lanes l JOIN mode_norm n ON l.mode=n.mode
ORDER BY days_above_mode_avg DESC;"""

sql, df = ask("Which lanes had rising lead times in Q2 2026?", SCM_TWEAKED)
display(df)
# Rotterdam-NL->EMEA-DACH (road, 9 days) tops the list vs its road-mode average (~5-6 days).

# COMMAND ----------

# MAGIC %md
# MAGIC ## SCM reasoning step: root cause → intervention
# MAGIC
# MAGIC Gather the structured evidence (lane OTIF trend, stockouts, service/backorders), hand it to the
# MAGIC LLM, and ask for a root-cause read plus **one concrete intervention** — the SCM analogue of the
# MAGIC finance recommended action.

# COMMAND ----------

lane_trend = spark.sql(f"""
  SELECT month, ROUND(SUM(ROUND(otif_pct*orders))/SUM(orders)*100,1) AS lane_otif_pct
  FROM {SCM}.otif WHERE lane='Rotterdam-NL->EMEA-DACH' AND month>=DATE'2026-03-01'
  GROUP BY month ORDER BY month
""").collect()
stockouts = spark.sql(f"""
  SELECT plant, sku, ROUND(days_of_supply,1) AS days_of_supply
  FROM {SCM}.inventory WHERE month=DATE'2026-05-01' AND stockout_flag=1
    AND plant IN ('Rotterdam-NL','Felling-UK')
""").collect()
service = spark.sql(f"""
  SELECT month, ROUND(service_pct*100,1) AS service_pct, backorder_units
  FROM {SCM}.service_levels WHERE region='EMEA' AND month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01'
  ORDER BY month
""").collect()

evidence = json.dumps({
    "lane_otif_pct_by_month": [r.asDict() for r in lane_trend],
    "may_stockouts": [r.asDict() for r in stockouts],
    "emea_service_and_backorders": [r.asDict() for r in service],
    "lane_lead_time": "Rotterdam-NL->EMEA-DACH road lane stepped from 5 to 9 days in Q2 2026",
})

scm_answer = reason(f"""You are an Akzo SCM control-tower copilot. Verified governed data (JSON):
{evidence}

Task: in under 160 words, (1) state the root cause of the May 2026 EMEA service drop tying together
lead time, stockout, and the OTIF/service/backorder numbers; (2) recommend ONE concrete intervention
for a supply planner. Use ONLY the numbers above. Note this is a diagnostic copilot — it recommends,
it does not execute the reroute (that is a governed write in the scm_interventions queue).
Format:
- Root cause: ...
- Evidence: OTIF ..., stockout ..., service/backorders ...
- Recommended intervention: ...""")
print(scm_answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 (SCM) — RETURN
# MAGIC The SCM leg now answers the supply half of the cross-domain question. **Verified:** Rotterdam
# MAGIC lane OTIF **96% → 88.9% (May) → 93.0% (Jun)**, two EMEA Decorative SKUs stocked out, EMEA service
# MAGIC **90.6%** with **~2,258** backorders in May.

# COMMAND ----------

# MAGIC %md
# MAGIC # Domain B — Commercial action assistant
# MAGIC
# MAGIC ## Commercial instructions (distilled from `genie/commercial_space.md`)
# MAGIC
# MAGIC >>> THIS IS A LAYER YOU TWEAK <<< — same recipe, third domain.

# COMMAND ----------

COM_INSTRUCTIONS = """You are the Akzo Commercial text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no fences.

TABLES (all under serverless_lakebase_praneeth_catalog.akzo_commercial):
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
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON c.account_id=a.account_id
WHERE c.month=DATE'2026-06-01' AND c.churn_score>0.7 ORDER BY c.churn_score DESC;"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: the three at-risk EMEA accounts

# COMMAND ----------

sql, df_risk = ask("Which Paints EMEA accounts are at churn risk in June 2026 and why? Include owner_rep, last_order_days, complaint_count, nps.", COM_INSTRUCTIONS)
display(df_risk)
# Expect ACC0001 Rhine Valley Decor Distributors (0.865), ACC0002 Benelux PaintPro (0.827),
# ACC0003 Nordic Coatings Supply (0.800) — all >0.7.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: run a golden question; then change the threshold instruction
# MAGIC
# MAGIC The revenue-at-risk trend shows the consequence of the service shock.

# COMMAND ----------

sql, df = ask("Show the monthly revenue trend in 2026 for the three at-risk EMEA accounts ACC0001, ACC0002, ACC0003.", COM_INSTRUCTIONS)
display(df)
# Expect combined revenue falling from ~EUR 375k (Jan) to ~EUR 169k (Jun).

# COMMAND ----------

# MAGIC %md
# MAGIC **Your turn — one tweak.** Change the churn threshold in the instructions from `0.7` to `0.5`
# MAGIC and re-run "which accounts are at churn risk in June 2026?" — more accounts qualify, showing how
# MAGIC a single instruction edit re-tunes the agent's definition of "at risk".

# COMMAND ----------

COM_TWEAKED = COM_INSTRUCTIONS.replace("churn_score > 0.7", "churn_score > 0.5").replace("churn_score>0.7", "churn_score>0.5")
sql, df = ask("Which accounts are at churn risk in June 2026?", COM_TWEAKED)
display(df)
# With the lower 0.5 cutoff the list widens beyond the canonical three.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Commercial reasoning step: signals → next-best-action
# MAGIC
# MAGIC The Commercial analogue of the recommended action: read the at-risk signals + revenue trend, tie
# MAGIC the churn to the **upstream service problem** (not pricing), and propose a concrete save play that
# MAGIC would be staged as a `commercial_action` for human approval.

# COMMAND ----------

risk_rows = [r.asDict() for r in df_risk.collect()]
rev_trend = spark.sql(f"""
  SELECT month, ROUND(SUM(revenue_eur)) AS combined_revenue_eur
  FROM {COM}.sales_actuals WHERE account_id IN ('ACC0001','ACC0002','ACC0003') AND month>=DATE'2026-01-01'
  GROUP BY month ORDER BY month
""").collect()

evidence = json.dumps({
    "at_risk_accounts_jun2026": risk_rows,
    "combined_revenue_trend": [r.asDict() for r in rev_trend],
    "upstream_context": "Paints EMEA OTIF/service collapsed in May 2026 (Rotterdam lane, stockouts); these are Decorative Paints (Architectural EMEA) buyers.",
})

com_answer = reason(f"""You are an Akzo Commercial action assistant. Verified governed data (JSON):
{evidence}

Task: in under 170 words, (1) confirm the three at-risk accounts and cite each one's churn_score and
the driving signals; (2) state that the churn is a DOWNSTREAM consequence of the EMEA service/OTIF
shock, not a pricing failure; (3) recommend ONE concrete next-best-action (save play) for the top
account's owner rep, framed around fixing the service issue, and note it would be logged as a
commercial_action for human approval (the assistant recommends, it does not approve discounts or send
email). Use ONLY the data above.
Format:
- At-risk accounts: ...
- Root cause: ...
- Next-best-action for ACC0001: ...""")
print(com_answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: three legs, one supervisor, one connected story
# MAGIC
# MAGIC The recipe repeated cleanly across three domains:
# MAGIC
# MAGIC | Leg | text2SQL over | Reasoning produces | Verified anchor |
# MAGIC |---|---|---|---|
# MAGIC | **Finance** (L1) | `akzo_finance` | variance decomposition + action | GM 39.6%→30.7% (−8.9pp) |
# MAGIC | **SCM** (this NB) | `akzo_scm` | root cause + intervention | Rotterdam OTIF 96%→88.9% May |
# MAGIC | **Commercial** (this NB) | `akzo_commercial` | signals + next-best-action | ACC0001/2/3 churn >0.7 |
# MAGIC
# MAGIC And they tell **one** story: the EMEA margin shock (finance) has a supply cause (SCM) and a
# MAGIC customer consequence (commercial). That is exactly the cross-domain question the **Supervisor
# MAGIC Agent** fuses — and each leg here is one of its subagents, each governed per-user by Layer 2's
# MAGIC RLS/OBO.
# MAGIC
# MAGIC **Next:** `04_supervisor_agent.py` ties the three legs under one router.
