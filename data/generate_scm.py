"""Deterministic synthetic SCM (supply chain) data generator for the
AkzoNobel coatings Databricks workshop.

Produces join-able parquet tables under data/output/scm/ that share the same
dimensional grain (sku x region x month) as the finance generator, plus an
embedded narrative: Paints EMEA OTIF collapses in May 2026 (lane lead-time
blowout + a stockout on key EMEA SKUs) and recovers only partially in June.
That supply/service shock is the SCM-side cause that ties to the finance
Paints-EMEA Q2 margin story.

Stdlib + numpy + pandas + pyarrow only. Fixed seed for full determinism.
"""

import os

import numpy as np
import pandas as pd

SEED = 43
rng = np.random.default_rng(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output", "scm")
FINANCE_PRODUCTS = os.path.join(HERE, "output", "finance", "products.parquet")

# ---------------------------------------------------------------------------
# Dimensions (match the finance generator so tables join cleanly)
# ---------------------------------------------------------------------------

# 24 monthly periods, first-of-month, 2024-07-01 .. 2026-06-01 (current = 2026-06).
MONTHS = pd.date_range("2024-07-01", "2026-06-01", freq="MS")
CURRENT_MONTH = pd.Timestamp("2026-06-01")

REGIONS = ["EMEA", "Americas", "APAC", "China"]

# 6 plants, each mapped to a region.
PLANTS = {
    "Rotterdam-NL": "EMEA",
    "Felling-UK": "EMEA",
    "Houston-US": "Americas",
    "Shanghai-CN": "China",
    "Pune-IN": "APAC",
    "Sao-Paulo-BR": "Americas",
}

# The narrative lane: a Rotterdam-origin EMEA lane.
NARRATIVE_LANE = "Rotterdam-NL->EMEA-DACH"
NARRATIVE_PLANT = "Rotterdam-NL"
NARRATIVE_REGION = "EMEA"

# ~10 lanes: origin_plant -> dest_region, with mode + base lead time + cost.
# (origin_plant, dest_region_label, mode, base_lead_time_days, cost_per_unit)
LANE_DEFS = [
    (NARRATIVE_LANE, "Rotterdam-NL", "EMEA-DACH", "road", 5, 2.10),
    ("Rotterdam-NL->EMEA-Nordics", "Rotterdam-NL", "EMEA-Nordics", "sea", 8, 1.75),
    ("Felling-UK->EMEA-UKI", "Felling-UK", "EMEA-UKI", "road", 4, 1.95),
    ("Houston-US->Americas-North", "Houston-US", "Americas-North", "road", 6, 2.30),
    ("Houston-US->Americas-South", "Houston-US", "Americas-South", "sea", 12, 1.60),
    ("Sao-Paulo-BR->Americas-LatAm", "Sao-Paulo-BR", "Americas-LatAm", "road", 7, 2.05),
    ("Shanghai-CN->China-East", "Shanghai-CN", "China-East", "road", 3, 1.40),
    ("Shanghai-CN->China-Inland", "Shanghai-CN", "China-Inland", "road", 6, 1.55),
    ("Pune-IN->APAC-India", "Pune-IN", "APAC-India", "road", 4, 1.50),
    ("Pune-IN->APAC-SEA", "Pune-IN", "APAC-SEA", "sea", 14, 1.30),
    ("Shanghai-CN->APAC-Pacific", "Shanghai-CN", "APAC-Pacific", "air", 5, 4.20),
]

# Map each lane to a dimension region for the otif/service grain.
DEST_TO_REGION = {
    "EMEA-DACH": "EMEA",
    "EMEA-Nordics": "EMEA",
    "EMEA-UKI": "EMEA",
    "Americas-North": "Americas",
    "Americas-South": "Americas",
    "Americas-LatAm": "Americas",
    "China-East": "China",
    "China-Inland": "China",
    "APAC-India": "APAC",
    "APAC-SEA": "APAC",
    "APAC-Pacific": "APAC",
}


def load_skus():
    """Reuse exact finance sku ids if available, else generate SKU0001..SKU0060.

    Returns a DataFrame with sku, product_line, region.
    """
    if os.path.exists(FINANCE_PRODUCTS):
        prod = pd.read_parquet(FINANCE_PRODUCTS)
        cols = {c.lower(): c for c in prod.columns}
        sku_col = cols.get("sku")
        pl_col = cols.get("product_line")
        reg_col = cols.get("region")
        df = pd.DataFrame({"sku": prod[sku_col].astype(str)})
        df["product_line"] = (
            prod[pl_col].astype(str) if pl_col else "Decorative"
        )
        df["region"] = prod[reg_col].astype(str) if reg_col else None
        return df

    # Deterministic fallback: SKU0001..SKU0060.
    n = 60
    skus = [f"SKU{i:04d}" for i in range(1, n + 1)]
    # First half Decorative (the "Paints" line), second half Performance Coatings.
    product_line = ["Decorative"] * 30 + ["Performance Coatings"] * 30
    # Assign a home region round-robin so each region has SKUs.
    region = [REGIONS[i % len(REGIONS)] for i in range(n)]
    return pd.DataFrame({"sku": skus, "product_line": product_line, "region": region})


PRODUCTS = load_skus()
ALL_SKUS = PRODUCTS["sku"].tolist()

# Key EMEA "Paints" SKUs (Decorative + EMEA) that suffer the May 2026 stockout.
# Prefer EMEA Decorative SKUs; fall back progressively if metadata is absent.
_is_deco = PRODUCTS["product_line"].str.contains("Decor", case=False, na=False)
_is_emea = PRODUCTS["region"].astype(str).str.upper().eq("EMEA")
_emea_deco = PRODUCTS[_is_deco & _is_emea]
_deco = PRODUCTS[_is_deco]
if len(_emea_deco) >= 2:
    KEY_EMEA_SKUS = _emea_deco["sku"].tolist()[:2]
elif len(_deco) >= 2:
    KEY_EMEA_SKUS = _deco["sku"].tolist()[:2]
else:
    KEY_EMEA_SKUS = ALL_SKUS[:2]


def month_index(ts):
    return int(np.where(MONTHS == ts)[0][0])


# ---------------------------------------------------------------------------
# Table: lanes
# ---------------------------------------------------------------------------

def build_lanes():
    """Static lane master.

    lead_time_days is the *current* (Q2 2026) value, so the narrative lane
    shows the elevated lead time; per-month lead time lives in the otif logic.
    """
    rows = []
    for lane_id, origin, dest, mode, base_lt, cost in LANE_DEFS:
        # Narrative lane: current lead time reflects the Q2 2026 blowout (5 -> 9).
        lead = 9 if lane_id == NARRATIVE_LANE else base_lt
        rows.append(
            {
                "lane_id": lane_id,
                "origin_plant": origin,
                "dest_region": dest,
                "mode": mode,
                "lead_time_days": int(lead),
                "cost_per_unit": round(float(cost), 2),
            }
        )
    return pd.DataFrame(rows)


def lane_lead_time(lane_id, base_lt, month):
    """Per-month lead time. Narrative lane steps 5 -> 9 across Q2 2026."""
    if lane_id != NARRATIVE_LANE:
        return base_lt
    # Q2 2026 = Apr/May/Jun 2026. Ramp: Apr 7, May 9, Jun 8 (partial recovery).
    if month == pd.Timestamp("2026-04-01"):
        return 7
    if month == pd.Timestamp("2026-05-01"):
        return 9
    if month == pd.Timestamp("2026-06-01"):
        return 8
    return base_lt


# ---------------------------------------------------------------------------
# Table: otif
# ---------------------------------------------------------------------------
# Grain: plant x region x lane x sku x month.
# Each lane carries a basket of SKUs from its origin plant's region. To keep the
# table workshop-sized we assign ~5 SKUs per lane deterministically.

def skus_for_lane(lane_idx):
    """Deterministic ~5-SKU basket per lane, drawn round-robin from ALL_SKUS."""
    k = 5
    start = (lane_idx * k) % len(ALL_SKUS)
    picks = [ALL_SKUS[(start + j) % len(ALL_SKUS)] for j in range(k)]
    # Ensure the narrative lane carries the key EMEA SKUs so the stockout bites.
    if LANE_DEFS[lane_idx][0] == NARRATIVE_LANE:
        for s in KEY_EMEA_SKUS:
            if s not in picks:
                picks[-1] = s if picks[-1] not in KEY_EMEA_SKUS else picks[-1]
        # force-include both key skus
        merged = list(dict.fromkeys(KEY_EMEA_SKUS + picks))[:k]
        picks = merged
    return picks


def build_otif():
    rows = []
    for li, (lane_id, origin, dest, mode, base_lt, cost) in enumerate(LANE_DEFS):
        region = DEST_TO_REGION[dest]
        basket = skus_for_lane(li)
        # Baseline OTIF for the lane ~ 96% with tiny per-lane offset.
        lane_base = 0.96 + rng.uniform(-0.005, 0.005)
        for sku in basket:
            for month in MONTHS:
                # Orders: stable monthly volume with small noise + light seasonality.
                seasonal = 1.0 + 0.05 * np.sin(2 * np.pi * (month.month / 12.0))
                orders = int(max(40, rng.normal(220, 25) * seasonal))

                otif_target = lane_base + rng.normal(0, 0.008)

                # --- Embedded narrative shock (Paints EMEA, Rotterdam lane) ---
                if lane_id == NARRATIVE_LANE:
                    lt = lane_lead_time(lane_id, base_lt, month)
                    # Lead-time blowout degrades on-time directly.
                    if month == pd.Timestamp("2026-05-01"):
                        otif_target = 0.915 + rng.normal(0, 0.004)  # non-key SKUs
                    elif month == pd.Timestamp("2026-06-01"):
                        otif_target = 0.93 + rng.normal(0, 0.004)  # partial recovery
                    elif month == pd.Timestamp("2026-04-01"):
                        otif_target = 0.945 + rng.normal(0, 0.004)  # early slip
                    # Key EMEA SKUs hit by the May stockout drop harder (in-full fails).
                    if sku in KEY_EMEA_SKUS and month == pd.Timestamp("2026-05-01"):
                        otif_target = 0.855 + rng.normal(0, 0.005)

                otif_target = float(np.clip(otif_target, 0.5, 0.999))

                # Decompose into on_time and in_full such that
                # otif = (on_time AND in_full) / orders is consistent.
                # Model perfect orders = on_time AND in_full directly.
                perfect = int(round(orders * otif_target))
                perfect = min(perfect, orders)

                # on_time and in_full are each >= perfect (perfect is the AND).
                # Add small independent slack so on_time/in_full read realistically.
                slack_ot = int(round(rng.uniform(0.0, 0.03) * orders))
                slack_if = int(round(rng.uniform(0.0, 0.03) * orders))
                # During the stockout, in_full is the binding constraint on key SKUs.
                if sku in KEY_EMEA_SKUS and month == pd.Timestamp("2026-05-01"):
                    slack_if = 0  # in_full collapses to ~perfect
                    slack_ot = int(round(rng.uniform(0.02, 0.04) * orders))

                on_time = min(orders, perfect + slack_ot)
                in_full = min(orders, perfect + slack_if)
                # perfect = orders that are BOTH on-time AND in-full, so it is the
                # binding overlap and must not exceed either component count.
                perfect = min(perfect, on_time, in_full)
                # Truncate (not round) so otif_pct never rounds above the true ratio.
                otif_pct = np.floor(perfect / orders * 10000) / 10000 if orders else 0.0

                rows.append(
                    {
                        "plant": origin,
                        "region": region,
                        "lane": lane_id,
                        "sku": sku,
                        "month": month.date(),
                        "orders": int(orders),
                        "on_time": int(on_time),
                        "in_full": int(in_full),
                        "otif_pct": float(otif_pct),
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table: inventory
# ---------------------------------------------------------------------------
# Grain: plant x sku x month. Each plant stocks the SKUs that ship on its lanes.

def plant_sku_pairs():
    pairs = {}
    for li, (lane_id, origin, dest, mode, base_lt, cost) in enumerate(LANE_DEFS):
        basket = skus_for_lane(li)
        pairs.setdefault(origin, set()).update(basket)
    return {p: sorted(s) for p, s in pairs.items()}


def build_inventory():
    rows = []
    pairs = plant_sku_pairs()
    for plant, skus in pairs.items():
        for sku in skus:
            safety = int(max(200, rng.normal(800, 120)))
            base_on_hand = int(rng.normal(2600, 300))
            for month in MONTHS:
                on_hand = int(max(0, rng.normal(base_on_hand, 180)))
                daily_demand = max(1.0, rng.normal(90, 12))
                stockout = 0

                # --- Narrative stockout: key EMEA SKUs at Rotterdam, May 2026 ---
                is_key = (
                    plant == NARRATIVE_PLANT
                    and sku in KEY_EMEA_SKUS
                )
                if is_key and month == pd.Timestamp("2026-05-01"):
                    on_hand = int(rng.uniform(80, 220))  # well below safety stock
                    stockout = 1
                elif is_key and month == pd.Timestamp("2026-04-01"):
                    on_hand = int(safety * rng.uniform(0.85, 1.0))  # drawing down
                elif is_key and month == pd.Timestamp("2026-06-01"):
                    on_hand = int(safety * rng.uniform(1.0, 1.2))  # rebuilding

                days_of_supply = round(on_hand / daily_demand, 1)
                if days_of_supply < 2.0 and stockout == 0 and not is_key:
                    # generic safety net so non-narrative noise rarely flags
                    on_hand = int(safety * rng.uniform(1.1, 1.4))
                    days_of_supply = round(on_hand / daily_demand, 1)

                rows.append(
                    {
                        "plant": plant,
                        "sku": sku,
                        "month": month.date(),
                        "on_hand_units": int(on_hand),
                        "safety_stock": int(safety),
                        "days_of_supply": float(days_of_supply),
                        "stockout_flag": int(stockout),
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table: service_levels
# ---------------------------------------------------------------------------
# Grain: region x month.

def build_service_levels():
    rows = []
    for region in REGIONS:
        base = 0.97 + rng.uniform(-0.005, 0.005)
        for month in MONTHS:
            service = base + rng.normal(0, 0.005)
            backorder = int(max(0, rng.normal(120, 40)))

            # --- Narrative: EMEA service dips in May 2026, backorders spike ---
            if region == NARRATIVE_REGION:
                if month == pd.Timestamp("2026-05-01"):
                    service = 0.905 + rng.normal(0, 0.004)
                    backorder = int(rng.uniform(1900, 2300))  # spike
                elif month == pd.Timestamp("2026-06-01"):
                    service = 0.945 + rng.normal(0, 0.004)  # partial recovery
                    backorder = int(rng.uniform(700, 1000))
                elif month == pd.Timestamp("2026-04-01"):
                    service = 0.955 + rng.normal(0, 0.004)
                    backorder = int(rng.uniform(300, 500))

            service = float(np.clip(service, 0.5, 0.999))
            rows.append(
                {
                    "region": region,
                    "month": month.date(),
                    "service_pct": round(service, 4),
                    "backorder_units": int(backorder),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Write + verify
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    lanes = build_lanes()
    otif = build_otif()
    inventory = build_inventory()
    service = build_service_levels()

    tables = {
        "lanes": lanes,
        "otif": otif,
        "inventory": inventory,
        "service_levels": service,
    }
    for name, df in tables.items():
        path = os.path.join(OUT_DIR, f"{name}.parquet")
        df.to_parquet(path, engine="pyarrow", index=False)
        print(f"wrote {name:14s} rows={len(df):6d} -> {path}")

    # --- Verification: narrative OTIF signal ---
    print("\n=== Verification: Paints EMEA narrative ===")
    lane_otif = otif[otif["lane"] == NARRATIVE_LANE]

    def lane_otif_for(month):
        sub = lane_otif[lane_otif["month"] == month]
        # volume-weighted OTIF = sum(perfect)/sum(orders)
        perfect = (sub["otif_pct"] * sub["orders"]).sum()
        return round(perfect / sub["orders"].sum(), 4)

    baseline_months = [pd.Timestamp(d).date() for d in
                       ["2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01"]]
    base_vals = [lane_otif_for(m) for m in baseline_months]
    baseline = round(float(np.mean(base_vals)), 4)
    may = lane_otif_for(pd.Timestamp("2026-05-01").date())
    jun = lane_otif_for(pd.Timestamp("2026-06-01").date())
    apr = lane_otif_for(pd.Timestamp("2026-04-01").date())

    print(f"  lane                  : {NARRATIVE_LANE}")
    print(f"  baseline OTIF (Dec-Mar): {baseline:.1%}")
    print(f"  Apr 2026 OTIF         : {apr:.1%}")
    print(f"  May 2026 OTIF         : {may:.1%}   <-- should be ~89%")
    print(f"  Jun 2026 OTIF         : {jun:.1%}   <-- partial recovery")

    # stockout check
    inv_key = inventory[
        (inventory["plant"] == NARRATIVE_PLANT)
        & (inventory["sku"].isin(KEY_EMEA_SKUS))
        & (inventory["month"] == pd.Timestamp("2026-05-01").date())
    ]
    print(f"\n  key EMEA SKUs         : {KEY_EMEA_SKUS}")
    print(f"  May-2026 stockout rows: {int(inv_key['stockout_flag'].sum())} flagged")
    print(f"  May-2026 days_of_supply: {inv_key['days_of_supply'].tolist()}")

    # service level check
    svc = service[service["region"] == "EMEA"]
    svc_may = svc[svc["month"] == pd.Timestamp("2026-05-01").date()]
    svc_base = svc[svc["month"].isin(baseline_months)]["backorder_units"].mean()
    print(f"\n  EMEA service May 2026 : {svc_may['service_pct'].iloc[0]:.1%}")
    print(f"  EMEA backorders May   : {int(svc_may['backorder_units'].iloc[0])} "
          f"(baseline ~{int(svc_base)})")

    # confirm other regions stable in May
    print("\n  Other-region OTIF May 2026 (should stay ~96%):")
    for region in REGIONS:
        sub = otif[(otif["region"] == region) & (otif["lane"] != NARRATIVE_LANE)
                   & (otif["month"] == pd.Timestamp("2026-05-01").date())]
        if len(sub):
            wv = (sub["otif_pct"] * sub["orders"]).sum() / sub["orders"].sum()
            print(f"    {region:10s}: {wv:.1%}")

    return tables


if __name__ == "__main__":
    main()
