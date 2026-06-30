"""Workspace-portable configuration for the L100 LangGraph agent.

Nothing here is tied to one workspace. Every value resolves from the environment, and the
ones that cannot have a safe portable default fail fast with a clear error rather than
guessing:

    AKZO_CATALOG    Unity Catalog with the coatings data. If unset, falls back to the
                    workspace's current_catalog(). If neither resolves -> error (no 'main'
                    fallback, which would silently point at the wrong data).
    AKZO_SCHEMA     Schema with the finance tables. Defaults to "akzo_finance" (the
                    workshop-provisioned schema name; override if yours differs).
    LLM_ENDPOINT    Chat model serving endpoint. REQUIRED — there is no default, so the
                    agent never silently calls a model you did not choose. Set it in .env
                    or app.yaml (e.g. databricks-meta-llama-3-3-70b-instruct).
    DATABRICKS_HOST Workspace URL. Defaults to the Databricks SDK config (ambient auth).
"""

import logging
import os
import re
from typing import Optional

DEFAULT_SCHEMA = "akzo_finance"

_IDENT = re.compile(r"[A-Za-z0-9_]+")
_ENDPOINT = re.compile(r"[A-Za-z0-9_.-]+")


def _validate(name: str, value: str, pattern: re.Pattern) -> str:
    """Reject values that could be unsafe to interpolate into SQL or a URL path."""
    if not pattern.fullmatch(value):
        raise ValueError(f"Unsafe {name}: {value!r}.")
    return value


def get_current_catalog() -> Optional[str]:
    """Return the workspace's current catalog via Spark, or None if unavailable."""
    try:
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        return spark.sql("SELECT current_catalog()").first()[0]
    except Exception as e:  # noqa: BLE001 — local/offline use has no Spark
        logging.debug("current_catalog() unavailable: %s", e)
        return None


def get_catalog() -> str:
    """Resolve the catalog: AKZO_CATALOG env > current_catalog(). No silent fallback."""
    catalog = os.environ.get("AKZO_CATALOG") or get_current_catalog()
    if not catalog:
        raise RuntimeError(
            "Could not resolve a Unity Catalog. Set AKZO_CATALOG in your environment "
            "(.env or app.yaml), or run where current_catalog() is available."
        )
    return _validate("catalog", catalog, _IDENT)


def get_schema_name() -> str:
    """Return the bare finance schema name (no catalog)."""
    return _validate("schema", os.environ.get("AKZO_SCHEMA", DEFAULT_SCHEMA), _IDENT)


def get_schema() -> str:
    """Return the fully qualified ``catalog.schema`` for the finance tables."""
    return f"{get_catalog()}.{get_schema_name()}"


def get_llm_endpoint() -> str:
    """Resolve the chat model serving endpoint name. REQUIRED — no default."""
    endpoint = os.environ.get("LLM_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "LLM_ENDPOINT is not set. Set it in your environment (.env or app.yaml) to a "
            "chat model serving endpoint you are entitled to "
            "(e.g. databricks-meta-llama-3-3-70b-instruct)."
        )
    return _validate("LLM endpoint", endpoint, _ENDPOINT)


def get_databricks_host() -> Optional[str]:
    """Resolve the workspace host from env or the Databricks SDK config."""
    def _with_scheme(h):
        # Databricks Apps inject DATABRICKS_HOST as a bare hostname (no scheme);
        # the MCP/HTTP client needs an absolute http(s):// URL.
        if not h:
            return None
        h = h.rstrip("/")
        return h if h.startswith(("http://", "https://")) else f"https://{h}"

    host = os.environ.get("DATABRICKS_HOST")
    if host:
        return _with_scheme(host)
    try:
        from databricks.sdk import WorkspaceClient

        return _with_scheme(WorkspaceClient().config.host)
    except Exception as e:  # noqa: BLE001
        logging.debug("Could not resolve Databricks host: %s", e)
        return None


def get_finance_mcp_server_url() -> Optional[str]:
    """Build the managed MCP server URL for the UC functions over the finance schema.

    Managed MCP "UC functions" server pattern (Public Preview):
        {host}/api/2.0/mcp/functions/{catalog}/{schema}
    The agent consumes this read-only, governed by Unity Catalog + AI Gateway.
    Returns None if the host cannot be resolved (offline / local-only).
    """
    host = get_databricks_host()
    if not host:
        return None
    return f"{host}/api/2.0/mcp/functions/{get_catalog()}/{get_schema_name()}"


def use_local_tool() -> bool:
    """True only when AKZO_LOCAL_TOOL=1 — the explicit local-dev fallback that runs the
    lookup in-process via Spark instead of consuming the managed MCP server. Off by default;
    managed-MCP consumption is the default path."""
    return os.environ.get("AKZO_LOCAL_TOOL", "").strip() in ("1", "true", "True")
