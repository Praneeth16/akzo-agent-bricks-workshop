"""The Finance controlling copilot workflow — read -> reason -> recommend -> save.

This is the finance-SPECIFIC layer. It composes the shared modules:
  - text2sql / databricks_client  -> governed NL->SQL reads over akzo_finance
  - databricks_client.chat        -> the LLM reasoning step (number -> narrative + action)
  - lakebase                      -> the save/write-back plane (saved analyses)

It has two entry points:
  - ask(question)                 -> text2SQL answer + a grounded controller-ready narrative.
  - variance(product_line, region, from_period, to_period)
                                  -> a quantified price/volume/FX/cost bridge for a margin
                                     delta, plus an LLM-written narrative + recommended action.

Every step returns a `trace` (SQL + data sources) so the frontend's "How this works"
panel shows exactly which certified metric view / tables were used.
"""
from __future__ import annotations

import json
import re

import databricks_client as dbx
import lakebase as lb
import text2sql

CATALOG = "serverless_lakebase_praneeth_catalog"
FINANCE = f"{CATALOG}.akzo_finance"
METRIC_VIEW = f"{FINANCE}.mv_gross_margin"  # certified gross-margin metric view

SERVICE_IDENTITY = "finance-copilot@service"  # the app/service write identity in the audit trail

# 2026 quarter -> (first month, last month) as first-of-month DATE literals.
_QUARTERS = {
    "2026-Q1": ("2026-01-01", "2026-03-01"),
    "2026-Q2": ("2026-04-01", "2026-06-01"),
    "2026-Q3": ("2026-07-01", "2026-09-01"),
    "2026-Q4": ("2026-10-01", "2026-12-01"),
}


def _sql_str(s: str) -> str:
    """Escape a string for embedding in a SQL literal."""
    return s.replace("'", "''")


def _q_bounds(period: str) -> tuple[str, str]:
    if period not in _QUARTERS:
        raise ValueError(f"Unknown period {period!r}; expected one of {sorted(_QUARTERS)}")
    return _QUARTERS[period]


# ---------------------------------------------------------------------------
# ASK — NL question -> governed SQL (Genie pattern) -> grounded narrative
# ---------------------------------------------------------------------------
def ask(question: str) -> dict:
    """text2SQL over the finance golden questions (genie/finance_space.md as the system
    prompt), run on the governed warehouse, then an LLM reasoning step turns the rows into
    a controller-ready answer grounded ONLY in the retrieved numbers.

    Returns {sql, columns, rows, row_count, answer, trace}.
    """
    t2s = text2sql.ask(question)  # {sql, columns, rows, row_count}
    sql = t2s["sql"]
    rows = t2s.get("rows", [])

    if sql.strip().lower().startswith("select 'out_of_scope'"):
        answer = (
            "That question is outside the finance copilot's scope (margin / revenue / COGS / "
            "FX / budget variance over akzo_finance). Try the SCM or Commercial space, or ask "
            "about gross-margin variance for a product line and region."
        )
        return {**t2s, "answer": answer, "trace": _ask_trace(sql)}

    evidence = json.dumps(rows, default=str)
    reason_prompt = (
        "You are a finance controlling copilot for AkzoNobel coatings. Using ONLY the data "
        "below (do not invent figures), answer the question concisely for a controller. "
        "Include the relevant gross-margin %s, the percentage-point change, the named product "
        "line / region, and any price / volume / FX / cost drivers the data supports. Express "
        "margin as a percentage (revenue-weighted) and round to 1 decimal. The data is the "
        "result of this SQL, so the column names tell you what each value means:\n"
        f"SQL: {sql}\n\n"
        f"DATA (rows as JSON objects): {evidence}\n\n"
        f"QUESTION: {question}\n\nANSWER:"
    )
    answer = dbx.chat(
        messages=[{"role": "user", "content": reason_prompt}],
        max_tokens=600,
    ).strip()

    return {**t2s, "answer": answer, "trace": _ask_trace(sql)}


def _ask_trace(sql: str) -> dict:
    return {
        "step": "ask",
        "data_source": (
            f"Genie/text2SQL over {FINANCE}.* (certified metric view {METRIC_VIEW}); "
            f"reasoning by {dbx.CHAT_ENDPOINT}"
        ),
        "sql": [sql],
    }


# ---------------------------------------------------------------------------
# VARIANCE — the structured price/volume/FX/cost bridge for a margin delta
# ---------------------------------------------------------------------------
def variance(product_line: str, region: str, from_period: str, to_period: str) -> dict:
    """Quantify the gross-margin-% change for a product_line x region between two periods
    as a four-way bridge — price / volume / FX / cost — then turn the numbers into a
    controller narrative + recommended action.

    The bridge is computed from governed numbers (not the LLM): we pull per-period realized
    price/unit, units, unit COGS (and its raw-material/freight/energy buckets) from
    margin_actuals + cost_drivers, and the USD->EUR FX rate from fx_rates. We then attribute
    the margin-% change to four additive, margin-point drivers using a fixed bridge:

      Starting margin% m0 = gm0/rev0. We decompose by perturbing one factor at a time off
      the Q1 base (price, then cost, then FX-on-cost), holding the others at base, and read
      each driver's marginal effect on margin%. Volume is ~neutral on margin-% by construction
      (scale cancels in a ratio); we report it explicitly and fold any residual into it so the
      four legs sum exactly to the observed delta.
    """
    f_lo, f_hi = _q_bounds(from_period)
    t_lo, t_hi = _q_bounds(to_period)

    metrics_sql = _build_metrics_sql(product_line, region, from_period, f_lo, f_hi, to_period, t_lo, t_hi)
    res = dbx.run_sql(metrics_sql)
    by_q = {r["period"]: r for r in res["rows"]}
    if from_period not in by_q or to_period not in by_q:
        raise ValueError(
            f"No data for {product_line} x {region} in {from_period} and/or {to_period}"
        )
    q0 = _coerce(by_q[from_period])
    q1 = _coerce(by_q[to_period])

    bridge = _decompose(q0, q1)

    narrative = _reason(product_line, region, from_period, to_period, q0, q1, bridge)

    return {
        "product_line": product_line,
        "region": region,
        "from_period": from_period,
        "to_period": to_period,
        "periods": {from_period: q0, to_period: q1},
        "bridge": bridge,
        "narrative": narrative["narrative"],
        "recommended_action": narrative["recommended_action"],
        "trace": {
            "step": "variance",
            "data_source": (
                f"{FINANCE}.margin_actuals + {FINANCE}.cost_drivers + {FINANCE}.fx_rates "
                f"(certified gross_margin_pct rule from metric view {METRIC_VIEW}); "
                f"reasoning by {dbx.CHAT_ENDPOINT}"
            ),
            "sql": [metrics_sql],
        },
    }


def _build_metrics_sql(product_line, region, p0, p0_lo, p0_hi, p1, p1_lo, p1_hi) -> str:
    """Per-period governed metrics for the two periods, certified margin% (revenue-weighted)."""
    pl = _sql_str(product_line)
    rg = _sql_str(region)
    return f"""
WITH base AS (
  SELECT
    CASE WHEN m.month BETWEEN DATE'{p0_lo}' AND DATE'{p0_hi}' THEN '{p0}'
         WHEN m.month BETWEEN DATE'{p1_lo}' AND DATE'{p1_hi}' THEN '{p1}' END AS period,
    m.month, m.units, m.revenue_eur, m.cogs_eur, m.gross_margin_eur,
    c.raw_material_cost, c.freight_cost, c.energy_cost, c.overhead
  FROM {FINANCE}.margin_actuals m
  JOIN {FINANCE}.products p ON m.sku = p.sku
  LEFT JOIN {FINANCE}.cost_drivers c
    ON c.sku = m.sku AND c.region = m.region AND c.month = m.month
  WHERE p.product_line = '{pl}' AND p.region = '{rg}'
    AND m.month BETWEEN DATE'{p0_lo}' AND DATE'{p1_hi}'
),
fx AS (   -- EMEA Decorative input exposure rides USD raw-material sourcing
  SELECT
    CASE WHEN month BETWEEN DATE'{p0_lo}' AND DATE'{p0_hi}' THEN '{p0}'
         WHEN month BETWEEN DATE'{p1_lo}' AND DATE'{p1_hi}' THEN '{p1}' END AS period,
    AVG(rate_to_eur) AS usd_rate_to_eur
  FROM {FINANCE}.fx_rates
  WHERE currency = 'USD' AND month BETWEEN DATE'{p0_lo}' AND DATE'{p1_hi}'
  GROUP BY 1
)
SELECT
  b.period,
  SUM(b.units)                                              AS units,
  SUM(b.revenue_eur)                                        AS revenue_eur,
  SUM(b.cogs_eur)                                           AS cogs_eur,
  SUM(b.gross_margin_eur)                                   AS gross_margin_eur,
  ROUND(SUM(b.gross_margin_eur) / SUM(b.revenue_eur) * 100, 1) AS gross_margin_pct,
  ROUND(SUM(b.revenue_eur) / SUM(b.units), 2)               AS price_per_unit_eur,
  ROUND(SUM(b.cogs_eur) / SUM(b.units), 2)                  AS cogs_per_unit_eur,
  ROUND(SUM(b.raw_material_cost) / SUM(b.units), 2)         AS raw_mat_per_unit_eur,
  ROUND(SUM(b.freight_cost) / SUM(b.units), 2)              AS freight_per_unit_eur,
  ROUND(SUM(b.energy_cost) / SUM(b.units), 2)               AS energy_per_unit_eur,
  ROUND(SUM(b.overhead) / SUM(b.units), 2)                  AS overhead_per_unit_eur,
  ROUND(MAX(fx.usd_rate_to_eur), 4)                         AS usd_rate_to_eur
FROM base b LEFT JOIN fx ON fx.period = b.period
WHERE b.period IS NOT NULL
GROUP BY b.period
ORDER BY b.period
""".strip()


def _coerce(r: dict) -> dict:
    """SQL rows come back as strings; coerce the numeric columns to float/int."""
    out = dict(r)
    for k in (
        "units", "revenue_eur", "cogs_eur", "gross_margin_eur", "gross_margin_pct",
        "price_per_unit_eur", "cogs_per_unit_eur", "raw_mat_per_unit_eur",
        "freight_per_unit_eur", "energy_per_unit_eur", "overhead_per_unit_eur",
        "usd_rate_to_eur",
    ):
        if out.get(k) is not None:
            out[k] = float(out[k])
    if out.get("units") is not None:
        out["units"] = int(out["units"])
    return out


def _decompose(q0: dict, q1: dict) -> dict:
    """Attribute the margin-% delta to price / volume / FX / cost, additively in margin points.

    Method (Q0 is the base period). All on a per-unit basis so volume scale cancels:
      price0 = revenue/units, cost0 = cogs/units  ->  m0% = (price0 - cost0)/price0
      - PRICE  : change price0 -> price1, hold cost at cost0   -> Δm from price
      - COST   : change cost0  -> cost1 (ex-FX part), hold price at price1
      - FX     : the share of the cost change driven by the USD->EUR rate moving (the
                 raw-material leg is USD-sourced; the EUR translation moves with rate_to_eur).
                 We split the unit-cost increase into an FX-translation component and a
                 residual real-cost (raw-material) component.
      - VOLUME : margin-% is scale-invariant, so volume's direct effect on margin-% is ~0.
                 We report the unit change and fold the (tiny) reconciliation residual here so
                 price+volume+fx+cost sum EXACTLY to the observed margin-% delta.
    """
    price0, price1 = q0["price_per_unit_eur"], q1["price_per_unit_eur"]
    cost0, cost1 = q0["cogs_per_unit_eur"], q1["cogs_per_unit_eur"]
    raw0, raw1 = q0["raw_mat_per_unit_eur"], q1["raw_mat_per_unit_eur"]
    fx0, fx1 = q0["usd_rate_to_eur"], q1["usd_rate_to_eur"]

    m0 = (price0 - cost0) / price0 * 100.0
    m1 = (price1 - cost1) / price1 * 100.0
    total_delta = m1 - m0

    # PRICE: move price only (cost held at base), read the margin-% change.
    m_after_price = (price1 - cost0) / price1 * 100.0
    price_pp = m_after_price - m0

    # Split the unit raw-material increase into an FX-translation leg and a real-cost leg.
    # The USD-sourced raw-material cost in EUR scales ~1/rate_to_eur as EUR strengthens
    # (rate_to_eur falls). Counterfactual raw-material cost if FX had stayed at fx0:
    raw1_ex_fx = raw1 * (fx1 / fx0) if fx0 else raw1   # rate fell -> this is < raw1
    fx_cost_delta_per_unit = raw1 - raw1_ex_fx          # >0: EUR translation added to unit cost
    # Total unit-cost change, and the non-FX (real) cost change.
    cost_delta_per_unit = cost1 - cost0
    real_cost_delta_per_unit = cost_delta_per_unit - fx_cost_delta_per_unit

    # COST leg: real (ex-FX) unit-cost change, evaluated at the new price.
    cost1_ex_fx = cost0 + real_cost_delta_per_unit
    m_price_then_realcost = (price1 - cost1_ex_fx) / price1 * 100.0
    cost_pp = m_price_then_realcost - m_after_price

    # FX leg: the remaining cost move (the translation component), taking us to m1's cost.
    m_price_then_allcost = (price1 - cost1) / price1 * 100.0
    fx_pp = m_price_then_allcost - m_price_then_realcost

    # VOLUME: scale-invariant on margin-%, ~0. Fold any residual so the legs sum to total.
    explained = price_pp + cost_pp + fx_pp
    volume_pp = total_delta - explained

    units_change_pct = (
        (q1["units"] - q0["units"]) / q0["units"] * 100.0 if q0.get("units") else 0.0
    )
    price_change_pct = (price1 - price0) / price0 * 100.0 if price0 else 0.0
    raw_change_pct = (raw1 - raw0) / raw0 * 100.0 if raw0 else 0.0
    fx_change_pct = (fx1 - fx0) / fx0 * 100.0 if fx0 else 0.0

    return {
        "from_margin_pct": round(m0, 1),
        "to_margin_pct": round(m1, 1),
        "total_delta_pp": round(total_delta, 1),
        "drivers": {
            "price": {
                "delta_pp": round(price_pp, 1),
                "detail": f"realized price/unit {price0:.2f} -> {price1:.2f} EUR ({price_change_pct:+.1f}%)",
            },
            "volume": {
                "delta_pp": round(volume_pp, 1),
                "detail": f"units {q0['units']:,} -> {q1['units']:,} ({units_change_pct:+.1f}%); ~neutral on margin %",
            },
            "fx": {
                "delta_pp": round(fx_pp, 1),
                "detail": f"USD rate_to_eur {fx0:.4f} -> {fx1:.4f} ({fx_change_pct:+.1f}%); EUR-translation on USD-sourced inputs",
            },
            "cost": {
                "delta_pp": round(cost_pp, 1),
                "detail": f"raw-material/unit {raw0:.2f} -> {raw1:.2f} EUR ({raw_change_pct:+.1f}%); ex-FX real cost spike",
            },
        },
    }


def _reason(product_line, region, from_period, to_period, q0, q1, bridge) -> dict:
    """LLM reasoning step: turn the quantified bridge into a controller narrative + ONE
    concrete recommended action, grounded ONLY in the computed numbers. Returns strict JSON."""
    d = bridge["drivers"]
    evidence = {
        "product_line": product_line, "region": region,
        "from_period": from_period, "to_period": to_period,
        "from_margin_pct": bridge["from_margin_pct"], "to_margin_pct": bridge["to_margin_pct"],
        "total_delta_pp": bridge["total_delta_pp"],
        "bridge_pp": {k: d[k]["delta_pp"] for k in ("price", "volume", "fx", "cost")},
        "details": {k: d[k]["detail"] for k in ("price", "volume", "fx", "cost")},
        "periods": {from_period: q0, to_period: q1},
    }
    prompt = (
        "You are a finance controlling copilot for AkzoNobel coatings. Below is a VERIFIED, "
        "pre-computed four-way variance bridge (price/volume/FX/cost, in margin percentage "
        "points) for a product line x region between two periods. Do NOT recompute or invent "
        "any numbers — use only what is given.\n\n"
        f"EVIDENCE (JSON): {json.dumps(evidence, default=str)}\n\n"
        "Write a concise controller-ready variance narrative (<140 words) that: states the "
        "headline pp drop, walks the four drivers in order of impact (price, cost, FX, volume), "
        "and notes that the four legs sum to the total. Then give ONE concrete, specific "
        "recommended action a controller can take now (e.g. a pricing review, a procurement/"
        "hedging conversation, a budget re-forecast) — grounded in the dominant drivers.\n\n"
        'Return ONLY a JSON object: {"narrative": "<text>", "recommended_action": "<one action>"}'
    )
    raw = dbx.chat(messages=[{"role": "user", "content": prompt}], max_tokens=700).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        obj = json.loads(m.group(0) if m else raw)
        return {
            "narrative": str(obj.get("narrative", raw)).strip(),
            "recommended_action": str(obj.get("recommended_action", "")).strip(),
        }
    except Exception:
        return {"narrative": raw, "recommended_action": ""}


# ---------------------------------------------------------------------------
# SAVE — persist an analysis to Lakebase under the app/service identity
# ---------------------------------------------------------------------------
def _ensure_saved_table() -> None:
    """Create akzo.saved_analyses if it doesn't exist (idempotent)."""
    lb.execute(
        """CREATE TABLE IF NOT EXISTS saved_analyses (
             analysis_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
             kind          TEXT NOT NULL,
             title         TEXT,
             product_line  TEXT,
             region        TEXT,
             from_period   TEXT,
             to_period     TEXT,
             question      TEXT,
             summary       TEXT,
             payload       JSONB,
             created_by    TEXT,
             created_at    TIMESTAMPTZ DEFAULT now()
           )"""
    )


def save_analysis(kind: str, title: str, summary: str, payload: dict,
                  product_line: str | None = None, region: str | None = None,
                  from_period: str | None = None, to_period: str | None = None,
                  question: str | None = None) -> dict:
    """ACTION: write a saved analysis row to Lakebase under the service identity.
    Returns {analysis_id, created_at, trace}."""
    _ensure_saved_table()
    row = lb.execute(
        """INSERT INTO saved_analyses
             (kind, title, product_line, region, from_period, to_period,
              question, summary, payload, created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING analysis_id, created_at""",
        (kind, title, product_line, region, from_period, to_period,
         question, summary, json.dumps(payload, default=str), SERVICE_IDENTITY),
        returning=True,
    )
    return {
        "analysis_id": row["analysis_id"],
        "created_at": str(row["created_at"]),
        "trace": {
            "step": "save",
            "data_source": f"Lakebase {lb.PG_SCHEMA}.saved_analyses via {SERVICE_IDENTITY}",
            "sql": [
                f"CREATE TABLE IF NOT EXISTS {lb.PG_SCHEMA}.saved_analyses (...)",
                f"INSERT INTO {lb.PG_SCHEMA}.saved_analyses (kind, title, ..., created_by='{SERVICE_IDENTITY}') RETURNING analysis_id",
            ],
        },
    }


def list_saved(limit: int = 50) -> list[dict]:
    """List recent saved analyses, newest first."""
    _ensure_saved_table()
    rows = lb.query(
        """SELECT analysis_id, kind, title, product_line, region, from_period, to_period,
                  question, summary, created_by, created_at
           FROM saved_analyses ORDER BY analysis_id DESC LIMIT %s""",
        (limit,),
    )
    for r in rows:
        r["created_at"] = str(r["created_at"]) if r.get("created_at") else None
    return rows
