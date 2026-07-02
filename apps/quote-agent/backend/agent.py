"""The Pricing / Quote agent workflow — read -> reason -> act -> write -> approve.

This is the quote-SPECIFIC layer. It composes the shared modules:
  - text2sql / databricks_client  -> governed reads (parse, price)
  - lakebase                      -> the act/write/approve plane

Each step returns a trace dict (SQL + data sources + the Lakebase write) so the
frontend's "How this works" panel can show exactly what happened.
"""
from __future__ import annotations

import json
import os
import re

import databricks_client as dbx
import lakebase as lb
from action_plane import ActionPlane, evaluate, execute

CATALOG = os.environ.get("AKZO_CATALOG", "<catalog>")
SCHEMA = os.environ.get("AKZO_SCHEMA", "<schema>")
FINANCE = f"{CATALOG}.{SCHEMA}"

# Guardrail: flag a draft for escalation if its discount exceeds this, or if its
# post-discount margin % falls below this floor.
MAX_DISCOUNT_PCT = 15.0
MARGIN_FLOOR_PCT = 25.0

SERVICE_IDENTITY = "quote-agent@service"  # the app/service write identity in the audit trail


def _sql_str(s: str) -> str:
    """Escape a string for embedding in a SQL literal."""
    return s.replace("'", "''")


# ---------------------------------------------------------------------------
# STEP 1 — PARSE: ai_extract over the inbound RFQ text (governed, on warehouse)
# ---------------------------------------------------------------------------
def parse_rfq(rfq_text: str) -> dict:
    """Use ai_extract on the SQL warehouse to pull structured fields from a free-text RFQ.

    Returns {fields, matched, sql, data_source}. `fields` is the raw extraction;
    `matched` resolves the free-text product against the products table (SKU lookup).
    """
    labels = ["customer", "product", "region", "quantity_litres", "requested_terms"]
    extract_sql = (
        f"SELECT ai_extract('{_sql_str(rfq_text)}', "
        f"array('customer','product','region','quantity_litres','requested_terms')) AS extracted"
    )
    res = dbx.run_sql(extract_sql)
    raw = res["rows"][0]["extracted"] if res["rows"] else "{}"
    fields = json.loads(raw) if isinstance(raw, str) else (raw or {})

    # Normalize region to the known set.
    region = (fields.get("region") or "").strip()
    region_norm = _normalize_region(region)

    # Resolve the free-text product to a real SKU via a fuzzy match on product_name,
    # preferring the extracted region. This is a governed read against products.
    product_text = (fields.get("product") or "").strip()
    matched, match_sql = _match_product(product_text, region_norm)

    return {
        "fields": {
            "customer": fields.get("customer"),
            "product": product_text,
            "region": region_norm or region,
            "quantity_litres": _to_int(fields.get("quantity_litres")),
            "requested_terms": fields.get("requested_terms"),
        },
        "matched": matched,
        "trace": {
            "step": "parse",
            "data_source": f"ai_extract over RFQ text -> matched against {FINANCE}.products",
            "sql": [extract_sql, match_sql],
        },
    }


def _normalize_region(region: str) -> str:
    r = (region or "").lower()
    if any(k in r for k in ("emea", "europe", "rotterdam", "netherlands", "uk", "germany")):
        return "EMEA"
    if any(k in r for k in ("america", "us", "usa", "latam", "canada")):
        return "Americas"
    if any(k in r for k in ("apac", "asia", "australia", "pacific")):
        return "APAC"
    if "china" in r:
        return "China"
    return region or ""


def _to_int(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    digits = re.sub(r"[^0-9]", "", str(v))
    return int(digits) if digits else None


def _match_product(product_text: str, region: str) -> tuple[dict | None, str]:
    """Fuzzy-match the free-text product to a products SKU. Token-overlap scored in SQL."""
    if not product_text:
        return None, "-- no product text to match"
    tokens = [t for t in re.findall(r"[a-zA-Z]+", product_text.lower()) if len(t) > 2]
    if not tokens:
        return None, "-- no usable product tokens"
    score_terms = " + ".join(
        f"(CASE WHEN lower(product_name) LIKE '%{_sql_str(t)}%' THEN 1 ELSE 0 END)" for t in tokens
    )

    def _build(region_scope: str) -> str:
        # Scope to the requested region first (an EMEA RFQ should match an EMEA SKU);
        # within scope, rank by how many product-name tokens hit.
        where = f"({score_terms}) > 0"
        if region_scope:
            where += f" AND region = '{_sql_str(region_scope)}'"
        return (
            f"SELECT sku, product_name, product_line, region, currency, "
            f"list_price_eur, standard_cost_eur, ({score_terms}) AS name_score "
            f"FROM {FINANCE}.products WHERE {where} "
            f"ORDER BY name_score DESC LIMIT 1"
        )

    sql = _build(region)
    res = dbx.run_sql(sql)
    if not res["rows"] and region:
        # No SKU in the requested region matched the product text; fall back to any region.
        sql = _build("")
        res = dbx.run_sql(sql)
    if not res["rows"]:
        return None, sql
    row = res["rows"][0]
    return {
        "sku": row["sku"],
        "product_name": row["product_name"],
        "product_line": row["product_line"],
        "region": row["region"],
        "currency": row["currency"],
        "list_price_eur": float(row["list_price_eur"]),
        "standard_cost_eur": float(row["standard_cost_eur"]),
    }, sql


# ---------------------------------------------------------------------------
# STEP 2 — PRICE: governed lookup of list price, cost, recent realized margin
# ---------------------------------------------------------------------------
def price(sku: str, region: str | None = None) -> dict:
    """Pull pricing basis for a SKU: list price + standard cost from products, and the
    most-recent realized margin from margin_actuals. Returns the suggested (list) price
    and implied unit margin."""
    region_filter = f" AND region = '{_sql_str(region)}'" if region else ""
    products_sql = (
        f"SELECT sku, product_name, region, currency, list_price_eur, standard_cost_eur, "
        f"ROUND(list_price_eur - standard_cost_eur, 2) AS unit_margin_eur, "
        f"ROUND((list_price_eur - standard_cost_eur) / list_price_eur * 100, 1) AS unit_margin_pct "
        f"FROM {FINANCE}.products WHERE sku = '{_sql_str(sku)}'{region_filter} LIMIT 1"
    )
    prod = dbx.run_sql(products_sql)
    if not prod["rows"]:
        raise ValueError(f"SKU {sku} not found")
    p = prod["rows"][0]

    margin_sql = (
        f"SELECT month, units, revenue_eur, gross_margin_eur, "
        f"ROUND(gross_margin_pct * 100, 1) AS realized_margin_pct, "
        f"ROUND(revenue_eur / NULLIF(units,0), 2) AS realized_price_eur "
        f"FROM {FINANCE}.margin_actuals "
        f"WHERE sku = '{_sql_str(sku)}'{region_filter} "
        f"ORDER BY month DESC LIMIT 1"
    )
    margin = dbx.run_sql(margin_sql)
    recent = margin["rows"][0] if margin["rows"] else None

    return {
        "sku": p["sku"],
        "product_name": p["product_name"],
        "region": p["region"],
        "currency": p["currency"],
        "list_price_eur": float(p["list_price_eur"]),
        "standard_cost_eur": float(p["standard_cost_eur"]),
        "unit_margin_eur": float(p["unit_margin_eur"]),
        "unit_margin_pct": float(p["unit_margin_pct"]),
        "recent_realized": {
            "month": str(recent["month"]) if recent else None,
            "realized_price_eur": float(recent["realized_price_eur"]) if recent and recent["realized_price_eur"] is not None else None,
            "realized_margin_pct": float(recent["realized_margin_pct"]) if recent and recent["realized_margin_pct"] is not None else None,
        } if recent else None,
        "trace": {
            "step": "price",
            "data_source": f"{FINANCE}.products (list/cost) + {FINANCE}.margin_actuals (recent realized margin)",
            "sql": [products_sql, margin_sql],
        },
    }


# ---------------------------------------------------------------------------
# STEP 3+4 — DRAFT + GUARDRAIL: compute the quote line and check the discount
# ---------------------------------------------------------------------------
def draft_quote(list_price_eur: float, standard_cost_eur: float, quantity_units: int,
                discount_pct: float) -> dict:
    """Compute the quote line items, total, post-discount margin, and run the guardrail check."""
    net_unit_price = round(list_price_eur * (1 - discount_pct / 100.0), 2)
    extended_price = round(net_unit_price * quantity_units, 2)
    unit_margin = round(net_unit_price - standard_cost_eur, 2)
    margin_pct = round((unit_margin / net_unit_price) * 100, 1) if net_unit_price else 0.0
    total_margin = round(unit_margin * quantity_units, 2)
    total_cost = round(standard_cost_eur * quantity_units, 2)

    flags = []
    if discount_pct > MAX_DISCOUNT_PCT:
        flags.append(f"Discount {discount_pct}% exceeds the {MAX_DISCOUNT_PCT}% policy limit.")
    if margin_pct < MARGIN_FLOOR_PCT:
        flags.append(f"Post-discount margin {margin_pct}% is below the {MARGIN_FLOOR_PCT}% floor.")

    return {
        "quantity_units": quantity_units,
        "list_price_eur": list_price_eur,
        "discount_pct": discount_pct,
        "net_unit_price_eur": net_unit_price,
        "extended_price_eur": extended_price,
        "standard_cost_eur": standard_cost_eur,
        "total_cost_eur": total_cost,
        "unit_margin_eur": unit_margin,
        "margin_pct": margin_pct,
        "total_margin_eur": total_margin,
        "guardrail_flags": flags,
        "requires_escalation": bool(flags),
    }


# ---------------------------------------------------------------------------
# STEP 5 — WRITE: stage the quote to Lakebase as pending + open an approval row
# ---------------------------------------------------------------------------
def create_quote(account_id: str, sku: str, region: str, quantity_units: int,
                 list_price_eur: float, quoted_price_eur: float, discount_pct: float,
                 rationale: str) -> dict:
    """ACTION: write a pending quote row + a pending quote_approvals row, under the
    app/service identity. Returns {quote_id, status, trace}."""
    row = lb.execute(
        """INSERT INTO quotes
           (account_id, sku, region, quantity_units, list_price_eur,
            quoted_price_eur, discount_pct, rationale, status, created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)
           RETURNING quote_id, status, created_at""",
        (account_id, sku, region, quantity_units, list_price_eur,
         quoted_price_eur, discount_pct, rationale, SERVICE_IDENTITY),
        returning=True,
    )
    quote_id = row["quote_id"]
    lb.execute(
        """INSERT INTO quote_approvals (quote_id, decision) VALUES (%s, 'pending')""",
        (quote_id,),
    )
    return {
        "quote_id": quote_id,
        "status": row["status"],
        "created_at": str(row["created_at"]),
        "trace": {
            "step": "write",
            "data_source": f"Lakebase {lb.PG_SCHEMA}.quotes + {lb.PG_SCHEMA}.quote_approvals (pending) via {SERVICE_IDENTITY}",
            "sql": [
                "INSERT INTO akzo.quotes (... status='pending', created_by='quote-agent@service') RETURNING quote_id",
                "INSERT INTO akzo.quote_approvals (quote_id, decision='pending')",
            ],
        },
    }


# ---------------------------------------------------------------------------
# APPROVAL QUEUE — list pending, and the approve/reject decision
# ---------------------------------------------------------------------------
def list_approvals(status: str = "pending") -> list[dict]:
    """List quotes joined to their approval ledger row, newest first."""
    rows = lb.query(
        """SELECT q.quote_id, q.account_id, q.sku, q.region, q.quantity_units,
                  q.list_price_eur, q.quoted_price_eur, q.discount_pct, q.rationale,
                  q.status, q.created_by, q.created_at,
                  a.decision, a.approver, a.comment, a.decided_at
           FROM quotes q
           LEFT JOIN quote_approvals a ON a.quote_id = q.quote_id
           WHERE q.status = %s
           ORDER BY q.quote_id DESC LIMIT 100""",
        (status,),
    )
    for r in rows:
        for k in ("list_price_eur", "quoted_price_eur", "discount_pct"):
            if r.get(k) is not None:
                r[k] = float(r[k])
        r["created_at"] = str(r["created_at"]) if r.get("created_at") else None
        r["decided_at"] = str(r["decided_at"]) if r.get("decided_at") else None
    return rows


def decide(quote_id: int, decision: str, approver: str, comment: str | None = None) -> dict:
    """APPROVAL FLOW: flip a pending quote to approved/rejected with audit. Guarded by
    status='pending' so a decision can't be re-applied."""
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")

    quote = lb.execute(
        """UPDATE quotes SET status = %s
           WHERE quote_id = %s AND status = 'pending'
           RETURNING quote_id, status""",
        (decision, quote_id),
        returning=True,
    )
    if quote is None:
        raise ValueError(f"Quote {quote_id} is not pending (already decided or missing)")

    lb.execute(
        """UPDATE quote_approvals
           SET decision = %s, approver = %s, comment = %s, decided_at = now()
           WHERE quote_id = %s""",
        (decision, approver, comment, quote_id),
    )

    # ACTION PLANE: on approval, the quote doesn't just flip to 'approved' in the
    # ledger — it actually GOES OUT. Stage + auto-approve + execute a quote_send
    # action through the governed Action Plane (email the customer + log a CRM
    # task), so the approval has a real external effect with an auditable ref.
    dispatched = None
    if decision == "approved":
        dispatched = dispatch_quote_send(quote_id, approver)

    return {
        "quote_id": quote_id,
        "status": quote["status"],
        "approver": approver,
        "dispatched": dispatched,
        "trace": {
            "step": "approve",
            "data_source": f"Lakebase {lb.PG_SCHEMA}.quotes + {lb.PG_SCHEMA}.quote_approvals (audit: approver, decided_at)",
            "sql": [
                f"UPDATE akzo.quotes SET status='{decision}' WHERE quote_id={quote_id} AND status='pending'",
                f"UPDATE akzo.quote_approvals SET decision='{decision}', approver=..., decided_at=now() WHERE quote_id={quote_id}",
            ],
        },
    }


# ---------------------------------------------------------------------------
# ACTION PLANE — on approval, the quote actually GOES OUT (email + CRM task)
# ---------------------------------------------------------------------------
def dispatch_quote_send(quote_id: int, approver: str) -> dict:
    """Stage + execute a governed `quote_send` action for an approved quote.

    Reads the quote row, builds the customer email + CRM-task payload, proposes
    the action through the Action Plane, auto-approves it (the human already
    approved the quote upstream), then executes it via the connectors so the
    quote really 'goes out' (mock email + CRM task) with an auditable external
    ref. Returns {action_id, status, external_ref, guardrail, result} or, on a
    failure, {error}. Never raises — a dispatch hiccup must not undo the approval.
    """
    try:
        rows = lb.query(
            """SELECT quote_id, account_id, sku, region, quantity_units,
                      quoted_price_eur, discount_pct
               FROM quotes WHERE quote_id = %s""",
            (quote_id,),
        )
        if not rows:
            return {"error": f"quote {quote_id} not found for dispatch"}
        q = rows[0]
        qty = int(q["quantity_units"])
        unit = float(q["quoted_price_eur"])
        discount = float(q["discount_pct"])
        extended = round(unit * qty, 2)
        subject = f"Quote #{quote_id} — {q['sku']} for {q['account_id']}"
        payload = {
            "customer": q["account_id"],
            "account": q["account_id"],
            "subject": subject,
            "body": (
                f"Dear {q['account_id']},\n\n"
                f"Please find your quote for {qty} units of {q['sku']} "
                f"({q['region']}) at EUR {unit}/unit ({discount}% off), "
                f"total EUR {extended}. This quote was approved by {approver}.\n\n"
                f"Kind regards,\nAkzoNobel Pricing"
            ),
            "task": f"Quote #{quote_id} sent to {q['account_id']} — follow up on acceptance.",
            "discount_pct": discount,
            "amount_eur": extended,
        }

        ap = ActionPlane()
        action = ap.propose(
            agent="quote-agent",
            action_type="quote_send",
            subject=subject,
            payload=payload,
            region=q["region"] or "",
            requested_by=approver,
            level=2,
        )
        verdict = evaluate(action)
        action_id = action["id"]

        # The human approved the quote upstream → auto-approve the send action,
        # then execute. The executor re-runs guardrails as the final gate and
        # escalates instead of sending if they breach.
        ap.approve(action_id, approver=approver)
        final = execute(action_id, ap=ap)

        return {
            "action_id": action_id,
            "status": final.get("status"),
            "external_ref": final.get("external_ref"),
            "guardrail": verdict,
            "result": final.get("result"),
        }
    except Exception as e:
        return {"error": f"quote_send dispatch failed: {e}"}
