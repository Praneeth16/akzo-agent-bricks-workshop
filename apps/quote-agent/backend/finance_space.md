# Genie Space — Akzo Finance

> Paste the **Instructions** block into the Genie space's *Instructions* field, and add the
> **example SQL** pairs as *Sample / Trusted Questions* (or SQL examples). All SQL is Spark SQL
> against `serverless_lakebase_praneeth_catalog.akzo_finance.*`. Do not invent columns — every column below exists in
> `data/output/finance/README.md`.

---

## 1. Space title + description

**Title:** Akzo Finance — Margin & Variance Controlling

**Description:** Ask plain-English questions about AkzoNobel's coatings gross margin, revenue, cost
of goods, FX exposure, and budget variance — by SKU, product line, region, and month. This space is
for finance controllers and FP&A: it explains *why* margin moved (price vs volume vs FX vs cost),
compares actuals to budget, and drills into raw-material, freight, energy, and overhead cost
buckets. Reporting currency is **EUR** and the current month is **2026-06**.

---

## 2. Tables in scope

All tables fully-qualified under `serverless_lakebase_praneeth_catalog.akzo_finance`.

| Table | Purpose | Key columns | Grain |
|---|---|---|---|
| `serverless_lakebase_praneeth_catalog.akzo_finance.products` | SKU master / product dimension | `sku`, `product_name`, `product_line` (Decorative Paints \| Performance Coatings), `region` (EMEA/Americas/APAC/China), `currency`, `list_price_eur`, `standard_cost_eur` | one row per SKU |
| `serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals` | Realized monthly P&L per SKU×region | `sku`, `region`, `month` (DATE, first-of-month), `units`, `revenue_eur`, `cogs_eur`, `gross_margin_eur`, `gross_margin_pct` (fraction, 0.42 = 42%) | sku × region × month |
| `serverless_lakebase_praneeth_catalog.akzo_finance.margin_budget` | Plan / budget figures (no shocks) | `sku`, `region`, `month`, `budget_units`, `budget_revenue_eur`, `budget_margin_eur` | sku × region × month |
| `serverless_lakebase_praneeth_catalog.akzo_finance.fx_rates` | Monthly FX to EUR | `currency` (EUR/USD/GBP/CNY), `month`, `rate_to_eur` (EUR=1.0) | currency × month |
| `serverless_lakebase_praneeth_catalog.akzo_finance.cost_drivers` | COGS decomposition | `sku`, `region`, `month`, `raw_material_cost`, `freight_cost`, `energy_cost`, `overhead` (EUR; sum reconciles to `cogs_eur`) | sku × region × month |

> Invariants: `gross_margin_eur = revenue_eur - cogs_eur`; `gross_margin_pct = gross_margin_eur / revenue_eur`;
> `raw_material_cost + freight_cost + energy_cost + overhead ≈ cogs_eur`.

---

## 3. Join hints / relationships

- `margin_actuals.sku = products.sku` — bring in `product_line`, `region`, `currency`. (Region also lives on `margin_actuals`; they agree.)
- `cost_drivers` joins to `margin_actuals` on `(sku, region, month)` — use it to split a COGS / cost movement.
- `margin_budget` joins to `margin_actuals` on `(sku, region, month)` — actual-vs-budget variance.
- `fx_rates` joins on `products.currency = fx_rates.currency` and `fx_rates.month = margin_actuals.month` — to attribute the FX-translation component.
- A SKU's local currency comes from `products.currency`; EMEA SKUs are EUR, so EMEA FX impact flows through SKUs sourced/priced in USD/CNY exposure (see the FX rule in §4).

---

## 4. Certified metrics / business-term definitions (always use these)

- **gross_margin_pct (certified)** — `SUM(gross_margin_eur) / SUM(revenue_eur)` when aggregating across rows. **Never average the row-level `gross_margin_pct`**; always re-derive it as a revenue-weighted ratio of the summed EUR amounts.
- **gross_margin_eur** — `revenue_eur - cogs_eur`.
- **"Paints EMEA"** := `products.product_line = 'Decorative Paints' AND products.region = 'EMEA'`. (The EMEA Decorative SKUs are `DEC-1000, DEC-1004, DEC-1008, DEC-1012, DEC-1016, DEC-1020, DEC-1024, DEC-1028`.)
- **Quarters (2026):** Q1 = months `2026-01-01..2026-03-01`; Q2 = months `2026-04-01..2026-06-01`.
- **Budget variance** — `actual - budget` on the matching `(sku, region, month)` grain; favorable when margin actual > budget.
- **Variance decomposition (price / volume / FX / cost)** — explain a gross-margin-% change between two periods as four additive drivers:
  - **Price** — change in realized price per unit (`revenue_eur / units`) holding units constant.
  - **Volume** — change in `units` (mix/scale effect on absolute margin; roughly neutral on margin-% if price and cost are flat).
  - **FX** — EUR-translation effect from `fx_rates.rate_to_eur` moving for the SKU's `currency` between periods (EUR strengthening = headwind on realized EUR revenue).
  - **Cost** — change in unit COGS, drillable into `raw_material_cost`, `freight_cost`, `energy_cost`, `overhead` from `cost_drivers`.
  > For Paints EMEA Q1→Q2 2026 the certified decomposition is ≈ **price −3pp, FX −2pp, raw-material/cost −3pp, volume ~flat**, summing to the ≈ **8.9pp** margin-% drop (39.6% → 30.7%).

---

## 5. General instructions for the space

- Currency is **EUR**; never convert away from EUR unless the user explicitly asks for local currency.
- Current month is **2026-06**; "this month / latest / current" = `2026-06-01`. "Year to date 2026" = `month >= '2026-01-01'`.
- `month` is a DATE at first-of-month — always compare against `'YYYY-MM-01'` literals and filter ranges inclusive of both endpoints.
- Always express margin percentage as the **revenue-weighted certified ratio** (sum of EUR amounts), not an average of `gross_margin_pct`.
- Round percentages to 1 decimal and EUR amounts to whole euros in answers.
- Prefer the certified metric definitions in §4. If a question needs a metric not defined here, say what you computed.
- Decline politely if asked about supply chain (OTIF/inventory/lanes), customer/account/churn, or anything outside finance — route the user to the Akzo SCM or Akzo Commercial space.

---

## 6. Example NL question → SQL pairs

> ⭐ = golden question (must answer the embedded narrative).

### ⭐ Q1. "Why did Paints EMEA gross margin drop in Q2 2026 — is it price, volume, FX, or cost?"

```sql
WITH base AS (
  SELECT
    CASE WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
         WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    m.units, m.revenue_eur, m.cogs_eur, m.gross_margin_eur,
    c.raw_material_cost, c.freight_cost, c.energy_cost, c.overhead
  FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
  JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
  LEFT JOIN serverless_lakebase_praneeth_catalog.akzo_finance.cost_drivers c
    ON c.sku = m.sku AND c.region = m.region AND c.month = m.month
  WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
    AND m.month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
)
SELECT
  qtr,
  SUM(units)                                            AS units,
  ROUND(SUM(revenue_eur) / SUM(units), 2)               AS price_per_unit_eur,
  ROUND(SUM(gross_margin_eur) / SUM(revenue_eur) * 100, 1) AS gross_margin_pct,
  ROUND(SUM(raw_material_cost) / SUM(units), 2)         AS raw_mat_cost_per_unit,
  ROUND(SUM(freight_cost)      / SUM(units), 2)         AS freight_cost_per_unit,
  ROUND(SUM(energy_cost)       / SUM(units), 2)         AS energy_cost_per_unit
FROM base
GROUP BY qtr
ORDER BY qtr;
```
*Answer:* GM% falls ~39.6% (Q1) → ~30.7% (Q2). Price-per-unit drops (price erosion) and raw-material cost-per-unit jumps ~15–20%; volume is roughly flat. Combine with Q2 below for the FX leg.

### ⭐ Q2. "Show Paints EMEA gross margin % by month for 2026."

```sql
SELECT
  m.month,
  ROUND(SUM(m.gross_margin_eur) / SUM(m.revenue_eur) * 100, 1) AS gross_margin_pct,
  SUM(m.revenue_eur) AS revenue_eur
FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
  AND m.month >= DATE'2026-01-01'
GROUP BY m.month
ORDER BY m.month;
```
*Answer:* Stable ~39–40% Jan–Mar, then a clear step-down across Apr/May/Jun 2026.

### ⭐ Q3. "Which region × product line had the biggest margin decline Q1→Q2 2026?"

```sql
WITH q AS (
  SELECT p.product_line, p.region,
    CASE WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
         WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    m.revenue_eur, m.gross_margin_eur
  FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
  JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
  WHERE m.month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
),
g AS (
  SELECT product_line, region, qtr,
    SUM(gross_margin_eur) / SUM(revenue_eur) * 100 AS gm_pct
  FROM q GROUP BY product_line, region, qtr
)
SELECT
  product_line, region,
  ROUND(MAX(CASE WHEN qtr='Q1' THEN gm_pct END), 1) AS q1_gm_pct,
  ROUND(MAX(CASE WHEN qtr='Q2' THEN gm_pct END), 1) AS q2_gm_pct,
  ROUND(MAX(CASE WHEN qtr='Q2' THEN gm_pct END) - MAX(CASE WHEN qtr='Q1' THEN gm_pct END), 1) AS delta_pp
FROM g
GROUP BY product_line, region
ORDER BY delta_pp ASC;
```
*Answer:* Decorative Paints × EMEA shows ~ −8.9pp; every other combo moves < ±1pp.

### Q4. "What is total gross margin and margin % for the whole company in June 2026?"

```sql
SELECT
  SUM(revenue_eur)      AS revenue_eur,
  SUM(gross_margin_eur) AS gross_margin_eur,
  ROUND(SUM(gross_margin_eur) / SUM(revenue_eur) * 100, 1) AS gross_margin_pct
FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals
WHERE month = DATE'2026-06-01';
```

### Q5. "Break down Paints EMEA COGS into raw material, freight, energy, and overhead for Q2 2026."

```sql
SELECT
  ROUND(SUM(c.raw_material_cost)) AS raw_material_cost_eur,
  ROUND(SUM(c.freight_cost))      AS freight_cost_eur,
  ROUND(SUM(c.energy_cost))       AS energy_cost_eur,
  ROUND(SUM(c.overhead))          AS overhead_eur
FROM serverless_lakebase_praneeth_catalog.akzo_finance.cost_drivers c
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON c.sku = p.sku
WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
  AND c.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01';
```
*Answer:* Raw material is the dominant and fastest-rising bucket in Q2.

### Q6. "How did EUR FX rates for USD and CNY move in Q2 2026?"

```sql
SELECT currency, month, rate_to_eur
FROM serverless_lakebase_praneeth_catalog.akzo_finance.fx_rates
WHERE currency IN ('USD','CNY')
  AND month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
ORDER BY currency, month;
```
*Answer:* `rate_to_eur` for USD/CNY drifts down in Q2 (EUR strengthens), the FX headwind leg of the margin story.

### Q7. "Show actual vs budget gross margin for Paints EMEA by month in 2026."

```sql
SELECT
  m.month,
  ROUND(SUM(m.gross_margin_eur))  AS actual_margin_eur,
  ROUND(SUM(b.budget_margin_eur)) AS budget_margin_eur,
  ROUND(SUM(m.gross_margin_eur) - SUM(b.budget_margin_eur)) AS variance_eur
FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.margin_budget b
  ON b.sku = m.sku AND b.region = m.region AND b.month = m.month
WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
  AND m.month >= DATE'2026-01-01'
GROUP BY m.month
ORDER BY m.month;
```
*Answer:* Actuals track budget through Q1, then fall short in Q2 (unfavorable variance).

### Q8. "What is the realized price per unit for Paints EMEA each month in 2026, and is it eroding?"

```sql
SELECT
  m.month,
  SUM(m.units)                                 AS units,
  ROUND(SUM(m.revenue_eur) / SUM(m.units), 2)  AS realized_price_eur
FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
  AND m.month >= DATE'2026-01-01'
GROUP BY m.month
ORDER BY m.month;
```
*Answer:* Realized price/unit drifts down ~3–4% into Q2 — the price-erosion leg.

### Q9. "Top 5 SKUs by margin decline Q1→Q2 2026 within Paints EMEA."

```sql
WITH q AS (
  SELECT m.sku,
    CASE WHEN m.month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
         WHEN m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    m.revenue_eur, m.gross_margin_eur
  FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
  JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
  WHERE p.product_line = 'Decorative Paints' AND p.region = 'EMEA'
    AND m.month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
)
SELECT sku,
  ROUND(MAX(CASE WHEN qtr='Q2' THEN gm_pct END) - MAX(CASE WHEN qtr='Q1' THEN gm_pct END), 1) AS delta_pp
FROM (
  SELECT sku, qtr, SUM(gross_margin_eur)/SUM(revenue_eur)*100 AS gm_pct
  FROM q GROUP BY sku, qtr
) s
GROUP BY sku
ORDER BY delta_pp ASC
LIMIT 5;
```

### Q10. "Compare Paints EMEA Q2 2026 margin % against Decorative Paints in the other three regions."

```sql
WITH q2 AS (
  SELECT p.region, m.revenue_eur, m.gross_margin_eur
  FROM serverless_lakebase_praneeth_catalog.akzo_finance.margin_actuals m
  JOIN serverless_lakebase_praneeth_catalog.akzo_finance.products p ON m.sku = p.sku
  WHERE p.product_line = 'Decorative Paints'
    AND m.month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01'
)
SELECT region,
  ROUND(SUM(gross_margin_eur) / SUM(revenue_eur) * 100, 1) AS q2_gross_margin_pct
FROM q2
GROUP BY region
ORDER BY q2_gross_margin_pct;
```
*Answer:* EMEA is the clear outlier; Americas/APAC/China stay near their stable baseline.
