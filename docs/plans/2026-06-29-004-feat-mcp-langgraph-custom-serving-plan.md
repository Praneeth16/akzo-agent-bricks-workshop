# Plan 004 — Net-new notebooks: managed MCP + native MAS, custom LangGraph agents, custom/model serving

Created: 2026-06-29
Status: PLAN (not yet built). Execution will be `/ce-work` after approval.
Output posture: guard-and-degrade (user decision) — always-run core cells, infra-gated steps behind
flags / try-except so each notebook runs green even where the feature/GPU is absent, exactly like
`notebooks/04_trust_and_governance.py`'s gateway section. Verify the runnable core in Lakebase praneeth
(profile `fe-vm-lakebase-praneeth`) the same way the 5 chapters were verified (one-off serverless job
run; fix-on-fail loop).

## Problem frame

The 5 consolidated chapters cover diagnose -> act -> automate -> trust -> docs. They do NOT cover three
surfaces the team asked for:

1. **Agent Bricks native Multi-Agent Supervisor + managed MCP** — registering Genie spaces, Knowledge
   Assistants, UC functions, and **UC-governed managed MCP connectors** (Google Drive / Jira / Slack /
   GitHub) as governed subagent tools, under OBO. (Plan 003 T1.1/T1.2.)
2. **Custom agents with LangGraph** — build an agent in code (the lead framework per
   `AKZONOBEL_WORKSHOP_PLAN.md`), wrap it in the MLflow agent interface, and **serve it for consumption**:
   standalone endpoint AND plugged into an existing workflow (the supervisor / a job). (User request.)
3. **Custom / OSS / local LLM model serving** — log -> UC register -> Model Serving endpoint; Provisioned
   Throughput FM API for fine-tuned/OSS models; External Models via AI Gateway. (Plan 003 T2.1.)

These are net-new (never in the original 12), so they extend the curriculum rather than re-consolidate it.

## Scope decision: three notebooks (ch6, ch7, ch8)

| New notebook | Title | Covers | Tier |
|---|---|---|---|
| `06_native_mas_managed_mcp.py` | Agent Bricks: native MAS + managed MCP | register Genie/KA/UC-functions/managed-MCP as governed subagent tools; OBO; call the MAS endpoint | T1 (high value, broadly runnable) |
| `07_custom_agent_langgraph.py` | Build & serve a custom agent (LangGraph) | LangGraph StateGraph agent over the Paints EMEA tools -> MLflow `ResponsesAgent` -> UC register -> `agents.deploy()` -> consume standalone + as a workflow subagent | T1/T2 (build always-runs; deploy guarded) |
| `08_custom_model_serving.py` | Serve a custom / OSS / fine-tuned model | log/point-at a model -> UC register -> Model Serving endpoint; Provisioned Throughput FM API; External Models via AI Gateway | T2 (for-later; GPU/PT cost-gated) |

ch7 and ch8 could merge into one "bring your own agent & model" chapter; kept separate here so the
LangGraph agent story (most-requested) stays focused and the cost-gated model-serving story is optional.
Decision to confirm at `/ce-work` start. Numbering continues 06-08 after the 5 chapters; total stays a
clean "5 core + 3 advanced/optional" rather than breaking the "max 5" core arc.

---

## ch6 — Native MAS + managed MCP

**Goal:** show the *managed product* behind ch1's hand-rolled router: an Agent Bricks Multi-Agent
Supervisor that orchestrates registered subagents, including **managed MCP** tool connectors, under OBO
and built-in tracing — no router/fuser code.

**Teaching arc (SEE -> TWEAK -> RETURN):**
- SEE: the three Akzo Genie spaces + a Knowledge Assistant + a UC function, registered as MAS subagents;
  read the MAS config and call its endpoint with the flagship question; open the built-in trace.
- TWEAK: add/remove a subagent **description** (the same lever as ch1's `ROUTING_DESCRIPTION`) and re-ask;
  watch routing change. Then add a **managed MCP** connector (e.g. GitHub or Slack) as a tool and show the
  MAS can now reach it under UC governance.
- RETURN: contrast with ch1 — same route->call->fuse, now managed + OBO + traced + MCP tools, on one
  governed plane. This is the Foundry-counter slide made real.

**Implementation units:**
- U6.1 — Setup widgets: `catalog`, `mas_endpoint` (optional, default empty), `genie_space_ids` (optional).
- U6.2 — Inventory existing subagents (GUARDED): list the workspace's Genie spaces / KA / registered MCP
  connections via SDK; print what is available. Degrade to "none found, here is how to create them" text.
- U6.3 — Register subagents (GUARDED, flag default off): SDK/UI walkthrough to register the 3 Genie spaces
  + a KA + a UC function as MAS subagents, and a **managed MCP connection** (UC catalog connection of type
  the managed-MCP feature exposes) for Google Drive/Jira/Slack/GitHub. If the managed-MCP feature is not
  enabled, print the enablement steps and skip. **VERIFY-ON-LAB:** exact SDK surface for registering
  managed MCP as a MAS tool (Agent Bricks is GA; managed MCP connector GA/PrPr status varies by region).
- U6.4 — Call the MAS endpoint (GUARDED): `w.serving_endpoints.query(...)` against `mas_endpoint` with the
  flagship question via the `agent/v1/responses` task; print the answer + show how to pull the trace. If no
  endpoint, fall back to ch1's local `supervise()` so the cell still demonstrates route->fuse.
- U6.5 — The MCP-as-tool gotcha (markdown + guarded call): the managed-MCP **Genie URL is stateless** —
  use the GA Genie Conversation API for stateful multi-turn; the managed MCP endpoint for single-shot tool
  calls. (Plan 003 T1.2.)

**Always-run core (green without the feature):** U6.1, U6.2 (degrades), U6.4 fallback to ch1 `supervise()`.
**Guarded:** U6.3 registration, U6.4 live MAS query, U6.5 live MCP call.

**Dependencies / prereqs:** Agent Bricks enabled; serverless; the 3 Genie spaces (created in ch1 setup);
optional KA + managed-MCP feature. Reference: `docs.databricks.com/aws/en/reference/api` (Serving + Agent
responses task), Agent Bricks MAS docs, managed MCP docs.

---

## ch7 — Build & serve a custom agent (LangGraph)

**Goal:** "bring any framework, no lock-in." Build a real **LangGraph** agent in code, wrap it in the MLflow
agent interface, register to UC, deploy to Model Serving with the Agent Framework, and consume it two ways.

**The agent:** a small Paints-EMEA LangGraph `StateGraph` that reuses tools we already have:
- tool `finance_sql(question)` — the ch1 text2SQL + reasoning leg (governed UC read).
- tool `propose_action(action)` — the ch2 action-plane `ap_propose` (governed write, stays `proposed`).
- graph: router node -> tool node(s) -> responder node. Deliberately tiny and readable.

**Serving interface:** MLflow **`ResponsesAgent`** (the current Mosaic AI Agent Framework interface;
`AKZONOBEL_WORKSHOP_PLAN.md` notes CrewAI/Agno/Claude Code SDK also work via this same interface — call
that out so the "any framework" message lands). Log with `mlflow.pyfunc.log_model`/`mlflow.langchain`
declaring `resources` (the serving endpoints + UC tables the agent touches, so OBO/permissions propagate).

**Teaching arc:**
- SEE: define the LangGraph agent; invoke it **in-process** (`graph.invoke(...)`) on the flagship question
  — proves the agent works before any serving. (This is the always-green core.)
- TWEAK: add or swap a tool / edit the system node prompt; re-invoke; watch behavior change.
- RETURN (serve it): log -> `mlflow.register_model` to UC -> `databricks.agents.deploy(uc_name, version)`
  -> a Model Serving endpoint. Then **consume**:
  1. **Standalone:** query the endpoint (`w.serving_endpoints.query` / REST / `ai_query`) with a question.
  2. **In an existing workflow:** register the deployed agent as a **subagent/tool of the ch6 MAS** (or call
     it from a Databricks Job task), so the supervisor delegates to your custom LangGraph agent. Closes the
     loop: custom code -> governed served agent -> orchestrated by the platform.

**Implementation units:**
- U7.1 — `%pip install langgraph langchain databricks-agents mlflow` + `restartPython` (serverless lacks
  these, confirmed by the ch2/ch5 runs needing pip).
- U7.2 — Setup widgets: `catalog`, `llm_endpoint`, `uc_model_name`, `deploy` (bool, default False),
  `lakebase_instance` (for the propose tool).
- U7.3 — Define the LangGraph agent (StateGraph + 2 tool nodes + responder). Inline the finance text2SQL
  helper (from ch1) and a minimal `ap_propose` (from ch2) so the notebook is self-contained.
- U7.4 — Wrap in MLflow `ResponsesAgent`; `predict` smoke test in-process (ALWAYS-RUN core).
- U7.5 — Log model with `resources=[DatabricksServingEndpoint(llm_endpoint), DatabricksTable(...)]`;
  `mlflow.register_model` to `catalog.akzo_ops.<uc_model_name>`. (Logging+register always-run; cheap.)
- U7.6 — Deploy (GUARDED, `deploy=False` default): `from databricks import agents; agents.deploy(name, ver)`
  -> serving endpoint. Slow + uses compute; flagged off for verification. **VERIFY-ON-LAB:** `agents.deploy`
  signature + readiness wait.
- U7.7 — Consume standalone (GUARDED on endpoint existing): query the endpoint; print the response. If not
  deployed, query the in-process agent instead so the cell demonstrates the same I/O.
- U7.8 — Consume in a workflow (markdown + guarded): register the served agent as a ch6 MAS subagent, or a
  `notebook_task`/`agents` call from a job; show the supervisor delegating to it.

**Always-run core:** U7.1-U7.5 + U7.7 fallback (in-process). **Guarded:** U7.6 deploy, U7.7 live endpoint
query, U7.8 workflow wiring.

**Risk:** `databricks-agents` + `langgraph` versions on serverless; `ResponsesAgent` API drift. Pin loose,
verify on lab. Reference: `AnanyaDBJ/databricks-ai-workshops` L300 LangGraph for the canonical pattern.

---

## ch8 — Serve a custom / OSS / fine-tuned model

**Goal:** the model-serving counterpart to ch7's agent-serving: stand up an endpoint for a model you bring
(custom pyfunc, an OSS model, or a fine-tuned one), and show the three serving routes Databricks offers.

**Teaching arc:**
- SEE: the three routes — (a) **Provisioned Throughput FM API** for a supported base/fine-tuned model
  (serverless, no GPU mgmt); (b) **Custom Model Serving** (`workload_type=GPU_LARGE`) for an arbitrary
  logged model; (c) **External Models** fronted by the Unity AI Gateway (governed, ties back to ch4).
- TWEAK: change the served entity / scale-to-zero / workload size and re-read config.
- RETURN: the served model is callable via `ai_query` and governed by the same AI Gateway plane as ch4.

**Implementation units:**
- U8.1 — Setup widgets: `catalog`, `uc_model_name`, `serving_endpoint_name`, `create_endpoint` (bool,
  default False), `route` (pt | custom_gpu | external).
- U8.2 — Log a tiny custom pyfunc model + `register_model` to UC (ALWAYS-RUN, cheap; proves the log->register
  path without GPU).
- U8.3 — Provisioned Throughput route (GUARDED): create a PT endpoint over a supported FM via the FM API.
  Degrade to walkthrough if PT not available in-region.
- U8.4 — Custom GPU route (GUARDED, default off): `w.serving_endpoints.create(..., workload_type=GPU_LARGE)`
  for the logged model. Cost + availability gated; flagged off. **VERIFY-ON-LAB:** GPU_LARGE availability.
- U8.5 — External Models via AI Gateway (markdown + guarded): point an AI Gateway route at an external
  provider; ties to ch4's gateway governance.
- U8.6 — Consume: `ai_query(endpoint, prompt)` against whichever endpoint exists; else the logged model's
  in-process `predict`.

**Always-run core:** U8.1, U8.2, U8.6 fallback. **Guarded:** U8.3/U8.4/U8.5 endpoint creation.

**Risk:** GPU/PT cost, region availability, time. This is the most likely to stay walkthrough in the
verification run; flag clearly what was executed vs shown. Reference plan 003 T2.1 + the Serving API ref.

---

## Cross-cutting

- **Guard-and-degrade pattern (mandatory):** every infra-gated cell wrapped so a missing
  feature/endpoint/GPU prints a clear "skipped, here is how" and the notebook still finishes green. Core
  cells (build, log, register, in-process predict, governed reads) always run. This is the ch4 gateway
  pattern, now applied consistently.
- **Self-contained:** inline the small helpers each notebook needs (finance text2SQL, `ap_propose`,
  `pg()`), same as the 5 chapters — candidates run one-by-one, no cross-notebook imports.
- **`%pip` preamble + `restartPython`** wherever a lib is not preinstalled on serverless (`langgraph`,
  `langchain`, `databricks-agents`, `databricks-vectorsearch` already needed). First cell, always.
- **Verification:** import to `/Users/praneeth.paikray@databricks.com/akzo-verify/`, submit a one-off
  serverless job, poll to terminal, fix-on-fail. Pass the optional `bearer_token` param where an external
  call needs interactive-equivalent auth (the ch2/ch3 pattern). Expect ch7 U7.6/ch8 U8.4 to stay guarded
  (deploy/GPU not run in the headless job) — verify the always-run core green and note what was guarded.
- **DAB:** add ch6/ch7/ch8 as optional tasks (not in the main dependency chain, since deploy/GPU are
  gated). Update `databricks.yml` after build.
- **Hub `content.ts` `NOTEBOOKS[]`** is already stale (lists the old 10) — refresh it to the 5 core + these
  3 advanced when built. (Tracked separately as the existing follow-up.)

## Open items to confirm before `/ce-work`
1. Three notebooks (ch6/ch7/ch8) vs merge ch7+ch8 into one "BYO agent & model" chapter? (Recommend: keep
   ch6 separate; merge ch7+ch8 only if the team wants brevity.)
2. Managed-MCP feature + Agent Bricks MAS endpoint: do they exist/enabled on the lab today? (Gates ch6 live
   cells; otherwise ch6 is walkthrough + ch1-fallback.)
3. Is GPU_LARGE / Provisioned Throughput budget available for a real ch8 deploy demo, or keep it
   walkthrough? (User chose guard-and-degrade, so default is: do not create GPU endpoints in verification.)
4. LangGraph version to pin + confirm `databricks-agents` `ResponsesAgent` + `agents.deploy` API on the lab
   (VERIFY-ON-LAB at Day-0 dry run).

---

## DEFERRED — make "agents take action" unmistakable on screen (supervisor demo)

Status: agreed, parked for later. Context: in `akzo-supervisor-v2` the action ladder runs end to end
(propose → approve → execute → connectors fire → receipts in Lakebase `akzo.external_system_log`), but
the action is **invisible to a viewer**: the target is the Mock External Systems app (no visible surface),
the default action is an `scm_reroute` (a Teams ping + ServiceNow ticket — abstract), and the only on-screen
proof is a `ref_id` + status badge. Build three moves so the action lands visually:

1. **Live "Inbox" on the Mock Systems app (biggest payoff).** `apps/mock-systems/backend/main.py` already
   serves `GET /` (HTML, currently just an endpoint list) + `GET /api/log` + has Lakebase access. Replace the
   static `/` page with a **live feed of `external_system_log`** — emails sent, POs raised, tickets opened,
   Teams alerts — each with payload + timestamp + ref_id, newest first, auto-refresh. Demo flow: ask →
   approve → **execute** in the supervisor → open the Mock Systems URL → the artifact **appears**. The
   "agent did something real" reveal.
2. **Inline receipt in the supervisor app.** After `execute`, fetch the receipt(s) (the mock `/api/log` or
   the action `result.connectors`) and render the actual artifact in the Actions panel — "Agent sent this
   email to <customer>", "Agent raised this €92k PO to TiO2 Supplier NL" — not just a ref id. Add to
   `apps/supervisor/frontend/src/ActionsPanel.tsx`.
3. **Default to a tangible action.** Stage `scm_reorder` (a €92k purchase order) or `quote_send` (a customer
   quote email) by default instead of `scm_reroute`, so the executed action is visceral. Tune the
   recommendation→action mapping in `apps/supervisor/frontend/src/App.tsx` (`ActBody` mapping) /
   `agent.py` recommended-action.

Also relevant: the **`akzo-action-center` app** is purpose-built for this (queue + maturity ladder + full
lineage across all actions) — restyle it in the AkzoNobel-AppKit theme and use it as the "operations view"
alongside the supervisor.

### Carry-over fixes/notes from the OBO + action work (so the demo stays green)
- **Connection token expiry:** execute currently works because `akzo_external_systems` was ALTERed with a
  user token (mock-app-authorized, ~1h TTL). For a durable demo, mint from a **service principal (M2M)**
  granted `CAN_USE` on `akzo-mock-systems` and rotate. The v2 SP (`843eff49-...`) `/api/2.0/permissions/apps`
  grant attempt returned empty (didn't apply) — find the correct apps-ACL grant path so the SP-direct
  connector fallback also works without my token.
- **SoD model (shipped):** `/api/act` attributes the proposal to the **agent** (`requested_by=agent_name`),
  so the signed-in human can approve in-UI (no second profile / admin panel). Keep this.
- **OBO + Genie scope (shipped):** `apps/supervisor/databricks.yml` sets `user_api_scopes:[sql,
  dashboards.genie]`; legs read real Genie under the signed-in user. A new user must **re-consent** on first
  open for the forwarded token to carry the Genie scope.
- **Thinking indicator (shipped):** staged progress in `App.tsx` while the supervisor turn runs.
