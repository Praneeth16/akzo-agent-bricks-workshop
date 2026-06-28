# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 2 — Per-user truth: Unity Catalog RLS/ABAC + OBO
# MAGIC
# MAGIC *Reveals the read-governance half of use case #4, the AI governance & policy agent.*
# MAGIC
# MAGIC In the cold open, a **controller** and an **EMEA planner** asked the *same* question and got
# MAGIC answers backed by *different rows*. That was not the agent being clever — it was **Unity Catalog
# MAGIC row-level security** enforcing each caller's data scope, and **On-Behalf-Of (OBO)** carrying the
# MAGIC caller's identity through the agent into the query. This notebook is the reference build behind
# MAGIC that moment.
# MAGIC
# MAGIC **3-beat rhythm:**
# MAGIC 1. **See** — controller vs planner, same question, different rows.
# MAGIC 2. **Tweak** — flip one persona attribute in the `personas` table and re-run the `whoami` / RLS
# MAGIC    smoke test as that persona.
# MAGIC 3. **Return** — re-run the supervisor's Finance leg as both personas; the data changes with the
# MAGIC    user, no agent code touched.
# MAGIC
# MAGIC **Honest scope (this is the answer to Akzo's 2,000-user-rollout fear):** OBO + UC/RLS govern
# MAGIC **reads** — Genie and the Supervisor enforce the caller's UC permissions on the data and on
# MAGIC subagent access. It does **not** automatically govern every **write**. Lakebase writes use
# MAGIC Postgres roles independently; UC-registered Lakebase is read-only. Writes are governed separately
# MAGIC (Layer 5) by app/service identity + approval + audit. We state this plainly here.
# MAGIC
# MAGIC **What you'll learn:** how a Unity Catalog row filter (a BOOLEAN SQL UDF) + an ABAC persona table
# MAGIC turn one physical table into per-caller views, and why this is the load-bearing mechanism behind
# MAGIC "same question, different rows" under OBO.
# MAGIC
# MAGIC **Prerequisites:** run `01_*` first — it creates the `akzo_finance.margin_actuals` table this
# MAGIC notebook governs. You need a serverless SQL warehouse / cluster and permission to `CREATE SCHEMA`,
# MAGIC `CREATE FUNCTION`, and `ALTER TABLE ... SET ROW FILTER` in the catalog below.
# MAGIC
# MAGIC **How to run (~10 min):** execute top-to-bottom. The notebook seeds **you** as the controller so
# MAGIC every cell runs end-to-end on your own identity; persona rows for planner/rep are illustrative.
# MAGIC Follow the **SEE → TWEAK → RETURN** beats in order — each builds on the filter applied earlier.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Pin the catalog and schema names, ensure the `akzo_ops` schema exists (it holds the persona table
# MAGIC and RLS function), and print **who you are**. That `current_user()` value is the identity every
# MAGIC filter check below resolves against, so confirm it's really you before proceeding.

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
FIN = f"{CATALOG}.akzo_finance"
OPS = f"{CATALOG}.akzo_ops"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OPS}")
spark.sql(f"USE CATALOG {CATALOG}")

me = spark.sql("SELECT current_user() AS u").first()["u"]
print("You are:", me)

# COMMAND ----------

# MAGIC %md
# MAGIC ## The personas mapping
# MAGIC
# MAGIC RLS is driven by a small governed table that maps each user to a **role** and a **region scope**.
# MAGIC This is the ABAC (attribute-based access control) source of truth — change a row here and every
# MAGIC table protected by the filter function changes what that user can see.
# MAGIC
# MAGIC | Role | Region scope | Meaning |
# MAGIC |---|---|---|
# MAGIC | `controller` | `ALL` | sees every region |
# MAGIC | `planner` | `EMEA` | sees EMEA only |
# MAGIC | `rep` | (one segment) | sees one commercial segment |
# MAGIC
# MAGIC We seed **the current user as the controller** so this notebook runs end-to-end for you, plus two
# MAGIC illustrative personas. (In the staged workshop these are real Day-0 test users.)

# COMMAND ----------

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
# MAGIC **Look for:** three rows. Your email shows `controller / ALL`; the planner is scoped to `EMEA`;
# MAGIC the rep is scoped to one segment. These three rows are the entire access policy — everything
# MAGIC downstream is derived from them.

# COMMAND ----------

# MAGIC %md
# MAGIC ## The row-level-security function
# MAGIC
# MAGIC A UC **row filter** is a SQL UDF returning BOOLEAN. It receives the value of the protected
# MAGIC column (here, a row's `region`) and returns whether the **current caller** may see that row.
# MAGIC The logic: look up the caller in `personas`; if their `region_scope` is `ALL` they see
# MAGIC everything, otherwise only rows matching their region. Account admins always pass (so the table
# MAGIC stays manageable).

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
print("Created row-filter function:", f"{OPS}.fn_region_rls")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Apply the ROW FILTER to a governed finance table
# MAGIC
# MAGIC We attach the filter to `margin_actuals` on its `region` column. From now on **every** read of
# MAGIC this table — by a notebook, a dashboard, Genie, or the Supervisor Agent — is automatically
# MAGIC scoped to the caller's persona. The agent does not implement security; UC enforces it underneath.
# MAGIC
# MAGIC > The same one-line `ALTER` applies to any SCM/commercial table (e.g. `akzo_scm.otif` on its
# MAGIC > `region` column). One filter function, reused across the lakehouse.

# COMMAND ----------

spark.sql(f"ALTER TABLE {FIN}.margin_actuals SET ROW FILTER {OPS}.fn_region_rls ON (region)")
print("ROW FILTER applied to", f"{FIN}.margin_actuals", "on (region)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: same question, different rows
# MAGIC
# MAGIC `current_user()` is the OBO identity — in an agent call it is the *end user*, not the agent's
# MAGIC service principal. The query below counts visible regions **for whoever is running it**. As the
# MAGIC controller (you), the filter returns all 4 regions.

# COMMAND ----------

display(spark.sql(f"""
SELECT current_user() AS whoami,
       COUNT(DISTINCT region) AS regions_visible,
       collect_set(region)    AS regions
FROM {FIN}.margin_actuals
"""))
# Controller persona -> regions_visible = 4 (EMEA, Americas, APAC, China)

# COMMAND ----------

# MAGIC %md
# MAGIC **Look for:** `regions_visible = 4` and all four regions in the set. You're the controller, so the
# MAGIC filter passes every row. Keep this number in mind — the planner check below should collapse it to 1.

# COMMAND ----------

# MAGIC %md
# MAGIC **What the EMEA planner would see.** We cannot fully impersonate another user from this notebook
# MAGIC (that's exactly OBO's job at the Genie/agent layer), so we demonstrate the filter's logic two
# MAGIC honest ways:
# MAGIC
# MAGIC 1. **The predicate the planner's persona produces** — apply the planner's scope (`EMEA`)
# MAGIC    directly and confirm it collapses to one region.
# MAGIC 2. **The filter function evaluated against the planner persona** — show the function returns
# MAGIC    TRUE only for EMEA rows when the caller is the planner.

# COMMAND ----------

# (1) The rows a planner (region_scope='EMEA') would be left with:
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
# MAGIC **Look for:** `regions_visible = 1`, set `[EMEA]`. The same table that gave you 4 regions yields 1
# MAGIC for the planner — that delta is the entire point of this notebook, reproduced without leaving your
# MAGIC own session.

# COMMAND ----------

# MAGIC %md
# MAGIC **The cold-open moment, explained.** The controller's Finance leg answered the margin question
# MAGIC over **all four regions**; the planner's identical question was answered over **EMEA only**.
# MAGIC Same Genie space, same SQL — different governed truth, because OBO carried a different identity
# MAGIC into the same row-filtered table.

# COMMAND ----------

# Controller view of the margin question (all regions visible to you):
display(spark.sql(f"""
SELECT region,
       ROUND(SUM(gross_margin_eur)/SUM(revenue_eur)*100,1) AS q2_gross_margin_pct
FROM {FIN}.margin_actuals
WHERE month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01'
GROUP BY region ORDER BY q2_gross_margin_pct
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC **Look for:** one Q2 gross-margin row **per region** (4 rows for you, the controller). This is the
# MAGIC actual business answer the Finance leg returns — and it's already row-filtered, so a planner running
# MAGIC the identical SQL would get only the EMEA row.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: flip one persona attribute, re-run the smoke test
# MAGIC
# MAGIC The hands-on tweak: change **one** persona's `region_scope` and re-run the visibility check.
# MAGIC Below we promote the planner from `EMEA` to `ALL` (then revert). Run the smoke-test cell after
# MAGIC each change to watch the visible-region count move.

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

# >>> THE TWEAK <<< : widen the planner's scope to ALL
spark.sql(f"UPDATE {OPS}.personas SET region_scope='ALL' WHERE user_email='planner.emea@akzo.example'")
print("planner after  tweak:", regions_visible_for("planner.emea@akzo.example"), "region(s)")

# revert so the demo stays in its canonical state
spark.sql(f"UPDATE {OPS}.personas SET region_scope='EMEA' WHERE user_email='planner.emea@akzo.example'")
print("planner reverted    :", regions_visible_for("planner.emea@akzo.example"), "region(s)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Look for:** the printed sequence `1 → 4 → 1`. One `UPDATE` to a single persona row instantly
# MAGIC widened then re-narrowed what that user can see — no table reload, no agent change. That live
# MAGIC re-scope is the governance story Akzo cares about for a 2,000-user rollout.

# COMMAND ----------

# MAGIC %md
# MAGIC **Other one-line tweaks to try** (each is a single statement, then re-run the smoke test):
# MAGIC - Re-scope the rep to a different segment: `UPDATE ... SET segment_scope='Industrial' WHERE role='rep'`.
# MAGIC - Add yourself a second persona row and watch `EXISTS` widen your scope.
# MAGIC - Apply `fn_region_rls` to `akzo_scm.otif` (`ALTER TABLE ... SET ROW FILTER ... ON (region)`)
# MAGIC   and confirm the SCM leg is now governed the same way.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: the supervisor, governed per user
# MAGIC
# MAGIC With the row filter live, the Finance leg from Layer 1 is now **automatically** per-user: the
# MAGIC controller's supervisor answers over all regions, the planner's over EMEA — and neither the
# MAGIC Genie space nor the agent has a single line of access-control code. UC enforces it under OBO.
# MAGIC
# MAGIC **Verified:** controller persona → **4 regions**; planner persona → **1 region (EMEA)**, same
# MAGIC table, same question.
# MAGIC
# MAGIC ### Write governance is different — say it plainly
# MAGIC OBO/RLS govern **reads**. They do **not** govern writes. When the agent stops answering and
# MAGIC starts *acting* (Layer 5), the write path is:
# MAGIC - **Lakebase (Postgres)** writes use **Postgres roles**, not UC RLS. UC-registered Lakebase is
# MAGIC   **read-only**.
# MAGIC - The demo writes through an **app/service identity** with an **approval queue + audit trail**.
# MAGIC - So "who can see what" (here) and "who can change what" (Layer 5) are two separate governance
# MAGIC   planes. Conflating them is the mistake; keeping them distinct is the honest 2,000-user story.
# MAGIC
# MAGIC ### Cleanup (optional)
# MAGIC To detach the filter (e.g. to reset for another walkthrough):
# MAGIC `ALTER TABLE serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals DROP ROW FILTER`
# MAGIC
# MAGIC **Next:** `03_scm_commercial_legs.py`.

# COMMAND ----------

# Leave the table governed for the supervisor demo. Uncomment to reset:
# spark.sql(f"ALTER TABLE {FIN}.margin_actuals DROP ROW FILTER")
print("Layer 2 complete. margin_actuals is row-filtered by persona under OBO.")
