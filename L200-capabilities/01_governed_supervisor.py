# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC The legs call real Genie spaces via the Genie Spaces / Conversation API, which needs a recent
# MAGIC `databricks-sdk` (`w.genie.start_conversation_and_wait` + `get_message_query_result`). Install, then
# MAGIC restart Python. (Run this cell first; it is the only `%pip` in the notebook.)

# COMMAND ----------

# MAGIC %pip install --quiet "databricks-sdk>=0.96"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 1 — A governed multi-agent supervisor
# MAGIC
# MAGIC ### Where this sits in the workshop
# MAGIC
# MAGIC The whole workshop is **one connected story**: AkzoNobel's *Paints EMEA* gross margin fell ~8% in
# MAGIC Q2 2026. Five chapters take you from "answer the question" to "an agent that acts on it, safely."
# MAGIC
# MAGIC ```
# MAGIC   ┌─────────────────────────────────────────────────────────────────────────────┐
# MAGIC   │  CH1  Governed supervisor   ── diagnose: finance + supply + commercial        │ ← you are here
# MAGIC   │  CH2  Agents that act       ── memory, staging, approval, governed execution  │
# MAGIC   │  CH3  Autonomous loop       ── detect → decide → auto-act or escalate         │
# MAGIC   │  CH4  Trust & governance    ── MLflow eval + judge, AI Gateway at scale       │
# MAGIC   │  CH5  Document intelligence ── parse / extract PDFs → embed → RAG + SQL       │
# MAGIC   └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### What you build in this chapter
# MAGIC
# MAGIC One **multi-agent supervisor** that, given a cross-domain question, decides which domain experts to
# MAGIC consult, runs each over **governed** Unity Catalog data, and fuses one answer — and does it
# MAGIC **per-user** (the same question returns different rows to different people). It is assembled in four
# MAGIC parts, each building on the last:
# MAGIC
# MAGIC ```
# MAGIC   PART A                 PART B                 PART C                    PART D
# MAGIC   ┌──────────┐           ┌──────────┐           ┌──────────────┐          ┌──────────────┐
# MAGIC   │ Finance  │           │  OBO +   │           │  + SCM       │          │  SUPERVISOR  │
# MAGIC   │ domain   │  ──────▶  │  UC row  │  ──────▶  │  + Commercial│  ─────▶  │  route → run │
# MAGIC   │ agent    │  govern   │  filter  │ generalize│  legs        │  compose │  legs → fuse │
# MAGIC   └──────────┘   it      └──────────┘  the      └──────────────┘  them    └──────────────┘
# MAGIC    text2SQL +            same question          one recipe,                one chat,
# MAGIC    reasoning             different rows         three domains              cross-domain
# MAGIC ```
# MAGIC
# MAGIC ### The 3-beat rhythm (every part)
# MAGIC 1. **SEE** — the governed number/behaviour the part is built on.
# MAGIC 2. **TWEAK** — change *one* thing (an instruction, a persona, a routing line) and re-run.
# MAGIC 3. **RETURN** — see how that part becomes a piece of the supervisor.
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - A **serverless** SQL warehouse / cluster, and access to a chat model serving endpoint.
# MAGIC - The synthetic data loaded into `<catalog>.akzo_finance / akzo_scm / akzo_commercial`
# MAGIC   (run `L200-capabilities/00_setup_load_data.py`, or `data/load_to_uc.py`, once first).
# MAGIC - Permission to `CREATE SCHEMA/VIEW/FUNCTION` and `ALTER TABLE ... SET ROW FILTER` in the catalog.
# MAGIC
# MAGIC ### How to run (~25 min)
# MAGIC Top-to-bottom, cell by cell. The two widgets at the top let you point this at **your own** catalog
# MAGIC and chat model, so it runs unchanged in any workspace. Watch each printed *Generated SQL* and compare
# MAGIC results against the `# Expect ...` comments.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters
# MAGIC
# MAGIC Widgets make the notebook portable: `catalog` (where the `akzo_*` schemas live), `llm_endpoint` (the
# MAGIC router/fuser model), and the three **Genie space ids**. When a domain's space id is set, that leg
# MAGIC calls the **real Genie space** via the Genie Conversation API (Genie generates + runs the governed
# MAGIC SQL); when blank, it falls back to the in-code `ai_query` reproduction so the notebook still runs
# MAGIC anywhere. Create the three spaces from code first with `genie/create_genie_spaces.py` (it writes the
# MAGIC ids), or paste each space id from the UI (`/genie/rooms/<space_id>`). The defaults are blank, so the
# MAGIC notebook runs on the `ai_query` fallback until you fill them in.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Unity Catalog (blank = current_catalog())")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8", "Router/fuser model endpoint")
# Paste your Genie space ids from the UI (open each space; the id is the last URL segment
# of /genie/rooms/<space_id>), or run genie/create_genie_spaces.py to create them.
# Blank a field to use the ai_query fallback.
dbutils.widgets.text("finance_space_id", "", "Finance Genie space id")
dbutils.widgets.text("scm_space_id", "", "SCM Genie space id")
dbutils.widgets.text("commercial_space_id", "", "Commercial Genie space id")

CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")   # e.g. databricks-claude-opus-4-8 / databricks-gpt-5-5

FIN = f"{CATALOG}.akzo_finance"
SCM = f"{CATALOG}.akzo_scm"
COM = f"{CATALOG}.akzo_commercial"
OPS = f"{CATALOG}.akzo_ops"

# Per-domain Genie space ids (empty string -> that leg uses the ai_query fallback).
LEG_SPACE_IDS = {
    "FINANCE": dbutils.widgets.get("finance_space_id").strip(),
    "SCM": dbutils.widgets.get("scm_space_id").strip(),
    "COMMERCIAL": dbutils.widgets.get("commercial_space_id").strip(),
}

spark.sql(f"USE CATALOG {CATALOG}")

import json
from databricks.sdk import WorkspaceClient
_w = WorkspaceClient()   # used for the real Genie Conversation API calls

def genie_leg(space_id: str, question: str) -> dict:
    """Call a REAL Genie space via the Conversation API: Genie generates + runs governed SQL.
    Returns {sql, rows, error} matching run_governed_sql's contract so the supervisor is unchanged."""
    try:
        msg = _w.genie.start_conversation_and_wait(space_id=space_id, content=question)
        sql, rows = None, []
        for att in (msg.attachments or []):
            if getattr(att, "query", None) is not None:
                sql = att.query.query
                res = _w.genie.get_message_query_result(
                    space_id=space_id, conversation_id=msg.conversation_id, message_id=msg.id)
                sr = getattr(res, "statement_response", None)
                if sr and sr.result and sr.result.data_array:
                    cols = [c.name for c in sr.manifest.schema.columns]
                    rows = [dict(zip(cols, r)) for r in sr.result.data_array]
        return {"sql": sql or "(Genie returned no SQL attachment)", "rows": rows, "error": None}
    except Exception as e:
        return {"sql": f"(Genie call failed: {str(e)[:160]})", "rows": [], "error": str(e)[:300]}

print("Catalog     :", CATALOG)
print("Finance     :", FIN)
print("SCM         :", SCM)
print("Commercial  :", COM)
print("Ops (RLS)   :", OPS)
print("LLM endpoint:", LLM_ENDPOINT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — the building blocks (one LLM primitive, three helpers)
# MAGIC
# MAGIC Every agent in this notebook — the domain legs, the router, the fuser — makes the **same single
# MAGIC model call**. We define it once as `llm()` and reuse it everywhere, so there is exactly one place
# MAGIC the model is invoked.
# MAGIC
# MAGIC ```
# MAGIC          ┌──────────────────────────── llm(prompt) ────────────────────────────┐
# MAGIC          │                    ai_query(endpoint, prompt) on serverless          │
# MAGIC          └─────────────────────────────────┬───────────────────────────────────┘
# MAGIC                  ┌───────────────┬──────────┴───────────┬──────────────┐
# MAGIC              text2sql()       reason()               route()         fuse()
# MAGIC            NL → governed     numbers → a            question →     evidence → one
# MAGIC               SQL          finding/action        which legs?     governed answer
# MAGIC ```
# MAGIC
# MAGIC - **`llm(prompt)`** — the one model call (uses `ai_query`, which runs on serverless and is itself
# MAGIC   governed; see the AI Functions reference in `docs.databricks.com/aws/en/reference/api`).
# MAGIC - **`text2sql(question, instructions)`** — the Genie-space pattern in code: a domain's *Instructions*
# MAGIC   block + the question → ONE Spark SQL query, fences stripped.
# MAGIC - **`run_governed_sql(sql)`** — runs the generated SQL on serverless **under the caller's UC
# MAGIC   identity** (so row-level security applies), returning rows or a captured error.

# COMMAND ----------

def llm(prompt: str) -> str:
    """The one model call everything shares. ai_query runs on serverless under UC governance."""
    return spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS out",
        args={"endpoint": LLM_ENDPOINT, "prompt": prompt},
    ).first()["out"]

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        for lang in ("sql", "json"):
            if text.lstrip().lower().startswith(lang):
                text = text.lstrip()[len(lang):]
    return text.strip()

def text2sql(question: str, instructions: str) -> str:
    """Genie-space pattern: turn an NL question into ONE governed Spark SQL query."""
    return _strip_fences(llm(instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:"))

def reason(prompt: str) -> str:
    """A reasoning step: hand the model structured evidence, get a grounded finding/action back."""
    return llm(prompt)

def run_governed_sql(sql: str, limit: int = 50) -> dict:
    """Run generated SQL under the caller's UC identity. Capture errors so one bad leg can't crash a turn."""
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(limit).collect()]
        return {"sql": sql, "rows": rows, "error": None}
    except Exception as e:
        return {"sql": sql, "rows": [], "error": str(e)[:300]}

def to_df(result: dict):
    """Display helper: rows -> DataFrame, or a one-row status (never an all-None dict, which Spark
    cannot infer a schema from when a query legitimately returns zero rows)."""
    if result["rows"]:
        return spark.createDataFrame(result["rows"])
    return spark.createDataFrame([{"status": result["error"] or "no rows returned"}])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — the Genie spaces (created from code)
# MAGIC
# MAGIC The three domain legs call **real Genie spaces** through the Genie Conversation API. Those spaces are
# MAGIC created **from code** (not the UI) by `genie/create_genie_spaces.py`, which uses the Genie Spaces
# MAGIC Management API — `w.genie.create_space(warehouse_id, serialized_space, title=...)` — with a version-2
# MAGIC `serialized_space` (tables + instructions + example SQL + sample questions). Run it once:
# MAGIC
# MAGIC ```bash
# MAGIC python3 genie/create_genie_spaces.py --profile <your-cli-profile>
# MAGIC # writes genie/space_ids.json -> paste the ids into the finance/scm/commercial widgets above
# MAGIC ```
# MAGIC
# MAGIC The cell below **verifies** the three spaces exist on the workspace (it does not recreate them).
# MAGIC Each leg then calls its space via `genie_leg()` (Genie writes + runs the governed SQL under the
# MAGIC caller's identity — OBO); blank a space-id widget to fall back to the in-code `ai_query` reproduction.
# MAGIC
# MAGIC > **Governance note:** in a deployed app the Genie reads run under the **end user** (OBO), so the app
# MAGIC > must carry the `dashboards.genie` + `sql` user-API scopes (set on the app / via its DAB resource).
# MAGIC > In this notebook you are the caller, so your own permissions apply.

# COMMAND ----------

_titles = {
    "FINANCE": "Akzo Finance — Margin & Variance Controlling",
    "SCM": "Akzo SCM — OTIF & Service Control Tower",
    "COMMERCIAL": "Akzo Commercial — Accounts, Churn & Next-Best-Action",
}
_existing = {s.title: s.space_id for s in (_w.genie.list_spaces().spaces or [])}
for dom, title in _titles.items():
    sid = LEG_SPACE_IDS.get(dom, "")
    found = _existing.get(title)
    if sid and found:
        ok = "OK (real Genie)" if sid == found else f"WARN id mismatch (workspace has {found})"
        print(f"  {dom:11s} space '{title}' -> {ok}")
    elif found and not sid:
        print(f"  {dom:11s} space exists ({found}) but widget blank -> leg uses ai_query fallback")
    elif sid and not found:
        print(f"  {dom:11s} widget id set but space NOT found -> run genie/create_genie_spaces.py")
    else:
        print(f"  {dom:11s} no space + no id -> ai_query fallback (or run create_genie_spaces.py)")

# COMMAND ----------

# MAGIC %md
# MAGIC # PART A — The Finance domain agent
# MAGIC
# MAGIC *Use case #1: the Finance controlling copilot.*
# MAGIC
# MAGIC A controller asks *"Paints EMEA gross margin dropped ~8% in Q2 — is it price, volume, FX, or supply,
# MAGIC and what should I do?"* The finance leg turns that into **governed SQL** over Unity Catalog, then a
# MAGIC **reasoning step** turns the numbers into a variance decomposition + a recommended action.

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — the certified metric and the Q2 drop
# MAGIC
# MAGIC A **certified metric view** is how Unity Catalog makes "gross margin %" mean one thing everywhere.
# MAGIC The rule is easy to get wrong: margin % must be a **revenue-weighted ratio of summed EUR amounts** —
# MAGIC `SUM(gross_margin_eur) / SUM(revenue_eur)` — never the average of row-level `gross_margin_pct`. The
# MAGIC view bakes that in, so the agent, a dashboard, and you cannot disagree.

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
  FROM {FIN}.margin_actuals m
  JOIN {FIN}.products p
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
# MAGIC **The number the Finance leg defends.** Query the certified view with `MEASURE()` to see Paints EMEA
# MAGIC gross margin step down Q1 → Q2 2026 — the same metric a controller sees in BI, governed in UC.

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
# MAGIC **What to look for:** two rows. `gross_margin_pct` falls ~39.6% → ~30.7% (the ~8.9pp drop),
# MAGIC `price_per_unit_eur` slides ~34.5 → ~32.7, and `units` stays roughly flat. Flat volume is the first
# MAGIC clue: the damage is price- and cost-driven, not a demand collapse — which the next cell decomposes.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The variance decomposition (price / volume / FX / cost)
# MAGIC
# MAGIC The reasoning step explains the ~8.9pp drop as a **four-way bridge**:
# MAGIC
# MAGIC | Driver | How it's measured | Source |
# MAGIC |---|---|---|
# MAGIC | **Price** | change in realized price/unit (`revenue_eur/units`) | `margin_actuals` |
# MAGIC | **Volume** | change in `units` (~neutral on margin-% if price & cost flat) | `margin_actuals` |
# MAGIC | **FX** | EUR-translation effect from `rate_to_eur` moving for the SKU's currency | `fx_rates` |
# MAGIC | **Cost** | change in unit COGS (raw-material/freight/energy/overhead) | `cost_drivers` |
# MAGIC
# MAGIC We pull every component for Q1 vs Q2 so the LLM reasons over **structured evidence**, not one number.

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
# MAGIC ## TWEAK — the Genie pattern in code: change one instruction, run one query
# MAGIC
# MAGIC A pre-staged **Genie space** turns a plain-English question into governed SQL using its *Instructions*
# MAGIC + example SQL. We reproduce that pattern directly with `text2sql` so the notebook is self-contained:
# MAGIC **the Genie space's instructions become the system prompt.** This is the call the Finance leg makes —
# MAGIC and the thing you tweak.
# MAGIC
# MAGIC > Upgrade path: to use the real Genie space, call the **Genie Conversation API** with the space's
# MAGIC > `space_id` (created in the UI from `genie/finance_space.md`). The text below is the same instruction
# MAGIC > block you paste into that space.

# COMMAND ----------

# >>> THIS IS THE LAYER YOU TWEAK <<< — edit one rule / one example, re-run ONE question below.
FINANCE_INSTRUCTIONS = f"""You are the Akzo Finance text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no markdown fences.

TABLES (all under {FIN}):
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
FROM {FIN}.margin_actuals m
JOIN {FIN}.products p ON m.sku=p.sku
WHERE p.product_line='Decorative Paints' AND p.region='EMEA' AND m.month>=DATE'2026-01-01'
GROUP BY m.month ORDER BY m.month;"""

def ask_finance(question: str, instructions: str = FINANCE_INSTRUCTIONS):
    """Generate SQL from NL, run it on serverless, return (sql, rows-dict). The Genie-space loop."""
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    return run_governed_sql(sql)

result = ask_finance("Why did Paints EMEA gross margin drop in Q2 2026 versus Q1 — show both quarters' margin %?")
display(to_df(result))

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** first the **Generated SQL** — confirm the model honoured the certified rule
# MAGIC (`SUM(gross_margin_eur)/SUM(revenue_eur)`, not an average) and the `Decorative Paints` + `EMEA`
# MAGIC filter. Then the same ~39.6% → ~30.7% you saw in SEE, now produced from plain English.
# MAGIC
# MAGIC **Your turn — the one tweak.** The cell below appends one `Q:/SQL:` example (a COGS-bucket breakdown)
# MAGIC at call time, then asks the matching question. The model mirrors the new example. Try editing the
# MAGIC rounding rule, or pointing a question at `mv_gross_margin` (`MEASURE(...)`) and confirming the number
# MAGIC matches — that is the certified view doing its job.

# COMMAND ----------

TWEAKED = FINANCE_INSTRUCTIONS + f"""

EXAMPLE (added by tweak):
Q: "Break Paints EMEA Q2 2026 COGS into raw material, freight, energy and overhead."
SQL: SELECT ROUND(SUM(c.raw_material_cost)) AS raw_material_eur, ROUND(SUM(c.freight_cost)) AS freight_eur,
ROUND(SUM(c.energy_cost)) AS energy_eur, ROUND(SUM(c.overhead)) AS overhead_eur
FROM {FIN}.cost_drivers c
JOIN {FIN}.products p ON c.sku=p.sku
WHERE p.product_line='Decorative Paints' AND p.region='EMEA'
AND c.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01';"""

result2 = ask_finance("Which cost driver is responsible for the COGS increase in Paints EMEA in Q2 2026?",
                      instructions=TWEAKED)
display(to_df(result2))
# Expect raw_material_cost to dominate — the TiO2/resin spike, ~15-20% up in Q2.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The reasoning step: number → decomposition → recommended action
# MAGIC
# MAGIC A copilot is more than text2SQL. After retrieving governed numbers, a **reasoning step** turns them
# MAGIC into a controller-ready bridge + a concrete action. We feed the `df_decomp` table to the LLM and ask
# MAGIC for the four-way attribution — grounded **only** in the numbers, no hallucinated figures.

# COMMAND ----------

decomp_rows = [r.asDict() for r in df_decomp.collect()]
evidence = json.dumps(decomp_rows, default=str)   # default=str so any DATE/Decimal serializes cleanly

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

print(reason(REASONING_PROMPT))

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — this is the supervisor's Finance leg
# MAGIC
# MAGIC The certified view + `text2sql` + the reasoning step **are** what the supervisor invokes when a
# MAGIC question's finance part is routed here. Your tweak changes the whole supervisor's answer with no
# MAGIC other wiring touched.
# MAGIC
# MAGIC **Proved on governed data:** Paints EMEA gross margin **39.6% (Q1) → 30.7% (Q2)** (~8.9pp); bridge =
# MAGIC price ~−3pp, raw-material cost ~−3pp, FX ~−2pp, volume ~flat.
# MAGIC
# MAGIC **Honest scope (sets up Part B):** this leg reads governed UC tables under *your* identity. The
# MAGIC controller and the EMEA planner asking the same question should see different rows — that is UC
# MAGIC row-level security + OBO, which we add next.

# COMMAND ----------

# MAGIC %md
# MAGIC # PART B — Per-user truth: UC row-level security + OBO
# MAGIC
# MAGIC *The read-governance half of use case #4: the AI governance & policy agent.*
# MAGIC
# MAGIC A **controller** and an **EMEA planner** ask the *same* question and get answers backed by
# MAGIC *different rows*. That is **Unity Catalog row-level security (RLS)** enforcing each caller's scope,
# MAGIC and **On-Behalf-Of (OBO)** carrying the caller's identity through the agent into the query.
# MAGIC
# MAGIC ```
# MAGIC     same question ─────────────▶  margin_actuals  (ROW FILTER on region)
# MAGIC                                          │
# MAGIC              ┌───────────────────────────┴───────────────────────────┐
# MAGIC          controller (scope ALL)                          planner (scope EMEA)
# MAGIC          sees 4 regions                                  sees 1 region
# MAGIC ```
# MAGIC
# MAGIC **Honest scope:** OBO + RLS govern **reads**. They do **not** automatically govern writes — those use
# MAGIC Postgres roles + approval + audit (Chapter 2). Keeping the two planes distinct is the honest answer to
# MAGIC a 2,000-user rollout.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The personas mapping (ABAC source of truth)
# MAGIC
# MAGIC RLS is driven by a small governed table mapping each user to a **role** and a **region scope**. Change
# MAGIC a row here and every table protected by the filter changes what that user sees. We seed **the current
# MAGIC user as the controller** so the notebook runs end-to-end for you, plus two illustrative personas.
# MAGIC
# MAGIC | Role | Region scope | Meaning |
# MAGIC |---|---|---|
# MAGIC | `controller` | `ALL` | sees every region |
# MAGIC | `planner` | `EMEA` | sees EMEA only |
# MAGIC | `rep` | (one segment) | sees one commercial segment |

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OPS}")
me = spark.sql("SELECT current_user() AS u").first()["u"]
print("You are:", me)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {OPS}.personas (
  user_email   STRING COMMENT 'UC principal (email)',
  role         STRING COMMENT 'controller | planner | rep',
  region_scope STRING COMMENT 'ALL or a single region: EMEA/Americas/APAC/China',
  segment_scope STRING COMMENT 'for reps: one commercial segment, else ALL'
)
COMMENT 'ABAC persona mapping that drives Unity Catalog row-level security'
""")

spark.sql(f"""
INSERT OVERWRITE {OPS}.personas VALUES
  ('{me}',                  'controller', 'ALL',  'ALL'),
  ('planner.emea@akzo.example', 'planner', 'EMEA', 'ALL'),
  ('rep.arch@akzo.example',     'rep',     'EMEA', 'Architectural')
""")
display(spark.sql(f"SELECT * FROM {OPS}.personas ORDER BY role"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## The row filter, applied to a governed finance table
# MAGIC
# MAGIC A UC **row filter** is a SQL UDF returning BOOLEAN. It receives the protected column (a row's
# MAGIC `region`) and returns whether the **current caller** may see that row: look the caller up in
# MAGIC `personas`; `ALL` sees everything, otherwise only matching regions; account admins always pass. We
# MAGIC attach it to `margin_actuals` — from now on **every** read (notebook, dashboard, Genie, supervisor)
# MAGIC is automatically scoped to the caller's persona. The agent implements no security; UC enforces it.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {OPS}.fn_region_rls(row_region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: caller sees a region row only if their persona scope is ALL or matches it'
RETURN
  is_account_group_member('admins')
  OR EXISTS (
    SELECT 1 FROM {OPS}.personas p
    WHERE p.user_email = current_user()
      AND (p.region_scope = 'ALL' OR p.region_scope = row_region)
  )
""")
spark.sql(f"ALTER TABLE {FIN}.margin_actuals SET ROW FILTER {OPS}.fn_region_rls ON (region)")
print("ROW FILTER applied to", f"{FIN}.margin_actuals", "on (region)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — same question, different rows
# MAGIC
# MAGIC `current_user()` is the OBO identity — in an agent call it is the *end user*, not the agent's service
# MAGIC principal. As the controller (you), the filter returns all 4 regions. We then show the rows a planner
# MAGIC (scope `EMEA`) would be left with — we can't fully impersonate another user from a notebook (that is
# MAGIC exactly OBO's job at the Genie/agent layer), so we apply the planner's scope directly.

# COMMAND ----------

display(spark.sql(f"""
SELECT current_user() AS whoami,
       COUNT(DISTINCT region) AS regions_visible,
       collect_set(region)    AS regions
FROM {FIN}.margin_actuals
"""))
# Controller persona -> regions_visible = 4 (EMEA, Americas, APAC, China)

# COMMAND ----------

display(spark.sql(f"""
SELECT 'planner.emea@akzo.example' AS as_if_user,
       COUNT(DISTINCT region) AS regions_visible,
       collect_set(region)    AS regions
FROM {FIN}.margin_actuals
WHERE region = (SELECT region_scope FROM {OPS}.personas WHERE user_email='planner.emea@akzo.example')
"""))
# Planner persona -> regions_visible = 1 (EMEA only)

# COMMAND ----------

# MAGIC %md
# MAGIC **Look for:** controller → 4 regions, planner → 1 (`EMEA`). Same table, same question, different
# MAGIC governed truth — because OBO carried a different identity into the same row-filtered table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — flip one persona attribute, watch the scope move
# MAGIC
# MAGIC Change **one** persona's `region_scope` and re-run the visibility check. We widen the planner from
# MAGIC `EMEA` to `ALL`, then revert — watch the visible-region count go `1 → 4 → 1`. One `UPDATE`, no table
# MAGIC reload, no agent change. That live re-scope is the governance story Akzo cares about.

# COMMAND ----------

def regions_visible_for(user_email: str) -> int:
    """Smoke test: how many regions a persona's scope would expose (filter-equivalent)."""
    return spark.sql(f"""
      SELECT COUNT(DISTINCT m.region) AS n
      FROM {FIN}.margin_actuals m
      WHERE EXISTS (
        SELECT 1 FROM {OPS}.personas p
        WHERE p.user_email = '{user_email}'
          AND (p.region_scope = 'ALL' OR p.region_scope = m.region)
      )
    """).first()["n"]

print("planner before tweak:", regions_visible_for("planner.emea@akzo.example"), "region(s)")
spark.sql(f"UPDATE {OPS}.personas SET region_scope='ALL' WHERE user_email='planner.emea@akzo.example'")
print("planner after  tweak:", regions_visible_for("planner.emea@akzo.example"), "region(s)")
spark.sql(f"UPDATE {OPS}.personas SET region_scope='EMEA' WHERE user_email='planner.emea@akzo.example'")
print("planner reverted    :", regions_visible_for("planner.emea@akzo.example"), "region(s)")
# Expect the sequence: 1 -> 4 -> 1

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — the supervisor, governed per user
# MAGIC
# MAGIC With the filter live, the Finance leg is now **automatically** per-user: the controller's supervisor
# MAGIC answers over all regions, the planner's over EMEA — neither the Genie space nor the agent has a line
# MAGIC of access-control code. UC enforces it under OBO.
# MAGIC
# MAGIC **Write governance is different — plainly:** OBO/RLS govern reads. Lakebase (Postgres) writes use
# MAGIC Postgres roles; UC-registered Lakebase is read-only. The write path (Chapter 2) is app/service
# MAGIC identity + approval + audit. "Who can see what" and "who can change what" are two separate planes.
# MAGIC
# MAGIC > To reset for another walkthrough: `ALTER TABLE {FIN}.margin_actuals DROP ROW FILTER`. We leave it on
# MAGIC > so the supervisor demo below is governed.

# COMMAND ----------

# MAGIC %md
# MAGIC # PART C — More domain legs: SCM + Commercial
# MAGIC
# MAGIC *Use case #2 (SCM control tower) and use case #5 (Commercial action assistant).*
# MAGIC
# MAGIC The point of this part: the **recipe repeats**. Genie-space instructions + `text2sql` + a reasoning
# MAGIC step, applied to two more domains. That repetition *is* the lesson — and it tells one connected
# MAGIC story: the EMEA margin shock has a **supply cause** (SCM) and a **commercial consequence** (churn).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Domain A — SCM control tower
# MAGIC
# MAGIC >>> A LAYER YOU TWEAK <<< — edit one rule / add one example, re-run one SCM question. Same `text2sql`
# MAGIC helper as Part A, a different instruction block. The certified rule here: OTIF is **orders-weighted**,
# MAGIC never a flat average.

# COMMAND ----------

SCM_INSTRUCTIONS = f"""You are the Akzo SCM text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no fences.

TABLES (all under {SCM}):
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
FROM {SCM}.otif
WHERE lane='Rotterdam-NL->EMEA-DACH' AND month>=DATE'2026-01-01'
GROUP BY month ORDER BY month;"""

def ask(question: str, instructions: str):
    sql = text2sql(question, instructions)
    print("Generated SQL:\n" + sql + "\n")
    r = run_governed_sql(sql)
    return r

# SEE: the Rotterdam OTIF dip the SCM leg explains
r = ask("Show monthly OTIF for the Rotterdam-NL to EMEA-DACH lane in 2026.", SCM_INSTRUCTIONS)
display(to_df(r))
# Expect ~96% Jan-Mar -> 88.9% May -> ~93.0% June: the disrupted EMEA lane.

# COMMAND ----------

# MAGIC %md
# MAGIC **SCM reasoning step: root cause → intervention.** Gather structured evidence (lane OTIF trend,
# MAGIC stockouts, service/backorders), hand it to the LLM, ask for a root cause + **one concrete
# MAGIC intervention**. The model reasons only over the verified JSON — and is told to *recommend, not
# MAGIC execute* (the reroute is a governed write, Chapter 2).

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

scm_evidence = json.dumps({
    "lane_otif_pct_by_month": [r.asDict() for r in lane_trend],
    "may_stockouts": [r.asDict() for r in stockouts],
    "emea_service_and_backorders": [r.asDict() for r in service],
    "lane_lead_time": "Rotterdam-NL->EMEA-DACH road lane stepped from 5 to 9 days in Q2 2026",
}, default=str)

print(reason(f"""You are an Akzo SCM control-tower copilot. Verified governed data (JSON):
{scm_evidence}

Task: in under 160 words, (1) state the root cause of the May 2026 EMEA service drop tying together
lead time, stockout, and the OTIF/service/backorder numbers; (2) recommend ONE concrete intervention
for a supply planner. Use ONLY the numbers above. Note this is a diagnostic copilot — it recommends,
it does not execute the reroute (that is a governed write in the scm_interventions queue).
Format:
- Root cause: ...
- Evidence: OTIF ..., stockout ..., service/backorders ...
- Recommended intervention: ..."""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Domain B — Commercial action assistant
# MAGIC
# MAGIC >>> A LAYER YOU TWEAK <<< — same recipe, third domain. "At churn risk" := `churn_score > 0.7`. The
# MAGIC reasoning step ties the churn to the **upstream service problem** (not pricing) — the same fusion the
# MAGIC supervisor does across all three legs next.

# COMMAND ----------

COM_INSTRUCTIONS = f"""You are the Akzo Commercial text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no fences.

TABLES (all under {COM}):
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
FROM {COM}.churn_signals c
JOIN {COM}.accounts a ON c.account_id=a.account_id
WHERE c.month=DATE'2026-06-01' AND c.churn_score>0.7 ORDER BY c.churn_score DESC;"""

# SEE: the three at-risk EMEA accounts
r_risk = ask("Which Paints EMEA accounts are at churn risk in June 2026 and why? Include owner_rep, last_order_days, complaint_count, nps.", COM_INSTRUCTIONS)
display(to_df(r_risk))
# Expect ACC0001 Rhine Valley Decor Distributors (0.865), ACC0002 Benelux PaintPro (0.827),
# ACC0003 Nordic Coatings Supply (0.800) — all >0.7.

# COMMAND ----------

# MAGIC %md
# MAGIC **Commercial reasoning step: signals → next-best-action.** Read the at-risk signals + revenue trend,
# MAGIC tie the churn to the upstream service shock, propose a save play that would be staged as a
# MAGIC `commercial_action` for human approval (it recommends; it does not approve discounts or send email).

# COMMAND ----------

rev_trend = spark.sql(f"""
  SELECT month, ROUND(SUM(revenue_eur)) AS combined_revenue_eur
  FROM {COM}.sales_actuals WHERE account_id IN ('ACC0001','ACC0002','ACC0003') AND month>=DATE'2026-01-01'
  GROUP BY month ORDER BY month
""").collect()

com_evidence = json.dumps({
    "at_risk_accounts_jun2026": r_risk["rows"],
    "combined_revenue_trend": [r.asDict() for r in rev_trend],
    "upstream_context": "Paints EMEA OTIF/service collapsed in May 2026 (Rotterdam lane, stockouts); these are Decorative Paints (Architectural EMEA) buyers.",
}, default=str)

print(reason(f"""You are an Akzo Commercial action assistant. Verified governed data (JSON):
{com_evidence}

Task: in under 170 words, (1) confirm the three at-risk accounts and cite each one's churn_score and
the driving signals; (2) state that the churn is a DOWNSTREAM consequence of the EMEA service/OTIF
shock, not a pricing failure; (3) recommend ONE concrete next-best-action (save play) for the top
account's owner rep, framed around fixing the service issue, and note it would be logged as a
commercial_action for human approval. Use ONLY the data above.
Format:
- At-risk accounts: ...
- Root cause: ...
- Next-best-action for ACC0001: ..."""))

# COMMAND ----------

# MAGIC %md
# MAGIC **The recipe repeated cleanly across three domains:**
# MAGIC
# MAGIC | Leg | text2SQL over | Reasoning produces | Verified anchor |
# MAGIC |---|---|---|---|
# MAGIC | **Finance** (A) | `akzo_finance` | variance decomposition + action | GM 39.6%→30.7% (−8.9pp) |
# MAGIC | **SCM** (C) | `akzo_scm` | root cause + intervention | Rotterdam OTIF 96%→88.9% May |
# MAGIC | **Commercial** (C) | `akzo_commercial` | signals + next-best-action | ACC0001/2/3 churn >0.7 |
# MAGIC
# MAGIC One story: the EMEA margin shock (finance) has a supply cause (SCM) and a customer consequence
# MAGIC (commercial). That is exactly the cross-domain question the supervisor fuses next.

# COMMAND ----------

# MAGIC %md
# MAGIC # PART D — The supervisor itself
# MAGIC
# MAGIC *Use case #3: the flagship Multi-Agent Supervisor.*
# MAGIC
# MAGIC One supervisor that, given a question, **decides which legs to call**, runs them, and **fuses one
# MAGIC governed answer** — with a routing trace you can inspect.
# MAGIC
# MAGIC ```
# MAGIC   question ─▶ ROUTER ─▶ {FINANCE, SCM, COMMERCIAL}? ─▶ run chosen legs ─▶ FUSER ─▶ one answer
# MAGIC                 │              (the layer you tweak)        (governed,           (grounded in
# MAGIC            one LLM call         routing = config            per-user OBO)         the rows only)
# MAGIC ```
# MAGIC
# MAGIC **The flagship question** is *not* single-cause: the supervisor must route to **Finance** (margin
# MAGIC bridge) **and SCM** (the Rotterdam shock) and fuse them into "it is BOTH a margin/cost issue AND a
# MAGIC supply/service issue → here is the action."

# COMMAND ----------

# MAGIC %md
# MAGIC ## The legs as subagents, and the router
# MAGIC
# MAGIC Each leg is the same shape as Parts A/C. The supervisor treats each as a **subagent** it can choose
# MAGIC to invoke — exactly how a native Agent Bricks MAS treats a registered Genie space. The **router** is
# MAGIC one LLM call given the question + a one-line **description** per subagent; it returns JSON naming the
# MAGIC domains to call. *This is the layer you tweak* — change a description and the same question routes
# MAGIC differently. In a native MAS, this description **is** the per-subagent "description" field.

# COMMAND ----------

LEG_INSTRUCTIONS = {"FINANCE": FINANCE_INSTRUCTIONS, "SCM": SCM_INSTRUCTIONS, "COMMERCIAL": COM_INSTRUCTIONS}

def call_leg(domain: str, question: str) -> dict:
    """Invoke one domain subagent. If the domain's Genie space id is set, call the REAL Genie space
    (Genie writes + runs the governed SQL under the caller's identity); otherwise fall back to the
    in-code ai_query reproduction. Same {domain, sql, rows, error} contract either way."""
    space_id = LEG_SPACE_IDS.get(domain, "")
    if space_id:
        r = genie_leg(space_id, question)
    else:
        r = run_governed_sql(text2sql(question, LEG_INSTRUCTIONS[domain]))
    return {"domain": domain, "via": "genie_space" if space_id else "ai_query", **r}

# >>> THIS IS THE LAYER YOU TWEAK <<< — edit a domain's description line and re-run supervise() below.
ROUTING_DESCRIPTION = {
    "FINANCE":    "Gross margin, price/realized price per unit, FX translation, COGS / raw-material / freight / energy cost, budget variance. Use for any 'why did margin/price/cost change' question.",
    "SCM":        "OTIF (on-time-in-full), inventory, stockouts, days of supply, transport lanes, lead times, service levels, backorders. Use for supply, service, delivery, or fulfilment questions.",
    "COMMERCIAL": "Customer accounts, churn risk/score, NPS, complaints, sales/revenue by account, pipeline. Use for customer-risk, retention, or account-impact questions.",
}

def route(question: str, descriptions: dict = ROUTING_DESCRIPTION) -> dict:
    lines = "\n".join(f"- {d}: {desc}" for d, desc in descriptions.items())
    prompt = f"""You are the routing controller for an AkzoNobel Multi-Agent Supervisor. Registered domain subagents:
{lines}

Decide which subagent(s) are needed to fully answer the user's question. A cross-domain "why" question
often needs several. Output ONLY a JSON object, no prose:
{{"domains": ["FINANCE"|"SCM"|"COMMERCIAL", ...], "reason": "<one sentence per chosen domain>"}}

Question: {question}"""
    raw = _strip_fences(llm(prompt))
    try:
        decision = json.loads(raw)
    except Exception:
        decision = {"domains": ["FINANCE", "SCM", "COMMERCIAL"], "reason": "router parse fallback: " + raw[:200]}
    decision["domains"] = [d for d in decision.get("domains", []) if d in LEG_INSTRUCTIONS]
    return decision

# COMMAND ----------

# MAGIC %md
# MAGIC ## The fuser, and the full supervisor turn
# MAGIC
# MAGIC After the chosen legs run, the supervisor hands their **structured rows** (not free text) to a final
# MAGIC LLM call that fuses one answer, grounded only in the retrieved numbers. `supervise()` is the whole
# MAGIC loop: route → call legs → fuse, returning a trace + the fused answer.

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
    return llm(prompt)

def supervise(question: str, descriptions: dict = ROUTING_DESCRIPTION, verbose: bool = True) -> dict:
    """Full supervisor turn: route -> call chosen legs -> fuse. Returns a trace + the fused answer."""
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
# MAGIC ## SEE — route + fuse the flagship cross-domain question
# MAGIC
# MAGIC Watch the **routing trace** first (which domains, why), then the per-leg SQL, then the single fused
# MAGIC answer. The routing — not the prose — is the interesting part.

# COMMAND ----------

FLAGSHIP = "Paints EMEA gross margin dropped ~8% in Q2 2026 — is it price, volume, or a supply/service issue, and what should I do?"

result = supervise(FLAGSHIP)
print("=" * 80)
print("FUSED ANSWER")
print("=" * 80)
print(result["answer"])
# Expect routing -> FINANCE + SCM (often + COMMERCIAL), and a fused answer that names the
# ~8.9pp margin bridge (price/FX/raw-material) AND the Rotterdam OTIF dip to ~89% in May.

# COMMAND ----------

# MAGIC %md
# MAGIC **The routing trace, as a table.** A native MAS shows this in its trace UI; here we render the same
# MAGIC information — which subagents were consulted, and the governed SQL each ran. One row per consulted
# MAGIC subagent; if a leg shows an error, its SQL is right there to debug.

# COMMAND ----------

trace_rows = [
    {"domain": lr["domain"], "via": lr.get("via", ""), "rows_returned": len(lr["rows"]),
     "error": lr["error"] or "", "generated_sql": lr["sql"]}
    for lr in result["legs"]
]
display(spark.createDataFrame(trace_rows))

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — edit the routing description, watch routing change
# MAGIC
# MAGIC We **narrow** Finance to *cost only* and **widen** SCM to own "price/margin pressure from supply".
# MAGIC Re-running the *same* flagship question routes differently — the router follows the descriptions, not
# MAGIC the question's wording. Same question, edited descriptions, different route: **routing is config.**

# COMMAND ----------

TWEAKED_DESCRIPTION = {
    "FINANCE":    "Raw-material, freight, energy, and overhead COST levels only. Does NOT cover price, margin, or FX.",
    "SCM":        "OTIF, stockouts, lead times, lanes, service, backorders — AND any margin/price pressure caused by a supply or service disruption.",
    "COMMERCIAL": "Customer accounts, churn risk/score, NPS, complaints, account revenue. Use for customer-risk questions.",
}

tweaked = supervise(FLAGSHIP, descriptions=TWEAKED_DESCRIPTION)
print("=" * 80)
print("FUSED ANSWER (after routing-description tweak)")
print("=" * 80)
print(tweaked["answer"])

# COMMAND ----------

display(spark.createDataFrame([
    {"variant": "default",  "domains_routed": ", ".join(result["decision"]["domains"]),
     "reason": result["decision"].get("reason", "")},
    {"variant": "tweaked",  "domains_routed": ", ".join(tweaked["decision"]["domains"]),
     "reason": tweaked["decision"].get("reason", "")},
]))
# Look for: the domains_routed column differs between rows. Routing followed the description, not the words.

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — one chat, cross-domain, governed per user
# MAGIC
# MAGIC The supervisor reads → routes → calls the governed legs → fuses one answer. **Verified:** the
# MAGIC flagship question routes to **Finance + SCM** (usually + Commercial); the fused answer connects the
# MAGIC **~8.9pp margin bridge** (price/FX/raw-material) to the **Rotterdam OTIF dip to ~89% in May**,
# MAGIC concluding it is *both* a margin/cost issue *and* a supply/service issue, with a concrete action.
# MAGIC
# MAGIC ### How OBO governs this supervisor
# MAGIC Every `call_leg` runs its SQL **as the calling user**. With Part B's row filter live, the controller
# MAGIC sees all four regions and the EMEA planner sees EMEA only — *same routing, different governed truth*.
# MAGIC OBO also gates subagent access (a user who lacks access to a Genie space cannot have the supervisor
# MAGIC route to it on their behalf). OBO governs **reads only** — writes are governed in Chapter 2.
# MAGIC
# MAGIC ### Upgrade path: this router → a native Agent Bricks Multi-Agent Supervisor
# MAGIC This notebook is a faithful, self-contained reproduction. To move to the managed product:
# MAGIC 1. **Register each Genie space as a subagent** of a Multi-Agent Supervisor (Agent Bricks UI / SDK),
# MAGIC    pasting the same `genie/*_space.md` instructions. The per-subagent **description** field is exactly
# MAGIC    the `ROUTING_DESCRIPTION` you tweaked here. (Keep a single supervisor under ~20 subagents; the UI
# MAGIC    lets you select more, but stay focused — we use exactly the 3 Akzo domains.)
# MAGIC 2. The MAS runs the route → call → fuse loop for you, **with OBO and tracing built in** — no
# MAGIC    router/fuser code to maintain.
# MAGIC 3. Call the deployed MAS endpoint with the `agent/v1/responses` task (see the Serving + Agent API
# MAGIC    reference under `docs.databricks.com/aws/en/reference/api`). The optional cell below shows the call
# MAGIC    shape; comment it in once your own MAS is registered over the three Akzo Genie spaces.
# MAGIC
# MAGIC ```python
# MAGIC # Optional — call a deployed native MAS endpoint once you have registered one.
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC w = WorkspaceClient()
# MAGIC resp = w.serving_endpoints.query(
# MAGIC     name="<your-mas-endpoint>",
# MAGIC     extra_params={"input": [{"role": "user", "content": FLAGSHIP}]},
# MAGIC )
# MAGIC print(resp)
# MAGIC ```
# MAGIC
# MAGIC **Next:** `02_agents_that_act.py` — the supervisor stops answering and starts *acting*, on a governed
# MAGIC write plane (memory, staging, approval, external execution).
