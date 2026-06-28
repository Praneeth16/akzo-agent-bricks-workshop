# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 4 — The supervisor itself
# MAGIC
# MAGIC *Reveals use case #3, the flagship Multi-Agent Supervisor.*
# MAGIC
# MAGIC Layers 1 and 3 built three domain legs (Finance, SCM, Commercial), each a Genie space over
# MAGIC governed UC tables + a text2SQL call + a reasoning step. This layer is the **composition**: one
# MAGIC supervisor that, given a question, **decides which legs to call**, runs them, and **fuses one
# MAGIC governed answer** — with a routing trace you can open and inspect.
# MAGIC
# MAGIC This notebook is the **reference build** behind the Layer-4 hands-on block. In the room you do
# MAGIC not stand up a supervisor — it is pre-staged. You **edit the routing description, re-run one
# MAGIC cross-domain question, and watch routing change.**
# MAGIC
# MAGIC **3-beat rhythm:**
# MAGIC 1. **See** — the routing decision for the flagship question (open the trace; routing is the
# MAGIC    interesting part).
# MAGIC 2. **Tweak** — edit the **routing description** and re-run; watch which legs get called change.
# MAGIC 3. **Return** — one chat, cross-domain, governed per user.
# MAGIC
# MAGIC **The flagship question:** *"Paints EMEA gross margin dropped ~8% in Q2 — is it price, volume, or
# MAGIC a supply/service issue, and what should I do?"* The right answer is **not** single-cause: the
# MAGIC supervisor must route to **Finance** (margin bridge: price/FX/raw-material) **and SCM** (the
# MAGIC Rotterdam OTIF/stockout shock) and fuse them into "it is BOTH a margin/cost issue AND a
# MAGIC supply/service issue → here is the action."
# MAGIC
# MAGIC > **Upgrade path (documented at the end):** this router is a faithful, self-contained
# MAGIC > reproduction of an **Agent Bricks Multi-Agent Supervisor**. A real MAS endpoint
# MAGIC > (`mas-f14da7dc-endpoint`) exists in this workspace as a reference. We show how to move from this
# MAGIC > `ai_query` router to a native MAS, and how **OBO** enforces per-user data access at the
# MAGIC > Genie-call layer.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC We pin the catalog and the serving endpoint once. `databricks-claude-opus-4-7` is the LLM behind
# MAGIC both the **router** (which legs to call) and the **fuser** (one governed answer). The three legs
# MAGIC reuse the exact text2SQL pattern from notebooks 01 and 03.

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
FIN = f"{CATALOG}.akzo_finance"
SCM = f"{CATALOG}.akzo_scm"
COM = f"{CATALOG}.akzo_commercial"
LLM_ENDPOINT = "databricks-claude-opus-4-7"   # or "databricks-gpt-5-5"

spark.sql(f"USE CATALOG {CATALOG}")
print("Finance    :", FIN)
print("SCM        :", SCM)
print("Commercial :", COM)
print("LLM        :", LLM_ENDPOINT)

import json

# COMMAND ----------

# MAGIC %md
# MAGIC ## The three domain legs (the Genie pattern, in code)
# MAGIC
# MAGIC Each leg is the same shape as in notebooks 01/03: a distilled **Genie-space instruction block**
# MAGIC drives an `ai_query` text2SQL call, the SQL runs on serverless under the caller's identity, and a
# MAGIC reasoning step turns the rows into a domain finding. The supervisor treats each leg as a
# MAGIC **subagent** it can choose to invoke — exactly how a native MAS treats a registered Genie space.
# MAGIC
# MAGIC The instruction blocks below are the same ones the standalone notebooks tweak; here they are the
# MAGIC supervisor's registered subagents.

# COMMAND ----------

# --- Distilled Genie-space instructions (same text as genie/*_space.md, abbreviated for the leg) ---

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
LEG_SCHEMA = {"FINANCE": "akzo_finance", "SCM": "akzo_scm", "COMMERCIAL": "akzo_commercial"}

# COMMAND ----------

# MAGIC %md
# MAGIC ### The leg machinery: three tiny functions
# MAGIC
# MAGIC These are the reusable building blocks every subagent shares. `_ai_query` is the single LLM call
# MAGIC (used by router, legs, and fuser alike). `text2sql` wraps a Genie-space instruction block to turn a
# MAGIC question into governed SQL. `call_leg` runs that SQL on serverless **under the caller's UC identity**
# MAGIC and catches failures so one bad leg can't sink the whole supervisor turn — that resilience is why the
# MAGIC supervisor can route broadly without fear.

# COMMAND ----------

def _ai_query(prompt: str) -> str:
    """One call to the chat model on serverless."""
    return spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS out",
        args={"endpoint": LLM_ENDPOINT, "prompt": prompt},
    ).first()["out"]

def text2sql(question: str, instructions: str) -> str:
    """Genie-space text2SQL pattern: NL question -> governed Spark SQL."""
    sql = _ai_query(instructions + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    return sql

def call_leg(domain: str, question: str) -> dict:
    """Invoke one domain subagent: generate SQL, run it on serverless (under the caller's UC identity),
    return the rows. Returns a structured leg-result the supervisor will fuse."""
    sql = text2sql(question, LEG_INSTRUCTIONS[domain])
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(50).collect()]
        err = None
    except Exception as e:  # a leg can fail without sinking the supervisor
        rows, err = [], str(e)[:300]
    return {"domain": domain, "sql": sql, "rows": rows, "error": err}

# COMMAND ----------

# MAGIC %md
# MAGIC ## The router — the layer you tweak
# MAGIC
# MAGIC The router is one LLM call. It is given (a) the user question and (b) a **routing description**:
# MAGIC one line per registered subagent describing *what that domain knows*. It returns a JSON object
# MAGIC naming the domains to call and *why*. **This is the layer you tweak** — change a description line
# MAGIC and the same question routes differently.
# MAGIC
# MAGIC > In a native Agent Bricks MAS, this routing description **is** the per-subagent "description"
# MAGIC > field you fill in when you register each Genie space. Editing it here is editing exactly that.

# COMMAND ----------

# >>> THIS IS THE LAYER YOU TWEAK <<< — edit a domain's description line and re-run the router below.
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
    # keep only known domains, preserve order
    decision["domains"] = [d for d in decision.get("domains", []) if d in LEG_INSTRUCTIONS]
    return decision

# COMMAND ----------

# MAGIC %md
# MAGIC ## The fuser — one governed answer from the chosen legs
# MAGIC
# MAGIC After the chosen legs run, the supervisor hands their **structured rows** (not free text) to a
# MAGIC final LLM call that fuses one controller-ready answer, grounded only in the retrieved numbers.
# MAGIC For the flagship question it must conclude the problem is **both** margin/cost **and**
# MAGIC supply/service, and give a concrete action.

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
# MAGIC ## BEAT 1 — SEE: route + fuse the flagship cross-domain question
# MAGIC
# MAGIC Run the supervisor on the cold-open question. Watch the **routing trace** first (which domains,
# MAGIC why), then the per-leg SQL, then the single fused answer. The routing — not the prose — is the
# MAGIC interesting part, so we print it explicitly.

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
# MAGIC **The routing trace, as a table.** A native MAS shows this in its trace UI; here we render the
# MAGIC same information — which subagents were consulted, why, and the governed SQL each one ran.

# COMMAND ----------

trace_rows = [
    {"domain": lr["domain"], "rows_returned": len(lr["rows"]),
     "error": lr["error"] or "", "generated_sql": lr["sql"]}
    for lr in result["legs"]
]
display(spark.createDataFrame(trace_rows))

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** one row per consulted subagent. You should see FINANCE and SCM (often
# MAGIC COMMERCIAL too), each with a non-zero `rows_returned` and an empty `error`. If a leg shows an error,
# MAGIC its generated SQL is right there in the table to debug — the trace is the audit trail.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: edit the routing description, watch routing change
# MAGIC
# MAGIC This is the hands-on moment. We **narrow the Finance description** so it only claims to know about
# MAGIC *cost*, and **widen the SCM description** to explicitly own "price/margin pressure from supply".
# MAGIC Re-running the *same* flagship question now routes differently — the router follows the
# MAGIC descriptions, not the question's wording. This is exactly what changing a subagent's description
# MAGIC in a native MAS does.

# COMMAND ----------

TWEAKED_DESCRIPTION = {
    # narrowed: Finance now only advertises cost, not price/margin
    "FINANCE":    "Raw-material, freight, energy, and overhead COST levels only. Does NOT cover price, margin, or FX.",
    # widened: SCM now claims the price/margin-from-supply story too
    "SCM":        "OTIF, stockouts, lead times, lanes, service, backorders — AND any margin/price pressure caused by a supply or service disruption.",
    "COMMERCIAL": "Customer accounts, churn risk/score, NPS, complaints, account revenue. Use for customer-risk questions.",
}

tweaked = supervise(FLAGSHIP, descriptions=TWEAKED_DESCRIPTION)
print("=" * 80)
print("FUSED ANSWER (after routing-description tweak)")
print("=" * 80)
print(tweaked["answer"])

# COMMAND ----------

# MAGIC %md
# MAGIC **Compare the two routing decisions.** Same question, different descriptions → different routing.
# MAGIC That is the whole lesson of this layer: **routing is configuration, not code.**

# COMMAND ----------

display(spark.createDataFrame([
    {"variant": "default",  "domains_routed": ", ".join(result["decision"]["domains"]),
     "reason": result["decision"].get("reason", "")},
    {"variant": "tweaked",  "domains_routed": ", ".join(tweaked["decision"]["domains"]),
     "reason": tweaked["decision"].get("reason", "")},
]))

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** the `domains_routed` column should differ between the two rows. After the tweak,
# MAGIC the margin/price story should follow the *description* into SCM (and drop out of the now-cost-only
# MAGIC FINANCE leg). Identical question, edited descriptions, different route — proving routing is config.

# COMMAND ----------

# MAGIC %md
# MAGIC **Other one-line tweaks to try** (edit `ROUTING_DESCRIPTION`, re-run `supervise(...)`):
# MAGIC - Ask a churn question ("are we about to lose EMEA accounts?") — should route to **COMMERCIAL**
# MAGIC   (and SCM once it learns churn is service-driven).
# MAGIC - Remove a domain's description entirely — the router can no longer reach that leg.
# MAGIC - Add a new line for a hypothetical "DOCS" subagent and watch the router start naming it.

# COMMAND ----------

# MAGIC %md
# MAGIC ## A pure-routing question (the trace IS the answer)
# MAGIC
# MAGIC Golden question q5 asks the supervisor to *explain its own routing*. This proves the trace is
# MAGIC first-class — the supervisor can report which domains it consulted and what each contributed.

# COMMAND ----------

q5 = supervise("Which domains did you consult to answer the EMEA margin question, and what did each contribute?")
print(q5["answer"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: one chat, cross-domain, governed per user
# MAGIC
# MAGIC The supervisor reads → routes → calls the governed legs → fuses one answer. **Verified on this
# MAGIC workspace:** the flagship question routes to **Finance + SCM** (usually + Commercial) and the
# MAGIC fused answer connects the **~8.9pp margin bridge** (price/FX/raw-material) to the **Rotterdam
# MAGIC OTIF dip to ~89% in May**, concluding it is *both* a margin/cost issue *and* a supply/service
# MAGIC issue, with a concrete action (fix the lane/stockout; review the TiO2 contract; protect at-risk
# MAGIC EMEA accounts).
# MAGIC
# MAGIC ### How OBO governs this supervisor (per-user data access at the Genie-call layer)
# MAGIC Every `call_leg` runs its SQL **as the calling user**. In the workshop the legs are real Genie
# MAGIC spaces invoked through the supervisor, and **On-Behalf-Of (OBO)** carries the end user's identity
# MAGIC into each Genie call. So:
# MAGIC - The **controller** asking the flagship question sees all four regions; the **EMEA planner**
# MAGIC   asking the *same* question sees EMEA only — because Layer 2's UC row filter on `margin_actuals`
# MAGIC   (and any leg's tables) is enforced under the caller's identity. Same routing, different governed
# MAGIC   truth.
# MAGIC - OBO also gates **subagent access**: a user who lacks access to a Genie space cannot have the
# MAGIC   supervisor route to it on their behalf.
# MAGIC - OBO governs **reads only.** When the supervisor stops answering and starts *acting* (Layer 5),
# MAGIC   the write path is governed separately by app/service identity + approval + audit — not OBO.
# MAGIC
# MAGIC ### Upgrade path: this router → a native Agent Bricks Multi-Agent Supervisor
# MAGIC This notebook is a faithful, self-contained reproduction. To move to the managed product:
# MAGIC 1. **Register each Genie space as a subagent** of a Multi-Agent Supervisor (Agent Bricks UI / SDK),
# MAGIC    pasting the same `genie/*_space.md` instructions. The per-subagent **description** field is
# MAGIC    exactly the `ROUTING_DESCRIPTION` you tweaked here.
# MAGIC 2. The MAS does the route → call → fuse loop for you, **with OBO and tracing built in** — no
# MAGIC    router/fuser code to maintain.
# MAGIC 3. Call the deployed MAS endpoint with the `agent/v1/responses` task. A reference MAS endpoint
# MAGIC    already lives in this workspace: **`mas-f14da7dc-endpoint`** (state READY). The optional cell
# MAGIC    below shows how to call it; comment it in once your own MAS is registered over the three Akzo
# MAGIC    Genie spaces.
# MAGIC
# MAGIC ```python
# MAGIC # Optional — call a deployed native MAS endpoint (reference: mas-f14da7dc-endpoint).
# MAGIC # Replace with your own MAS registered over Akzo Finance / SCM / Commercial Genie spaces.
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC w = WorkspaceClient()
# MAGIC resp = w.serving_endpoints.query(
# MAGIC     name="mas-f14da7dc-endpoint",
# MAGIC     dataframe_records=None,  # use the responses-API input shape for agent/v1/responses
# MAGIC     extra_params={"input": [{"role": "user", "content": FLAGSHIP}]},
# MAGIC )
# MAGIC print(resp)
# MAGIC ```
# MAGIC
# MAGIC **Next:** `05_lakebase_memory_action.py` — the supervisor stops answering and starts *acting*.
