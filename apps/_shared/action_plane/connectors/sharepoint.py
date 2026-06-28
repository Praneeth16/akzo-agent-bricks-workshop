"""SharePoint connector → mock `POST /sharepoint/upload` (body: path, title)."""
from __future__ import annotations

from typing import Any

from . import _http

SYSTEM = "sharepoint"
PATH = "/sharepoint/upload"


def send(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an action payload to the SharePoint-upload endpoint and POST it.

    Accepts `path`/`location` and `title`/`subject`/`document`.
    """
    path = payload.get("path") or payload.get("location") or "/Shared Documents"
    title = (
        payload.get("title")
        or payload.get("subject")
        or payload.get("document")
        or "AkzoNobel document"
    )
    return _http.post(SYSTEM, PATH, {"path": path, "title": str(title)})
