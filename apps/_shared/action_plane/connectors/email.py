"""Email connector → mock `POST /email` (body: to, subject, body)."""
from __future__ import annotations

from typing import Any

from . import _http

SYSTEM = "email"
PATH = "/email"


def send(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an action payload to the email endpoint and POST it.

    Accepts `to`/`recipient`/`customer_email`, `subject`, and `body`/`message`.
    """
    to = payload.get("to") or payload.get("recipient") or payload.get("customer_email")
    subject = payload.get("subject") or payload.get("title") or "AkzoNobel update"
    body = payload.get("body") or payload.get("message") or payload.get("summary") or ""
    body = {"to": to or "customer@akzonobel.com", "subject": subject, "body": str(body)}
    return _http.post(SYSTEM, PATH, body)
