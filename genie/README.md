# Genie Spaces — Prebuilt Configs (Akzo Coatings Workshop)

This folder holds the **prebuilt Genie space configurations** for the three workshop domains.
Each file is what the **facilitator pastes into the corresponding Databricks Genie space** before
the session — the space *Instructions* plus a set of curated example NL→SQL pairs (add them as
*Sample / Trusted Questions* or SQL examples). Pre-loading these makes Genie answer the demo's
golden questions reliably and consistently on the first try.

| File | Genie space name | Catalog.schema |
|---|---|---|
| [`finance_space.md`](finance_space.md) | **Akzo Finance** | `<catalog>.akzo_finance` |
| [`scm_space.md`](scm_space.md) | **Akzo SCM** | `<catalog>.akzo_scm` |
| [`commercial_space.md`](commercial_space.md) | **Akzo Commercial** | `<catalog>.akzo_commercial` |

> Catalog = your workshop catalog `<catalog>` (schemas prefixed `akzo_`). All SQL is Spark SQL written
> against the real columns documented in `data/output/<domain>/README.md` — no invented columns.

## Prerequisites

- The data is loaded — run [`../data/load_to_uc.py`](../data/README.md) first, so the
  `akzo_finance` / `akzo_scm` / `akzo_commercial` tables exist for the spaces to attach.
- A **serverless SQL warehouse** (the spaces run their SQL on it) and a catalog you can read.
- To create spaces from code: the **Databricks Python SDK** (`pip install databricks-sdk`) and
  permission to create Genie spaces in the workspace.

## Two ways to create the spaces

### Option A — from code (recommended)

[`create_genie_spaces.py`](create_genie_spaces.py) creates all three spaces, seeds each with the
prebuilt config, prints the ids, and writes them to `space_ids.json`:

```bash
AKZO_CATALOG=<catalog> DATABRICKS_WAREHOUSE_ID=<id> python3 genie/create_genie_spaces.py
# or, with a named CLI profile:
python3 genie/create_genie_spaces.py --profile <your_profile>
```

It reads `AKZO_CATALOG` + `DATABRICKS_WAREHOUSE_ID` from the environment (and stops with
`Set AKZO_CATALOG and DATABRICKS_WAREHOUSE_ID before running.` if either is missing). It is
**idempotent** — a space whose title already exists is trashed and recreated, so re-running
re-seeds cleanly. Output:

```
Wrote genie/space_ids.json: {"finance": "...", "scm": "...", "commercial": "..."}
```

`space_ids.json` is generated per-workspace and git-ignored — it never ships with private ids.

### Option B — by hand in the UI

Use the facilitator steps [below](#how-to-use-facilitator). Create each space, attach the tables,
and paste the config from the matching `*_space.md`.

## Get each space id (to paste into notebooks / apps)

Whichever way you created the spaces, the downstream materials need each space's **id**:

1. Open a space in the Databricks UI.
2. The id is the **last URL segment** of `/genie/rooms/<space_id>` — copy it.
3. Paste it where prompted:
   - **L200 chapter 1 notebook** — the `finance_space_id` / `scm_space_id` / `commercial_space_id`
     widgets at the top of `../L200-capabilities/01_governed_supervisor.py`.
   - **Supervisor app** — the `FINANCE_SPACE_ID` / `SCM_SPACE_ID` / `COMMERCIAL_SPACE_ID` env vars
     in `../apps/supervisor/app.yaml` (or `.env` locally).

Leave a field **blank** to fall back to the in-code `ai_query` reproduction — the notebook still
runs anywhere, it just doesn't call the real Genie space for that domain.

## How to use (facilitator)

1. Create (or open) each Genie space and attach the listed tables (catalog <catalog>, schemas akzo_finance/akzo_scm/akzo_commercial).
2. Open the matching `*_space.md` file:
   - Copy **§5 General instructions** + the **§4 certified metric / business-term definitions** into the space *Instructions* field.
   - Add the **§6 example NL → SQL pairs** as the space's sample/trusted questions (paste the SQL as the curated answer).
3. Smoke-test each space with the ⭐ golden questions in §6 — they should reproduce the embedded narrative.

## Troubleshooting

- **`Set AKZO_CATALOG and DATABRICKS_WAREHOUSE_ID before running.`** — export both env vars (see
  [`../SETUP.md`](../SETUP.md) step 1) before running the script.
- **Space created but answers are wrong / out of scope** — confirm the tables are attached and the
  **§4 + §5** instructions are pasted into the space *Instructions* field; that is what keeps Genie
  on the certified metrics.
- **Permission denied creating a space** — you need rights to create Genie spaces and `SELECT` on
  the `akzo_*` schemas. Ask your workspace admin, or use Option B by hand under an account that has
  them.

## Each file contains

1. **Space title + description** — business-user framing.
2. **Tables in scope** — fully-qualified `<catalog>.akzo_<schema>.<table>`, purpose, key columns, grain.
3. **Join hints / relationships** — how the tables connect.
4. **Certified metrics / business-term definitions** — the canonical formulas Genie must use.
5. **General instructions** — currency (EUR), current month (2026-06), prefer certified metrics, decline out-of-scope.
6. **8–12 example NL → SQL pairs**, including the ⭐ golden questions per domain.

## How "Paints EMEA" maps to filters (single source of truth)

"Paints EMEA" is the recurring demo lens. It maps **differently per domain** because the join keys differ:

| Domain | "Paints EMEA" filter |
|---|---|
| **Finance** | Join `margin_actuals.sku = products.sku`, then `product_line = 'Decorative Paints' AND region = 'EMEA'`. EMEA Decorative SKUs: `DEC-1000, DEC-1004, DEC-1008, DEC-1012, DEC-1016, DEC-1020, DEC-1024, DEC-1028`. |
| **SCM** | `otif/inventory` filtered to `region = 'EMEA'` + Decorative SKUs (`sku LIKE 'DEC-%'`, or join to `<catalog>.akzo_finance.products` where `product_line = 'Decorative Paints'`). Narrative lane = `Rotterdam-NL->EMEA-DACH`; EMEA plants = Rotterdam-NL, Felling-UK. |
| **Commercial** | `accounts.region = 'EMEA' AND accounts.segment = 'Architectural'` (the Decorative-Paints buyers). The 3 at-risk accounts are `ACC0001`, `ACC0002`, `ACC0003`. |

Other shared conventions: `month` (and `close_month`) are DATEs at first-of-month — compare against
`'YYYY-MM-01'` literals. **Q1 2026** = `2026-01-01..2026-03-01`; **Q2 2026** = `2026-04-01..2026-06-01`.
Reporting currency is **EUR**; current month is **2026-06**.

## The connected narrative (across all three spaces)

The data is engineered so the three domains tell one story for **Q2 2026**:

1. **Finance** — Paints EMEA gross margin drops ~8.9pp (39.6% → 30.7%), decomposing into price erosion (~−3pp), adverse FX (~−2pp), and a raw-material cost spike (~−3pp); volume flat.
2. **SCM** — the upstream cause: the `Rotterdam-NL->EMEA-DACH` lane lead time steps 5 → 9 days, dragging OTIF to ~88.9% and EMEA service to ~90.6% in May, with two key EMEA SKUs stocking out and backorders spiking to ~2,258.
3. **Commercial** — the downstream effect: three EMEA Architectural ("Paints") accounts (ACC0001/0002/0003) cross `churn_score > 0.7` by June, with revenue falling from ~€375k (Jan) to ~€169k (Jun), rising complaints, and negative NPS.

A Multi-Agent Supervisor over these three spaces can therefore connect *margin → service → churn* end-to-end.
