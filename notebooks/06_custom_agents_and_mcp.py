# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC The custom-agent + MCP stack is not preinstalled on serverless. Install it, then restart Python.
# MAGIC (Run this cell first; it is the only `%pip` in the notebook.) Versions per the Databricks MCP docs:
# MAGIC `mcp>=1.9`, `databricks-sdk[openai]`, `mlflow>=3.1`, `databricks-agents>=1.0`, `databricks-mcp`,
# MAGIC plus `databricks-langchain` + `langgraph` for the LangGraph agent.

# COMMAND ----------

# MAGIC %pip install --quiet "mcp>=1.9" "databricks-sdk[openai]" "mlflow>=3.1.0" "databricks-agents>=1.0.0" "databricks-mcp" "databricks-langchain" "langgraph"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 6 — Custom agents (LangGraph) + managed MCP, served
# MAGIC
# MAGIC ### Where this sits
# MAGIC
# MAGIC ```
# MAGIC   CH1-CH5  core workshop (governed supervisor -> act -> autonomous -> trust -> docs)
# MAGIC   CH6      Custom agents + managed MCP, served for consumption                      <- you are here
# MAGIC   CH7      Serve a custom / OSS / fine-tuned model
# MAGIC ```
# MAGIC
# MAGIC "Bring any framework, any model, no lock-in." Chapter 1 hand-rolled a router. Here we build a real
# MAGIC **LangGraph** agent, wrap it in the MLflow **`ResponsesAgent`** interface (so it gets tracing, eval,
# MAGIC and serving for free), give it **managed MCP** tools, then **serve it** and consume it two ways.
# MAGIC
# MAGIC ```
# MAGIC   PART A  Managed MCP        ── connect to a Databricks managed MCP server, list + call tools (governed by UC)
# MAGIC   PART B  LangGraph agent    ── create_react_agent(ChatDatabricks, tools) wrapped as a ResponsesAgent
# MAGIC   PART C  Log -> register -> deploy ── MLflow log_model(resources=...) -> UC -> agents.deploy() -> endpoint
# MAGIC   PART D  Consume            ── standalone (/responses) AND in a workflow (MAS subagent / job)
# MAGIC ```
# MAGIC
# MAGIC ### Guard-and-degrade
# MAGIC Always-run core: build the agent, **in-process `predict`**, `log_model`, `register_model`. Infra-gated
# MAGIC steps behind flags / try-except: managed MCP (Public Preview feature), `agents.deploy` (slow + uses
# MAGIC compute), the live `/responses` query. So this notebook runs green even where MCP/serving are off.
# MAGIC
# MAGIC ### Grounded in docs (treated as reference)
# MAGIC - Managed MCP servers + URLs: `docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp`
# MAGIC - Author an agent (ResponsesAgent, LangGraph): `.../generative-ai/agent-framework/author-agent`
# MAGIC - Deploy an agent (Model Serving): `agents.deploy`, `mlflow.pyfunc.log_model(resources=...)`
# MAGIC
# MAGIC ### Prerequisites
# MAGIC Serverless enabled; a chat model serving endpoint; the `akzo_finance` data (CH1) for the agent's tool;
# MAGIC permission to register a UC model. Managed MCP + agent serving are optional (guarded).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_lakebase_praneeth_catalog", "Unity Catalog")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-7", "Chat model endpoint")
dbutils.widgets.text("uc_model_name", "serverless_lakebase_praneeth_catalog.akzo_ops.akzo_langgraph_agent", "UC model name to register")
dbutils.widgets.text("genie_space_id", "", "Genie Space id for MCP (optional)")
dbutils.widgets.dropdown("deploy", "false", ["true", "false"], "Deploy to Model Serving (slow)")

CATALOG = dbutils.widgets.get("catalog")
FIN = f"{CATALOG}.akzo_finance"
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")
UC_MODEL_NAME = dbutils.widgets.get("uc_model_name")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id").strip()
DEPLOY = dbutils.widgets.get("deploy") == "true"

import json, os
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
HOST = w.config.host
spark.sql(f"USE CATALOG {CATALOG}")
print("Catalog:", CATALOG, "| LLM:", LLM_ENDPOINT, "| UC model:", UC_MODEL_NAME)
print("Workspace host:", HOST, "| deploy:", DEPLOY)

# COMMAND ----------

# MAGIC %md
# MAGIC # PART A — Connect to a Databricks managed MCP server
# MAGIC
# MAGIC Managed MCP servers (Public Preview) are ready-to-use, governed by Unity Catalog + Unity AI Gateway.
# MAGIC URL patterns (from the docs):
# MAGIC
# MAGIC | Server | URL pattern | OAuth scope |
# MAGIC |---|---|---|
# MAGIC | UC functions | `/api/2.0/mcp/functions/{catalog}/{schema}/{function}` | `unity-catalog` |
# MAGIC | Genie Space | `/api/2.0/mcp/genie/{genie_space_id}` | `genie` |
# MAGIC | AI Search | `/api/2.0/mcp/ai-search/{catalog}/{schema}/{index}` | `ai-search` |
# MAGIC | Databricks SQL | `/api/2.0/mcp/sql` | `sql` |
# MAGIC
# MAGIC We connect to the **UC functions** server for `system.ai` (the built-in tools, e.g. the
# MAGIC `system__ai__python_exec` code interpreter) with `DatabricksMCPClient`, list tools, and call one.
# MAGIC Guarded: if managed MCP is not enabled, the cell prints how to enable it and continues.

# COMMAND ----------

MCP_SERVER_URL = f"{HOST}/api/2.0/mcp/functions/system/ai"
MANAGED_MCP_AVAILABLE = False
try:
    from databricks_mcp import DatabricksMCPClient
    mcp_client = DatabricksMCPClient(server_url=MCP_SERVER_URL, workspace_client=w)
    tools = mcp_client.list_tools()
    print(f"Managed MCP OK — {len(tools)} tools from {MCP_SERVER_URL}:")
    for t in tools[:8]:
        print("  -", t.name)
    # Call the built-in python_exec code-interpreter tool through the governed MCP server.
    result = mcp_client.call_tool("system__ai__python_exec", {"code": "print('hello from MCP')"})
    print("called system__ai__python_exec ->", "".join(c.text for c in result.content)[:120])
    MANAGED_MCP_AVAILABLE = True
except Exception as e:
    print("Managed MCP not available here — skipping (feature is Public Preview, enable in AI Gateway > MCPs).")
    print("  detail:", str(e)[:160])

# COMMAND ----------

# MAGIC %md
# MAGIC **Genie / AI Search as MCP tools.** The same `DatabricksMCPClient` connects to a Genie Space
# MAGIC (`/api/2.0/mcp/genie/{id}`) or an AI Search index. We probe the Genie Space MCP only if you supplied
# MAGIC a `genie_space_id` widget. (Note: the Genie Space MCP is *stateless* — it invokes Genie as a tool and
# MAGIC does not carry conversation history; for multi-turn use Genie in a multi-agent system / the GA Genie
# MAGIC Conversation API.)

# COMMAND ----------

if GENIE_SPACE_ID:
    try:
        from databricks_mcp import DatabricksMCPClient
        gurl = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
        gtools = DatabricksMCPClient(server_url=gurl, workspace_client=w).list_tools()
        print(f"Genie Space MCP OK — tools: {[t.name for t in gtools]}")
    except Exception as e:
        print("Genie Space MCP probe failed:", str(e)[:160])
else:
    print("No genie_space_id provided — skipping the Genie MCP probe (set the widget to try it).")

# COMMAND ----------

# MAGIC %md
# MAGIC # PART B — Build a custom agent with LangGraph, wrapped as a `ResponsesAgent`
# MAGIC
# MAGIC `ResponsesAgent` is the MLflow interface Databricks recommends: wrap **any** framework (LangGraph here;
# MAGIC CrewAI / OpenAI Agents SDK / Claude Code SDK work the same way) and get AI Playground, Agent
# MAGIC Evaluation, tracing, and serving for free.
# MAGIC
# MAGIC The agent: a LangGraph ReAct agent (`create_react_agent(ChatDatabricks(...), tools=[...])`) with one
# MAGIC governed tool — `finance_sql`, the CH1 text2SQL leg (read-only over `akzo_finance`). We author it as a
# MAGIC **file** (`agent.py`) so the same code is both imported here for an in-process smoke test and logged
# MAGIC via MLflow models-from-code for serving.

# COMMAND ----------

AGENT_DIR = "/tmp/akzo_agent"
os.makedirs(AGENT_DIR, exist_ok=True)
AGENT_FILE = f"{AGENT_DIR}/agent.py"

# The agent source. Config is injected via placeholders (kept out of f-strings to avoid brace clashes).
AGENT_SRC = '''
"""LangGraph ReAct agent wrapped as an MLflow ResponsesAgent. Models-from-code entry point."""
import mlflow
from typing import Any
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from databricks_langchain import ChatDatabricks

LLM_ENDPOINT_NAME = "__LLM_ENDPOINT__"
FIN = "__FIN__"

mlflow.langchain.autolog()

@tool
def finance_sql(question: str) -> str:
    """Answer an AkzoNobel finance question by generating governed Spark SQL over the akzo_finance
    tables and running it. Use for gross margin, price, FX, and cost questions."""
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    instructions = (
        "You are the Akzo Finance text-to-SQL agent. Output ONE Spark SQL query, no prose, no fences. "
        "Tables under " + FIN + ": products(sku,product_line,region,...), "
        "margin_actuals(sku,region,month,units,revenue_eur,cogs_eur,gross_margin_eur). "
        "gross_margin_pct=SUM(gross_margin_eur)/SUM(revenue_eur) (never average). "
        "'Paints EMEA' := product_line='Decorative Paints' AND region='EMEA', join on sku. "
        "Q1 2026=2026-01-01..2026-03-01, Q2=2026-04-01..2026-06-01; round % to 1 decimal."
    )
    sql = spark.sql("SELECT ai_query(:e, :p) AS s",
                    args={"e": LLM_ENDPOINT_NAME, "p": instructions + "\\n\\nQ: " + question + "\\nSQL:"}).first()["s"].strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(20).collect()]
        return "SQL: " + sql + "\\nROWS: " + str(rows)
    except Exception as e:
        return "SQL failed: " + str(e)[:200] + " | SQL was: " + sql

_graph = create_react_agent(ChatDatabricks(endpoint=LLM_ENDPOINT_NAME), tools=[finance_sql])

class AkzoLangGraphAgent(ResponsesAgent):
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        # Map ResponsesAgent input -> LangChain messages (single-turn).
        msgs = [{"role": m.get("role", "user"), "content": m.get("content", "")}
                for m in [i.model_dump() if hasattr(i, "model_dump") else i for i in request.input]]
        out = _graph.invoke({"messages": msgs})
        final = out["messages"][-1]
        text = getattr(final, "content", None) or (final.get("content") if isinstance(final, dict) else str(final))
        return ResponsesAgentResponse(output=[{
            "id": "msg-1", "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        }])

AGENT = AkzoLangGraphAgent()
mlflow.models.set_model(AGENT)
'''.replace("__LLM_ENDPOINT__", LLM_ENDPOINT).replace("__FIN__", FIN)

with open(AGENT_FILE, "w") as f:
    f.write(AGENT_SRC)
print("Wrote agent to", AGENT_FILE)

# COMMAND ----------

# MAGIC %md
# MAGIC **In-process smoke test (always-run core).** Import the agent from the file and call `predict`
# MAGIC directly — proves the LangGraph agent + the governed `finance_sql` tool work before any serving.

# COMMAND ----------

import sys
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)
from agent import AGENT
from mlflow.types.responses import ResponsesAgentRequest

def answer_text(r) -> str:
    """Extract the assistant text from a ResponsesAgentResponse (output items are typed OutputItem
    objects, not dicts — normalize via model_dump)."""
    item = r.output[0]
    d = item.model_dump() if hasattr(item, "model_dump") else item
    return d["content"][0]["text"]

resp = AGENT.predict(ResponsesAgentRequest(
    input=[{"role": "user", "content": "What was Paints EMEA gross margin in Q1 vs Q2 2026?"}]))
print(answer_text(resp)[:800])

# COMMAND ----------

# MAGIC %md
# MAGIC # PART C — Log -> register -> deploy
# MAGIC
# MAGIC Log the agent via **models-from-code** (`python_model=agent.py`), declaring `resources` so the served
# MAGIC agent's identity is granted what it needs (the LLM endpoint; managed-MCP resources are auto-collected
# MAGIC via `DatabricksMCPClient.get_databricks_resources()` when MCP is on). Register to UC. Then
# MAGIC `agents.deploy()` (GUARDED behind the `deploy` widget — it stands up a real serving endpoint).

# COMMAND ----------

import mlflow
from mlflow.models.resources import DatabricksServingEndpoint

mlflow.set_registry_uri("databricks-uc")
me = w.current_user.me().user_name
mlflow.set_experiment(f"/Users/{me}/akzo_langgraph_agent")

resources = [DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT)]
if MANAGED_MCP_AVAILABLE:
    try:
        from databricks_mcp import DatabricksMCPClient
        resources.extend(DatabricksMCPClient(server_url=MCP_SERVER_URL, workspace_client=w).get_databricks_resources())
    except Exception as e:
        print("could not auto-collect MCP resources:", str(e)[:120])

with mlflow.start_run():
    logged = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model=AGENT_FILE,
        resources=resources,
        pip_requirements=["databricks-langchain", "langgraph", "databricks-agents", "mlflow>=3.1.0", "databricks-mcp"],
    )
print("Logged model:", logged.model_uri)

registered = mlflow.register_model(logged.model_uri, UC_MODEL_NAME)
print("Registered:", UC_MODEL_NAME, "version", registered.version)

# COMMAND ----------

# MAGIC %md
# MAGIC **Deploy (guarded).** `agents.deploy` provisions a Model Serving endpoint for the registered agent —
# MAGIC slow and uses compute, so it is behind the `deploy` widget (default false). Flip it to `true` to run
# MAGIC the real deploy.

# COMMAND ----------

ENDPOINT_NAME = None
if DEPLOY:
    from databricks import agents
    deployment = agents.deploy(model_name=UC_MODEL_NAME, model_version=registered.version)
    ENDPOINT_NAME = getattr(deployment, "endpoint_name", None) or getattr(deployment, "name", None)
    print("Deployed agent serving endpoint:", ENDPOINT_NAME)
else:
    print("Deploy disabled (deploy=false). Logged + registered to UC; flip the widget to deploy.")
    print("When deployed, query it with the snippet in PART D.")

# COMMAND ----------

# MAGIC %md
# MAGIC # PART D — Consume the agent
# MAGIC
# MAGIC **1) Standalone.** Query the deployed `/responses` endpoint with an OAuth token (PATs are not
# MAGIC supported for agent endpoints). If not deployed, we fall back to the in-process agent so the cell
# MAGIC still demonstrates the same request/response shape.

# COMMAND ----------

question = "Decompose the Paints EMEA Q2 2026 margin drop."
if ENDPOINT_NAME:
    out = w.serving_endpoints.query(name=ENDPOINT_NAME,
                                    extra_params={"input": [{"role": "user", "content": question}]})
    print("Standalone endpoint response:", str(out)[:800])
else:
    r = AGENT.predict(ResponsesAgentRequest(input=[{"role": "user", "content": question}]))
    print("(in-process fallback) ", answer_text(r)[:800])

# COMMAND ----------

# MAGIC %md
# MAGIC **2) In an existing workflow.** Two governed ways to plug this served agent into the platform:
# MAGIC
# MAGIC - **As a subagent of a native Multi-Agent Supervisor.** Agent Bricks MAS (and the managed **Supervisor
# MAGIC   API**, Beta) orchestrate registered subagents + managed MCP tools with OBO + built-in tracing — no
# MAGIC   router/fuser code. Register this agent's UC model / serving endpoint as a subagent so the supervisor
# MAGIC   can delegate the finance sub-question to it. (Create the MAS in Agent Bricks UI / SDK; paste the
# MAGIC   subagent description — the same lever as CH1's `ROUTING_DESCRIPTION`.)
# MAGIC - **As a Databricks Job task.** Call the served endpoint (or `mlflow.pyfunc.load_model(UC_MODEL_NAME)`)
# MAGIC   from a job step, so the agent runs inside an existing pipeline/workflow on a schedule.
# MAGIC
# MAGIC ```python
# MAGIC # Consume from any workflow step, no serving endpoint required:
# MAGIC import mlflow
# MAGIC agent = mlflow.pyfunc.load_model("models:/<uc_model_name>@champion")  # or a version
# MAGIC agent.predict({"input": [{"role": "user", "content": "..."}]})
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## What we built
# MAGIC
# MAGIC - **Managed MCP** — connected to a Databricks managed MCP server with `DatabricksMCPClient`, listed +
# MAGIC   called governed tools (UC-permissioned, AI-Gateway-monitored). [Guarded on the Public Preview feature.]
# MAGIC - **Custom LangGraph agent** — `create_react_agent(ChatDatabricks, [finance_sql])` wrapped in MLflow
# MAGIC   `ResponsesAgent`; proven with an **in-process `predict`**.
# MAGIC - **Served** — `log_model(resources=...)` -> `register_model` to UC -> `agents.deploy()` (guarded) ->
# MAGIC   a Model Serving `/responses` endpoint.
# MAGIC - **Consumed** — standalone query, and the two governed workflow paths (MAS subagent / job +
# MAGIC   `load_model`).
# MAGIC
# MAGIC "Any framework, any model, no lock-in" — the same `ResponsesAgent` wrapper takes CrewAI, the OpenAI
# MAGIC Agents SDK, or the Claude Code SDK, all governed on the one Databricks plane.
# MAGIC
# MAGIC **Next:** `07_custom_model_serving.py` — serve a custom / OSS / fine-tuned *model* (not agent):
# MAGIC Provisioned Throughput, custom GPU serving, External Models via AI Gateway.
