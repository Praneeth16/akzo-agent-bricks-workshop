"""Deterministic synthetic FINANCE data generator for the AkzoNobel Databricks workshop.

Generates reproducible parquet tables (seed=42) describing a coatings company's
finances across 24 monthly periods, 4 regions, and 2 product lines.

Embedded narrative the demo depends on:
  Paints EMEA (Decorative Paints x EMEA) gross_margin_pct drops ~8 percentage
  points in Q2 2026 (Apr/May/Jun) vs Q1 2026 and vs budget. The drop decomposes
  into roughly:
    - price erosion         ~ -3pp  (realized price down)
    - adverse FX (EUR/USD, EUR/CNY) ~ -2pp
    - raw-material spike (TiO2 + resin, +15-20%) ~ -3pp
  Volume stays roughly flat. All other region x line combos stay stable so the
  EMEA Q2 drop is the clear signal.

Only stdlib + numpy + pandas + pyarrow. No network.
"""

import os

import numpy as np
import pandas as pd

SEED = 42
RNG = np.random.default_rng(SEED)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "finance")

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
MONTHS = pd.date_range("2024-07-01", "2026-06-01", freq="MS")  # 24 first-of-month periods
REGIONS = ["EMEA", "Americas", "APAC", "China"]
PRODUCT_LINES = ["Decorative Paints", "Performance Coatings"]

# Region -> local currency (reporting currency is EUR)
REGION_CURRENCY = {
    "EMEA": "EUR",
    "Americas": "USD",
    "APAC": "GBP",   # GBP must be present; APAC reports in GBP for this dataset
    "China": "CNY",
}

Q1_2026 = [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01"), pd.Timestamp("2026-03-01")]
Q2_2026 = [pd.Timestamp("2026-04-01"), pd.Timestamp("2026-05-01"), pd.Timestamp("2026-06-01")]


# ---------------------------------------------------------------------------
# Product name pools (generic coatings names, no real trademarks)
# ---------------------------------------------------------------------------
DECORATIVE_NAMES = [
    "Interior Matt Emulsion", "Interior Silk Emulsion", "Interior Soft Sheen Emulsion",
    "Premium Interior Vinyl Matt", "Kitchen & Bathroom Emulsion", "Durable Interior Eggshell",
    "Exterior Masonry Emulsion", "Smooth Exterior Wall Paint", "Textured Exterior Coating",
    "Weatherproof Facade Paint", "Quick-Dry Wood Primer", "Multi-Surface Primer Undercoat",
    "Acrylic Wall Primer Sealer", "Stain-Block Primer", "Satinwood Wood & Metal",
    "Gloss Wood & Metal", "Eggshell Trim Paint", "Exterior Wood Stain",
    "Decking Protector Oil", "Interior Wood Varnish", "Anti-Mould Bathroom Coating",
    "One-Coat Ceiling Paint", "Tintable Base White", "Garden Furniture Paint",
    "Floor & Tile Paint", "Radiator Enamel", "Metal Shed & Fence Paint",
    "Heritage Chalky Emulsion", "Feature Wall Velvet Matt", "Damp Seal Basecoat",
]

PERFORMANCE_NAMES = [
    "Epoxy Powder Topcoat", "Polyester Powder Coating", "Architectural Powder Finish",
    "Hybrid Powder Primer", "Anti-Corrosion Powder Coat", "Marine Antifouling Paint",
    "Marine Topside Enamel", "Hull Primer Epoxy", "Yacht Deck Coating",
    "Ballast Tank Coating", "Heavy-Duty Protective Epoxy", "Zinc-Rich Primer",
    "Intumescent Fire Coating", "Tank Lining Novolac", "Pipeline Protective Coat",
    "Structural Steel Topcoat", "Polyurethane Industrial Finish", "Concrete Floor Sealer",
    "High-Build Surface Tolerant Epoxy", "Aluminium Pretreatment Primer",
    "Offshore Splash-Zone Coating", "Bridge Maintenance Coating", "Rail Car Topcoat",
    "Chemical-Resistant Lining", "Insulative Thermal Coating", "Wind Turbine Blade Coating",
    "Automotive Refinish Clearcoat", "Coil Coating Primer", "Petrochemical Tank Epoxy",
    "Abrasion-Resistant Deck Paint",
]


def _round_money(x):
    return np.round(x, 2)


# ---------------------------------------------------------------------------
# 1. products
# ---------------------------------------------------------------------------
def build_products():
    rows = []
    for line, names in [("Decorative Paints", DECORATIVE_NAMES),
                        ("Performance Coatings", PERFORMANCE_NAMES)]:
        prefix = "DEC" if line == "Decorative Paints" else "PFC"
        # 30 SKUs per line -> 60 total. Assign regions round-robin so every
        # region x line combo has ~7-8 SKUs.
        for i, base_name in enumerate(names):
            region = REGIONS[i % len(REGIONS)]
            currency = REGION_CURRENCY[region]
            sku = f"{prefix}-{1000 + i}"
            product_name = base_name

            if line == "Decorative Paints":
                # paints: lower price, lower cost
                list_price = RNG.uniform(18.0, 55.0)
                margin_target = RNG.uniform(0.40, 0.52)
            else:
                # performance coatings: higher price, higher cost, richer margin
                list_price = RNG.uniform(45.0, 220.0)
                margin_target = RNG.uniform(0.30, 0.45)

            standard_cost = list_price * (1.0 - margin_target)
            rows.append({
                "sku": sku,
                "product_name": product_name,
                "product_line": line,
                "region": region,
                "currency": currency,
                "list_price_eur": _round_money(list_price),
                "standard_cost_eur": _round_money(standard_cost),
            })
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# 2. fx_rates  (rate_to_eur: multiply a local-currency amount by this to get EUR)
# ---------------------------------------------------------------------------
def build_fx_rates():
    # base rates (local currency -> EUR)
    base = {"EUR": 1.0, "USD": 0.925, "GBP": 1.155, "CNY": 0.129}
    # Q2-2026 adverse move for USD and CNY (they weaken vs EUR => fewer EUR per unit)
    rows = []
    for cur, b in base.items():
        for m in MONTHS:
            if cur == "EUR":
                rate = 1.0
            else:
                # mild monthly drift
                drift = RNG.normal(0.0, 0.004)
                rate = b * (1.0 + drift)
                # adverse FX in Q2 2026 for USD & CNY: local weakens ~4-5%
                if cur in ("USD", "CNY") and m in Q2_2026:
                    # progressive weakening across the quarter
                    step = Q2_2026.index(m)  # 0,1,2
                    rate = b * (1.0 - (0.030 + 0.010 * step))
            rows.append({"currency": cur, "month": m, "rate_to_eur": round(float(rate), 6)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. margin_actuals + 4. margin_budget + 5. cost_drivers
# ---------------------------------------------------------------------------
def build_actuals_budget_drivers(products, fx):
    fx_lookup = {(r.currency, r.month): r.rate_to_eur for r in fx.itertuples()}

    actuals = []
    budget = []
    drivers = []

    for p in products.itertuples():
        sku = p.sku
        region = p.region
        line = p.product_line
        currency = p.currency
        list_price = p.list_price_eur
        std_cost = p.standard_cost_eur

        is_paints_emea = (line == "Decorative Paints" and region == "EMEA")

        # Baseline monthly volume per SKU (stable with mild seasonality + noise)
        base_units = RNG.uniform(800, 4000) if line == "Decorative Paints" else RNG.uniform(120, 900)

        # Per-SKU stable realized-price ratio vs list (discounting)
        base_price_ratio = RNG.uniform(0.90, 0.98)

        for m in MONTHS:
            month_idx = list(MONTHS).index(m)

            # ---- volume: mild seasonality + small noise, roughly flat trend ----
            seasonal = 1.0 + 0.06 * np.sin(2 * np.pi * (m.month / 12.0))
            unit_noise = RNG.normal(1.0, 0.03)
            units = base_units * seasonal * unit_noise
            # very mild organic growth over 24 months
            units *= (1.0 + 0.002 * month_idx)
            units = max(1.0, units)

            # ---- realized price (EUR) ----
            price_ratio = base_price_ratio * RNG.normal(1.0, 0.01)
            realized_price = list_price * price_ratio

            # ---- per-unit cost (EUR), starts near standard cost ----
            unit_cost = std_cost * RNG.normal(1.0, 0.015)

            # FX effect: realized price for non-EUR regions partly reflects local
            # currency translated to EUR. Model an FX headwind on EUR-realized price.
            fx_rate = fx_lookup[(currency, m)]
            fx_base = {"EUR": 1.0, "USD": 0.925, "GBP": 1.155, "CNY": 0.129}[currency]
            fx_factor = fx_rate / fx_base  # 1.0 normally, <1 when local weakens

            # ----------------------------------------------------------------
            # EMBEDDED NARRATIVE: Paints EMEA Q2 2026 margin erosion (~8pp)
            # ----------------------------------------------------------------
            rm_multiplier = 1.0  # raw-material cost multiplier
            if is_paints_emea and m in Q2_2026:
                step = Q2_2026.index(m)  # 0,1,2 across Apr/May/Jun
                # (a) price erosion ~ -3pp: realized price down ~3.5%
                realized_price *= (1.0 - 0.035)
                # (b) adverse FX ~ -2pp: EMEA sells into USD/CNY export markets;
                #     model a EUR-translation headwind on realized price ~2.3%
                realized_price *= (1.0 - 0.023)
                # (c) raw-material spike (TiO2 + resin) ~ +15-20% on raw material,
                #     contributing ~ -3pp to margin. Ramps across the quarter.
                rm_multiplier = 1.0 + (0.15 + 0.025 * step)  # 1.15 -> 1.20

            revenue = units * realized_price
            cogs = units * unit_cost

            # apply raw-material spike to cogs for Paints EMEA Q2
            if rm_multiplier != 1.0:
                # raw material is ~55% of unit cost; spike only that portion
                rm_portion = 0.55
                cogs = units * unit_cost * ((1 - rm_portion) + rm_portion * rm_multiplier)

            revenue = float(_round_money(revenue))
            cogs = float(_round_money(cogs))
            gross_margin = float(_round_money(revenue - cogs))
            gm_pct = round(gross_margin / revenue, 4) if revenue > 0 else 0.0

            actuals.append({
                "sku": sku, "region": region, "month": m,
                "units": int(round(units)),
                "revenue_eur": revenue,
                "cogs_eur": cogs,
                "gross_margin_eur": gross_margin,
                "gross_margin_pct": gm_pct,
            })

            # ---- budget: planned at standard cost & list*base_ratio, no shocks ----
            budget_units = int(round(base_units * seasonal * (1.0 + 0.002 * month_idx)))
            budget_price = list_price * base_price_ratio
            budget_revenue = float(_round_money(budget_units * budget_price))
            budget_cogs = budget_units * std_cost
            budget_margin = float(_round_money(budget_revenue - budget_cogs))
            budget.append({
                "sku": sku, "region": region, "month": m,
                "budget_units": budget_units,
                "budget_revenue_eur": budget_revenue,
                "budget_margin_eur": budget_margin,
            })

            # ---- cost_drivers: decompose cogs into 4 buckets (sum ~= cogs) ----
            # nominal split: raw material 55%, freight 12%, energy 13%, overhead 20%
            raw_share = 0.55
            freight_share = 0.12
            energy_share = 0.13
            overhead_share = 0.20

            base_cogs_no_spike = units * unit_cost
            raw_material = base_cogs_no_spike * raw_share * rm_multiplier
            freight = base_cogs_no_spike * freight_share * RNG.normal(1.0, 0.02)
            energy = base_cogs_no_spike * energy_share * RNG.normal(1.0, 0.02)
            overhead = base_cogs_no_spike * overhead_share * RNG.normal(1.0, 0.02)

            # reconcile bucket sum to actual cogs (close the small rounding/noise gap)
            bucket_sum = raw_material + freight + energy + overhead
            if bucket_sum > 0:
                scale = cogs / bucket_sum
                raw_material *= scale
                freight *= scale
                energy *= scale
                overhead *= scale

            drivers.append({
                "sku": sku, "region": region, "month": m,
                "raw_material_cost": float(_round_money(raw_material)),
                "freight_cost": float(_round_money(freight)),
                "energy_cost": float(_round_money(energy)),
                "overhead": float(_round_money(overhead)),
            })

    return (pd.DataFrame(actuals), pd.DataFrame(budget), pd.DataFrame(drivers))


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_narrative(products, actuals):
    merged = actuals.merge(products[["sku", "product_line"]], on="sku")
    pe = merged[(merged.product_line == "Decorative Paints") & (merged.region == "EMEA")]

    def wavg_gm(df):
        return df.gross_margin_eur.sum() / df.revenue_eur.sum()

    q1 = pe[pe.month.isin(Q1_2026)]
    q2 = pe[pe.month.isin(Q2_2026)]
    q1_gm = wavg_gm(q1)
    q2_gm = wavg_gm(q2)
    drop_pp = (q1_gm - q2_gm) * 100

    # other combos stability check (max abs Q1->Q2 swing)
    other = merged[~((merged.product_line == "Decorative Paints") & (merged.region == "EMEA"))]
    swings = []
    for (ln, rg), g in other.groupby(["product_line", "region"]):
        g1 = g[g.month.isin(Q1_2026)]
        g2 = g[g.month.isin(Q2_2026)]
        if g1.revenue_eur.sum() > 0 and g2.revenue_eur.sum() > 0:
            swings.append(abs(wavg_gm(g1) - wavg_gm(g2)) * 100)
    max_other_swing = max(swings) if swings else 0.0

    return {
        "paints_emea_q1_gm_pct": round(q1_gm * 100, 2),
        "paints_emea_q2_gm_pct": round(q2_gm * 100, 2),
        "drop_pp": round(drop_pp, 2),
        "max_other_combo_q1q2_swing_pp": round(max_other_swing, 2),
    }


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------
def write_readme(out_dir, products, actuals, budget, fx, drivers, checks):
    readme = f"""# Finance Domain — Synthetic Data

Deterministic synthetic dataset for the AkzoNobel (coatings company) Databricks
workshop. Generated by `data/generate_finance.py` with a fixed seed (42), so
output is fully reproducible. Reporting currency is **EUR**.

## Dimensions

- **Time:** 24 monthly periods, `month` as a DATE (first-of-month), from
  `2024-07-01` through `2026-06-01`. Current month = 2026-06.
- **Regions:** EMEA, Americas, APAC, China.
- **Product lines:** Decorative Paints, Performance Coatings.
- **Currencies:** EUR (EMEA), USD (Americas), GBP (APAC), CNY (China). Reporting = EUR.
- **SKUs:** 60 total (30 per product line), generic coatings names (no real trademarks).

## Tables

### `products.parquet`  ({len(products)} rows)
One row per SKU.
| column | description |
|---|---|
| `sku` | SKU id (`DEC-####` decorative, `PFC-####` performance) |
| `product_name` | generic coatings product name |
| `product_line` | Decorative Paints \\| Performance Coatings |
| `region` | EMEA \\| Americas \\| APAC \\| China |
| `currency` | local currency of the SKU's region |
| `list_price_eur` | list price in EUR |
| `standard_cost_eur` | standard unit cost in EUR |

### `margin_actuals.parquet`  ({len(actuals)} rows)
Actual monthly performance per SKU x region. Internally consistent:
`gross_margin_eur = revenue_eur - cogs_eur`, `gross_margin_pct = gross_margin_eur / revenue_eur`.
| column | description |
|---|---|
| `sku`, `region`, `month` | grain |
| `units` | units sold |
| `revenue_eur` | realized revenue in EUR |
| `cogs_eur` | cost of goods sold in EUR |
| `gross_margin_eur` | revenue - cogs |
| `gross_margin_pct` | margin / revenue (fraction, e.g. 0.42 = 42%) |

### `margin_budget.parquet`  ({len(budget)} rows)
Planned/budget figures per SKU x region x month (no shocks — the "plan").
| column | description |
|---|---|
| `sku`, `region`, `month` | grain |
| `budget_units` | planned units |
| `budget_revenue_eur` | planned revenue in EUR |
| `budget_margin_eur` | planned gross margin in EUR |

### `fx_rates.parquet`  ({len(fx)} rows)
Monthly FX rates. `rate_to_eur` converts one unit of local currency to EUR
(EUR = 1.0). USD ~0.92, GBP ~1.16, CNY ~0.13, with monthly drift.
| column | description |
|---|---|
| `currency` | EUR \\| USD \\| GBP \\| CNY |
| `month` | first-of-month DATE |
| `rate_to_eur` | local -> EUR multiplier |

### `cost_drivers.parquet`  ({len(drivers)} rows)
COGS decomposition per SKU x region x month. The four buckets reconcile to
`cogs_eur` in `margin_actuals` (raw material ~55%, freight ~12%, energy ~13%,
overhead ~20%).
| column | description |
|---|---|
| `sku`, `region`, `month` | grain |
| `raw_material_cost` | raw material (TiO2, resin, pigments, solvents) EUR |
| `freight_cost` | inbound/outbound freight EUR |
| `energy_cost` | energy / utilities EUR |
| `overhead` | manufacturing overhead EUR |

## Embedded narrative (the demo signal)

**Paints EMEA** = Decorative Paints product line in region EMEA. Its weighted
gross margin % drops materially in **Q2 2026** (Apr/May/Jun) vs Q1 2026 and vs
budget, while every other region x line combo stays stable. The drop decomposes
roughly into:

- **Price erosion (~ -3pp):** realized price falls ~3.5% in Q2.
- **Adverse FX (~ -2pp):** EUR strengthens vs USD/CNY (~ -2.3% EUR-translation
  headwind on realized price); see `fx_rates` Q2 2026 for USD/CNY.
- **Raw-material spike (~ -3pp):** TiO2 + resin push `raw_material_cost` up
  ~15-20% in Q2; visible in `cost_drivers`.

Volume stays roughly flat.

### Verified numbers (this run)

- Paints EMEA Q1 2026 gross margin %: **{checks['paints_emea_q1_gm_pct']}%**
- Paints EMEA Q2 2026 gross margin %: **{checks['paints_emea_q2_gm_pct']}%**
- Drop: **{checks['drop_pp']} pp**
- Max Q1->Q2 swing across all other region x line combos: **{checks['max_other_combo_q1q2_swing_pp']} pp** (stable)
"""
    with open(os.path.join(out_dir, "README.md"), "w") as f:
        f.write(readme)


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    products = build_products()
    fx = build_fx_rates()
    actuals, budget, drivers = build_actuals_budget_drivers(products, fx)

    # Spark read_files rejects INT64 TIMESTAMP(NANOS); write month at microsecond precision.
    for _df in (actuals, budget, fx, drivers):
        if "month" in _df.columns:
            _df["month"] = pd.to_datetime(_df["month"]).astype("datetime64[us]")

    products.to_parquet(os.path.join(OUT_DIR, "products.parquet"), index=False)
    actuals.to_parquet(os.path.join(OUT_DIR, "margin_actuals.parquet"), index=False)
    budget.to_parquet(os.path.join(OUT_DIR, "margin_budget.parquet"), index=False)
    fx.to_parquet(os.path.join(OUT_DIR, "fx_rates.parquet"), index=False)
    drivers.to_parquet(os.path.join(OUT_DIR, "cost_drivers.parquet"), index=False)

    checks = verify_narrative(products, actuals)
    write_readme(OUT_DIR, products, actuals, budget, fx, drivers, checks)

    print("Wrote parquet files to:", OUT_DIR)
    print(f"  products.parquet        {len(products):>6} rows")
    print(f"  margin_actuals.parquet  {len(actuals):>6} rows")
    print(f"  margin_budget.parquet   {len(budget):>6} rows")
    print(f"  fx_rates.parquet        {len(fx):>6} rows")
    print(f"  cost_drivers.parquet    {len(drivers):>6} rows")
    print()
    print("Narrative verification (Paints EMEA = Decorative Paints x EMEA):")
    print(f"  Q1 2026 gross margin %:        {checks['paints_emea_q1_gm_pct']}%")
    print(f"  Q2 2026 gross margin %:        {checks['paints_emea_q2_gm_pct']}%")
    print(f"  Drop:                          {checks['drop_pp']} pp")
    print(f"  Max other combo Q1->Q2 swing:  {checks['max_other_combo_q1q2_swing_pp']} pp")

    # cost_drivers reconciliation sanity check
    recon = drivers.assign(
        bucket_sum=drivers.raw_material_cost + drivers.freight_cost
        + drivers.energy_cost + drivers.overhead
    ).merge(actuals[["sku", "region", "month", "cogs_eur"]], on=["sku", "region", "month"])
    max_recon_err = (recon.bucket_sum - recon.cogs_eur).abs().max()
    print(f"  Max cost_drivers vs cogs gap:  {max_recon_err:.4f} EUR")


if __name__ == "__main__":
    main()
