"""Ticket connector → mock `POST /servicenow/ticket` (body: summary, priority)."""
from __future__ import annotations

from typing import Any

from . import _http

SYSTEM = "ticket"
PATH = "/servicenow/ticket"


def send(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an action payload to the ServiceNow-ticket endpoint and POST it.

    Accepts `summary`/`subject`/`message` and optional `priority` (default P3).
    """
    summary = (
        payload.get("summary")
        or payload.get("subject")
        or payload.get("message")
        or payload.get("reason")
        or "Agent-raised ticket"
    )
    priority = payload.get("priority") or "P3"
    return _http.post(
        SYSTEM, PATH, {"summary": str(summary), "priority": str(priority)}
    )
