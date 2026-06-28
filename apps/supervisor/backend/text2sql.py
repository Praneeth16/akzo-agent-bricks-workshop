"""Text2SQL — the SHARED natural-language-to-governed-SQL module.

Takes a domain's Genie space instructions (a `genie/<domain>_space.md` file) as
the system prompt, asks the chat model to turn an NL question into a single Spark
SQL statement, executes it on the governed warehouse, and returns
{sql, columns, rows}. The Supervisor + Finance apps reuse this by pointing
`genie_instructions_path` at their own domain's space file.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

import databricks_client as dbx

# Default to the finance space; resolved relative to this file so it works from
# any cwd (local dev or the Apps runtime).
# Ship a self-contained copy of the domain Genie instructions inside backend/ so the
# app works when deployed standalone. Falls back to the repo genie/ dir if the bundled
# copy is absent. Override with GENIE_INSTRUCTIONS_PATH.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(_HERE, "finance_space.md")
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "genie", "finance_space.md"))
_DEFAULT_GENIE = os.environ.get(
    "GENIE_INSTRUCTIONS_PATH",
    _BUNDLED if os.path.isfile(_BUNDLED) else _REPO,
)

_SYSTEM_PREAMBLE = """You are a Spark SQL generator for a governed Databricks lakehouse.
Use ONLY the tables, columns, and business definitions described below. Never invent columns.
Return a SINGLE Spark SQL statement that answers the question — no commentary, no markdown
fences, no trailing semicolon explanation. If the question cannot be answered from these tables,
return exactly: SELECT 'out_of_scope' AS error.

Domain instructions:
---
{instructions}
---
Output ONLY the SQL.
"""


@lru_cache(maxsize=8)
def _instructions(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def _strip_sql(text: str) -> str:
    """Pull a clean SQL statement out of a model response (handles code fences)."""
    t = text.strip()
    fence = re.search(r"```(?:sql)?\s*(.+?)```", t, re.DOTALL | re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    return t.rstrip(";").strip()


def generate_sql(question: str, genie_instructions_path: str | None = None) -> str:
    """NL question -> Spark SQL string, grounded in the domain Genie instructions."""
    path = genie_instructions_path or _DEFAULT_GENIE
    system = _SYSTEM_PREAMBLE.format(instructions=_instructions(path))
    raw = dbx.chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        max_tokens=1800,
    )
    return _strip_sql(raw)


def ask(question: str, genie_instructions_path: str | None = None) -> dict:
    """NL question -> {sql, columns, rows, row_count}. The full text2sql round trip."""
    sql = generate_sql(question, genie_instructions_path)
    result = dbx.run_sql(sql)
    return {"sql": sql, **result}
