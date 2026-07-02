"""AkzoNobel L100 code-your-own agent.

A minimal LangGraph ReAct agent — ``create_react_agent(ChatDatabricks(...), tools=[...])``
— wrapped in the MLflow ``ResponsesAgent`` interface so it gets tracing, evaluation, and
serving for free. It CONSUMES exactly ONE read-only managed MCP tool: the
``coatings_data_lookup`` UC function exposed by the Databricks managed UC-functions MCP
server over the governed finance schema (``AKZO_SCHEMA``). Read-only — no actions.

How the one tool is wired
-------------------------
Default (managed MCP, the path the workshop teaches): the workshop registers a single
read-only Unity Catalog function ``{catalog}.{schema}.coatings_data_lookup(question
STRING)`` — see ``scripts/register_uc_function.sql``. At start-up the agent connects a
``DatabricksMCPClient`` to ``{host}/api/2.0/mcp/functions/{catalog}/{schema}``, lists the
tools that server exposes, picks the ``coatings_data_lookup`` tool, and binds a thin
LangChain tool that calls it via ``client.call_tool(...)``. The call is governed by Unity
Catalog + the AI Gateway — the agent never touches Spark directly on this path.

Local-dev fallback (``AKZO_LOCAL_TOOL=1`` only): if you want to iterate without a live
managed-MCP server, the agent runs an in-process Spark implementation of the same lookup.
That path enforces a real single-statement, read-only, schema-scoped SQL guard (sqlglot).
It is explicitly off by default; managed-MCP consumption is the default.

This is the L100 rung of the "any framework, any model, no lock-in" ladder: the same
``ResponsesAgent`` wrapper takes the OpenAI Agents SDK (L200) or a LangGraph supervisor
(L300). Nothing is hardcoded to a workspace — catalog, schema, LLM endpoint, and MCP URL
all resolve from the environment (see ``agent_server/utils.py``).
"""

import logging
from typing import Any

import mlflow
from databricks_langchain import ChatDatabricks
from langchain_core.tools import StructuredTool, tool
from langgraph.prebuilt import create_react_agent
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

from agent_server.sql_guard import assert_read_only_select
from agent_server.utils import (
    get_finance_mcp_server_url,
    get_llm_endpoint,
    get_schema,
    use_local_tool,
)

# Trace every LangChain/LangGraph step into the active MLflow experiment.
mlflow.langchain.autolog()

LLM_ENDPOINT = get_llm_endpoint()
FINANCE_SCHEMA = get_schema()

# The single read-only UC function the workshop registers and the agent consumes through
# the managed UC-functions MCP server. The MCP server exposes UC functions with names of the
# form ``<catalog>__<schema>__<function>``; we match on the function suffix so the catalog
# stays portable.
UC_FUNCTION_NAME = "coatings_data_lookup"

SYSTEM_PROMPT = (
    "You are the AkzoNobel Coatings finance assistant. Answer questions about gross "
    "margin, price, FX, cost, and product performance for AkzoNobel's coatings business. "
    "You have ONE read-only tool that looks up coatings finance data over the "
    f"`{FINANCE_SCHEMA}` tables. Always ground your answer in the tool's result — never "
    "invent numbers. If the tool returns no rows, say so plainly and do not fabricate a "
    "figure. Keep answers concise and cite the figures you used."
)


# ----------------------------------------------------------------------------------------
# Managed MCP path (default) — consume the one read-only UC function via the MCP server.
# ----------------------------------------------------------------------------------------
def _build_mcp_tool() -> StructuredTool:
    """Connect to the managed UC-functions MCP server, find the one read-only
    ``coatings_data_lookup`` tool it exposes, and wrap it as a LangChain tool."""
    from databricks.sdk import WorkspaceClient
    from databricks_mcp import DatabricksMCPClient

    server_url = get_finance_mcp_server_url()
    if not server_url:
        raise RuntimeError(
            "Could not resolve the managed MCP server URL (no Databricks host). "
            "Set DATABRICKS_HOST, or use AKZO_LOCAL_TOOL=1 for local-only dev."
        )

    workspace_client = WorkspaceClient()
    client = DatabricksMCPClient(server_url=server_url, workspace_client=workspace_client)

    tools = client.list_tools()
    match = next((t for t in tools if t.name.endswith(UC_FUNCTION_NAME)), None)
    if match is None:
        available = ", ".join(t.name for t in tools) or "(none)"
        raise RuntimeError(
            f"The managed MCP server at {server_url} does not expose a "
            f"`{UC_FUNCTION_NAME}` tool. Register it first (see "
            f"scripts/register_uc_function.sql). Tools found: {available}."
        )
    mcp_tool_name = match.name

    def _lookup(question: str) -> str:
        result = client.call_tool(mcp_tool_name, {"question": question})
        text = "".join(getattr(c, "text", "") for c in result.content).strip()
        return text or "No result returned by the lookup tool."

    return StructuredTool.from_function(
        func=_lookup,
        name="coatings_data_lookup",
        description=(
            "Look up AkzoNobel coatings finance data (gross margin, price, FX, cost, product "
            "performance) over the finance tables. Read-only. Pass a natural-language "
            "question; returns the grounded data."
        ),
    )


# ----------------------------------------------------------------------------------------
# Local-dev fallback (AKZO_LOCAL_TOOL=1) — in-process Spark, with a real read-only guard.
# ----------------------------------------------------------------------------------------
@tool
def coatings_data_lookup_local(question: str) -> str:
    """LOCAL-DEV ONLY. Look up AkzoNobel coatings finance data by generating governed
    read-only Spark SQL over the finance tables and running it in-process. Use for
    gross margin, price, FX, cost, and product-performance questions. Read-only: a single
    SELECT statement, validated and scoped to the finance schema; never writes."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    instructions = (
        "You are the AkzoNobel coatings text-to-SQL helper. Output ONE read-only Spark SQL "
        "SELECT query, no prose, no code fences, no semicolons. "
        f"Reference ONLY tables in {FINANCE_SCHEMA}: "
        f"{FINANCE_SCHEMA}.products(sku, product_name, product_line, region), "
        f"{FINANCE_SCHEMA}.margin_actuals(sku, region, month, units, revenue_eur, cogs_eur, gross_margin_eur). "
        "gross_margin_pct = SUM(gross_margin_eur) / SUM(revenue_eur) (never average a ratio). "
        "'Paints EMEA' := product_line='Decorative Paints' AND region='EMEA', joined on sku. "
        "Q1 2026 = 2026-01-01..2026-03-01, Q2 2026 = 2026-04-01..2026-06-01. Round % to 1 decimal."
    )
    prompt = instructions + "\n\nQ: " + question + "\nSQL:"
    sql = (
        spark.sql("SELECT ai_query(:e, :p) AS s", args={"e": LLM_ENDPOINT, "p": prompt})
        .first()["s"]
        .strip()
    )
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    try:
        # Real guard: exactly one statement, root is a SELECT, every table ref is inside
        # the finance schema. Raises ValueError otherwise.
        assert_read_only_select(sql, FINANCE_SCHEMA)
    except ValueError as e:
        return f"Refused (read-only guard): {e} | SQL was: {sql}"
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(20).collect()]
        if not rows:
            return "No rows returned. SQL: " + sql
        return "SQL: " + sql + "\nROWS: " + str(rows)
    except Exception as e:  # noqa: BLE001 — surface the error to the model, don't crash the run
        return "SQL failed: " + str(e)[:200] + " | SQL was: " + sql


def _build_tool():
    """Select the one read-only tool: managed MCP by default, local Spark only when
    AKZO_LOCAL_TOOL=1."""
    if use_local_tool():
        return coatings_data_lookup_local
    try:
        return _build_mcp_tool()
    except Exception as e:  # noqa: BLE001 — never let a managed-MCP hiccup crash the server
        logging.warning(
            "Managed MCP tool unavailable (%s); falling back to the in-process local tool. "
            "Check the workspace host, that coatings_data_lookup is registered, and that the "
            "app's principal has EXECUTE on it.", e,
        )
        return coatings_data_lookup_local


_graph = create_react_agent(
    ChatDatabricks(endpoint=LLM_ENDPOINT),
    tools=[_build_tool()],
    prompt=SYSTEM_PROMPT,
)


def _to_lc_messages(request: ResponsesAgentRequest) -> list[dict[str, Any]]:
    """Map a ResponsesAgent request to LangChain-style message dicts."""
    items = [i.model_dump() if hasattr(i, "model_dump") else i for i in request.input]
    return [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in items
    ]


def _final_text(graph_output: dict[str, Any]) -> str:
    """Extract the assistant's final text from a LangGraph result."""
    final = graph_output["messages"][-1]
    text = getattr(final, "content", None)
    if text is None and isinstance(final, dict):
        text = final.get("content")
    return text if isinstance(text, str) else str(text)


class AkzoLangGraphAgent(ResponsesAgent):
    """LangGraph ReAct agent exposed through the MLflow ResponsesAgent interface."""

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        out = _graph.invoke({"messages": _to_lc_messages(request)})
        return ResponsesAgentResponse(
            output=[
                {
                    "id": "msg-1",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": _final_text(out)}],
                }
            ]
        )


AGENT = AkzoLangGraphAgent()

# Models-from-code entry point: `mlflow.pyfunc.log_model(python_model="agent.py", ...)`
# discovers the agent through this call.
mlflow.models.set_model(AGENT)
