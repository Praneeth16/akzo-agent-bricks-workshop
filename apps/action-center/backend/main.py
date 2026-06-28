"""FastAPI app for the Action Center — the exec's single screen for "agents act, governed."

Serves the JSON API under /api/* and the built React frontend (static) at /. It is a
thin read/act layer over the shared Action Plane (`action_plane`): the cross-agent
action queue, the maturity-ladder counts, the per-action audit lineage + guardrail
verdict, and the approve / reject / execute controls.

Run locally:  uvicorn main:app --reload --port 8000  (from backend/, with the CLI profile env set)
In Databricks Apps: app.yaml runs uvicorn on $DATABRICKS_APP_PORT.
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import databricks_client as dbx
from action_plane import (
    ActionNotFound,
    ActionPlane,
    IllegalTransition,
    UnroutableAction,
    evaluate,
    execute,
)

app = FastAPI(title="AkzoNobel Action Center")

# CORS so the Vite dev server (5173) can call the API during local frontend dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ap = ActionPlane()


# ---- request models -------------------------------------------------------
class RejectReq(BaseModel):
    reason: str


def end_user(request: Request) -> str:
    """The authenticated END USER from the Databricks Apps identity headers — never
    trusted from the request body. Falls back to the SDK identity (app SP) locally."""
    hdr = request.headers
    user = (hdr.get("X-Forwarded-Email")
            or hdr.get("X-Forwarded-Preferred-Username")
            or hdr.get("X-Forwarded-User"))
    if user:
        return user
    try:
        return dbx.current_user()
    except Exception:
        return "action-center@service"


# ---- API routes -----------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "identity": dbx.current_user()}


@app.get("/api/ladder")
def ladder():
    """Counts grouped by maturity level + status — feeds the LadderMeter."""
    try:
        rows = ap.ladder_counts()
    except Exception as e:
        raise HTTPException(500, f"ladder failed: {e}")
    # Roll the (level, status) rows up into one object per level 1-4.
    levels = {
        lvl: {"level": lvl, "total": 0, "by_status": {}} for lvl in (1, 2, 3, 4)
    }
    for r in rows:
        lvl = r["level"]
        bucket = levels.setdefault(lvl, {"level": lvl, "total": 0, "by_status": {}})
        bucket["by_status"][r["status"]] = r["count"]
        bucket["total"] += r["count"]
    return {"levels": [levels[lvl] for lvl in sorted(levels)]}


@app.get("/api/actions")
def list_actions(
    status: Optional[str] = None,
    level: Optional[int] = None,
    agent: Optional[str] = None,
):
    """The cross-agent action queue, newest first, optionally filtered."""
    try:
        return {"actions": ap.list(status=status, agent=agent, level=level)}
    except Exception as e:
        raise HTTPException(500, f"list failed: {e}")


@app.get("/api/actions/{action_id}")
def get_action(action_id: int):
    """The action row + ordered events (audit lineage) + the live guardrail verdict."""
    try:
        action = ap.get(action_id)
    except ActionNotFound:
        raise HTTPException(404, f"action {action_id} not found")
    except Exception as e:
        raise HTTPException(500, f"get failed: {e}")
    # The guardrail verdict is what the executor will re-check before execute —
    # surface it in the detail so the exec sees governance before acting.
    try:
        verdict = evaluate(action)
    except Exception as e:
        verdict = {"passed": False, "breaches": [f"evaluate failed: {e}"], "checks": []}
    return {"action": action, "guardrails": verdict}


@app.post("/api/actions/{action_id}/approve")
def approve(action_id: int, request: Request):
    """Approve as the authenticated user (headers, not body). Separation of duties:
    the proposer of an action may not approve it."""
    approver = end_user(request)
    try:
        action = ap.get(action_id)
        if action.get("requested_by") and action["requested_by"] == approver:
            raise HTTPException(
                403, "separation of duties: you cannot approve an action you requested"
            )
        ap.approve(action_id, approver)
    except HTTPException:
        raise
    except ActionNotFound:
        raise HTTPException(404, f"action {action_id} not found")
    except IllegalTransition as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"approve failed: {e}")
    return get_action(action_id)


@app.post("/api/actions/{action_id}/reject")
def reject(action_id: int, req: RejectReq, request: Request):
    if not req.reason.strip():
        raise HTTPException(400, "reason is required")
    try:
        ap.reject(action_id, end_user(request), req.reason)
    except ActionNotFound:
        raise HTTPException(404, f"action {action_id} not found")
    except IllegalTransition as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"reject failed: {e}")
    return get_action(action_id)


@app.post("/api/actions/{action_id}/execute")
def execute_action(action_id: int):
    """Run the approved action through its connector(s) via the L3 executor.

    The executor re-checks guardrails as a final gate; a breach escalates instead
    of acting. Returns the post-execute action + guardrail verdict.
    """
    try:
        result = execute(action_id, ap=ap)
    except ActionNotFound:
        raise HTTPException(404, f"action {action_id} not found")
    except UnroutableAction as e:
        raise HTTPException(422, str(e))
    except IllegalTransition as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"execute failed: {e}")
    # `execute` returns either an error envelope or the final action dict.
    if "error" in result:
        raise HTTPException(409, result.get("message", result["error"]))
    return get_action(action_id)


# ---- static frontend (built React) ---------------------------------------
# Mounted last so /api/* wins. Serves frontend/dist if it exists.
_HERE = os.path.dirname(os.path.abspath(__file__))
_DIST = os.path.normpath(os.path.join(_HERE, "..", "frontend", "dist"))

if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_DIST, "index.html"))

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # SPA fallback: any non-API path serves index.html.
        candidate = os.path.join(_DIST, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
