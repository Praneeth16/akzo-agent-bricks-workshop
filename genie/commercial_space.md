# Genie Space — Akzo Commercial

> Paste the **Instructions** block into the Genie space's *Instructions* field, and add the
> **example SQL** pairs as *Sample / Trusted Questions*. All SQL is Spark SQL against
> `serverless_lakebase_praneeth_catalog.akzo_commercial.*`. Every column below exists in `data/output/commercial/README.md` —
> do not invent columns.

---

## 1. Space title + description

**Title:** Akzo Commercial — Accounts, Pipeline & Churn Risk

**Description:** Ask plain-English questions about AkzoNobel's coatings sales and customers: account
revenue and margin trends, open pipeline by stage and product line, and customer churn-risk signals
(churn score, days since last order, complaints, NPS) — by account, region, segment, and month.
This space is for sales leaders and account managers: it flags *which* accounts are at risk and
*why*, and links revenue erosion to the underlying service/quality problems. Amounts are in **EUR**;
current month is **2026-06**.

---

## 2. Tables in scope

All tables fully-qualified under `serverless_lakebase_praneeth_catalog.akzo_commercial`.

| Table | Purpose | Key columns | Grain |
|---|---|---|---|
| `serverless_lakebase_praneeth_catalog.akzo_commercial.accounts` | Customer / account master | `account_id`, `account_name`, `region` (EMEA/Americas/APAC/China), `segment` (Architectural / Industrial / Marine & Protective / Automotive Refinish), `industry`, `owner_rep` | one row per account |
| `serverless_lakebase_praneeth_catalog.akzo_commercial.pipeline` | Open & closed opportunities | `opp_id`, `account_id`, `stage`, `amount_eur`, `close_month` (DATE), `product_line` (Decorative Paints \| Performance Coatings) | one row per opportunity |
| `serverless_lakebase_praneeth_catalog.akzo_commercial.sales_actuals` | Realized sales per account | `account_id`, `month` (DATE), `revenue_eur`, `volume_units`, `margin_eur` | account × month |
| `serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals` | Monthly churn-risk signals | `account_id`, `month`, `churn_score` (0–1), `last_order_days`, `complaint_count`, `nps` | account × month |

---

## 3. Join hints / relationships

- `churn_signals.account_id = accounts.account_id` — bring in `account_name`, `region`, `segment`, `owner_rep`.
- `sales_actuals.account_id = accounts.account_id` (and `month`) — revenue/margin trend per account.
- `churn_signals` joins to `sales_actuals` on `(account_id, month)` — pair a rising churn score with declining revenue.
- `pipeline.account_id = accounts.account_id` — open opportunity value; use `pipeline.product_line` to see which line an account buys.
- **"Paints EMEA accounts"** = EMEA accounts in the **Architectural** segment (the Decorative-Paints buyers). Confirmed via pipeline: these accounts' opportunities are `product_line = 'Decorative Paints'`. The 8 EMEA-Architectural accounts include the 3 at-risk ones (ACC0001/0002/0003).

---

## 4. Certified metrics / business-term definitions (always use these)

- **churn_risk threshold** — an account is **at churn risk** when `churn_score > 0.7`. Evaluate on the relevant month (default: latest = `2026-06-01`).
- **"why" of churn risk** — read alongside the supporting signals: rising `last_order_days`, rising `complaint_count`, falling `nps`, and declining `sales_actuals.revenue_eur`.
- **"Paints EMEA accounts"** := `accounts.region = 'EMEA' AND accounts.segment = 'Architectural'` (Decorative Paints buyers). The three at-risk ones are **ACC0001 Rhine Valley Decor Distributors, ACC0002 Benelux PaintPro, ACC0003 Nordic Coatings Supply**.
- **open pipeline** — `pipeline` rows whose `stage` is not `ClosedWon`/`ClosedLost`.
- **revenue / margin** — `SUM(revenue_eur)` / `SUM(margin_eur)` from `sales_actuals` over the chosen grain.
- **Quarters (2026):** Q1 = `2026-01-01..2026-03-01`; Q2 = `2026-04-01..2026-06-01`.
- > Narrative anchors (seed 44): Jun-2026 churn_score — ACC0001 **0.865**, ACC0002 **0.827**, ACC0003 **0.800** (all > 0.7); their combined revenue falls from ~€375k (Jan) to ~€169k (Jun). All other accounts stay below ~0.3 and stable. The decline ties to the Paints-EMEA margin + OTIF/service problems (poor service → churn).

---

## 5. General instructions for the space

- Amounts are in **EUR**; current month is **2026-06** (`latest / now` = `2026-06-01`). `month` and `close_month` are DATEs at first-of-month — compare against `'YYYY-MM-01'` literals.
- Use the **churn_score > 0.7** threshold for "at risk" unless the user gives a different cutoff.
- When asked *why* an account is at risk, return the supporting signals (last_order_days, complaint_count, nps) and the revenue trend, not just the score.
- Round churn_score to 3 decimals and EUR to whole euros.
- Prefer the certified definitions in §4.
- Decline politely if asked about gross margin / cost / FX (route to Akzo Finance) or OTIF / inventory / lanes (route to Akzo SCM) — though you may note that poor service is the upstream cause of the churn signals.

---

## 6. Example NL question → SQL pairs

> ⭐ = golden question (must answer the embedded narrative).

### ⭐ Q1. "Which Paints EMEA accounts are at churn risk and why?"

```sql
SELECT
  a.account_id, a.account_name, a.owner_rep,
  ROUND(c.churn_score, 3) AS churn_score,
  c.last_order_days, c.complaint_count, c.nps
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON c.account_id = a.account_id
WHERE a.region = 'EMEA' AND a.segment = 'Architectural'
  AND c.month = DATE'2026-06-01'
  AND c.churn_score > 0.7
ORDER BY c.churn_score DESC;
```
*Answer:* ACC0001 (0.865), ACC0002 (0.827), ACC0003 (0.800) — flagged by high churn_score, long `last_order_days`, multiple complaints, and deeply negative NPS.

### ⭐ Q2. "Show revenue trend for the 3 at-risk EMEA accounts."

```sql
SELECT s.month, ROUND(SUM(s.revenue_eur)) AS revenue_eur
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.sales_actuals s
WHERE s.account_id IN ('ACC0001','ACC0002','ACC0003')
  AND s.month >= DATE'2026-01-01'
GROUP BY s.month
ORDER BY s.month;
```
*Answer:* Combined revenue falls steadily from ~€375k (Jan 2026) to ~€169k (Jun 2026) — accelerating in Q2 alongside the service shock.

### ⭐ Q3. "Which accounts have churn_score above 0.7 in June 2026?"

```sql
SELECT
  a.account_id, a.account_name, a.region, a.segment,
  ROUND(c.churn_score, 3) AS churn_score
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON c.account_id = a.account_id
WHERE c.month = DATE'2026-06-01' AND c.churn_score > 0.7
ORDER BY c.churn_score DESC;
```
*Answer:* Exactly the three EMEA Architectural accounts ACC0001/0002/0003; no other account crosses 0.7.

### Q4. "Show the churn_score trend for ACC0001, ACC0002, ACC0003 across 2026."

```sql
SELECT c.account_id, c.month, ROUND(c.churn_score, 3) AS churn_score
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
WHERE c.account_id IN ('ACC0001','ACC0002','ACC0003')
  AND c.month >= DATE'2026-01-01'
ORDER BY c.account_id, c.month;
```
*Answer:* Scores climb through Q2, crossing 0.7 by June.

### Q5. "Which owner reps cover the at-risk accounts and what is their open pipeline?"

```sql
SELECT
  a.owner_rep,
  COUNT(DISTINCT p.opp_id) AS open_opps,
  ROUND(SUM(p.amount_eur)) AS open_pipeline_eur
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.pipeline p ON p.account_id = a.account_id
WHERE a.account_id IN ('ACC0001','ACC0002','ACC0003')
  AND p.stage NOT IN ('ClosedWon','ClosedLost')
GROUP BY a.owner_rep
ORDER BY open_pipeline_eur DESC;
```

### Q6. "Compare June 2026 churn_score for EMEA Architectural accounts vs the rest of the book."

```sql
SELECT
  CASE WHEN a.region = 'EMEA' AND a.segment = 'Architectural'
       THEN 'Paints EMEA' ELSE 'Other' END AS cohort,
  COUNT(*)                       AS accounts,
  ROUND(AVG(c.churn_score), 3)   AS avg_churn_score,
  ROUND(MAX(c.churn_score), 3)   AS max_churn_score
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON c.account_id = a.account_id
WHERE c.month = DATE'2026-06-01'
GROUP BY 1
ORDER BY avg_churn_score DESC;
```
*Answer:* The Paints EMEA cohort carries the elevated scores; the rest of the book stays low.

### Q7. "What is total revenue and margin by region for June 2026?"

```sql
SELECT a.region,
       ROUND(SUM(s.revenue_eur)) AS revenue_eur,
       ROUND(SUM(s.margin_eur))  AS margin_eur
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.sales_actuals s
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON s.account_id = a.account_id
WHERE s.month = DATE'2026-06-01'
GROUP BY a.region
ORDER BY revenue_eur DESC;
```

### Q8. "Show open Decorative Paints pipeline for EMEA accounts by stage."

```sql
SELECT p.stage,
       COUNT(*)                 AS opps,
       ROUND(SUM(p.amount_eur)) AS pipeline_eur
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.pipeline p
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON p.account_id = a.account_id
WHERE a.region = 'EMEA'
  AND p.product_line = 'Decorative Paints'
  AND p.stage NOT IN ('ClosedWon','ClosedLost')
GROUP BY p.stage
ORDER BY pipeline_eur DESC;
```

### Q9. "Which accounts had the biggest revenue decline Q1→Q2 2026?"

```sql
WITH q AS (
  SELECT account_id,
    CASE WHEN month BETWEEN DATE'2026-01-01' AND DATE'2026-03-01' THEN 'Q1'
         WHEN month BETWEEN DATE'2026-04-01' AND DATE'2026-06-01' THEN 'Q2' END AS qtr,
    revenue_eur
  FROM serverless_lakebase_praneeth_catalog.akzo_commercial.sales_actuals
  WHERE month BETWEEN DATE'2026-01-01' AND DATE'2026-06-01'
)
SELECT a.account_id, a.account_name, a.region,
  ROUND(SUM(CASE WHEN qtr='Q1' THEN revenue_eur END)) AS q1_rev,
  ROUND(SUM(CASE WHEN qtr='Q2' THEN revenue_eur END)) AS q2_rev,
  ROUND(SUM(CASE WHEN qtr='Q2' THEN revenue_eur END)
      - SUM(CASE WHEN qtr='Q1' THEN revenue_eur END)) AS delta_eur
FROM q JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a ON q.account_id = a.account_id
GROUP BY a.account_id, a.account_name, a.region
ORDER BY delta_eur ASC
LIMIT 10;
```
*Answer:* ACC0001/0002/0003 top the decline list.

### Q10. "For the at-risk accounts, show churn_score next to revenue each month in 2026."

```sql
SELECT
  c.account_id, c.month,
  ROUND(c.churn_score, 3) AS churn_score,
  ROUND(s.revenue_eur)    AS revenue_eur,
  c.complaint_count, c.nps
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.sales_actuals s
  ON s.account_id = c.account_id AND s.month = c.month
WHERE c.account_id IN ('ACC0001','ACC0002','ACC0003')
  AND c.month >= DATE'2026-01-01'
ORDER BY c.account_id, c.month;
```
*Answer:* Rising churn_score tracks falling revenue and worsening complaints/NPS — the joined "why" view.
