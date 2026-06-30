#!/usr/bin/env python3
"""Create the three AkzoNobel Genie spaces (Finance / SCM / Commercial) FROM CODE.

Uses the Genie Spaces Management API (`w.genie.create_space`) with a version-2 `serialized_space`
payload, grounded in the Databricks "Use the Genie Spaces API" doc
(docs.databricks.com/aws/en/genie/conversation-api). Validation rules enforced here:
  - every id is a 32-hex string (generated with the documented formula)
  - arrays that carry ids/identifiers are PRE-SORTED (tables by identifier; sample_questions /
    example_question_sqls by id)
  - at most ONE text_instruction per space
  - version = 2

Idempotent: a space whose title already exists is trashed and recreated, so re-running re-seeds
cleanly. Prints the three space_ids and writes them to genie/space_ids.json for the supervisor
(notebook + app) to consume. Run:  python3 genie/create_genie_spaces.py  (profile via env or --profile)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import random

from databricks.sdk import WorkspaceClient

CAT = os.environ.get("AKZO_CATALOG")
WAREHOUSE = os.environ.get("DATABRICKS_WAREHOUSE_ID")
if not CAT or not WAREHOUSE:
    raise SystemExit("Set AKZO_CATALOG and DATABRICKS_WAREHOUSE_ID before running.")
FIN, SCM, COM = f"{CAT}.akzo_finance", f"{CAT}.akzo_scm", f"{CAT}.akzo_commercial"


def gid() -> str:
    """A valid 32-hex Genie id (documented generator)."""
    t = int((datetime.datetime.now() - datetime.datetime(1582, 10, 15)).total_seconds() * 1e7)
    return f"{(t & 0xFFFFFFFFFFFF0000) | (1 << 12) | ((t & 0xFFFF) >> 4):016x}{random.getrandbits(62) | 0x8000000000000000:016x}"


def _by_id(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda x: x["id"])


def serialized(tables: list[dict], instruction: list[str], examples: list[dict],
               samples: list[str]) -> str:
    """Build a version-2 serialized_space string with all validation rules satisfied."""
    payload = {
        "version": 2,
        "config": {"sample_questions": _by_id([{"id": gid(), "question": [q]} for q in samples])},
        "data_sources": {"tables": sorted(tables, key=lambda t: t["identifier"])},
        "instructions": {
            "text_instructions": [{"id": gid(), "content": instruction}],  # at most 1
            "example_question_sqls": _by_id([{"id": gid(), **e} for e in examples]),
        },
    }
    return json.dumps(payload)


# ---- the three domain definitions (tables + 1 instruction + example SQL + sample questions) ----

SPACES = {
    "finance": {
        "title": "Akzo Finance — Margin & Variance Controlling",
        "description": "AkzoNobel coatings gross margin, COGS, FX, and budget variance by SKU / line / region / month. Reporting currency EUR; current month 2026-06.",
        "tables": [
            {"identifier": f"{FIN}.cost_drivers", "description": ["COGS decomposition per sku x region x month: raw_material_cost, freight_cost, energy_cost, overhead (EUR; sum reconciles to cogs_eur)."]},
            {"identifier": f"{FIN}.fx_rates", "description": ["Monthly FX to EUR by currency (EUR/USD/GBP/CNY); rate_to_eur (EUR=1.0)."]},
            {"identifier": f"{FIN}.margin_actuals", "description": ["Realized monthly P&L per sku x region: units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct (fraction)."]},
            {"identifier": f"{FIN}.products", "description": ["SKU master: product_line (Decorative Paints|Performance Coatings), region, currency, list_price_eur, standard_cost_eur."]},
        ],
        "instruction": [
            "Reporting currency is EUR; current month is 2026-06. ",
            "gross_margin_pct = SUM(gross_margin_eur)/SUM(revenue_eur) when aggregating; NEVER average row-level gross_margin_pct. ",
            "'Paints EMEA' := products.product_line='Decorative Paints' AND products.region='EMEA'; join margin_actuals.sku=products.sku. ",
            "Quarters 2026: Q1=2026-01-01..2026-03-01, Q2=2026-04-01..2026-06-01. month is first-of-month DATE. Round percentages to 1 decimal.",
        ],
        "examples": [
            {"question": ["Show Paints EMEA gross margin % by month for 2026"],
             "sql": ["SELECT m.month, ROUND(SUM(m.gross_margin_eur)/SUM(m.revenue_eur)*100,1) AS gross_margin_pct\n",
                     f"FROM {FIN}.margin_actuals m JOIN {FIN}.products p ON m.sku=p.sku\n",
                     "WHERE p.product_line='Decorative Paints' AND p.region='EMEA' AND m.month>=DATE'2026-01-01'\n",
                     "GROUP BY m.month ORDER BY m.month"]},
            {"question": ["Break Paints EMEA Q2 2026 COGS into raw material, freight, energy, overhead"],
             "sql": ["SELECT ROUND(SUM(c.raw_material_cost)) raw_material_eur, ROUND(SUM(c.freight_cost)) freight_eur,\n",
                     "ROUND(SUM(c.energy_cost)) energy_eur, ROUND(SUM(c.overhead)) overhead_eur\n",
                     f"FROM {FIN}.cost_drivers c JOIN {FIN}.products p ON c.sku=p.sku\n",
                     "WHERE p.product_line='Decorative Paints' AND p.region='EMEA' AND c.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01'"]},
        ],
        "samples": ["What happened to Paints EMEA gross margin in Q2 2026 versus Q1?",
                    "Which cost driver caused the Paints EMEA COGS increase in Q2 2026?"],
    },
    "scm": {
        "title": "Akzo SCM — OTIF & Service Control Tower",
        "description": "AkzoNobel supply chain: OTIF, inventory/stockouts, lanes/lead times, service levels and backorders by plant / lane / region / month.",
        "tables": [
            {"identifier": f"{SCM}.inventory", "description": ["On-hand vs safety stock per plant x sku x month; days_of_supply, stockout_flag (1=stockout)."]},
            {"identifier": f"{SCM}.lanes", "description": ["Transport lanes: origin_plant, dest_region, mode (road|sea|air), lead_time_days, cost_per_unit."]},
            {"identifier": f"{SCM}.otif", "description": ["On-time-in-full per plant x region x lane x sku x month: orders, on_time, in_full, otif_pct."]},
            {"identifier": f"{SCM}.service_levels", "description": ["Region x month service_pct (fraction, 0.906=90.6%) and backorder_units."]},
        ],
        "instruction": [
            "OTIF (aggregated) = SUM(ROUND(otif_pct*orders))/SUM(orders); weight by orders, NEVER average otif_pct. ",
            "The narrative EMEA lane is 'Rotterdam-NL->EMEA-DACH'; EMEA plants Rotterdam-NL, Felling-UK. 'Paints EMEA' := region='EMEA' AND sku LIKE 'DEC-%'. ",
            "service_pct is a fraction; multiply by 100 to present a percentage. Quarters 2026: Q2=2026-04-01..2026-06-01. month is first-of-month DATE. Round percentages to 1 decimal.",
        ],
        "examples": [
            {"question": ["Show monthly OTIF for the Rotterdam-NL->EMEA-DACH lane in 2026"],
             "sql": ["SELECT month, ROUND(SUM(ROUND(otif_pct*orders))/SUM(orders)*100,1) AS lane_otif_pct, SUM(orders) AS orders\n",
                     f"FROM {SCM}.otif WHERE lane='Rotterdam-NL->EMEA-DACH' AND month>=DATE'2026-01-01'\n",
                     "GROUP BY month ORDER BY month"]},
            {"question": ["Which EMEA SKUs stocked out at Rotterdam in May 2026?"],
             "sql": ["SELECT sku, ROUND(days_of_supply,1) AS days_of_supply\n",
                     f"FROM {SCM}.inventory WHERE plant='Rotterdam-NL' AND month=DATE'2026-05-01' AND stockout_flag=1\n",
                     "ORDER BY days_of_supply"]},
        ],
        "samples": ["Why did Rotterdam->EMEA-DACH OTIF drop in May 2026?",
                    "Show EMEA service level and backorders by month in Q2 2026"],
    },
    "commercial": {
        "title": "Akzo Commercial — Accounts, Churn & Next-Best-Action",
        "description": "AkzoNobel commercial: account churn risk, NPS, complaints, pipeline and sales by account / segment / region / month.",
        "tables": [
            {"identifier": f"{COM}.accounts", "description": ["Account master: region, segment (Architectural|Industrial|Marine & Protective|Automotive Refinish), industry, owner_rep."]},
            {"identifier": f"{COM}.churn_signals", "description": ["Per account x month: churn_score (0-1), last_order_days, complaint_count, nps."]},
            {"identifier": f"{COM}.pipeline", "description": ["Opportunities: stage, amount_eur, close_month, product_line."]},
            {"identifier": f"{COM}.sales_actuals", "description": ["Per account x month: revenue_eur, volume_units, margin_eur."]},
        ],
        "instruction": [
            "'at churn risk' := churn_score>0.7 (evaluate on month=2026-06-01 unless told otherwise). ",
            "'Paints EMEA accounts' := accounts.region='EMEA' AND accounts.segment='Architectural' (Decorative Paints buyers). When asked WHY at risk, also return last_order_days, complaint_count, nps and the revenue trend. ",
            "month/close_month are first-of-month DATEs; current=2026-06. Round churn_score to 3 decimals, EUR to whole euros.",
        ],
        "examples": [
            {"question": ["Which Paints EMEA accounts are at churn risk in June 2026 and why?"],
             "sql": ["SELECT a.account_id, a.account_name, ROUND(c.churn_score,3) AS churn_score, c.last_order_days, c.complaint_count, c.nps\n",
                     f"FROM {COM}.churn_signals c JOIN {COM}.accounts a ON c.account_id=a.account_id\n",
                     "WHERE c.month=DATE'2026-06-01' AND c.churn_score>0.7 AND a.region='EMEA' AND a.segment='Architectural'\n",
                     "ORDER BY c.churn_score DESC"]},
            {"question": ["Show the 2026 monthly revenue trend for accounts ACC0001, ACC0002, ACC0003"],
             "sql": ["SELECT month, ROUND(SUM(revenue_eur)) AS combined_revenue_eur\n",
                     f"FROM {COM}.sales_actuals WHERE account_id IN ('ACC0001','ACC0002','ACC0003') AND month>=DATE'2026-01-01'\n",
                     "GROUP BY month ORDER BY month"]},
        ],
        "samples": ["Which EMEA accounts are at churn risk and why?",
                    "What is the revenue trend for the at-risk EMEA accounts in 2026?"],
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
    args = ap.parse_args()
    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    me = w.current_user.me().user_name
    existing = {s.title: s.space_id for s in (w.genie.list_spaces().spaces or [])}

    out = {}
    for key, d in SPACES.items():
        if d["title"] in existing:
            print(f"[{key}] trashing existing space {existing[d['title']]}")
            try:
                w.genie.trash_space(existing[d["title"]])
            except Exception as e:
                print("  trash err:", str(e)[:120])
        ser = serialized(d["tables"], d["instruction"], d["examples"], d["samples"])
        sp = w.genie.create_space(warehouse_id=WAREHOUSE, serialized_space=ser,
                                  title=d["title"], description=d["description"],
                                  parent_path=f"/Workspace/Users/{me}")
        out[key] = sp.space_id
        print(f"[{key}] created space_id={sp.space_id}  ({sp.title})")

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "space_ids.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote genie/space_ids.json:", json.dumps(out))
    print("Supervisor (notebook 01 + apps/supervisor) reads these to call REAL Genie via the Conversation API.")


if __name__ == "__main__":
    main()
