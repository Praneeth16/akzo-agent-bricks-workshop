"""Teams connector → mock `POST /teams` (body: channel, message)."""
from __future__ import annotations

from typing import Any

from . import _http

SYSTEM = "teams"
PATH = "/teams"


def send(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an action payload to the Teams endpoint and POST it.

    Accepts `channel`, and `message`/`body`/`summary` as the post text.
    """
    channel = payload.get("channel") or payload.get("team") or "SCM Ops"
    message = (
        payload.get("message")
        or payload.get("body")
        or payload.get("summary")
        or payload.get("subject")
        or ""
    )
    return _http.post(SYSTEM, PATH, {"channel": channel, "message": str(message)})
