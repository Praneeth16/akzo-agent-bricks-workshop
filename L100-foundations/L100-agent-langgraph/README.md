# L100 · Code-your-own agent — LangGraph + managed MCP

This is the bridge from no-code to code. In `00_sql_ai_functions` you called models straight
from SQL, and in `01_agent_bricks_types` you assembled agents with no code at all. Here you
write the agent yourself: a small LangGraph ReAct agent, wrapped in the MLflow
`ResponsesAgent` interface, that answers AkzoNobel coatings finance questions through exactly
one read-only tool.

The agent is deliberately minimal. It has a single tool, `coatings_data_lookup`, that turns a
question into governed read-only SQL over your personal schema's tables and runs it. No actions,
no writes — read-only by construction. The point is the shape, not the surface area: the same
`ResponsesAgent` wrapper carries any framework, so the OpenAI Agents SDK in L200 and the
LangGraph supervisor in L300 plug into the identical serving, tracing, and evaluation plane.
"Any framework, any model, no lock-in."

## How this fits the ladder

LangGraph (L100) → OpenAI Agents SDK (L200) → LangGraph supervisor (L300), all unified by
MLflow `ResponsesAgent`. The mix is on purpose: it shows the wrapper is framework-agnostic.

## Nothing is hardcoded

Like the L100 notebooks, this template is portable across workspaces. The catalog resolves
from `AKZO_CATALOG`, falling back to `current_catalog()` (your assigned catalog on a lab such
as Vocareum) — there is no silent `main` fallback, so a mis-set catalog fails loudly instead
of reading the wrong data. The schema has no default — set `AKZO_SCHEMA` to your personal schema (labs that restrict `CREATE SCHEMA` provision one flat schema per user). `LLM_ENDPOINT` is **required**
(no default), so the agent never silently calls a model you did not choose. No workspace URL,
profile, warehouse, or Lakebase instance is baked in anywhere.

## The one tool: a read-only managed MCP function

The agent **consumes** exactly one read-only tool through the Databricks managed UC-functions
MCP server: the `coatings_data_lookup` Unity Catalog function over your personal schema (`AKZO_SCHEMA`). The workshop
registers it once with `scripts/register_uc_function.sql`. At start-up the agent connects a
`DatabricksMCPClient` to `{host}/api/2.0/mcp/functions/{catalog}/{schema}`, lists the tools
the server exposes, picks `coatings_data_lookup`, and binds it into `create_react_agent`. The
call is governed by Unity Catalog + the AI Gateway — no client-side SQL, no actions, read-only.

For local iteration without a live managed-MCP server, set `AKZO_LOCAL_TOOL=1` to use an
in-process Spark fallback of the same lookup. That path runs model-generated SQL through a real
read-only guard (`agent_server/sql_guard.py`, sqlglot): it rejects anything that is not a single
SELECT statement and rejects any table reference outside the configured schema. The fallback
is off by default — managed-MCP consumption is the default path.

## Prerequisites

1. A Databricks workspace with the **L100 coatings data** loaded (the tables
   from the shared data setup).
2. The `coatings_data_lookup` UC function registered — run `scripts/register_uc_function.sql`
   once (skip if you only run locally with `AKZO_LOCAL_TOOL=1`).
3. **uv** — Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
4. **Node.js 20+** — for the chat UI ([install via nvm](https://github.com/nvm-sh/nvm))
5. **Databricks CLI** v0.283.0+ — authenticated to your workspace.

## Quick start (local)

```bash
# 1. Navigate to this folder
cd L100-foundations/L100-agent-langgraph

# 2. Run the setup wizard (auth, MLflow experiment, .env)
uv run quickstart

# 3. Set LLM_ENDPOINT (required) — and register the UC function if you have not yet:
#    edit .env to set LLM_ENDPOINT, then run scripts/register_uc_function.sql in the workspace.

# 4. Start the agent + chat UI
uv run start-app
```

Open **http://localhost:3000** and ask, for example,
*"What was Paints EMEA gross margin in Q1 vs Q2 2026?"* — the answer comes back grounded in
the tool's SQL result, and the call shows up in the MLflow trace.

Test the API directly:
```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{ "input": [{ "role": "user", "content": "What was Paints EMEA gross margin in Q1 vs Q2 2026?" }] }'
```

## How it works

```
User (chat UI :3000 / curl :8000)
  │
  ▼
AgentServer (FastAPI, /invocations)  ── MLflow tracing for free
  │
  ▼
AkzoLangGraphAgent (MLflow ResponsesAgent)
  │
  ▼
create_react_agent(ChatDatabricks(LLM_ENDPOINT), [coatings_data_lookup])
  │
  └── coatings_data_lookup ──► managed UC-functions MCP server (default)
                               {host}/api/2.0/mcp/functions/{catalog}/{schema}
                               governed by Unity Catalog + AI Gateway
                               (AKZO_LOCAL_TOOL=1 → in-process Spark fallback w/ SQL guard)
```

`agent_server/utils.py` builds the MCP URL from the environment; nothing is workspace-specific.

## Key files

| File | What it does |
|------|--------------|
| `agent_server/agent.py` | The LangGraph ReAct agent, wrapped as a `ResponsesAgent`. Consumes the one read-only MCP tool (default) or the local Spark fallback. Models-from-code entry point. |
| `agent_server/utils.py` | Portable config: catalog (no `main` fallback), schema, required LLM endpoint, MCP URL, local-tool flag — all from env. |
| `agent_server/sql_guard.py` | sqlglot read-only guard for the local fallback: single SELECT only, table refs confined to the configured schema. |
| `agent_server/start_server.py` | FastAPI server (`/health`, `/invocations`) that delegates to the agent, with MLflow tracing. |
| `scripts/register_uc_function.sql` | Registers the one read-only `coatings_data_lookup` UC function the MCP server exposes. |
| `scripts/quickstart.py` | First-time setup: auth, MLflow experiment, `.env`. |
| `scripts/start_app.py` | Runs the backend and the chat UI together. |
| `scripts/preflight.py` | Starts the server and sends a test request before deploy. |
| `app.yaml` / `databricks.yml` | Databricks Apps deployment config. |

## Customizing the agent

- **Model** — set `LLM_ENDPOINT` in `.env` (required; any Foundation Model or external endpoint
  you are entitled to, e.g. `databricks-meta-llama-3-3-70b-instruct`).
- **Catalog / schema** — set `AKZO_CATALOG` / `AKZO_SCHEMA` in `.env`.
- **Local vs MCP** — set `AKZO_LOCAL_TOOL=1` to use the in-process fallback; unset for managed MCP.
- **System prompt** — edit `SYSTEM_PROMPT` in `agent_server/agent.py`.

## Deploying to Databricks

```bash
# 1. Verify everything works locally
uv run preflight

# 2. Deploy (uploads code, creates/updates the app)
databricks bundle deploy

# 3. Start the app (required after deploy)
databricks bundle run akzo_l100_agent_langgraph
```

The deployed app's run-as principal needs `SELECT` on the finance tables (and access to
the LLM endpoint). Grant these in Unity Catalog — they are not baked into this template.

## Logging the agent as a model (optional)

Because the agent is authored as a file with `mlflow.models.set_model(AGENT)`, you can log it
via models-from-code and register it to Unity Catalog for serving or as a Multi-Agent
Supervisor subagent — exactly the path the `06_custom_agents_and_mcp` notebook walks through:

```python
import mlflow
from mlflow.models.resources import DatabricksServingEndpoint
from agent_server.utils import get_llm_endpoint

with mlflow.start_run():
    logged = mlflow.pyfunc.log_model(
        name="agent",
        python_model="agent_server/agent.py",
        resources=[DatabricksServingEndpoint(endpoint_name=get_llm_endpoint())],
        pip_requirements=["databricks-langchain", "langgraph", "databricks-agents", "mlflow>=3.1.0", "databricks-mcp"],
    )
mlflow.register_model(logged.model_uri, "<catalog>.<schema>.akzo_l100_langgraph_agent")
```

## Using Claude Code

| What you want to do | Skill |
|---------------------|-------|
| Set up for the first time | `/quickstart` |
| Run the agent locally | `/run-locally` |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `uv run quickstart` fails on auth | Run `databricks auth login` manually, then retry |
| Port 8000 / 3000 already in use | `lsof -ti :8000 \| xargs kill -9` (or use `--port`) |
| Tool returns no rows or SQL errors | Confirm the finance tables exist in your schema; set `AKZO_CATALOG` if the data is in another catalog |
| "App already exists" on deploy | Bind the bundle: `databricks bundle deployment bind <key> <app-name> --auto-approve` |
| Permission errors after deploy | Ensure the app principal has `SELECT` on your schema and access to the LLM endpoint |

## Free Edition Notes

Databricks Apps cap at **3 per account**, **24h max runtime** after each start/update/redeploy.
This app plus L200 ch2/ch3's `mock-systems` app = 2 of 3 slots — leaves 1 free for whatever
else you deploy in this workshop.

Alternative/guidance: stop or delete apps you are not actively demoing before deploying the
next one (`databricks apps delete <name>`, or via the Apps UI), and redeploy right before a
demo (resets the 24h clock) rather than leaving it running the whole workshop.

## Next

`02_simple_agent_evaluation.ipynb` and `03_short_term_memory.ipynb` — evaluate this agent with
MLflow judges, add tracing, and wire a human-feedback loop.
