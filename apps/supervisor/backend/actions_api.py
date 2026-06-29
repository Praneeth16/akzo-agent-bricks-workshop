"""Shared FastAPI routes that wire an app to the Action Plane.

Reused verbatim by every agent app (supervisor / finance-copilot / quote-agent):
each app mounts this router under `/api` so it can drive the full
Act → Approve → Execute → Confirm loop without leaving the app, all through the
one governed Action Plane (`action_plane`).

    from actions_api import build_actions_router
    app.include_router(build_actions_router("supervisor-agent"))

`agent_name` is the app's stable identity stamped on every action it proposes
(also used to scope `GET /api/actions` to this app's own queue). Keep it thin —
all real logic lives in `action_plane`.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import databricks_client as dbx
from action_plane import (
    ActionNotFound,
    ActionPlane,
    IllegalTransition,
    evaluate,
    execute,
)


class ActReq(BaseModel):
    action_type: str
    subject: str
    payload: dict[str, Any]
    region: str
    level: int = 2


def _end_user(request: Request, agent_name: str) -> str:
    """The authenticated END USER, taken from the Databricks Apps identity headers
    (NEVER from the request body — body identity is untrusted). Databricks Apps
    forwards the signed-in user as `X-Forwarded-Email` / `-Preferred-Username`.
    Falls back to the SDK identity (the app SP) and finally a service tag for local
    dev where the headers are absent."""
    hdr = request.headers
    user = (hdr.get("X-Forwarded-Email")
            or hdr.get("X-Forwarded-Preferred-Username")
            or hdr.get("X-Forwarded-User"))
    if user:
        return user
    try:
        return dbx.current_user()
    except Exception:
        return f"{agent_name}@service"


def build_actions_router(agent_name: str) -> APIRouter:
    """Return an APIRouter exposing the Act→Approve→Execute loop for `agent_name`."""
    router = APIRouter(prefix="/api")
    ap = ActionPlane()

    @router.post("/act")
    def act(req: ActReq, request: Request):
        """Stage an action through the Action Plane + return its guardrail verdict."""
        try:
            # The AGENT proposes the action (it advised it); the human then APPROVES it. Attributing
            # the proposal to the agent (not the signed-in user) is the correct separation of duties:
            # proposer (agent) != approver (human), so a single signed-in user can approve in the UI
            # without a second identity or an admin panel.
            action = ap.propose(
                agent=agent_name,
                action_type=req.action_type,
                subject=req.subject,
                payload=req.payload,
                region=req.region,
                requested_by=agent_name,
                level=req.level,
            )
            verdict = evaluate(action)
            return {"action": action, "guardrail": verdict}
        except Exception as e:
            raise HTTPException(500, f"propose failed: {e}")

    @router.get("/actions")
    def actions(status: Optional[str] = None):
        """List this agent's actions (newest first), optionally filtered by status."""
        try:
            return {"actions": ap.list(status=status, agent=agent_name)}
        except Exception as e:
            raise HTTPException(500, f"list actions failed: {e}")

    @router.get("/actions/{action_id}")
    def get_action(action_id: int):
        """Return one action with its full event lineage + guardrail verdict."""
        try:
            action = ap.get(action_id)
            return {"action": action, "guardrail": evaluate(action)}
        except ActionNotFound as e:
            raise HTTPException(404, str(e))
        except Exception as e:
            raise HTTPException(500, f"get action failed: {e}")

    @router.post("/actions/{action_id}/approve")
    def approve(action_id: int, request: Request):
        """proposed|escalated → approved, then return the action + lineage.

        The approver is the authenticated user (headers), never the request body.
        Separation of duties: the proposer of an action may not approve it."""
        try:
            approver = _end_user(request, agent_name)
            action = ap.get(action_id)
            if action.get("requested_by") and action["requested_by"] == approver:
                raise HTTPException(
                    403, "separation of duties: you cannot approve an action you requested"
                )
            ap.approve(action_id, approver=approver)
            return {"action": ap.get(action_id)}
        except HTTPException:
            raise
        except ActionNotFound as e:
            raise HTTPException(404, str(e))
        except IllegalTransition as e:
            raise HTTPException(409, str(e))
        except Exception as e:
            raise HTTPException(500, f"approve failed: {e}")

    @router.post("/actions/{action_id}/execute")
    def execute_action(action_id: int):
        """Execute an approved action through its connector(s); return final action."""
        try:
            result = execute(action_id, ap=ap)
            if isinstance(result, dict) and result.get("error") == "not_approved":
                raise HTTPException(409, result["message"])
            return {"action": result}
        except HTTPException:
            raise
        except ActionNotFound as e:
            raise HTTPException(404, str(e))
        except Exception as e:
            raise HTTPException(500, f"execute failed: {e}")

    return router
