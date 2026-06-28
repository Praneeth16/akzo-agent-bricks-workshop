"""Executor — the L3 "execute externally" step of the Action Plane.

`execute(action_id)` takes an **approved** action, re-runs the guardrails as a
final gate, dispatches it to the right connector(s) for its `action_type`, and
drives the state machine `approved → executing → executed | failed | escalated`,
recording the external system ref(s) and connector detail along the way. Every
state transition appends an `action_events` row via the `ActionPlane` methods, so
the full lineage — including which connector ran, the path used, and the external
ref — is reconstructable from `action_events`.

Routing (`ROUTING`): each `action_type` maps to an ordered list of connector keys
(see `connectors.SYSTEMS`). Multiple connectors run as a sequence; the first
connector's `ref_id` becomes the action's `external_ref`, and every connector's
result is recorded.

    quote_send        → email, crm        (send the quote, then log a CRM task)
    price_change      → crm               (record the price action against the account)
    forecast_override → teams             (notify the planning channel)
    scm_reorder       → erp_po            (raise the purchase order)
    scm_reroute       → teams, ticket     (alert ops, then open a tracking ticket)
    crm_task          → crm               (create the CRM task)
    escalation        → ticket            (open a ServiceNow ticket)
"""
from __future__ import annotations

from typing import Any

from . import connectors, guardrails
from .model import APPROVED, ActionPlane

# action_type → ordered connector keys (keys of connectors.SYSTEMS).
ROUTING: dict[str, list[str]] = {
    "quote_send": ["email", "crm"],
    "price_change": ["crm"],
    "forecast_override": ["teams"],
    "scm_reorder": ["erp_po"],
    "scm_reroute": ["teams", "ticket"],
    "crm_task": ["crm"],
    "escalation": ["ticket"],
}


class UnroutableAction(Exception):
    """Raised when an action_type has no connector route."""


def _payload(action: dict[str, Any]) -> dict[str, Any]:
    import json
    raw = action.get("payload")
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}
    return dict(raw)


def execute(action_id: int, ap: ActionPlane | None = None) -> dict[str, Any]:
    """Execute an approved action through its connector(s).

    Returns the final action dict (with `events`). On a guardrail breach the
    action is escalated and the escalated action is returned (no external call is
    made). On a connector exception the action is marked failed.
    """
    ap = ap or ActionPlane()
    action = ap.get(action_id)

    # Gate 1: only an approved action may execute.
    if action["status"] != APPROVED:
        return {
            "error": "not_approved",
            "message": f"action {action_id} is '{action['status']}', not 'approved'",
            "action": action,
        }

    action_type = action["action_type"]
    route = ROUTING.get(action_type)
    if not route:
        raise UnroutableAction(
            f"no connector route for action_type '{action_type}'"
        )

    # Gate 2: re-run guardrails as the final pre-execute check.
    verdict = guardrails.evaluate(action)
    if not verdict["passed"]:
        reason = "; ".join(verdict["breaches"]) or "guardrail breach"
        ap.escalate(action_id, reason=reason, actor="executor")
        return ap.get(action_id)

    payload = _payload(action)
    ap.mark_executing(action_id, actor="executor")

    # Run the route connector-by-connector so a mid-sequence failure does not erase
    # the record of connectors that already fired (their side effects are real and
    # irreversible — an email is sent, a PO is raised).
    results: list[dict[str, Any]] = []
    for key in route:
        module = connectors.SYSTEMS[key]
        try:
            result = module.send(payload)
        except Exception as exc:
            completed_refs = [r["ref_id"] for r in results]
            partial = bool(results)  # at least one connector already had an effect
            ap._event(
                action_id,
                "partial_failure" if partial else "connector_failed",
                f"connector:{key}",
                {"failed_connector": key, "error": str(exc),
                 "completed_refs": completed_refs},
            )
            ap.mark_failed(
                action_id,
                result={
                    "error": str(exc),
                    "failed_connector": key,
                    "completed_connectors": results,   # full record of what DID fire
                    "completed_refs": completed_refs,
                    "needs_reconciliation": partial,    # operator must reconcile side effects
                },
                actor="executor",
            )
            # Record the first real external ref so the irreversible side effect is
            # visible on the action row, not only buried in result.
            updated = ap.get(action_id)
            return updated
        results.append(result)
        ap._event(
            action_id,
            "connector",
            f"connector:{key}",
            {"system": result["system"], "external_ref": result["ref_id"],
             "via": result.get("via"), "raw": result["raw"]},
        )

    external_ref = results[0]["ref_id"] if results else None
    ap.mark_executed(
        action_id,
        result={"connectors": results, "route": route},
        external_ref=external_ref,
        actor="executor",
    )
    return ap.get(action_id)
