# Genie Space — Akzo SCM

> Paste the **Instructions** block into the Genie space's *Instructions* field, and add the
> **example SQL** pairs as *Sample / Trusted Questions*. All SQL is Spark SQL against
> `<catalog>.<schema>.*`. Every column below exists in `data/output/scm/README.md` — do not invent columns.

---

## 1. Space title + description

**Title:** Akzo SCM — Service, OTIF & Inventory

**Description:** Ask plain-English questions about AkzoNobel's coatings supply chain: on-time-in-full
(OTIF) delivery performance, inventory health and stockouts, lane lead times and freight cost, and
regional customer service levels — by plant, region, lane, SKU, and month. This space is for supply
chain planners and S&OP: it pinpoints *where* and *why* service slipped (lead-time blowouts,
stockouts, backorders). Distances/costs are in **EUR**; current month is **2026-06**.

---

## 2. Tables in scope

All tables fully-qualified under `<catalog>.<schema>`.

| Table | Purpose | Key columns | Grain |
|---|---|---|---|
| `<catalog>.<schema>.otif` | On-Time-In-Full delivery performance | `plant`, `region` (EMEA/Americas/APAC/China), `lane`, `sku`, `month` (DATE), `orders`, `on_time`, `in_full`, `otif_pct` | plant × region × lane × sku × month |
| `<catalog>.<schema>.inventory` | Inventory health & stockouts | `plant`, `sku`, `month`, `on_hand_units`, `safety_stock`, `days_of_supply`, `stockout_flag` (1=stockout) | plant × sku × month |
| `<catalog>.<schema>.lanes` | Lane master (current values) | `lane_id`, `origin_plant`, `dest_region`, `mode` (road/sea/air), `lead_time_days` (current/Q2 2026), `cost_per_unit` (EUR) | one row per lane |
| `<catalog>.<schema>.service_levels` | Regional customer service | `region`, `month`, `service_pct`, `backorder_units` | region × month |

> SKUs are finance-aligned (`DEC-####` Decorative Paints, `PFC-####` Performance Coatings).
> Plants: Rotterdam-NL, Felling-UK (EMEA); Houston-US, Sao-Paulo-BR (Americas); Shanghai-CN (China); Pune-IN (APAC).

---

## 3. Join hints / relationships

- `otif.lane = lanes.lane_id` — bring in `mode`, `lead_time_days`, `cost_per_unit`, `origin_plant`, `dest_region`.
- `otif.plant = inventory.plant` and `otif.sku = inventory.sku` (and `month`) — connect a service dip to a stockout.
- `service_levels` is region×month only — join to `otif`/`inventory` on `region` + `month` for the regional rollup.
- To make this **"Paints EMEA"**, filter `otif.region = 'EMEA'` and SKUs that are Decorative Paints. The Decorative EMEA SKUs are `DEC-1000, DEC-1004, DEC-1008, DEC-1012, DEC-1016, DEC-1020, DEC-1024, DEC-1028`; or join to `<catalog>.<schema>.products` on `sku` and filter `product_line='Decorative Paints'` for the authoritative list (cross-catalog read, same SKU ids).
- The narrative EMEA lane is **`Rotterdam-NL->EMEA-DACH`**.

---

## 4. Certified metrics / business-term definitions (always use these)

- **OTIF (certified)** — perfect orders / total orders. When aggregating across rows compute it volume-weighted: `SUM(perfect) / SUM(orders)`, where per row `perfect = round(otif_pct * orders)`. **Do not average `otif_pct`** across rows; weight by `orders`. (Row-level `otif_pct` already = perfect/orders, and is ≤ on_time/orders and ≤ in_full/orders.)
- **service_pct** — order-fill / customer service level for a region-month (from `service_levels`); higher is better.
- **stockout** — a row in `inventory` with `stockout_flag = 1` (on-hand critically below safety stock; `days_of_supply` ~1).
- **"Paints EMEA"** := `region = 'EMEA'` AND SKU in Decorative Paints (`sku LIKE 'DEC-%'`, or joined to `products.product_line='Decorative Paints'`).
- **Quarters (2026):** Q1 = `2026-01-01..2026-03-01`; Q2 = `2026-04-01..2026-06-01`.
- **Rising lead time** — a lane whose `lead_time_days` (now in `lanes`) is elevated vs its historical steady value; the narrative lane stepped 5 → 9 days during Q2 2026.
- > Narrative anchors (seed 43): `Rotterdam-NL->EMEA-DACH` OTIF ~95.9% baseline → **88.9% May 2026** → 93.0% Jun; EMEA `service_pct` ~97% → **90.6% May** → 94.5% Jun; EMEA `backorder_units` ~94 → **2,258 May**; **2** key EMEA SKUs stock out at Rotterdam in May. All other regions/lanes ~96% OTIF in May.

---

## 5. General instructions for the space

- Current month is **2026-06**; "latest / now" = `2026-06-01`. `month` is a DATE at first-of-month — compare against `'YYYY-MM-01'` literals.
- Always compute OTIF as the **volume-weighted certified ratio** (`SUM(perfect)/SUM(orders)`), never the average of `otif_pct`.
- Express OTIF and service percentages to 1 decimal; costs in EUR.
- `lanes.lead_time_days` holds the *current* lead time; for historical lead-time trend infer from OTIF/service over `month`, since `otif`/`service_levels` are the time series.
- Prefer the certified definitions in §4.
- Decline politely if asked about gross margin / cost / FX (route to Akzo Finance) or accounts / churn / pipeline (route to Akzo Commercial).

---

## 6. Example NL question → SQL pairs

> ⭐ = golden question (must answer the embedded narrative).

### ⭐ Q1. "Why did OTIF for Paints EMEA drop in May 2026?"

```sql
WITH o AS (
  SELECT month,
         SUM(ROUND(otif_pct * orders)) AS perfect,
         SUM(orders)                   AS orders
  FROM <catalog>.<schema>.otif
  WHERE region = 'EMEA' AND sku LIKE 'DEC-%'
    AND month BETWEEN DATE'2026-03-01' AND DATE'2026-06-01'
  GROUP BY month
)
SELECT o.month,
       ROUND(o.perfect / o.orders * 100, 1) AS otif_pct,
       s.service_pct,
       s.backorder_units
FROM o
JOIN <catalog>.<schema>.service_levels s
  ON s.region = 'EMEA' AND s.month = o.month
ORDER BY o.month;
```
*Answer:* OTIF and service_pct collapse in May 2026 while backorder_units spike (~2,258) — driven by the Rotterdam lane lead-time blowout plus key-SKU stockouts (see Q3/Q6).

### ⭐ Q2. "Which lanes had rising lead times in Q2 2026?"

```sql
-- Flag lanes whose current lead time is high RELATIVE TO THEIR MODE
-- (sea lanes are naturally long; the disruption shows as a road lane that's elevated).
WITH mode_norm AS (
  SELECT mode, AVG(lead_time_days) AS mode_avg_days
  FROM <catalog>.<schema>.lanes GROUP BY mode
)
SELECT l.lane_id, l.origin_plant, l.dest_region, l.mode,
       l.lead_time_days,
       ROUND(n.mode_avg_days, 1)                AS mode_avg_days,
       ROUND(l.lead_time_days - n.mode_avg_days, 1) AS days_above_mode_avg
FROM <catalog>.<schema>.lanes l
JOIN mode_norm n ON l.mode = n.mode
ORDER BY days_above_mode_avg DESC;
```
*Answer:* `Rotterdam-NL->EMEA-DACH` (road, 9 days) is the most-elevated lane vs its mode average (~5.6 days for road) — the disrupted EMEA lane. (Sea lanes like `Pune-IN->APAC-SEA` are longer in absolute days but normal for sea, so they do not top this list.) Corroborate with the lane's OTIF time series in Q5.

### ⭐ Q3. "Which EMEA SKUs stocked out in May 2026?"

```sql
SELECT i.plant, i.sku, i.on_hand_units, i.safety_stock,
       ROUND(i.days_of_supply, 1) AS days_of_supply
FROM <catalog>.<schema>.inventory i
WHERE i.month = DATE'2026-05-01'
  AND i.stockout_flag = 1
  AND i.plant IN ('Rotterdam-NL','Felling-UK')   -- EMEA plants
ORDER BY i.days_of_supply ASC;
```
*Answer:* Two key Decorative ("Paints") EMEA SKUs (e.g. `DEC-1000` Interior Matt Emulsion) stock out at Rotterdam in May with days_of_supply ~1.

### Q4. "Show EMEA service level and backorders by month for 2026."

```sql
SELECT month, service_pct, backorder_units
FROM <catalog>.<schema>.service_levels
WHERE region = 'EMEA' AND month >= DATE'2026-01-01'
ORDER BY month;
```
*Answer:* Steady ~97% until April, dips to ~90.6% in May with backorders spiking, partial recovery in June.

### Q5. "Show monthly OTIF for the Rotterdam-NL->EMEA-DACH lane in 2026."

```sql
SELECT month,
       ROUND(SUM(ROUND(otif_pct * orders)) / SUM(orders) * 100, 1) AS lane_otif_pct,
       SUM(orders) AS orders
FROM <catalog>.<schema>.otif
WHERE lane = 'Rotterdam-NL->EMEA-DACH' AND month >= DATE'2026-01-01'
GROUP BY month
ORDER BY month;
```
*Answer:* ~96% through Q1, down to ~88.9% in May, recovering to ~93% in June.

### Q6. "Compare EMEA OTIF to the other regions in May 2026."

```sql
SELECT region,
       ROUND(SUM(ROUND(otif_pct * orders)) / SUM(orders) * 100, 1) AS otif_pct,
       SUM(orders) AS orders
FROM <catalog>.<schema>.otif
WHERE month = DATE'2026-05-01'
GROUP BY region
ORDER BY otif_pct;
```
*Answer:* EMEA is the clear outlier in May (~lowest); Americas/APAC/China sit ~95.8–96.4%.

### Q7. "List EMEA lanes with their lead time and cost per unit, slowest first."

```sql
SELECT lane_id, mode, lead_time_days, cost_per_unit
FROM <catalog>.<schema>.lanes
WHERE dest_region LIKE 'EMEA%'
ORDER BY lead_time_days DESC, cost_per_unit DESC;
```

### Q8. "Which plant × SKU had the most stockout-months in 2026?"

```sql
SELECT plant, sku, SUM(stockout_flag) AS stockout_months
FROM <catalog>.<schema>.inventory
WHERE month >= DATE'2026-01-01'
GROUP BY plant, sku
HAVING SUM(stockout_flag) > 0
ORDER BY stockout_months DESC, plant, sku
LIMIT 20;
```

### Q9. "What were days of supply for DEC-1000 at Rotterdam through 2026?"

```sql
SELECT month, on_hand_units, safety_stock,
       ROUND(days_of_supply, 1) AS days_of_supply, stockout_flag
FROM <catalog>.<schema>.inventory
WHERE plant = 'Rotterdam-NL' AND sku = 'DEC-1000'
  AND month >= DATE'2026-01-01'
ORDER BY month;
```
*Answer:* Days of supply craters to ~1 in May 2026 with `stockout_flag = 1`.

### Q10. "How many EMEA Paints orders were affected (not perfect) in May 2026?"

```sql
SELECT
  SUM(orders)                              AS total_orders,
  SUM(ROUND(otif_pct * orders))            AS perfect_orders,
  SUM(orders) - SUM(ROUND(otif_pct * orders)) AS non_perfect_orders
FROM <catalog>.<schema>.otif
WHERE region = 'EMEA' AND sku LIKE 'DEC-%' AND month = DATE'2026-05-01';
```
*Answer:* Quantifies the May service gap that fed backorders and the downstream churn risk.
