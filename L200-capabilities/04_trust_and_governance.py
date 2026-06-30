# Databricks notebook source
# MAGIC %md
# MAGIC # Chapter 4 — Trust & governance at scale
# MAGIC
# MAGIC ### Where this sits
# MAGIC
# MAGIC ```
# MAGIC   CH1 Supervisor   CH2 Agents that act   CH3 Autonomous loop   CH4 Trust & governance   ← you are here
# MAGIC                                                                 CH5 Document intelligence
# MAGIC ```
# MAGIC
# MAGIC Two questions an exec asks before any agent ships: **"how do I know it's right?"** and **"how do I
# MAGIC govern it at scale?"** This chapter answers both.
# MAGIC
# MAGIC ```
# MAGIC   PART A  Trust          ── golden questions + an LLM judge → eval as a regression gate (MLflow-style)
# MAGIC   PART B  Govern at scale ── AI Gateway: one front door, routes + rate limits + spend + UC payload logs
# MAGIC ```
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - The Chapter 1 finance data loaded (`<catalog>.akzo_finance`), a chat model + an independent judge
# MAGIC   model endpoint. PART B's UC chargeback is self-contained; the live-gateway inspect/tweak is guarded
# MAGIC   so the notebook runs green even where that specific gateway endpoint is absent.
# MAGIC - Permission to create tables in `<catalog>.akzo_ops` / `<catalog>.akzo_gateway`.
# MAGIC
# MAGIC ### How to run (~20 min)
# MAGIC Top-to-bottom. The widgets set your catalog and the agent/judge/gateway endpoints.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters
# MAGIC
# MAGIC The **agent** under test and the **judge** are deliberately different models — the grader is not
# MAGIC marking its own homework.

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_lakebase_praneeth_catalog", "Unity Catalog")
dbutils.widgets.text("agent_endpoint", "databricks-claude-opus-4-7", "Agent under test")
dbutils.widgets.text("judge_endpoint", "databricks-gpt-5-5", "Independent judge")
dbutils.widgets.text("gateway_endpoint", "harman-aes-ai-gateway", "AI Gateway endpoint (PART B)")

CATALOG = dbutils.widgets.get("catalog")
FIN = f"{CATALOG}.akzo_finance"
OPS = f"{CATALOG}.akzo_ops"
GW = f"{CATALOG}.akzo_gateway"
AGENT_ENDPOINT = dbutils.widgets.get("agent_endpoint")
JUDGE_ENDPOINT = dbutils.widgets.get("judge_endpoint")
GATEWAY_ENDPOINT = dbutils.widgets.get("gateway_endpoint")
RUN_TAG = "ch4_finance_golden"

import json, re, uuid
from datetime import datetime, timezone

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OPS}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {GW}")
print("Finance:", FIN, "| Ops:", OPS, "| Gateway logs:", GW)
print("Agent:", AGENT_ENDPOINT, "| Judge:", JUDGE_ENDPOINT, "| Gateway endpoint:", GATEWAY_ENDPOINT)

def llm(endpoint: str, prompt: str) -> str:
    return spark.sql("SELECT ai_query(:e, :p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC # PART A — Trust: an eval set + an LLM judge
# MAGIC
# MAGIC *"No AI without measurable value."* A controller will not trust an answer because a chatbot said so.
# MAGIC Trust comes from **measurement**: hold the agent to a fixed set of **golden questions** with
# MAGIC known-good answers, and grade every response with an **independent LLM judge** for *correctness* and
# MAGIC *groundedness*. The verdict, not the vibe, ships.
# MAGIC
# MAGIC ```
# MAGIC   golden Qs ─▶ agent answers (text2SQL + reason) ─▶ judge scores ─▶ persist to UC ─▶ eval as a gate
# MAGIC               (the CH1 Finance leg)               correctness +     eval_runs +
# MAGIC                                                    groundedness     eval_results
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — the agent answers each golden question
# MAGIC
# MAGIC The 5 finance golden questions (the team's authored set). We reuse the Chapter 1 text2SQL + reasoning
# MAGIC pattern — we are evaluating the *real* agent, not a toy. Each case carries the must-hit facts
# MAGIC (`expected_answer_contains`) and `grading_notes` we hand the judge.

# COMMAND ----------

# Plain Python dict (no yaml dependency — pyyaml is not preinstalled on serverless).
GOLDEN = {
    "track": "finance",
    "golden_questions": [
        {"id": "q1",
         "question": "What happened to Paints EMEA gross margin in Q2 2026 versus Q1 2026?",
         "expected_answer_contains": ["Q1 2026 ~39.6%", "Q2 2026 ~30.7%", "drop of ~8.9 percentage points", "Decorative Paints", "EMEA"],
         "grading_notes": "Good: names line (Decorative Paints), region (EMEA), both quarter margins (~39.6% -> ~30.7%) and the ~8.9pp drop. Wrong: absolute EUR only, wrong region/line, or a drop near baseline noise."},
        {"id": "q2",
         "question": "Decompose the Paints EMEA Q2 2026 margin drop into price, volume, FX, and cost effects.",
         "expected_answer_contains": ["price erosion ~ -3pp", "adverse FX ~ -2pp", "raw-material spike ~ -3pp", "volume roughly flat"],
         "grading_notes": "Good: four-way bridge summing to ~ -8pp, price ~-3pp, FX ~-2pp, raw material ~-3pp, volume ~flat. Wrong: one cause only, omits FX, or claims a volume collapse."},
        {"id": "q3",
         "question": "Which cost driver is responsible for the COGS increase in Paints EMEA in Q2 2026?",
         "expected_answer_contains": ["raw material", "TiO2", "up ~15-20% in Q2", "freight/energy/overhead roughly stable"],
         "grading_notes": "Good: isolates raw_material_cost (TiO2 + resin) up ~15-20%, other buckets stable. Wrong: blames freight/energy, or cites total COGS without decomposition."},
        {"id": "q4",
         "question": "How much did adverse FX contribute to the Paints EMEA margin miss, and which currencies drove it?",
         "expected_answer_contains": ["~ -2pp FX headwind", "EUR strengthened", "USD", "CNY"],
         "grading_notes": "Good: ~-2pp FX impact, names EUR strengthening vs USD/CNY. Wrong: ignores currency direction or double-counts FX as price erosion."},
        {"id": "q5",
         "question": "Is the Q2 2026 margin problem specific to Paints EMEA or is it company-wide?",
         "expected_answer_contains": ["specific to Decorative Paints in EMEA", "other region x line combos stable", "not company-wide"],
         "grading_notes": "Good: isolated to Decorative Paints x EMEA, every other segment small Q1->Q2 swing. Wrong: generalizes the drop or skips the baseline comparison."},
    ],
}
QUESTIONS = GOLDEN["golden_questions"]
print(f"Golden questions: {len(QUESTIONS)}")
for q in QUESTIONS:
    print(f"  [{q['id']}] {q['question']}")

# COMMAND ----------

FINANCE_INSTRUCTIONS = f"""You are the Akzo Finance text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no markdown fences.

TABLES (all under {FIN}):
- products(sku, product_name, product_line['Decorative Paints'|'Performance Coatings'], region['EMEA'|'Americas'|'APAC'|'China'], currency, list_price_eur, standard_cost_eur)
- margin_actuals(sku, region, month DATE, units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct)
- fx_rates(currency['EUR'|'USD'|'GBP'|'CNY'], month, rate_to_eur)
- cost_drivers(sku, region, month, raw_material_cost, freight_cost, energy_cost, overhead)

CERTIFIED RULES:
- gross_margin_pct = SUM(gross_margin_eur)/SUM(revenue_eur). NEVER average row-level gross_margin_pct.
- "Paints EMEA" := products.product_line='Decorative Paints' AND region='EMEA'. Join margin_actuals.sku=products.sku.
- Q1 2026 = 2026-01-01..2026-03-01 ; Q2 = 2026-04-01..2026-06-01. month is first-of-month DATE. Round % to 1 decimal.
- ALWAYS alias every selected column (AS ...) and return labeled dimension columns alongside measures.
- For variance/decomposition, return Q1 AND Q2 side by side with price_per_unit, raw_material_cost, freight_cost,
  energy_cost, overhead, units, gross_margin_pct; include fx_rates for USD/CNY when FX/currencies are mentioned."""

def agent_answer(question: str) -> str:
    """The agent under test: text2SQL -> run on serverless -> reason over the numbers (CH1 pattern)."""
    sql = llm(AGENT_ENDPOINT, FINANCE_INSTRUCTIONS + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(50).collect()]
        evidence = json.dumps(rows, default=str)
    except Exception as e:
        evidence = f"(SQL failed: {e}). SQL was: {sql}"
    reason_prompt = (
        "You are a finance controlling copilot for AkzoNobel coatings. Using ONLY the data below "
        "(do not invent figures), answer the question concisely for a controller: relevant margin %s, "
        "the percentage-point change, the named product line/region, and any price/volume/FX/cost drivers "
        f"the data supports. The column names tell you what each value means:\nSQL: {sql}\n\n"
        f"DATA (rows as JSON): {evidence}\n\nQUESTION: {question}\n\nANSWER:")
    return llm(AGENT_ENDPOINT, reason_prompt).strip()

answers = {}
for q in QUESTIONS:
    answers[q["id"]] = agent_answer(q["question"])
    print(f"\n=== [{q['id']}] {q['question']}\n{answers[q['id']][:400]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The LLM judge (correctness + groundedness)
# MAGIC
# MAGIC The judge gets the question, the expected facts, the grading notes, and the agent's answer, and
# MAGIC returns strict JSON: `correctness` and `groundedness` in `[0,1]`, a `pass` boolean, and a rationale.
# MAGIC **Correctness** = does it hit the expected facts? **Groundedness** = is every claim supported by the
# MAGIC data, with no invented figures?
# MAGIC
# MAGIC > We use an `ai_query`-based judge so the notebook runs on any MLflow version. The `mlflow.genai`
# MAGIC > path (built-in `Correctness`/`Guidelines` scorers, `make_judge`, judge-alignment) is shown as a
# MAGIC > guarded optional cell at the end.

# COMMAND ----------

def judge(question, expected, grading_notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a finance copilot. Score the ANSWER against the EXPECTED FACTS.

QUESTION: {question}

EXPECTED FACTS (small wording/number rounding is fine):
{expected_str}

GRADING NOTES: {grading_notes}

ANSWER UNDER TEST:
{answer}

Return ONLY a JSON object, no prose, with exactly these keys:
{{"correctness": <float 0..1>, "groundedness": <float 0..1>, "pass": <true|false>, "rationale": "<one sentence>"}}
- correctness: fraction of expected facts correctly conveyed.
- groundedness: 1.0 if every claim is supported and no figures invented, lower if it hallucinates.
- pass: true only if correctness >= 0.6 AND groundedness >= 0.6."""
    raw = llm(JUDGE_ENDPOINT, prompt).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0) if m else raw)
    except Exception:
        v = {"correctness": 0.0, "groundedness": 0.0, "pass": False, "rationale": f"unparseable: {raw[:150]}"}
    v["correctness"] = float(v.get("correctness", 0.0))
    v["groundedness"] = float(v.get("groundedness", 0.0))
    v["pass"] = bool(v.get("pass", False))
    return v

verdicts = {}
for q in QUESTIONS:
    verdicts[q["id"]] = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), answers[q["id"]])
    v = verdicts[q["id"]]
    print(f"[{q['id']}] pass={v['pass']}  correctness={v['correctness']:.2f}  groundedness={v['groundedness']:.2f}  — {v['rationale']}")

pass_rate = sum(1 for v in verdicts.values() if v["pass"]) / len(verdicts)
print(f"\nPASS RATE: {pass_rate*100:.0f}%  ({sum(1 for v in verdicts.values() if v['pass'])}/{len(verdicts)})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Persist the run to Unity Catalog (`eval_runs` + `eval_results`)
# MAGIC
# MAGIC An eval that lives only in notebook output is not auditable. We write a one-row **run header** and
# MAGIC one **row per question**, so any change to the agent can be regression-compared run-over-run with a
# MAGIC `SELECT`.

# COMMAND ----------

spark.sql(f"""CREATE TABLE IF NOT EXISTS {OPS}.eval_runs (
  run_id STRING, run_tag STRING, track STRING, agent_endpoint STRING, judge_endpoint STRING,
  n_questions INT, n_pass INT, pass_rate DOUBLE, avg_correctness DOUBLE, avg_groundedness DOUBLE,
  created_at TIMESTAMP) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {OPS}.eval_results (
  run_id STRING, question_id STRING, question STRING, answer STRING, expected_facts STRING,
  correctness DOUBLE, groundedness DOUBLE, passed BOOLEAN, rationale STRING, created_at TIMESTAMP) USING DELTA""")

run_id = str(uuid.uuid4())
now = datetime.now(timezone.utc)
n = len(QUESTIONS)
n_pass = sum(1 for v in verdicts.values() if v["pass"])
avg_corr = sum(v["correctness"] for v in verdicts.values()) / n
avg_grnd = sum(v["groundedness"] for v in verdicts.values()) / n

spark.createDataFrame(
    [(run_id, RUN_TAG, GOLDEN.get("track", "finance"), AGENT_ENDPOINT, JUDGE_ENDPOINT,
      n, n_pass, n_pass / n, avg_corr, avg_grnd, now)],
    schema="run_id string, run_tag string, track string, agent_endpoint string, judge_endpoint string, "
           "n_questions int, n_pass int, pass_rate double, avg_correctness double, avg_groundedness double, created_at timestamp",
).write.mode("append").saveAsTable(f"{OPS}.eval_runs")

result_rows = [(run_id, q["id"], q["question"], answers[q["id"]], " | ".join(q["expected_answer_contains"]),
                verdicts[q["id"]]["correctness"], verdicts[q["id"]]["groundedness"],
                verdicts[q["id"]]["pass"], verdicts[q["id"]]["rationale"], now) for q in QUESTIONS]
spark.createDataFrame(
    result_rows,
    schema="run_id string, question_id string, question string, answer string, expected_facts string, "
           "correctness double, groundedness double, passed boolean, rationale string, created_at timestamp",
).write.mode("append").saveAsTable(f"{OPS}.eval_results")

print(f"Logged run {run_id}: {n_pass}/{n} pass, avg correctness {avg_corr:.2f}, avg groundedness {avg_grnd:.2f}")
display(spark.sql(f"SELECT question_id, ROUND(correctness,2) correctness, ROUND(groundedness,2) groundedness, passed, rationale FROM {OPS}.eval_results WHERE run_id = '{run_id}' ORDER BY question_id"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — tighten one expectation, re-grade
# MAGIC
# MAGIC Change *one* thing in the eval set and re-run the judge. Below we re-grade `q1` under a **stricter**
# MAGIC expectation (it must state the exact ~8.9pp figure, not "about 8%"). Watch the score move **without
# MAGIC touching the model** — the eval is the contract, independent of the agent.

# COMMAND ----------

TWEAK_QID = "q1"
TWEAKED_EXPECTED = [
    "explicitly states ~39.6% in Q1", "explicitly states ~30.7% in Q2",
    "states the drop is ~8.9 percentage points (not just 'about 8%')", "names Decorative Paints AND EMEA",
]
tq = next(q for q in QUESTIONS if q["id"] == TWEAK_QID)
re_answer = agent_answer(tq["question"])
re_verdict = judge(tq["question"], TWEAKED_EXPECTED,
                   "Stricter grading: the answer must state exact figures, not approximations.", re_answer)
print(f"[{TWEAK_QID}] re-graded under STRICTER expectations:")
print(f"  pass={re_verdict['pass']}  correctness={re_verdict['correctness']:.2f}  groundedness={re_verdict['groundedness']:.2f}")
print(f"  rationale: {re_verdict['rationale']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — the agent is now measurable (eval as a gate)
# MAGIC
# MAGIC The eval set is a **regression gate**: query `eval_runs` to compare runs over time; a drop in
# MAGIC `pass_rate` blocks a release. *"No AI without measurable value"* is now enforceable with a `SELECT`.

# COMMAND ----------

display(spark.sql(f"""
SELECT run_tag, agent_endpoint, judge_endpoint, n_pass, n_questions,
       ROUND(pass_rate*100,0) AS pass_pct, ROUND(avg_correctness,2) AS avg_correctness,
       ROUND(avg_groundedness,2) AS avg_groundedness, created_at
FROM {OPS}.eval_runs ORDER BY created_at DESC LIMIT 10"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### OPTIONAL — the `mlflow.genai` path (guarded)
# MAGIC
# MAGIC On DBR/MLflow versions that ship the GenAI eval API, replace the hand-rolled judge with built-in
# MAGIC scorers (`Correctness`, `Guidelines`) and align a judge to human labels with `make_judge`. Guarded
# MAGIC so it never breaks the run; flip the flag only where version-verified.

# COMMAND ----------

USE_MLFLOW_GENAI = False
if USE_MLFLOW_GENAI:
    try:
        import mlflow
        from mlflow.genai.scorers import Correctness, Guidelines
        eval_data = [{"inputs": {"question": q["question"]}, "outputs": answers[q["id"]],
                      "expectations": {"expected_facts": q["expected_answer_contains"]}} for q in QUESTIONS]
        results = mlflow.genai.evaluate(
            data=eval_data,
            scorers=[Correctness(), Guidelines(name="grounded", guidelines="No invented figures; supported by data.")])
        print("mlflow.genai.evaluate complete:", results)
    except Exception as e:
        print("mlflow.genai not available — the ai_query judge above is the portable default. (", e, ")")
else:
    print("mlflow.genai path disabled — the ai_query judge above is the portable default.")

# COMMAND ----------

# MAGIC %md
# MAGIC # PART B — Govern at scale: AI Gateway
# MAGIC
# MAGIC Every model call the supervisor and its legs make goes through **one front door** — the AI Gateway.
# MAGIC That single plane sets *routes*, *rate limits*, *spend caps*, *guardrails*, and *payload logging* —
# MAGIC all landing in **Unity Catalog**. Change a control once and every agent inherits it; no app redeploy.
# MAGIC
# MAGIC > **Status (say it out loud):** Unity **AI Gateway is Beta**; payload/inference-table logs are
# MAGIC > best-effort and can **lag up to ~1h**. So the "see" beat runs on **preseeded** UC logs and only
# MAGIC > **one** control is changed live. The endpoint-inspect + live-tweak cells are **guarded** — they
# MAGIC > skip cleanly if the gateway endpoint is not present in your workspace, so the UC chargeback (the
# MAGIC > real teaching value) always runs.

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — the gateway's live config (guarded)
# MAGIC
# MAGIC One endpoint is the front door for many models. Its `ai_gateway` block is where every control lives:
# MAGIC routes, rate limits, usage tracking, guardrails, the payload-log table. This skips gracefully if the
# MAGIC endpoint is not reachable in your workspace.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

try:
    ep = w.serving_endpoints.get(GATEWAY_ENDPOINT)
    cfg = ep.config or ep.pending_config
    print("Endpoint :", ep.name, "| ready:", ep.state.ready if ep.state else None)
    print("Routes (served entities -> model):")
    for se in (cfg.served_entities or []):
        print(f"  - {se.name}  ->  {se.entity_name or getattr(se,'external_model',None)}")
    ag = ep.ai_gateway
    if ag:
        print("Rate limits :", [(str(rl.key), rl.calls, str(rl.renewal_period)) for rl in (ag.rate_limits or [])])
        print("Usage track :", ag.usage_tracking_config.enabled if ag.usage_tracking_config else None)
        if ag.inference_table_config:
            itc = ag.inference_table_config
            print("Payload log :", f"{itc.catalog_name}.{itc.schema_name}.{itc.table_name_prefix}_payload (enabled={itc.enabled})")
        if ag.guardrails:
            print("Guardrails  : PII + safety on input/output (Beta)")
    GATEWAY_AVAILABLE = True
except Exception as e:
    print(f"Gateway endpoint '{GATEWAY_ENDPOINT}' not reachable here — skipping live inspect/tweak. ({str(e)[:120]})")
    print("The UC payload-log chargeback below still runs (it is self-contained).")
    GATEWAY_AVAILABLE = False

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — preseeded payload logs in Unity Catalog
# MAGIC
# MAGIC Real gateway logs lag ~1h (Beta), so we preseed `akzo_gateway.payload_logs` with realistic
# MAGIC request/response/usage/cost rows across AkzoNobel user-groups. The schema mirrors the real AI
# MAGIC Gateway payload table plus a few enrichment columns (`user_group`, token counts, `cost_usd`) so the
# MAGIC chargeback view works without parsing JSON live.

# COMMAND ----------

spark.sql(f"""CREATE TABLE IF NOT EXISTS {GW}.payload_logs (
  databricks_request_id STRING, request_time TIMESTAMP, request_date DATE, endpoint STRING,
  served_model STRING, model STRING, requester STRING, user_group STRING, request STRING, response STRING,
  input_tokens INT, output_tokens INT, total_tokens INT, cost_usd DOUBLE, status_code INT,
  execution_duration_ms BIGINT) USING DELTA
COMMENT 'Preseeded AI Gateway payload/usage logs for the Akzo workshop (real logs lag ~1h, Beta).'""")

import random
from datetime import timedelta
PRICE_PER_1K = {"chat-quality": 0.012, "chat-fast": 0.0008, "chat-cheap": 0.0003}
MODEL_OF = {"chat-quality": "databricks-claude-opus-4-7",
            "chat-fast": "databricks-meta-llama-3-3-70b-instruct", "chat-cheap": "databricks-gpt-oss-20b"}
SEED = [
    ("Finance", "controller.emea@akzonobel.com", "chat-quality",
     "Decompose the Paints EMEA Q2 2026 margin drop.", "Margin fell ~8.9pp: price ~-3pp, raw material ~-3pp, FX ~-2pp.", 480, 220),
    ("Finance", "planner.emea@akzonobel.com", "chat-fast",
     "Show Paints EMEA gross margin % by month for 2026.", "Jan 39.8% ... Jun 30.4%.", 210, 90),
    ("SCM", "planner.scm@akzonobel.com", "chat-fast",
     "Which EMEA lanes missed OTIF in Q2 and why?", "3 lanes below target; port congestion + safety-stock breach.", 260, 140),
    ("SCM", "controller.scm@akzonobel.com", "chat-quality",
     "Recommend an intervention for the Rotterdam->DE OTIF miss.", "Re-route 20% to rail; lift safety stock 6 weeks.", 320, 180),
    ("Commercial", "rep.benelux@akzonobel.com", "chat-fast",
     "Which accounts show churn risk this quarter?", "4 accounts with churn_score>0.7.", 230, 110),
    ("Commercial", "rep.dach@akzonobel.com", "chat-cheap",
     "Draft a next-best-action email for account A-1042.", "Schedule QBR, offer volume rebate.", 180, 260),
    ("Procurement", "buyer.raw@akzonobel.com", "chat-quality",
     "Summarize TiO2 escalation clauses across contracts.", "5 of 6 allow quarterly escalation; 2 non-standard.", 540, 240),
    ("Procurement", "buyer.freight@akzonobel.com", "chat-cheap",
     "List contracts with termination notice under 30 days.", "2 contracts: SUP-Logi-EU, SUP-Pack-NL.", 150, 70),
]
now2 = datetime.now(timezone.utc)
rows = []
for grp, who, served, req, resp, itok, otok in SEED:
    for _ in range(random.randint(3, 7)):
        in_t = itok + random.randint(-30, 40); out_t = otok + random.randint(-20, 50); tot = in_t + out_t
        cost = round(tot / 1000.0 * PRICE_PER_1K[served], 6)
        ts = now2 - timedelta(minutes=random.randint(5, 360))
        rows.append((f"req-{uuid.uuid4().hex[:12]}", ts, ts.date(), GATEWAY_ENDPOINT, served, MODEL_OF[served],
                     who, grp, req, resp, in_t, out_t, tot, cost, 200, random.randint(400, 2600)))
schema = ("databricks_request_id string, request_time timestamp, request_date date, endpoint string, "
          "served_model string, model string, requester string, user_group string, request string, "
          "response string, input_tokens int, output_tokens int, total_tokens int, cost_usd double, "
          "status_code int, execution_duration_ms bigint")
spark.sql(f"DELETE FROM {GW}.payload_logs")
spark.createDataFrame(rows, schema=schema).write.mode("append").saveAsTable(f"{GW}.payload_logs")
print(f"Preseeded {len(rows)} payload-log rows across {len({r[7] for r in rows})} user-groups.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — change one control live (guarded)
# MAGIC
# MAGIC Change exactly **one** gateway control on the running endpoint (the per-user rate limit) via the SDK
# MAGIC and read it back. No app redeploy; the change governs every agent immediately. Default **off** so the
# MAGIC notebook does not mutate a shared endpoint during an automated run; flip `DO_LIVE_TWEAK = True` to
# MAGIC demo it. It restores the original limit afterward.

# COMMAND ----------

DO_LIVE_TWEAK = False
NEW_USER_LIMIT = 60

if DO_LIVE_TWEAK and GATEWAY_AVAILABLE:
    from databricks.sdk.service.serving import (
        AiGatewayRateLimit, AiGatewayRateLimitKey, AiGatewayRateLimitRenewalPeriod,
        AiGatewayInferenceTableConfig, AiGatewayUsageTrackingConfig)
    def _user_limit(name):
        for rl in (w.serving_endpoints.get(name).ai_gateway.rate_limits or []):
            if str(rl.key).endswith("USER") or str(rl.key) == "user":
                return rl.calls
        return None
    before = _user_limit(GATEWAY_ENDPOINT)
    print("Per-user rate limit BEFORE:", before, "calls/min")
    itc = w.serving_endpoints.get(GATEWAY_ENDPOINT).ai_gateway.inference_table_config
    w.serving_endpoints.put_ai_gateway(
        name=GATEWAY_ENDPOINT,
        rate_limits=[AiGatewayRateLimit(calls=5000, key=AiGatewayRateLimitKey.ENDPOINT, renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
                     AiGatewayRateLimit(calls=NEW_USER_LIMIT, key=AiGatewayRateLimitKey.USER, renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE)],
        usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
        inference_table_config=itc)
    print("Per-user rate limit AFTER :", _user_limit(GATEWAY_ENDPOINT), "calls/min  <-- took effect live, no redeploy")
    # restore
    w.serving_endpoints.put_ai_gateway(
        name=GATEWAY_ENDPOINT,
        rate_limits=[AiGatewayRateLimit(calls=5000, key=AiGatewayRateLimitKey.ENDPOINT, renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
                     AiGatewayRateLimit(calls=(before or 100), key=AiGatewayRateLimitKey.USER, renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE)],
        usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True), inference_table_config=itc)
    print("Restored per-user rate limit to:", _user_limit(GATEWAY_ENDPOINT), "calls/min")
else:
    print("Live tweak disabled (DO_LIVE_TWEAK=False) or gateway not available — concept shown, no shared endpoint mutated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — cost & usage by user-group (the chargeback / audit view)
# MAGIC
# MAGIC What the governance owner actually wants: **who is spending, on which model, and is any group about
# MAGIC to blow the budget.** A plain `SELECT` over UC — the same governance plane as the rest of the
# MAGIC lakehouse.

# COMMAND ----------

display(spark.sql(f"""
SELECT user_group, COUNT(*) AS calls, SUM(total_tokens) AS total_tokens,
       ROUND(SUM(cost_usd), 4) AS cost_usd, ROUND(AVG(execution_duration_ms)) AS avg_latency_ms,
       ROUND(SUM(cost_usd) / COUNT(*), 5) AS cost_per_call
FROM {GW}.payload_logs GROUP BY user_group ORDER BY cost_usd DESC"""))

# COMMAND ----------

display(spark.sql(f"""
SELECT served_model, model, COUNT(*) AS calls, SUM(total_tokens) AS total_tokens,
       ROUND(SUM(cost_usd), 4) AS cost_usd
FROM {GW}.payload_logs GROUP BY served_model, model ORDER BY cost_usd DESC"""))
# chat-quality (Opus) should top cost_usd despite fewer calls — the argument for the route/spend-cap lever.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What we proved
# MAGIC
# MAGIC - **Trust** — the Finance agent was held to 5 golden questions; an **independent LLM judge** scored
# MAGIC   correctness + groundedness; every run + verdict is durable in UC (`eval_runs` / `eval_results`), so
# MAGIC   the agent is auditable and regression-testable. Tightening one expectation moved the score **without
# MAGIC   touching the model** — the eval is the contract.
# MAGIC - **Govern at scale** — one AI Gateway front door carries routes + rate limits + usage tracking +
# MAGIC   guardrails + UC payload logging. One control changes live (no redeploy), and cost/usage by
# MAGIC   user-group + model tier is a plain `SELECT` on the **same** governance plane as the lakehouse.
# MAGIC - **Honest Beta framing** — AI Gateway is Beta and logs lag ~1h, so "see" runs on preseeded logs and
# MAGIC   only one control changes live.
# MAGIC
# MAGIC **Next:** `05_document_intelligence.py` — turn raw PDFs into governed, queryable knowledge with the
# MAGIC native `ai_*` functions + Vector Search.
