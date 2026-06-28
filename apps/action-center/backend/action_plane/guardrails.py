"""Guardrail engine — policy checks run *before* an action executes.

`evaluate(action)` checks a proposed action against its row in `action_policies`
and returns a structured verdict. A breach does not mutate anything; the caller
(executor / autonomous loop) is responsible for `escalate()`-ing on a breach.

Policy columns (per PLAN §5 U1):
  max_discount_pct  — reject if payload.discount_pct exceeds this
  max_spend_eur     — reject if payload.spend_eur (or amount_eur) exceeds this
  allowed_regions   — text[]; reject if action.region not in this set
  requires_approval — informational: this action type may not auto-approve at L4

The action's `payload` is a JSON object; the checks read the relevant numeric
fields from it when present. Missing fields are treated as "nothing to check"
for that rule (a check with applicable=False), never as a breach.
"""
from __future__ import annotations

import json
from typing import Any

import lakebase


def _payload(action: dict[str, Any]) -> dict[str, Any]:
    raw = action.get("payload")
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}
    return dict(raw)


def _policy(action_type: str) -> dict[str, Any] | None:
    rows = lakebase.query(
        "SELECT * FROM action_policies WHERE action_type = %s", (action_type,)
    )
    return rows[0] if rows else None


def evaluate(action: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an action against its policy.

    Returns {"passed": bool, "breaches": [str, ...], "checks": [dict, ...]}.
    Each check is {"rule", "applicable", "passed", "limit", "value", "detail"}.
    """
    action_type = action.get("action_type")
    region = action.get("region")
    payload = _payload(action)

    checks: list[dict[str, Any]] = []
    breaches: list[str] = []

    policy = _policy(action_type)

    # Rule 0: the action type must itself be a known/allowed action type.
    allowed = policy is not None
    checks.append({
        "rule": "action_type_allowed",
        "applicable": True,
        "passed": allowed,
        "limit": None,
        "value": action_type,
        "detail": "known action type" if allowed
                  else f"no policy for action_type '{action_type}'",
    })
    if not allowed:
        breaches.append(f"action_type '{action_type}' is not allowed (no policy)")
        return {"passed": False, "breaches": breaches, "checks": checks}

    # Rule 1: discount cap.
    max_discount = policy.get("max_discount_pct")
    discount = payload.get("discount_pct")
    if max_discount is not None and discount is not None:
        ok = float(discount) <= float(max_discount)
        checks.append({
            "rule": "max_discount_pct", "applicable": True, "passed": ok,
            "limit": float(max_discount), "value": float(discount),
            "detail": f"discount {discount}% vs cap {max_discount}%",
        })
        if not ok:
            breaches.append(f"discount {discount}% exceeds cap {max_discount}%")
    else:
        checks.append({
            "rule": "max_discount_pct", "applicable": False, "passed": True,
            "limit": (float(max_discount) if max_discount is not None else None),
            "value": (float(discount) if discount is not None else None),
            "detail": "no discount on this action / no cap configured",
        })

    # Rule 2: spend cap. Accept either `spend_eur` or `amount_eur` — take the first
    # NON-NULL of the two (a present-but-null `spend_eur` must not shadow a real
    # `amount_eur`, which would let a large spend bypass the cap).
    max_spend = policy.get("max_spend_eur")
    spend = next((v for v in (payload.get("spend_eur"), payload.get("amount_eur"))
                  if v is not None), None)
    if max_spend is not None and spend is not None:
        # A non-numeric spend on a spend-capped action is a breach, not a skip.
        try:
            spend_val = float(spend)
        except (TypeError, ValueError):
            checks.append({
                "rule": "max_spend_eur", "applicable": True, "passed": False,
                "limit": float(max_spend), "value": None,
                "detail": f"spend value {spend!r} is not numeric",
            })
            breaches.append(f"spend value {spend!r} is not a valid number")
            spend_val = None
        if spend_val is not None:
            ok = spend_val <= float(max_spend)
            checks.append({
                "rule": "max_spend_eur", "applicable": True, "passed": ok,
                "limit": float(max_spend), "value": spend_val,
                "detail": f"spend EUR {spend_val} vs cap {max_spend}",
            })
            if not ok:
                breaches.append(f"spend EUR {spend_val} exceeds cap EUR {max_spend}")
    else:
        checks.append({
            "rule": "max_spend_eur", "applicable": False, "passed": True,
            "limit": (float(max_spend) if max_spend is not None else None),
            "value": (float(spend) if spend is not None else None),
            "detail": "no spend on this action / no cap configured",
        })

    # Rule 3: region scope.
    allowed_regions = policy.get("allowed_regions")
    if allowed_regions:
        ok = region in allowed_regions
        checks.append({
            "rule": "allowed_regions", "applicable": True, "passed": ok,
            "limit": list(allowed_regions), "value": region,
            "detail": f"region '{region}' "
                      + ("in scope" if ok else "out of scope"),
        })
        if not ok:
            breaches.append(
                f"region '{region}' not in allowed regions {list(allowed_regions)}"
            )
    else:
        checks.append({
            "rule": "allowed_regions", "applicable": False, "passed": True,
            "limit": None, "value": region,
            "detail": "no region restriction configured",
        })

    # Rule 4: requires_approval — informational for L4 auto-approve decisions.
    requires_approval = bool(policy.get("requires_approval"))
    checks.append({
        "rule": "requires_approval", "applicable": True, "passed": True,
        "limit": requires_approval, "value": requires_approval,
        "detail": ("human approval required before execute"
                   if requires_approval
                   else "may auto-approve within policy (L4)"),
    })

    return {"passed": len(breaches) == 0, "breaches": breaches, "checks": checks}
