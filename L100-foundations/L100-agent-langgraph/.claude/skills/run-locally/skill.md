---
name: run-locally
description: "Run and test the L100 LangGraph agent locally. Use when: (1) the user says 'run locally', 'start server', 'test agent', or 'localhost', (2) curl commands are needed to test the API, (3) troubleshooting local development, (4) configuring server options like port or hot-reload."
---

# Run the Agent Locally

## Start the Server + Chat UI

```bash
uv run start-app
```

Backend starts at http://localhost:8000, chat UI at http://localhost:3000.

## The one tool: managed MCP (default) vs local fallback

By default the agent consumes the read-only `coatings_data_lookup` UC function through the
managed UC-functions MCP server. Register it once in the workspace with
`scripts/register_uc_function.sql`, and make sure `LLM_ENDPOINT` is set (required, no default).

For local iteration without a live managed-MCP server, set `AKZO_LOCAL_TOOL=1` in `.env` to run
an in-process Spark fallback of the same lookup. The fallback validates model-generated SQL with
a real read-only guard (single SELECT only, table refs confined to `akzo_finance`).

## Server Options

```bash
uv run start-server --reload          # Hot-reload on code changes
uv run start-server --port 8001       # Custom port
uv run start-app --no-ui              # Backend only, skip the chat UI
```

## Test the API

**Non-streaming:**
```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{ "input": [{ "role": "user", "content": "What was Paints EMEA gross margin in Q1 vs Q2 2026?" }] }'
```

**Streaming:**
```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{ "input": [{ "role": "user", "content": "hi" }], "stream": true }'
```

A grounded answer should come back with a visible `coatings_data_lookup` tool call in the
MLflow trace (open the experiment in the workspace to inspect it).

## Pre-flight Before Deploy

```bash
uv run preflight
```

Starts the server, hits `/health`, and sends one `/invocations` request to catch config
and code errors early.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Port already in use** | `uv run start-server --port 8001`, or `lsof -ti :8000 \| xargs kill -9` |
| **Authentication errors** | Verify `.env`; re-run the **quickstart** skill |
| **Module not found** | `uv sync` to install dependencies |
| **MLflow experiment not found** | Ensure `MLFLOW_TRACKING_URI` is `databricks://<profile-name>` in `.env` |
| **Tool returns no rows / SQL error** | Confirm the `akzo_finance` tables exist in your catalog (run the L100 data setup); set `AKZO_CATALOG` if the data lives in another catalog |
| **`coatings_data_lookup` tool not found** | Register the UC function: run `scripts/register_uc_function.sql` in the workspace. Managed MCP is Public Preview — for local-only dev set `AKZO_LOCAL_TOOL=1` to use the in-process fallback |
| **`LLM_ENDPOINT is not set`** | Set `LLM_ENDPOINT` in `.env` (required, no default) |

## How It Works

```
User (chat UI :3000 / curl :8000)
  │
  ▼
AgentServer (FastAPI, /invocations)  ── MLflow tracing
  │
  ▼
AkzoLangGraphAgent (ResponsesAgent)
  │
  ▼
create_react_agent(ChatDatabricks, [coatings_data_lookup])
  │
  └── coatings_data_lookup ──► managed UC-functions MCP server over akzo_finance (default, governed)
                               AKZO_LOCAL_TOOL=1 → in-process Spark fallback with read-only SQL guard
```

## Next Steps

- Change the model: set `LLM_ENDPOINT` in `.env`.
- Point at another catalog: set `AKZO_CATALOG` in `.env`.
- Deploy: `databricks bundle deploy` then `databricks bundle run akzo_l100_agent_langgraph`
  (see the README).
