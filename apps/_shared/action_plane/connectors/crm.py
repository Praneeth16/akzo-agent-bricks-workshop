"""CRM connector → mock `POST /crm/task` (body: account, task, due)."""
from __future__ import annotations

from typing import Any

from . import _http

SYSTEM = "crm"
PATH = "/crm/task"


def send(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an action payload to the CRM-task endpoint and POST it.

    Accepts `account`/`customer`, `task`/`summary`/`subject`, and optional `due`.
    """
    account = payload.get("account") or payload.get("customer") or "Unknown account"
    task = (
        payload.get("task")
        or payload.get("summary")
        or payload.get("subject")
        or "Follow-up"
    )
    body = {"account": account, "task": str(task)}
    due = payload.get("due") or payload.get("due_date")
    if due is not None:
        body["due"] = str(due)
    return _http.post(SYSTEM, PATH, body)
