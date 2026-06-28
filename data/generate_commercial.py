"""Deterministic synthetic-data generator for the COMMERCIAL (sales) domain.

AkzoNobel (coatings) Databricks workshop. Fixed seed (44) -> reproducible.
Outputs parquet to data/output/commercial/ and appends a README.

Dimensions are aligned with the finance/scm domains for cross-domain coherence:
  Regions:      EMEA, Americas, APAC, China
  Segments:     Architectural, Industrial, Marine & Protective, Automotive Refinish
  Product lines: Decorative Paints, Performance Coatings
  Time:         24 monthly periods, 2024-07-01 .. 2026-06-01 (current = 2026-06)

EMBEDDED NARRATIVE (the demo depends on this):
  Exactly 3 named EMEA accounts buying Decorative Paints ("Paints EMEA") are
  clearly at churn risk in Q2 2026 (Apr/May/Jun 2026): rising churn_score
  (>0.7 by Jun 2026), increasing last_order_days, increasing complaint_count,
  falling nps, and declining sales_actuals revenue. Their decline ties to the
  Paints EMEA margin + OTIF/service problems (poor service -> churn risk).
  Every other account stays relatively stable so these 3 stand out.

Only stdlib + numpy + pandas + pyarrow.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

SEED = 44
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "commercial")

REGIONS = ["EMEA", "Americas", "APAC", "China"]
SEGMENTS = ["Architectural", "Industrial", "Marine & Protective", "Automotive Refinish"]
PRODUCT_LINES = ["Decorative Paints", "Performance Coatings"]

# 24 monthly periods, first-of-month, 2024-07-01 .. 2026-06-01 (current = 2026-06).
MONTHS = pd.date_range("2024-07-01", "2026-06-01", freq="MS")

# Q2 2026 = the churn window for the narrative.
Q2_2026 = pd.to_datetime(["2026-04-01", "2026-05-01", "2026-06-01"])

# The three memorable at-risk accounts (EMEA / Decorative Paints / Architectural).
AT_RISK = [
    "Rhine Valley Decor Distributors",
    "Benelux PaintPro",
    "Nordic Coatings Supply",
]

# Owner reps per region (sales territory ownership; aligns with RLS-by-territory story).
REPS = {
    "EMEA": ["Sofie Maes", "Lars Andersen", "Pieter de Vries", "Camille Laurent"],
    "Americas": ["Maria Santos", "James Carter", "Diego Alvarez"],
    "APAC": ["Aarav Sharma", "Mei Tanaka", "Wei Lim"],
    "China": ["Li Wei", "Zhang Min", "Chen Hao"],
}

# Plausible B2B name fragments by segment (distributors, contractors, OEMs).
NAME_PARTS = {
    "Architectural": (
        ["Rhine", "Benelux", "Nordic", "Iberia", "Alpine", "Atlantic", "Pacific",
         "Lakeside", "Summit", "Harbor", "Metro", "Continental", "Crown", "Vista"],
        ["Decor", "PaintPro", "Coatings", "Color", "Finishes", "Walls", "Surface", "Build"],
        ["Distributors", "Supply", "Trade", "Group", "Contractors", "Partners"],
    ),
    "Industrial": (
        ["Ferro", "Steelworks", "Forge", "Apex", "Titan", "Vertex", "Ironclad",
         "Precision", "Heavy", "Mega", "Industrial", "Unified"],
        ["Coat", "Protect", "Surface", "Industrial", "Steel", "Powder", "Finish"],
        ["Systems", "Works", "Industries", "Solutions", "Corp", "Manufacturing"],
    ),
    "Marine & Protective": (
        ["Blue", "Deep", "Harbor", "Coastal", "Ocean", "Pelagic", "North Sea",
         "Maritime", "Anchor", "Tidewater", "Gulf", "Offshore"],
        ["Marine", "Hull", "Yard", "Protective", "Shield", "Anti-Corr", "Dock"],
        ["Shipyards", "Marine", "Holdings", "Services", "Logistics", "Group"],
    ),
    "Automotive Refinish": (
        ["AutoFin", "Carcraft", "Velocity", "Chroma", "Bodyworks", "Speedline",
         "Refine", "Prestige", "Motor", "Gloss", "Spectra", "DriveLine"],
        ["Refinish", "Body", "Auto", "Paint", "Collision", "Detail", "Finish"],
        ["Centers", "Group", "Network", "Services", "Distributors", "Garages"],
    ),
}

INDUSTRY_BY_SEGMENT = {
    "Architectural": "Building & Construction",
    "Industrial": "General Industrial",
    "Marine & Protective": "Marine & Energy",
    "Automotive Refinish": "Transportation",
}


def _build_accounts(rng: np.random.Generator) -> pd.DataFrame:
    """~80 B2B accounts with region/segment/owner_rep. The 3 at-risk accounts
    are forced to be EMEA / Architectural so they plausibly buy Paints EMEA."""
    rows = []
    used_names: set[str] = set()

    # 1) The 3 narrative accounts, pinned to EMEA + Architectural.
    emea_arch_reps = REPS["EMEA"]
    for i, name in enumerate(AT_RISK):
        rows.append(
            {
                "account_id": f"ACC{1 + i:04d}",
                "account_name": name,
                "region": "EMEA",
                "segment": "Architectural",
                "industry": INDUSTRY_BY_SEGMENT["Architectural"],
                "owner_rep": emea_arch_reps[i % len(emea_arch_reps)],
            }
        )
        used_names.add(name)

    # 2) Remaining ~77 accounts spread across all region x segment combos.
    n_total = 80
    n_remaining = n_total - len(AT_RISK)
    next_id = len(AT_RISK) + 1
    while len(rows) < n_total:
        region = REGIONS[rng.integers(0, len(REGIONS))]
        segment = SEGMENTS[rng.integers(0, len(SEGMENTS))]
        a, b, c = NAME_PARTS[segment]
        name = f"{a[rng.integers(0, len(a))]} {b[rng.integers(0, len(b))]} {c[rng.integers(0, len(c))]}"
        if name in used_names:
            continue
        used_names.add(name)
        reps = REPS[region]
        rows.append(
            {
                "account_id": f"ACC{next_id:04d}",
                "account_name": name,
                "region": region,
                "segment": segment,
                "industry": INDUSTRY_BY_SEGMENT[segment],
                "owner_rep": reps[rng.integers(0, len(reps))],
            }
        )
        next_id += 1

    assert len(rows) == n_total
    _ = n_remaining
    return pd.DataFrame(rows)


def _account_product_line(rng: np.random.Generator, segment: str) -> str:
    """Architectural skews to Decorative Paints; others skew to Performance Coatings."""
    if segment == "Architectural":
        return "Decorative Paints" if rng.random() < 0.85 else "Performance Coatings"
    return "Performance Coatings" if rng.random() < 0.80 else "Decorative Paints"


def _build_sales_actuals(rng: np.random.Generator, accounts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Monthly revenue/volume/margin per account. At-risk accounts decline through Q2 2026."""
    at_risk_ids = set(accounts.loc[accounts["account_name"].isin(AT_RISK), "account_id"])

    # Per-account product line (used to know who is "Paints EMEA").
    prod_line = {}
    for _, acc in accounts.iterrows():
        if acc["account_id"] in at_risk_ids:
            prod_line[acc["account_id"]] = "Decorative Paints"  # Paints EMEA
        else:
            prod_line[acc["account_id"]] = _account_product_line(rng, acc["segment"])

    # Baseline scale per account (annual-ish size), with region effects.
    region_scale = {"EMEA": 1.0, "Americas": 1.1, "APAC": 0.85, "China": 0.9}

    rows = []
    n_months = len(MONTHS)
    t = np.arange(n_months)

    for _, acc in accounts.iterrows():
        aid = acc["account_id"]
        base = rng.uniform(60_000, 220_000) * region_scale[acc["region"]]
        # Gentle organic trend + mild seasonality, stable for most accounts.
        trend = rng.uniform(-0.0015, 0.004)  # monthly growth fraction
        seasonal = 0.05 * np.sin(2 * np.pi * (t + rng.integers(0, 12)) / 12.0)
        margin_pct_base = rng.uniform(0.18, 0.30)
        unit_price = rng.uniform(7.5, 16.0)  # eur per unit (avg)

        for i, month in enumerate(MONTHS):
            level = base * (1.0 + trend) ** i * (1.0 + seasonal[i])
            noise = rng.normal(1.0, 0.04)
            revenue = level * noise
            margin_pct = margin_pct_base + rng.normal(0.0, 0.01)

            if aid in at_risk_ids:
                # Decorative Paints EMEA service/margin problem: a slow erosion
                # starting ~Q4 2025, then a sharp Q2 2026 drop as service fails.
                if month >= pd.Timestamp("2025-10-01"):
                    months_since = (month.to_period("M") - pd.Period("2025-10", "M")).n
                    revenue *= (1.0 - 0.02 * months_since)  # slow erosion
                if month in set(Q2_2026):
                    q2_idx = list(Q2_2026).index(month)  # 0=Apr,1=May,2=Jun
                    drop = [0.78, 0.62, 0.48][q2_idx]  # steepening decline
                    revenue *= drop
                    margin_pct -= 0.04 + 0.02 * q2_idx  # margin squeeze too

            revenue = max(revenue, 1_000.0)
            margin_pct = float(np.clip(margin_pct, 0.05, 0.45))
            volume_units = int(round(revenue / unit_price))
            margin_eur = revenue * margin_pct

            rows.append(
                {
                    "account_id": aid,
                    "month": month.date(),
                    "revenue_eur": round(revenue, 2),
                    "volume_units": volume_units,
                    "margin_eur": round(margin_eur, 2),
                }
            )

    df = pd.DataFrame(rows)
    meta = {"at_risk_ids": at_risk_ids, "prod_line": prod_line}
    return df, meta


def _build_churn_signals(rng: np.random.Generator, accounts: pd.DataFrame, meta: dict) -> pd.DataFrame:
    """Monthly churn signals. At-risk accounts: rising churn_score (>0.7 by Jun 2026),
    increasing last_order_days, increasing complaint_count, falling nps."""
    at_risk_ids = meta["at_risk_ids"]
    rows = []

    # Pin Jun-2026 churn_score targets for the three at-risk accounts so they are
    # unmistakably > 0.7 and ordered by severity (matches revenue drop steepness).
    jun_target = {}
    sorted_at_risk = sorted(at_risk_ids)
    targets = [0.88, 0.82, 0.76]
    for aid, tgt in zip(sorted_at_risk, targets):
        jun_target[aid] = tgt

    for _, acc in accounts.iterrows():
        aid = acc["account_id"]
        is_risk = aid in at_risk_ids

        # Stable healthy baselines for normal accounts.
        base_churn = rng.uniform(0.05, 0.25)
        base_last_order = rng.integers(8, 28)
        base_complaints_lambda = rng.uniform(0.05, 0.5)
        base_nps = rng.integers(25, 65)

        for month in MONTHS:
            if is_risk and month >= pd.Timestamp("2025-10-01"):
                # Ramp from the start of the erosion to a forced Jun-2026 target.
                ramp = (month.to_period("M") - pd.Period("2025-10", "M")).n
                total = (pd.Period("2026-06", "M") - pd.Period("2025-10", "M")).n  # = 8
                frac = ramp / total
                churn = base_churn + (jun_target[aid] - base_churn) * frac
                churn += rng.normal(0.0, 0.01)
                # Steepen inside Q2 2026.
                if month in set(Q2_2026):
                    churn = max(churn, 0.7 + 0.05 * list(Q2_2026).index(month))
                last_order = int(base_last_order + 60 * frac + rng.normal(0, 2))
                complaints = int(round(0.5 + 6 * frac + rng.normal(0, 0.4)))
                nps = int(base_nps - (base_nps + 55) * frac + rng.normal(0, 3))
            else:
                churn = base_churn + rng.normal(0.0, 0.03)
                last_order = int(base_last_order + rng.normal(0, 3))
                complaints = int(rng.poisson(base_complaints_lambda))
                nps = int(base_nps + rng.normal(0, 4))

            churn = float(np.clip(churn, 0.0, 1.0))
            last_order = int(max(1, last_order))
            complaints = int(max(0, complaints))
            nps = int(np.clip(nps, -100, 100))

            rows.append(
                {
                    "account_id": aid,
                    "month": month.date(),
                    "churn_score": round(churn, 3),
                    "last_order_days": last_order,
                    "complaint_count": complaints,
                    "nps": nps,
                }
            )

    return pd.DataFrame(rows)


def _build_pipeline(rng: np.random.Generator, accounts: pd.DataFrame, meta: dict) -> pd.DataFrame:
    """Open + closed opportunities. At-risk accounts skew toward ClosedLost and
    stalled stages near Q2 2026; healthy accounts have a normal funnel."""
    at_risk_ids = meta["at_risk_ids"]
    prod_line = meta["prod_line"]
    stages = ["Prospect", "Qualify", "Propose", "Negotiate", "ClosedWon", "ClosedLost"]

    rows = []
    opp_n = 1
    close_window = pd.date_range("2025-07-01", "2026-12-01", freq="MS")

    for _, acc in accounts.iterrows():
        aid = acc["account_id"]
        is_risk = aid in at_risk_ids
        n_opps = int(rng.integers(2, 6))
        for _ in range(n_opps):
            if is_risk:
                # Their deals stall or fall out; weighted toward bad outcomes.
                stage = stages[rng.choice(len(stages), p=[0.10, 0.15, 0.15, 0.15, 0.10, 0.35])]
                amount = rng.uniform(15_000, 120_000)
            else:
                stage = stages[rng.choice(len(stages), p=[0.18, 0.18, 0.17, 0.15, 0.20, 0.12])]
                amount = rng.uniform(20_000, 200_000)
            close_month = close_window[rng.integers(0, len(close_window))]
            rows.append(
                {
                    "opp_id": f"OPP{opp_n:05d}",
                    "account_id": aid,
                    "stage": stage,
                    "amount_eur": round(float(amount), 2),
                    "close_month": close_month.date(),
                    "product_line": prod_line[aid],
                }
            )
            opp_n += 1

    return pd.DataFrame(rows)


def _write_readme(out_dir: str, frames: dict, accounts: pd.DataFrame, churn: pd.DataFrame) -> None:
    readme = os.path.join(out_dir, "README.md")
    at_risk = accounts[accounts["account_name"].isin(AT_RISK)][["account_id", "account_name"]]
    jun = churn[churn["month"] == pd.Timestamp("2026-06-01").date()]
    jun_risk = jun.merge(at_risk, on="account_id")

    lines = []
    lines.append("\n## commercial (sales domain)\n")
    lines.append(f"Generated by `data/generate_commercial.py` (seed={SEED}). "
                 "Deterministic; aligned with the finance/scm domains.\n")
    lines.append("**Dimensions:** Regions [EMEA, Americas, APAC, China] · "
                 "Segments [Architectural, Industrial, Marine & Protective, Automotive Refinish] · "
                 "Product lines [Decorative Paints, Performance Coatings] · "
                 "24 monthly periods 2024-07 .. 2026-06 (current = 2026-06).\n")
    lines.append("\n### Tables\n")
    lines.append("| table | rows | columns |")
    lines.append("|---|---|---|")
    for name, df in frames.items():
        lines.append(f"| `{name}` | {len(df):,} | {', '.join(df.columns)} |")
    lines.append("\n### Embedded narrative (demo-critical)\n")
    lines.append("Three EMEA accounts buying **Decorative Paints (\"Paints EMEA\")** are at clear "
                 "churn risk in Q2 2026: rising `churn_score` (>0.7 by Jun 2026), increasing "
                 "`last_order_days` and `complaint_count`, falling `nps`, and declining "
                 "`sales_actuals.revenue_eur`. The decline ties to the Paints EMEA margin + "
                 "OTIF/service problems (poor service -> churn risk). All other accounts are stable.\n")
    lines.append("\n**At-risk accounts (Jun 2026 churn_score):**\n")
    lines.append("| account_id | account_name | churn_score |")
    lines.append("|---|---|---|")
    for _, r in jun_risk.sort_values("churn_score", ascending=False).iterrows():
        lines.append(f"| {r['account_id']} | {r['account_name']} | {r['churn_score']} |")
    lines.append("")

    with open(readme, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    rng = np.random.default_rng(SEED)
    os.makedirs(OUT_DIR, exist_ok=True)

    accounts = _build_accounts(rng)
    sales_actuals, meta = _build_sales_actuals(rng, accounts)
    churn_signals = _build_churn_signals(rng, accounts, meta)
    pipeline = _build_pipeline(rng, accounts, meta)

    frames = {
        "accounts": accounts,
        "pipeline": pipeline,
        "sales_actuals": sales_actuals,
        "churn_signals": churn_signals,
    }
    for name, df in frames.items():
        df.to_parquet(os.path.join(OUT_DIR, f"{name}.parquet"), index=False, engine="pyarrow")

    _write_readme(OUT_DIR, frames, accounts, churn_signals)

    # ---- Report ----
    print(f"Output dir: {OUT_DIR}")
    print("Row counts:")
    for name, df in frames.items():
        print(f"  {name:15s} {len(df):>7,} rows  ({len(df.columns)} cols)")

    print("\n3 at-risk EMEA Decorative-Paints accounts (Jun 2026 churn_score):")
    jun = churn_signals[churn_signals["month"] == pd.Timestamp("2026-06-01").date()]
    at_risk = accounts[accounts["account_name"].isin(AT_RISK)][["account_id", "account_name"]]
    jun_risk = jun.merge(at_risk, on="account_id").sort_values("churn_score", ascending=False)
    for _, r in jun_risk.iterrows():
        print(f"  {r['account_id']}  {r['account_name']:35s}  churn_score={r['churn_score']}")

    # Sanity: revenue trajectory for the at-risk accounts over Q2 2026.
    print("\nSanity - at-risk revenue (EUR) Mar->Jun 2026:")
    q_months = pd.to_datetime(["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"])
    for aid in sorted(meta["at_risk_ids"]):
        nm = accounts.loc[accounts["account_id"] == aid, "account_name"].iloc[0]
        sub = sales_actuals[
            (sales_actuals["account_id"] == aid)
            & (sales_actuals["month"].isin([m.date() for m in q_months]))
        ].sort_values("month")
        traj = " -> ".join(f"{v:,.0f}" for v in sub["revenue_eur"])
        print(f"  {nm:35s} {traj}")


if __name__ == "__main__":
    main()
