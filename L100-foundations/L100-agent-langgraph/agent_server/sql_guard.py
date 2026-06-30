"""Read-only SQL guard for the local-dev lookup tool.

The managed-MCP path is governed by Unity Catalog and needs no client-side guard. The
local-dev Spark fallback runs model-generated SQL in-process, so it must prove, before
executing, that the SQL is a single read-only SELECT confined to the finance schema. We
parse with sqlglot (not a prefix check) so things like ``WITH x AS (...) INSERT ...``,
multiple statements separated by ``;``, or any write are rejected.
"""

from typing import Set

import sqlglot
from sqlglot import exp

# Statement node types that read but never mutate. Anything else (Insert, Update, Delete,
# Merge, Create, Drop, Alter, Command/SET/USE, etc.) is rejected.
_READ_ONLY_ROOTS = (exp.Select, exp.Union, exp.Subquery)


def _table_refs(tree: exp.Expression) -> Set[str]:
    """Collect every base-table reference as a lowercased ``db.table`` or ``table`` string.

    CTE names (defined by ``WITH``) are excluded — they are not physical tables.
    """
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    refs: Set[str] = set()
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in cte_names and not table.db:
            continue  # reference to a CTE, not a physical table
        db = table.db.lower()
        refs.add(f"{db}.{name}" if db else name)
    return refs


def assert_read_only_select(sql: str, finance_schema: str) -> None:
    """Raise ValueError unless ``sql`` is exactly ONE read-only SELECT whose every physical
    table reference lives in ``finance_schema`` (a ``catalog.schema`` string).

    Enforces:
      * exactly one statement (no ``;``-separated multi-statement, no trailing DDL/DML);
      * the root is a SELECT / UNION / parenthesised SELECT (CTEs ending in SELECT are OK);
      * no write/DDL nodes anywhere in the tree;
      * every base table is in ``<schema>`` (the ``schema`` part of catalog.schema), so the
        model cannot read outside akzo_finance.
    """
    try:
        statements = sqlglot.parse(sql, read="spark")
    except Exception as e:  # noqa: BLE001 — surface a parse failure as a guard rejection
        raise ValueError(f"could not parse SQL: {str(e)[:120]}")

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise ValueError(f"expected exactly one statement, got {len(statements)}")

    tree = statements[0]
    if not isinstance(tree, _READ_ONLY_ROOTS):
        raise ValueError(f"only SELECT statements are allowed, got {type(tree).__name__}")

    # Defense in depth: reject any mutating/DDL node anywhere in the parsed tree.
    forbidden = (
        exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop,
        exp.Alter, exp.Command, exp.Set, exp.Use,
    )
    if any(tree.find(node) for node in forbidden):
        raise ValueError("statement contains a write or DDL operation")

    # P2: confine reads to the finance schema. finance_schema is "catalog.schema"; UC
    # functions/tables are referenced as schema.table in SQL, so compare on the schema part.
    schema = finance_schema.split(".")[-1].lower()
    for ref in _table_refs(tree):
        ref_db = ref.split(".")[0] if "." in ref else ""
        if ref_db != schema:
            raise ValueError(
                f"table reference {ref!r} is outside the {schema} schema "
                f"(qualify tables as {schema}.<table>)"
            )
