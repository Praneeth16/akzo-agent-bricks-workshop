# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 1 — The domain agent: Finance over governed data
# MAGIC
# MAGIC *Reveals use case #1, the Finance controlling copilot.*
# MAGIC
# MAGIC This notebook is the **reference build** behind the Layer-1 hands-on block. In the room you do
# MAGIC not stand any of this up — it is pre-staged. You **tweak one thing and run one query**. This
# MAGIC notebook shows you exactly what that "one thing" is wired into.
# MAGIC
# MAGIC **The whole game (recap):** a controller asks *"Paints EMEA gross margin dropped ~8% in Q2 —
# MAGIC is it price, volume, FX, or supply, and what should I do?"* The supervisor routes the finance
# MAGIC part to a **Genie space** that turns the question into governed SQL over Unity Catalog tables,
# MAGIC then a reasoning step turns the number into a **variance decomposition + recommended action**.
# MAGIC
# MAGIC **This layer, peeled, follows the 3-beat rhythm:**
# MAGIC 1. **See** — the certified margin metric and the verified Q2 drop the Finance leg is answering.
# MAGIC 2. **Tweak** — edit one example-SQL / one instruction line, re-run **one** question through the
# MAGIC    LLM-text2SQL helper, watch the answer change.
# MAGIC 3. **Return** — the same governed call is what the supervisor's Finance leg invokes.
# MAGIC
# MAGIC **What's governed here:** every table is in `serverless_lakebase_praneeth_catalog.akzo_finance`,
# MAGIC every query runs on **serverless**, and the certified definition of "gross margin" lives in a
# MAGIC **Unity Catalog metric view** so the agent, the BI tool, and you all compute it the same way.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC We pin the catalog/schema and the serving endpoint once. The chat model
# MAGIC `databricks-claude-opus-4-7` is the LLM behind both `ai_query` (SQL) and the Python helper.

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
FIN = f"{CATALOG}.akzo_finance"
LLM_ENDPOINT = "databricks-claude-opus-4-7"   # or "databricks-gpt-5-5"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql("USE SCHEMA akzo_finance")
print("Catalog/schema:", FIN)
print("LLM endpoint  :", LLM_ENDPOINT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: the certified metric and the Q2 margin drop
# MAGIC
# MAGIC A **certified metric view** is how Unity Catalog makes "gross margin %" mean one thing
# MAGIC everywhere. The rule is non-obvious and easy to get wrong: you must compute margin % as a
# MAGIC **revenue-weighted ratio of summed EUR amounts** — `SUM(gross_margin_eur) / SUM(revenue_eur)` —
# MAGIC never the average of the row-level `gross_margin_pct`. The metric view bakes that rule in, so
# MAGIC the Genie space, the copilot, and a dashboard cannot disagree.
# MAGIC
# MAGIC We define `mv_gross_margin` with the dimensions the variance story needs: `product_line`,
# MAGIC `region`, `month`, `quarter`.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {FIN}.mv_gross_margin
WITH METRICS
LANGUAGE YAML
COMMENT 'Certified gross-margin metric view for Akzo coatings. Margin % is the revenue-weighted ratio SUM(gross_margin_eur)/SUM(revenue_eur) — never the average of row-level gross_margin_pct.'
AS $$
version: 0.1
source: |
  SELECT
    m.sku, m.region, m.month,
    p.product_line,
    CASE
      WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN '2026-Q1'
      WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN '2026-Q2'
    END AS quarter,
    m.units, m.revenue_eur, m.cogs_eur, m.gross_margin_eur
  FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
  JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p
    ON m.sku = p.sku
dimensions:
  - name: product_line
    expr: product_line
  - name: region
    expr: region
  - name: month
    expr: month
  - name: quarter
    expr: quarter
measures:
  - name: revenue_eur
    expr: SUM(revenue_eur)
  - name: gross_margin_eur
    expr: SUM(gross_margin_eur)
  - name: units
    expr: SUM(units)
  - name: gross_margin_pct
    expr: SUM(gross_margin_eur) / SUM(revenue_eur)
  - name: realized_price_per_unit
    expr: SUM(revenue_eur) / SUM(units)
$$
""")
print("Created certified metric view:", f"{FIN}.mv_gross_margin")

# COMMAND ----------

# MAGIC %md
# MAGIC **The number the Finance leg is defending.** Query the certified view with `MEASURE()` to see
# MAGIC Paints EMEA gross margin step down Q1 → Q2 2026. This is the same metric a controller sees in
# MAGIC the BI tool — one definition, governed in UC.

# COMMAND ----------

df_see = spark.sql(f"""
SELECT
  quarter,
  ROUND(MEASURE(gross_margin_pct) * 100, 1)      AS gross_margin_pct,
  ROUND(MEASURE(realized_price_per_unit), 2)     AS price_per_unit_eur,
  MEASURE(units)                                 AS units
FROM {FIN}.mv_gross_margin
WHERE product_line = 'Decorative Paints' AND region = 'EMEA'
  AND quarter IS NOT NULL
GROUP BY quarter
ORDER BY quarter
""")
display(df_see)
# Expected: 2026-Q1 ~39.6%, 2026-Q2 ~30.7%  ->  ~8.9pp drop. Price per unit erodes ~34.5 -> ~32.7.

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** two rows, Q1 and Q2. `gross_margin_pct` should fall from ~39.6% to ~30.7%
# MAGIC (the ~8.9pp drop the controller flagged), and `price_per_unit_eur` should slide from ~34.5 to
# MAGIC ~32.7 while `units` stays roughly flat. That flat volume is the first clue: the margin damage is
# MAGIC price- and cost-driven, not a demand collapse — which the next cell decomposes precisely.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The full variance decomposition (price / volume / FX / cost)
# MAGIC
# MAGIC The reasoning the copilot does is a **four-way bridge** that explains the ~8.9pp drop:
# MAGIC
# MAGIC | Driver | How it's measured | Source |
# MAGIC |---|---|---|
# MAGIC | **Price** | change in realized price/unit (`revenue_eur/units`) | `margin_actuals` |
# MAGIC | **Volume** | change in `units` (scale/mix; ~neutral on margin-% if price & cost flat) | `margin_actuals` |
# MAGIC | **FX** | EUR-translation effect from `rate_to_eur` moving for the SKU's currency | `fx_rates` |
# MAGIC | **Cost** | change in unit COGS, drillable to raw-material/freight/energy/overhead | `cost_drivers` |
# MAGIC
# MAGIC The query below pulls every component for Q1 vs Q2 so the LLM has structured evidence, not a
# MAGIC single number.

# COMMAND ----------

df_decomp = spark.sql(f"""
WITH base AS (
  SELECT
    CASE WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
         WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    m.units, m.revenue_eur, m.gross_margin_eur,
    c.raw_material_cost, c.freight_cost, c.energy_cost, c.overhead
  FROM {FIN}.margin_actuals m
  JOIN {FIN}.products p ON m.sku = p.sku
  LEFT JOIN {FIN}.cost_drivers c
    ON c.sku = m.sku AND c.region = m.region AND c.month = m.month
  WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
    AND m.month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
),
fx AS (   -- EMEA Decorative input exposure rides USD/CNY raw-material sourcing
  SELECT
    CASE WHEN month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
         WHEN month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    AVG(rate_to_eur) AS usd_rate
  FROM {FIN}.fx_rates WHERE currency = 'USD'
    AND month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
  GROUP BY 1
)
SELECT
  b.qtr,
  SUM(b.units)                                          AS units,
  ROUND(SUM(b.revenue_eur)/SUM(b.units), 2)             AS price_per_unit_eur,
  ROUND(SUM(b.gross_margin_eur)/SUM(b.revenue_eur)*100, 1) AS gross_margin_pct,
  ROUND(SUM(b.raw_material_cost)/SUM(b.units), 2)       AS raw_mat_per_unit,
  ROUND(SUM(b.freight_cost)/SUM(b.units), 2)            AS freight_per_unit,
  ROUND(SUM(b.energy_cost)/SUM(b.units), 2)             AS energy_per_unit,
  ROUND(MAX(fx.usd_rate), 4)                            AS usd_rate_to_eur
FROM base b JOIN fx ON fx.qtr = b.qtr
GROUP BY b.qtr
ORDER BY b.qtr
""")
display(df_decomp)
# Q1->Q2: price/unit ~34.5 -> ~32.7 (price erosion), raw_mat/unit ~11.5 -> ~13.4 (cost spike),
# USD rate_to_eur ~0.92 -> ~0.88 (EUR strengthened = FX headwind), volume ~flat.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The LLM-text2SQL helper (the Genie pattern, in code)
# MAGIC
# MAGIC The pre-staged **Akzo Finance Genie space** turns a plain-English golden question into governed
# MAGIC SQL using its *Instructions* + *example SQL* as context. Here we reproduce that pattern directly
# MAGIC with `ai_query` so the notebook is self-contained: **the genie space's instructions become the
# MAGIC system prompt.** This is the call the Finance leg makes, and it's the thing you'll *tweak*.
# MAGIC
# MAGIC > Upgrade path: to use the real Genie space instead of this helper, call the **Genie Conversation
# MAGIC > API** with the space's `space_id` (created in the UI from `genie/finance_space.md`). The system
# MAGIC > prompt below is the same instruction text you paste into that space.

# COMMAND ----------

# This SYSTEM_PROMPT is the distilled Instructions block from genie/finance_space.md.
# >>> THIS IS THE LAYER YOU TWEAK <<< — edit one rule or one example and re-run ONE question below.
FINANCE_INSTRUCTIONS = """You are the Akzo Finance text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no markdown fences.

TABLES (all under serverless_lakebase_praneeth_catalog.akzo_finance):
- products(sku, product_name, product_line['Decorative Paints'|'Performance Coatings'], region['EMEA'|'Americas'|'APAC'|'China'], currency, list_price_eur, standard_cost_eur)
- margin_actuals(sku, region, month DATE, units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct)
- margin_budget(sku, region, month, budget_units, budget_revenue_eur, budget_margin_eur)
- fx_rates(currency['EUR'|'USD'|'GBP'|'CNY'], month, rate_to_eur)
- cost_drivers(sku, region, month, raw_material_cost, freight_cost, energy_cost, overhead)

CERTIFIED RULES (always follow):
- gross_margin_pct = SUM(gross_margin_eur)/SUM(revenue_eur). NEVER average row-level gross_margin_pct.
- "Paints EMEA" := products.product_line='Decorative Paints' AND region='EMEA'. Join margin_actuals.sku=products.sku.
- Quarters 2026: Q1 = months 2026-01-01..2026-03-01 ; Q2 = months 2026-04-01..2026-06-01.
- month is a DATE at first-of-month; compare against 'YYYY-MM-01' literals; current month is 2026-06.
- Currency is EUR. Round percentages to 1 decimal in SELECT.

EXAMPLE:
Q: "Show Paints EMEA gross margin % by month for 2026."
SQL: SELECT m.month, ROUND(SUM(m.gross_margin_eur)/SUM(m.revenue_eur)*100,1) AS gross_margin_pct
FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku=p.sku
WHERE p.product_line='Decorative Paints' AND p.region='EMEA' AND m.month>=DATE'2026-01-01'
GROUP BY m.month ORDER BY m.month;"""

def text2sql(question: str, instructions: str = FINANCE_INSTRUCTIONS) -> str:
    """Ask the LLM to turn an NL question into governed Spark SQL (the Genie-space pattern)."""
    prompt = instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:"
    row = spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS sql",
        args={"endpoint": LLM_ENDPOINT, "prompt": prompt},
    ).first()
    sql = row["sql"].strip()
    # strip accidental markdown fences if the model adds them
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def ask_finance(question: str, instructions: str = FINANCE_INSTRUCTIONS):
    """Generate SQL from NL, run it on serverless, return (sql, dataframe)."""
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    return sql, spark.sql(sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: change one example, run one query
# MAGIC
# MAGIC Run a golden question through the helper. The LLM writes the SQL using the instructions above;
# MAGIC we execute it on serverless. **This is the live moment** — the same generate-then-run loop the
# MAGIC Genie space performs.

# COMMAND ----------

sql, df = ask_finance("Why did Paints EMEA gross margin drop in Q2 2026 versus Q1 — show both quarters' margin %?")
display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** first the **Generated SQL** printout — confirm the model honored the
# MAGIC certified rule (`SUM(gross_margin_eur)/SUM(revenue_eur)`, not an average of row-level pct) and the
# MAGIC `Decorative Paints` + `EMEA` filter. Then the result: the same ~39.6% → ~30.7% you saw in Beat 1,
# MAGIC now produced from plain English. If the SQL ignored a rule, that's exactly the behavior you'll
# MAGIC fix by editing the instructions below.

# COMMAND ----------

# MAGIC %md
# MAGIC **Your turn — the one tweak.** Pick *one* of these and re-run the cell above (or the next one):
# MAGIC
# MAGIC 1. **Edit an instruction.** In `FINANCE_INSTRUCTIONS`, change the rounding rule from
# MAGIC    `1 decimal` to `2 decimal` and re-run — the answer's precision changes.
# MAGIC 2. **Add an example.** Append a new `Q:/SQL:` pair (e.g. a COGS-bucket breakdown) and ask the
# MAGIC    matching question — the model now mirrors your example.
# MAGIC 3. **Swap the metric reference.** Point a question at `mv_gross_margin` (`MEASURE(...)`) instead
# MAGIC    of raw `margin_actuals` and confirm the number is identical — that's the certified view doing
# MAGIC    its job.
# MAGIC
# MAGIC The cell below is wired for tweak #2: it adds one example to the instructions at call time.

# COMMAND ----------

TWEAKED = FINANCE_INSTRUCTIONS + """

EXAMPLE (added by tweak):
Q: "Break Paints EMEA Q2 2026 COGS into raw material, freight, energy and overhead."
SQL: SELECT ROUND(SUM(c.raw_material_cost)) AS raw_material_eur, ROUND(SUM(c.freight_cost)) AS freight_eur,
ROUND(SUM(c.energy_cost)) AS energy_eur, ROUND(SUM(c.overhead)) AS overhead_eur
FROM serverless_lakebase_praneeth_catalog.akzo_finance.cost_drivers c
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON c.sku=p.sku
WHERE p.product_line='Decorative Paints' AND p.region='EMEA'
AND c.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01';"""

sql2, df2 = ask_finance("Which cost driver is responsible for the COGS increase in Paints EMEA in Q2 2026?",
                        instructions=TWEAKED)
display(df2)
# Expect raw_material_cost to dominate — the TiO2/resin spike, ~15-20% up in Q2.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The reasoning step: number → variance decomposition → recommended action
# MAGIC
# MAGIC A copilot is more than text2SQL. After it retrieves the governed numbers, a **reasoning step**
# MAGIC turns them into a controller-ready bridge and a concrete next action. We feed the structured
# MAGIC decomposition (the `df_decomp` table) to the LLM and ask for the four-way attribution + a
# MAGIC recommendation — grounded only in the numbers, no hallucinated figures.

# COMMAND ----------

import json

decomp_rows = [r.asDict() for r in df_decomp.collect()]
evidence = json.dumps(decomp_rows)

REASONING_PROMPT = f"""You are a finance controlling copilot for AkzoNobel coatings.
Here is the verified Paints EMEA (Decorative Paints x EMEA) data for 2026, Q1 vs Q2, as JSON:
{evidence}

FX note: USD rate_to_eur fell from ~0.926 (Jan) to ~0.879 (Jun) — EUR strengthened, a translation
headwind on the USD-sourced raw-material/input exposure.

Task: explain the gross-margin-% change Q1->Q2 as a four-way bridge — PRICE, VOLUME, FX, COST —
where the four roughly sum to the total margin-% change. Use ONLY the numbers above (do not invent
figures). Then give ONE concrete recommended action for the controller. Be concise (under 180 words).
Format:
- Headline: <one line with the pp drop>
- Price: ...
- Volume: ...
- FX: ...
- Cost: ...
- Recommended action: ..."""

reasoning = spark.sql(
    "SELECT ai_query(:endpoint, :prompt) AS answer",
    args={"endpoint": LLM_ENDPOINT, "prompt": REASONING_PROMPT},
).first()["answer"]
print(reasoning)

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** a controller-ready bridge where **price + volume + FX + cost roughly sum to
# MAGIC the ~−8.9pp** total, plus one concrete recommended action. Every figure should trace back to the
# MAGIC `df_decomp` JSON we passed in — if you see a number that wasn't in the evidence, that's a
# MAGIC hallucination and a signal to tighten the prompt. This is the step that turns governed data into a
# MAGIC decision, which is what makes it a copilot rather than a query tool.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: this is the supervisor's Finance leg
# MAGIC
# MAGIC Everything above — the certified `mv_gross_margin` view, the text2SQL helper, and the reasoning
# MAGIC step — is exactly what the **Supervisor Agent** invokes when a cross-domain question's *finance*
# MAGIC part is routed here. Your tweak to an instruction or example changes the answer the whole
# MAGIC supervisor gives, with no other wiring touched.
# MAGIC
# MAGIC **What we proved on governed data:**
# MAGIC - Paints EMEA gross margin **39.6% (Q1) → 30.7% (Q2)** — a **~8.9pp** drop, isolated to
# MAGIC   Decorative Paints × EMEA.
# MAGIC - Bridge: **price ~−3pp** (realized price ~34.5 → ~32.7/unit), **raw-material cost ~−3pp**
# MAGIC   (~11.5 → ~13.4/unit), **FX ~−2pp** (USD 0.926 → 0.879), **volume ~flat**.
# MAGIC
# MAGIC **Honest scope (sets up Layer 2):** this leg reads governed UC tables under *your* identity. The
# MAGIC controller and the EMEA planner asking the same question see different rows — that's
# MAGIC Unity-Catalog row-level security + OBO, the next layer.
# MAGIC
# MAGIC **Next:** `02_per_user_truth_uc_obo.py`.
