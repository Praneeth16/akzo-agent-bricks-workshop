# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — AI governance & policy agent (per-user truth + gateway control + audit)
# MAGIC
# MAGIC *Hackathon track #4. Forkable Day-2 starter — a slim distillation of `L200-capabilities/02_per_user_truth_uc_obo.py`
# MAGIC + `L200-capabilities/07_ai_gateway_govern.py`.*
# MAGIC
# MAGIC A **self-contained, forkable** governance agent. Unlike the domain tracks, the act surface here is
# MAGIC **not** a Lakebase write — it is the two governance planes themselves:
# MAGIC 1. **Read governance (OBO + UC RLS/ABAC):** a `personas` table maps email -> role -> region scope; a
# MAGIC    row-filter function scopes governed finance reads by persona. **The "act" is flipping a persona** and
# MAGIC    watching the same query return different rows.
# MAGIC 2. **Front-door governance (AI Gateway):** one endpoint governs routes, rate limits, spend caps, and
# MAGIC    UC-native payload logging. **The "act" is changing one gateway control** (a per-user rate limit) and
# MAGIC    reading the audit/chargeback view.
# MAGIC
# MAGIC Plus an **`ai_query` judge** over the 5 governance golden questions (which test whether the agent
# MAGIC *explains* the governance model correctly).
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak -> swap -> extend*. The four `# TODO (Day-2)`
# MAGIC markers are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** same `margin_actuals` query, different rows per persona —
# MAGIC **controller -> 4 regions** (EMEA, Americas, APAC, China); **planner / rep -> 1 region (EMEA)**. Enforced
# MAGIC by the persona scope under OBO, not by the agent.
# MAGIC
# MAGIC **Ship target:** a working notebook + a live persona-toggle trace + the UC payload-log chargeback view.
# MAGIC The full governance layer ships across the deployed apps' OBO + the gateway endpoint (clone, don't author).
# MAGIC
# MAGIC > **Status (say it out loud):** Unity **AI Gateway is Beta**; payload logs lag ~1h. We use **preseeded
# MAGIC > logs** for the "see" beat and change **one** control live. Point `GATEWAY_ENDPOINT` at your own
# MAGIC > AI Gateway endpoint — the BEAT-2 cell restores the control it changes.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, schemas, models, gateway endpoint

# COMMAND ----------

CATALOG = os.environ.get("AKZO_CATALOG") or spark.sql("SELECT current_catalog()").first()[0]
FIN = f"{CATALOG}.akzo_finance"
OPS = f"{CATALOG}.akzo_ops"
GW = f"{CATALOG}.akzo_gateway"
LLM_ENDPOINT = "databricks-claude-opus-4-8"   # the policy agent's explanation model
JUDGE_ENDPOINT = "databricks-gpt-5-5"          # an independent grader
GATEWAY_ENDPOINT = os.environ.get("DATABRICKS_GATEWAY_ENDPOINT", "<your-ai-gateway-endpoint>")  # the AI Gateway we govern

spark.sql(f"USE CATALOG {CATALOG}")
print("Finance:", FIN, "| Ops:", OPS, "| Gateway schema:", GW)
print("Gateway endpoint:", GATEWAY_ENDPOINT, "| LLM:", LLM_ENDPOINT, "| Judge:", JUDGE_ENDPOINT)

import json, re

def _ai_query(prompt: str, endpoint: str = LLM_ENDPOINT) -> str:
    return spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## The personas table (the ABAC source of truth)
# MAGIC
# MAGIC RLS is driven by this small governed table mapping each user to a role and a region scope. Pre-staged
# MAGIC by `L200-capabilities/02_per_user_truth_uc_obo.py` (idempotent re-seed here keeps the starter self-contained).
# MAGIC **`# TODO (Day-2) SPRINT 1` lives here.**

# COMMAND ----------

me = spark.sql("SELECT current_user() AS u").first()["u"]

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OPS}")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {OPS}.personas (
  user_email STRING, role STRING, region_scope STRING, segment_scope STRING)
COMMENT 'ABAC persona mapping that drives Unity Catalog row-level security'""")

# TODO (Day-2) SPRINT 1 — TWEAK THE PERSONA MODEL: add a role/region scope (e.g. an 'apac_planner'), or
#   change a scope, then re-run the BEAT-1 visibility check and watch the rows-per-persona change.
spark.sql(f"""INSERT OVERWRITE {OPS}.personas VALUES
  ('{me}',                        'controller', 'ALL',  'ALL'),
  ('planner.emea@akzo.example',   'planner',    'EMEA', 'ALL'),
  ('rep.arch@akzo.example',       'rep',        'EMEA', 'Architectural')""")
display(spark.sql(f"SELECT * FROM {OPS}.personas ORDER BY role"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: same query, different rows per persona (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC `current_user()` is the OBO identity — in an agent call it is the *end user*, not a service principal.
# MAGIC This counts how many regions each persona's scope exposes on the governed `margin_actuals` table — the
# MAGIC RLS-predicate logic the row-filter function `akzo_ops.fn_region_rls` enforces for real callers.

# COMMAND ----------

display(spark.sql(f"""
SELECT p.role, p.region_scope,
       COUNT(DISTINCT m.region) AS regions_visible,
       collect_set(m.region)    AS regions
FROM {FIN}.margin_actuals m
JOIN {OPS}.personas p ON (p.region_scope='ALL' OR p.region_scope=m.region)
GROUP BY p.role, p.region_scope
ORDER BY regions_visible DESC
"""))
# Expected: controller -> 4 regions; planner -> 1 (EMEA); rep -> 1 (EMEA). Same table, different governed truth.

# COMMAND ----------

# MAGIC %md
# MAGIC ## ACT (plane 1) — flip one persona attribute, re-run the smoke test
# MAGIC
# MAGIC The governance "action": widen the planner from `EMEA` to `ALL`, watch visibility jump, then revert.
# MAGIC No agent code changes — UC enforces the scope under OBO.

# COMMAND ----------

def regions_visible_for(user_email: str) -> int:
    return spark.sql(f"""
      SELECT COUNT(DISTINCT m.region) AS n FROM {FIN}.margin_actuals m
      WHERE EXISTS (SELECT 1 FROM {OPS}.personas p WHERE p.user_email='{user_email}'
                    AND (p.region_scope='ALL' OR p.region_scope=m.region))""").first()["n"]

print("planner before:", regions_visible_for("planner.emea@akzo.example"), "region(s)")
spark.sql(f"UPDATE {OPS}.personas SET region_scope='ALL' WHERE user_email='planner.emea@akzo.example'")
print("planner widened to ALL:", regions_visible_for("planner.emea@akzo.example"), "region(s)")
spark.sql(f"UPDATE {OPS}.personas SET region_scope='EMEA' WHERE user_email='planner.emea@akzo.example'")
print("planner reverted:", regions_visible_for("planner.emea@akzo.example"), "region(s)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ACT (plane 2) — change ONE AI Gateway control live, confirm it took effect
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 2` lives here. We change exactly one gateway control on the running endpoint —
# MAGIC the **per-user rate limit** — through the SDK, read it back, then restore it (shared endpoint). No app
# MAGIC redeploy; the change governs every agent calling through this endpoint immediately.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    AiGatewayRateLimit, AiGatewayRateLimitKey, AiGatewayRateLimitRenewalPeriod,
    AiGatewayInferenceTableConfig, AiGatewayUsageTrackingConfig,
)

w = WorkspaceClient()

def _user_limit(endpoint_name):
    ag = w.serving_endpoints.get(endpoint_name).ai_gateway
    for rl in (ag.rate_limits or []):
        if str(rl.key).endswith("USER") or str(rl.key) == "user":
            return rl.calls
    return None

before = _user_limit(GATEWAY_ENDPOINT)
print("Per-user rate limit BEFORE:", before, "calls/min")

# TODO (Day-2) SPRINT 2 — SWAP THE CONTROL: change NEW_USER_LIMIT (rate limit), or switch to a model-route
#   shift / spend-cap (usage tracking) as the live control. Re-run and watch the endpoint config change.
NEW_USER_LIMIT = 60

w.serving_endpoints.put_ai_gateway(
    name=GATEWAY_ENDPOINT,
    rate_limits=[
        AiGatewayRateLimit(calls=5000, key=AiGatewayRateLimitKey.ENDPOINT,
                           renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
        AiGatewayRateLimit(calls=NEW_USER_LIMIT, key=AiGatewayRateLimitKey.USER,
                           renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
    ],
    usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
    inference_table_config=AiGatewayInferenceTableConfig(
        enabled=True, catalog_name=CATALOG,
        schema_name="harman_aes_ai_models", table_name_prefix="gateway_inference_logs"),
)
print("Per-user rate limit AFTER :", _user_limit(GATEWAY_ENDPOINT), "calls/min  <-- the tweak took effect")

# Restore the shared endpoint so the next pair starts clean.
w.serving_endpoints.put_ai_gateway(
    name=GATEWAY_ENDPOINT,
    rate_limits=[
        AiGatewayRateLimit(calls=5000, key=AiGatewayRateLimitKey.ENDPOINT,
                           renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
        AiGatewayRateLimit(calls=(before or 100), key=AiGatewayRateLimitKey.USER,
                           renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
    ],
    usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
    inference_table_config=AiGatewayInferenceTableConfig(
        enabled=True, catalog_name=CATALOG,
        schema_name="harman_aes_ai_models", table_name_prefix="gateway_inference_logs"),
)
print("Restored per-user rate limit to:", _user_limit(GATEWAY_ENDPOINT), "calls/min")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The audit / chargeback view (UC-native payload logging)
# MAGIC
# MAGIC Who is spending, on which model tier — a plain `SELECT` over UC, the same governance plane as the
# MAGIC lakehouse data. Reads the **preseeded** `akzo_gateway.payload_logs` (real logs feed this once the ~1h
# MAGIC lag clears). Preseeded by `L200-capabilities/07_ai_gateway_govern.py`.

# COMMAND ----------

display(spark.sql(f"""
SELECT user_group, COUNT(*) AS calls, SUM(total_tokens) AS total_tokens,
       ROUND(SUM(cost_usd),4) AS cost_usd, ROUND(AVG(execution_duration_ms)) AS avg_latency_ms
FROM {GW}.payload_logs GROUP BY user_group ORDER BY cost_usd DESC
"""))
# Cost/usage by user-group (Finance, SCM, Commercial, Procurement) — the chargeback / audit view.

# COMMAND ----------

# MAGIC %md
# MAGIC ## REASON: the policy agent explains the governance model
# MAGIC
# MAGIC The governance agent's job is to *explain* what governs reads vs writes vs spend, grounded in the
# MAGIC two planes above. This is the answer to Akzo's 2,000-user-rollout governance fear.

# COMMAND ----------

GOVERNANCE_FACTS = (
    "READS: governed by Unity Catalog RLS/ABAC under OBO — the Genie/agent call runs as the END USER. "
    "personas(akzo_ops) maps email->role->region_scope; controller sees 4 regions, planner/rep see only EMEA; "
    "the agent cannot override UC. "
    "WRITES: NOT governed by OBO. UC-registered Lakebase is READ-ONLY. Agent writes go through an app/service "
    "identity into Lakebase write-back tables (quotes/quote_approvals/forecast_overrides/scm_interventions/"
    "commercial_actions) as 'pending', requiring a HUMAN approval with audit (created_by/approved_by). "
    "FRONT DOOR: AI Gateway governs routes, per-user/per-endpoint rate limits, spend caps, PII/safety "
    "guardrails, and UC-native payload logging (akzo_gateway.payload_logs, ~1h lag, preseeded for demo). "
    "One control change governs every agent with no app redeploy.")

def governance_answer(question: str) -> str:
    return _ai_query(
        "You are AkzoNobel's AI governance & policy agent. Using ONLY these governed facts (do not invent "
        f"mechanisms):\n{GOVERNANCE_FACTS}\n\nAnswer concisely and precisely. If a request would surface "
        "secrets or exceed scope, decline and explain.\n\nQUESTION: " + question + "\n\nANSWER:")

print(governance_answer("Same question, run as a controller and as a planner — why do they get different rows?"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — MEASURE: the LLM judge over the 5 governance golden questions
# MAGIC
# MAGIC `# TODO (Day-2) SPRINT 3` lives in `eval.yaml`. The agent answers each governance golden question from
# MAGIC `GOVERNANCE_FACTS`; an independent judge scores correctness + groundedness (these questions test whether
# MAGIC the agent explains the governance model correctly — including the failing case where it must decline).

# COMMAND ----------

import os, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/governance/eval.yaml"]:
        if os.path.exists(c):
            return c
    return None

_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else {"golden_questions": []}
QUESTIONS = GOLDEN.get("golden_questions", [])
print("Loaded", len(QUESTIONS), "golden questions from", _p)

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for an AI governance agent. Score the ANSWER against the EXPECTED FACTS.
QUESTION: {question}
EXPECTED FACTS (small wording differences are fine):
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

# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add a governance golden question to eval.yaml (e.g. "can a rep see
#   another segment's accounts?" or "where is PII redaction enforced?") and re-run this cell.
n_pass = 0
for q in QUESTIONS:
    v = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), governance_answer(q["question"]))
    n_pass += int(v["pass"])
    print(f"[{q['id']}] pass={v['pass']} corr={v['correctness']:.2f} grnd={v['groundedness']:.2f} — {v['rationale']}")
print(f"\nPASS RATE: {n_pass}/{len(QUESTIONS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole + ship
# MAGIC
# MAGIC Two governance planes, demonstrated and measurable: **reads** scoped per-user by UC RLS under OBO
# MAGIC (controller=4 regions, planner/rep=1), and the **front door** governed by one AI Gateway endpoint
# MAGIC (rate limit changed live + restored) with UC-native audit/chargeback logging.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** edit the `personas` model; re-run the BEAT-1 visibility check.
# MAGIC - **Sprint 2 (swap):** change one gateway control (`NEW_USER_LIMIT`, or a route/spend-cap); re-run.
# MAGIC - **Sprint 3 (extend):** add a governance golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Measurable value:** access-governance assurance moves from a manual security review (days) to a live,
# MAGIC in-product demonstration (controller vs planner returns different rows) in minutes.
# MAGIC
# MAGIC **Honest scope:** OBO/RLS govern **reads**; **writes** are a separate plane (Postgres roles + app
# MAGIC identity + approval + audit); UC-registered Lakebase is **read-only**. Keeping the two planes distinct
# MAGIC is the governance story, not a limitation to hide.
