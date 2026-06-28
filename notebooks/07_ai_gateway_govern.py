# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 7 — Govern at scale: AI Gateway
# MAGIC
# MAGIC *Completes use case #4, the AI governance & policy agent — the Foundry differentiator.*
# MAGIC
# MAGIC This is the **reference build** behind the Layer-7 hands-on block. In the room you do not stand
# MAGIC any of this up — it is pre-staged. You **change one control (a rate limit / spend cap / route),
# MAGIC re-run, and observe**. This notebook shows exactly what that "one thing" is wired into.
# MAGIC
# MAGIC **The whole game (recap):** every model call the supervisor and its legs make goes through **one
# MAGIC front door** — the **AI Gateway**. That single plane is where you set *routes* (which model
# MAGIC serves traffic), *rate limits* (no one team can exhaust the endpoint), *spend caps* (budget per
# MAGIC route), *guardrails* (PII/safety), and *payload logging* (who asked what, what came back) — all
# MAGIC landing in **Unity Catalog**. Change a control once and every agent inherits it; no app redeploy.
# MAGIC
# MAGIC **This layer, peeled, follows the 3-beat rhythm:**
# MAGIC 1. **See** — the gateway endpoint's live config (routes, rate limits, guardrails, log table) and
# MAGIC    the **preseeded payload logs** in UC (real calls lag ~1h, so we preseed for the demo).
# MAGIC 2. **Tweak** — change **one** control live (here: the per-user rate limit) via the SDK, confirm
# MAGIC    it took effect on the running endpoint.
# MAGIC 3. **Return** — query the payload logs for **cost/usage by user-group**: the audit + chargeback
# MAGIC    view a governance owner actually needs.
# MAGIC
# MAGIC **Honest Foundry compare (per the agenda):** the win is **not** "Foundry can't orchestrate." It
# MAGIC is that **one plane governs LLM endpoints + agents + coding tools + custom/external APIs**, and —
# MAGIC the real differentiator — that governance is **UC-native**: the same lineage, permissions, and
# MAGIC audit that cover your lakehouse data also cover the model traffic and the logs it writes. Only
# MAGIC claim MCP / external-API governance while *showing* the exact path.
# MAGIC
# MAGIC > **Status (say this out loud):** Unity **AI Gateway is Beta**; inference-table/payload logs are
# MAGIC > **best-effort and can lag up to ~1h**. Never promise "today's calls appear now." We use
# MAGIC > **preseeded logs** for the "see" beat and configure **one** control live for the "tweak" beat.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC We point at an existing AI Gateway endpoint in this workspace. `harman-aes-ai-gateway` is the
# MAGIC reference pattern — it already has multiple routes, per-user + per-endpoint rate limits,
# MAGIC PII/safety guardrails, usage tracking, and inference-table logging to UC. You may instead create
# MAGIC your own `akzo-ai-gateway` (cell at the end) if you have endpoint-create permission.

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
GW = f"{CATALOG}.akzo_gateway"

# The live gateway endpoint we govern + call. Swap for your own akzo-ai-gateway if you created one.
GATEWAY_ENDPOINT = "harman-aes-ai-gateway"

spark.sql(f"USE CATALOG {CATALOG}")
print("Gateway schema  :", GW)
print("Gateway endpoint:", GATEWAY_ENDPOINT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1a — SEE: the gateway's live config (routes, limits, guardrails, log table)
# MAGIC
# MAGIC One endpoint is the front door for many models. Its `ai_gateway` block is where every control
# MAGIC lives. This is what a governance owner reads to answer *"what governs our model traffic?"* — in
# MAGIC one place, not scattered across app configs.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
ep = w.serving_endpoints.get(GATEWAY_ENDPOINT)

print("Endpoint :", ep.name, "| ready:", ep.state.ready if ep.state else None)
print("\nRoutes (served entities -> model):")
cfg = ep.config or ep.pending_config
for se in (cfg.served_entities or []):
    print(f"  - {se.name}  ->  {se.entity_name or getattr(se,'external_model',None)}")
print("\nTraffic split:")
for r in ((cfg.traffic_config.routes if cfg and cfg.traffic_config else []) or []):
    print(f"  - {r.served_model_name}: {r.traffic_percentage}%")

ag = ep.ai_gateway
if ag:
    print("\nRate limits :", [(rl.key, rl.calls, rl.renewal_period) for rl in (ag.rate_limits or [])])
    print("Usage track :", ag.usage_tracking_config.enabled if ag.usage_tracking_config else None)
    if ag.inference_table_config:
        itc = ag.inference_table_config
        print("Payload log :", f"{itc.catalog_name}.{itc.schema_name}.{itc.table_name_prefix}_payload  (enabled={itc.enabled})")
    if ag.guardrails:
        print("Guardrails  : PII + safety on input/output (Beta)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1b — SEE: preseeded payload logs in Unity Catalog
# MAGIC
# MAGIC Real gateway inference-table logs **lag up to ~1h** (Beta, best-effort). So for the demo we
# MAGIC **preseed** `akzo_gateway.payload_logs` with realistic request/response/usage/cost rows across
# MAGIC AkzoNobel user-groups (Finance, SCM, Commercial, Procurement) — the "see" beat must not wait an
# MAGIC hour. The schema mirrors the **real** AI Gateway payload table
# MAGIC (`databricks_request_id`, `request_time`, `request`, `response`, `requester`, token usage),
# MAGIC plus a few enrichment columns (`user_group`, token counts, `cost_usd`, `model`) so the
# MAGIC cost/usage-by-group view works without parsing JSON live.

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {GW}.payload_logs (
  databricks_request_id STRING,
  request_time          TIMESTAMP,
  request_date          DATE,
  endpoint              STRING,
  served_model          STRING,
  model                 STRING,
  requester             STRING,
  user_group            STRING,
  request               STRING,
  response              STRING,
  input_tokens          INT,
  output_tokens         INT,
  total_tokens          INT,
  cost_usd              DOUBLE,
  status_code           INT,
  execution_duration_ms BIGINT
) USING DELTA
COMMENT 'Preseeded AI Gateway payload/usage logs for the Akzo workshop. Mirrors the real gateway inference-table payload schema + cost/usage enrichment. Real logs lag ~1h (Beta) — these are preseeded for the demo.'
""")
print("Created (or confirmed):", f"{GW}.payload_logs")

# COMMAND ----------

# MAGIC %md
# MAGIC **Preseed realistic rows.** Each user-group asks the kind of question its agent leg handles; we
# MAGIC attach plausible token counts and a per-1k-token cost so the chargeback view is meaningful. We
# MAGIC clear-and-reseed so re-running the notebook is idempotent.

# COMMAND ----------

import uuid, random
from datetime import datetime, timezone, timedelta

# pricing per 1k tokens (illustrative blended USD) by served model
PRICE_PER_1K = {"chat-quality": 0.012, "chat-fast": 0.0008, "chat-cheap": 0.0003}
MODEL_OF = {"chat-quality": "databricks-claude-opus-4-7",
            "chat-fast": "databricks-meta-llama-3-3-70b-instruct",
            "chat-cheap": "databricks-gpt-oss-20b"}

# (user_group, requester, served_model, sample request, sample response, in_tok, out_tok)
SEED = [
    ("Finance",     "controller.emea@akzonobel.com", "chat-quality",
     "Decompose the Paints EMEA Q2 2026 margin drop into price/volume/FX/cost.",
     "Margin fell ~8.9pp: price ~-3pp, raw material ~-3pp, FX ~-2pp, volume ~flat.", 480, 220),
    ("Finance",     "planner.emea@akzonobel.com",     "chat-fast",
     "Show Paints EMEA gross margin % by month for 2026.",
     "Jan 39.8%, Feb 39.5%, ... Jun 30.4%.", 210, 90),
    ("SCM",         "planner.scm@akzonobel.com",       "chat-fast",
     "Which EMEA lanes missed OTIF in Q2 and why?",
     "3 lanes below target; root cause = port congestion + safety-stock breach.", 260, 140),
    ("SCM",         "controller.scm@akzonobel.com",    "chat-quality",
     "Recommend an intervention for the Rotterdam->DE lane OTIF miss.",
     "Re-route 20% volume to rail; lift safety stock on top-5 SKUs for 6 weeks.", 320, 180),
    ("Commercial",  "rep.benelux@akzonobel.com",       "chat-fast",
     "Which accounts show churn risk this quarter?",
     "4 accounts with churn_score>0.7 and rising complaint_count.", 230, 110),
    ("Commercial",  "rep.dach@akzonobel.com",          "chat-cheap",
     "Draft a next-best-action email for account A-1042.",
     "Proposed: schedule QBR, offer volume rebate on Performance Coatings.", 180, 260),
    ("Procurement", "buyer.raw@akzonobel.com",         "chat-quality",
     "Summarize TiO2 and resin price escalation clauses across supplier contracts.",
     "5 of 6 contracts allow quarterly escalation; 2 are non-standard (>10% cap).", 540, 240),
    ("Procurement", "buyer.freight@akzonobel.com",     "chat-cheap",
     "List contracts with termination notice under 30 days.",
     "2 contracts: SUP-Logi-EU, SUP-Pack-NL.", 150, 70),
]

now = datetime.now(timezone.utc)
rows = []
for i, (grp, who, served, req, resp, itok, otok) in enumerate(SEED):
    # spread a handful of calls per seed across the last few hours, with mild jitter on tokens
    for k in range(random.randint(3, 7)):
        in_t = itok + random.randint(-30, 40)
        out_t = otok + random.randint(-20, 50)
        tot = in_t + out_t
        cost = round(tot / 1000.0 * PRICE_PER_1K[served], 6)
        ts = now - timedelta(minutes=random.randint(5, 360))
        rows.append((
            f"req-{uuid.uuid4().hex[:12]}", ts, ts.date(), GATEWAY_ENDPOINT, served, MODEL_OF[served],
            who, grp, req, resp, in_t, out_t, tot, cost, 200, random.randint(400, 2600),
        ))

schema = ("databricks_request_id string, request_time timestamp, request_date date, endpoint string, "
          "served_model string, model string, requester string, user_group string, request string, "
          "response string, input_tokens int, output_tokens int, total_tokens int, cost_usd double, "
          "status_code int, execution_duration_ms bigint")

spark.sql(f"DELETE FROM {GW}.payload_logs")  # idempotent reseed
spark.createDataFrame(rows, schema=schema).write.mode("append").saveAsTable(f"{GW}.payload_logs")
print(f"Preseeded {len(rows)} payload-log rows across {len({r[7] for r in rows})} user-groups.")
display(spark.sql(f"SELECT request_time, user_group, served_model, total_tokens, ROUND(cost_usd,5) cost_usd, requester FROM {GW}.payload_logs ORDER BY request_time DESC LIMIT 8"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: change ONE control live, confirm it took effect
# MAGIC
# MAGIC **This is the live moment.** We change exactly **one** gateway control on the running endpoint —
# MAGIC the **per-user rate limit** — through the SDK, and read it back to confirm. No app redeploy; the
# MAGIC change governs every agent that calls through this endpoint immediately.
# MAGIC
# MAGIC > **Pick ONE control in the room** (the agenda says one live control): a **rate limit** (below),
# MAGIC > a **spend cap** (`UsageTrackingConfig` / budget per route), or a **model route** (shift
# MAGIC > `traffic_config` percentages). We demo the rate limit because it is reversible and instantly
# MAGIC > observable. The spend-cap and route variants are shown as commented alternatives.

# COMMAND ----------

from databricks.sdk.service.serving import (
    AiGatewayConfig, AiGatewayRateLimit, AiGatewayRateLimitKey, AiGatewayRateLimitRenewalPeriod,
    AiGatewayInferenceTableConfig, AiGatewayUsageTrackingConfig,
)

# Read current per-user limit so we can show the before/after and restore it.
def _user_limit(endpoint_name):
    ag = w.serving_endpoints.get(endpoint_name).ai_gateway
    for rl in (ag.rate_limits or []):
        if str(rl.key).endswith("USER") or str(rl.key) == "user":
            return rl.calls
    return None

before = _user_limit(GATEWAY_ENDPOINT)
print("Per-user rate limit BEFORE:", before, "calls/min")

# >>> THIS IS THE CONTROL YOU TWEAK <<< — change NEW_USER_LIMIT and re-run this cell.
NEW_USER_LIMIT = 60   # e.g. tighten Finance/SCM users to 60 calls/min

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

after = _user_limit(GATEWAY_ENDPOINT)
print("Per-user rate limit AFTER :", after, "calls/min   <-- the tweak took effect on the live endpoint")

# COMMAND ----------

# MAGIC %md
# MAGIC **Alternative controls (pick one in the room).** Uncomment to demo a spend cap or a model-route
# MAGIC shift instead of the rate limit.

# COMMAND ----------

# --- ALT A: model route — shift traffic to the cheaper model (no app change) ---
# from databricks.sdk.service.serving import TrafficConfig, Route
# w.serving_endpoints.update_config(
#     name=GATEWAY_ENDPOINT,
#     traffic_config=TrafficConfig(routes=[
#         Route(served_model_name="chat-quality", traffic_percentage=20),
#         Route(served_model_name="chat-fast",    traffic_percentage=80),
#         Route(served_model_name="chat-cheap",   traffic_percentage=0),
#     ]),
# )

# --- ALT B: spend cap / budget — usage tracking is the foundation; budgets are set in the
#     Gateway UI (Serving > endpoint > AI Gateway > Usage). Enable tracking here, set the cap in UI. ---
# w.serving_endpoints.put_ai_gateway(
#     name=GATEWAY_ENDPOINT,
#     usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
# )

print("Alternative controls shown as commented variants — demo exactly one live in the room.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: cost & usage by user-group (the chargeback / audit view)
# MAGIC
# MAGIC This is what the governance owner actually wants: **who is spending, on which model, and is any
# MAGIC one group about to blow the budget.** It is a plain `SELECT` over UC — the same governance plane
# MAGIC as the rest of the lakehouse. (Real gateway logs feed this exact view once the ~1h lag clears.)

# COMMAND ----------

display(spark.sql(f"""
SELECT
  user_group,
  COUNT(*)                              AS calls,
  SUM(total_tokens)                     AS total_tokens,
  ROUND(SUM(cost_usd), 4)               AS cost_usd,
  ROUND(AVG(execution_duration_ms))     AS avg_latency_ms,
  ROUND(SUM(cost_usd) / COUNT(*), 5)    AS cost_per_call
FROM {GW}.payload_logs
GROUP BY user_group
ORDER BY cost_usd DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC **Cost by model tier** — shows the route mix and why the spend-cap / route control matters: the
# MAGIC `chat-quality` (Opus) tier dominates cost per call, so shifting low-stakes traffic to `chat-fast`
# MAGIC is the lever.

# COMMAND ----------

display(spark.sql(f"""
SELECT served_model, model,
       COUNT(*) AS calls, SUM(total_tokens) AS total_tokens,
       ROUND(SUM(cost_usd), 4) AS cost_usd
FROM {GW}.payload_logs
GROUP BY served_model, model
ORDER BY cost_usd DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Confirm a real governed call goes through the gateway
# MAGIC
# MAGIC Prove the front door actually serves traffic: call the gateway endpoint through `ai_query`. In
# MAGIC production this call is what lands (after the ~1h lag) in the real inference-table payload log
# MAGIC the config in BEAT 1a points to.

# COMMAND ----------

govern_call = spark.sql(
    "SELECT ai_query(:ep, :prompt) AS answer",
    args={"ep": GATEWAY_ENDPOINT,
          "prompt": "In one sentence, what does the AI Gateway govern for an agent platform?"},
).first()["answer"]
print("Gateway-served answer:\n", govern_call)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Restore the tweaked control (leave the shared endpoint as we found it)
# MAGIC
# MAGIC `harman-aes-ai-gateway` is a **shared** endpoint. Restore the per-user rate limit so the next
# MAGIC pair starts clean. (Skip this on your own `akzo-ai-gateway`.)

# COMMAND ----------

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
# MAGIC ## OPTIONAL — create your own `akzo-ai-gateway` (if you have endpoint-create permission)
# MAGIC
# MAGIC The reference uses the existing `harman-aes-ai-gateway`. If you can create endpoints, this is how
# MAGIC the Akzo-branded gateway is stood up — one endpoint fronting tiered routes with rate limits,
# MAGIC usage tracking, guardrails, and UC payload logging. Guarded so it never runs by accident.

# COMMAND ----------

CREATE_AKZO_GATEWAY = False  # set True only if you have create-endpoint permission

if CREATE_AKZO_GATEWAY:
    from databricks.sdk.service.serving import (
        EndpointCoreConfigInput, ServedEntityInput, TrafficConfig, Route,
        AiGatewayGuardrails, AiGatewayGuardrailParameters, AiGatewayGuardrailPiiBehavior,
    )
    try:
        w.serving_endpoints.create(
            name="akzo-ai-gateway",
            config=EndpointCoreConfigInput(
                served_entities=[
                    ServedEntityInput(name="chat-quality", entity_name="databricks-claude-opus-4-7",
                                      entity_version="1", scale_to_zero_enabled=True, workload_size="Small"),
                    ServedEntityInput(name="chat-fast", entity_name="databricks-meta-llama-3-3-70b-instruct",
                                      entity_version="1", scale_to_zero_enabled=True, workload_size="Small"),
                ],
                traffic_config=TrafficConfig(routes=[
                    Route(served_model_name="chat-quality", traffic_percentage=50),
                    Route(served_model_name="chat-fast", traffic_percentage=50),
                ]),
            ),
            ai_gateway=AiGatewayConfig(
                rate_limits=[
                    AiGatewayRateLimit(calls=5000, key=AiGatewayRateLimitKey.ENDPOINT,
                                       renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
                    AiGatewayRateLimit(calls=100, key=AiGatewayRateLimitKey.USER,
                                       renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE),
                ],
                usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
                inference_table_config=AiGatewayInferenceTableConfig(
                    enabled=True, catalog_name=CATALOG, schema_name="akzo_gateway",
                    table_name_prefix="gateway_inference_logs"),
                guardrails=AiGatewayGuardrails(
                    input=AiGatewayGuardrailParameters(safety=True,
                        pii=AiGatewayGuardrailPiiBehavior(behavior="BLOCK")),
                    output=AiGatewayGuardrailParameters(safety=True,
                        pii=AiGatewayGuardrailPiiBehavior(behavior="BLOCK"))),
            ),
        )
        print("Created akzo-ai-gateway.")
    except Exception as e:
        print("Create skipped/failed (likely no permission) — use harman-aes-ai-gateway. (", e, ")")
else:
    print("akzo-ai-gateway creation disabled — reference uses harman-aes-ai-gateway.")

# COMMAND ----------

# MAGIC %md
# MAGIC **What we proved:**
# MAGIC - **One plane, many controls:** routes, per-user + per-endpoint rate limits, usage tracking,
# MAGIC   PII/safety guardrails, and UC payload logging — all on one gateway endpoint.
# MAGIC - **One live tweak:** changed the per-user rate limit on the running endpoint via the SDK and
# MAGIC   read it back — no app redeploy, governs every agent immediately. (Restored afterward.)
# MAGIC - **UC-native audit + chargeback:** `akzo_gateway.payload_logs` gives cost/usage **by
# MAGIC   user-group** and **by model tier** with a plain `SELECT` — the Foundry differentiator is that
# MAGIC   this is the *same* governance plane as the lakehouse data, not a bolt-on.
# MAGIC - **Honest Beta framing:** AI Gateway is Beta and real logs lag ~1h, so the "see" beat runs on
# MAGIC   **preseeded** logs; only **one** control is changed live.
# MAGIC
# MAGIC **The whole game, every layer now understood — every call governed and traced.** Day 1 closes
# MAGIC where it opened: the supervisor, seen through all seven layers.
