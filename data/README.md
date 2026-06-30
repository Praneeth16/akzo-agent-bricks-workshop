# Data — Synthetic AkzoNobel Coatings Dataset + Unity Catalog Loader

This folder holds the shared dataset every tier of the workshop runs on, plus the loader that
lands it in **your** Unity Catalog. Run the loader once before any notebook, starter, or app.

> All data is synthetic. Product names, accounts, suppliers, and documents are invented for the
> workshop. The numbers are engineered so Finance, SCM, and Commercial tell one connected story
> for Q2 2026 (see [the narrative](#the-connected-narrative)).

---

## What you get

The loader creates **6 schemas** (all prefixed `akzo_`) in your catalog, plus **12 tables**, **2
volumes**, and **14 PDFs**:

| Schema | Tables | Holds |
|---|---|---|
| `akzo_finance` | `products`, `margin_actuals`, `margin_budget`, `fx_rates`, `cost_drivers` | SKU master + monthly P&L, budget, FX, COGS decomposition |
| `akzo_scm` | `otif`, `inventory`, `lanes`, `service_levels` | On-time-in-full, stock, lanes, regional service |
| `akzo_commercial` | `accounts`, `pipeline`, `sales_actuals`, `churn_signals` | Accounts, opportunities, realized sales, churn risk |
| `akzo_docs` | (volume `raw`) | 8 safety data sheets + 6 supplier contracts (PDFs) |
| `akzo_ops` | (volume `staging`) | Staging for parquet upload; your own eval/output tables later |
| `akzo_gateway` | — | Empty schema for AI Gateway payload logs (L200 chapter 4) |

Per-table column docs live in `output/<domain>/README.md` (finance, scm, commercial, docs).

---

## Prerequisites

- **Databricks CLI** installed and authenticated (`databricks auth login`, or a configured
  profile). The loader drives the CLI's statement-execution + `fs cp` APIs — no SDK needed.
- **A Unity Catalog you can write to**, and a **serverless SQL warehouse**. You need permission to
  `CREATE SCHEMA` and `CREATE VOLUME` in that catalog.
- **Python 3** with the standard library. The loader itself has no third-party deps.

The parquet and PDF files are **already committed** under `output/`, so you do not need to
generate them. (Regeneration is optional — see [below](#optional-regenerate-the-data).)

---

## Run the loader

Set two required environment variables, then run from the repo root:

```bash
AKZO_CATALOG=<your_catalog> \
DATABRICKS_WAREHOUSE_ID=<your_warehouse_id> \
python3 data/load_to_uc.py
```

If you use a named CLI profile, add it:

```bash
AKZO_CATALOG=<your_catalog> \
DATABRICKS_WAREHOUSE_ID=<your_warehouse_id> \
DATABRICKS_CONFIG_PROFILE=<your_profile> \
python3 data/load_to_uc.py
```

| Variable | Required | What it is |
|---|---|---|
| `AKZO_CATALOG` | yes | Your Unity Catalog name (schemas are created as `akzo_*` inside it) |
| `DATABRICKS_WAREHOUSE_ID` | yes | SQL warehouse id (Compute → SQL Warehouses → your warehouse → copy the id) |
| `DATABRICKS_CONFIG_PROFILE` | no | A named CLI profile. Omit to use the CLI's default auth chain. |

If you forget the required vars, the loader stops with:

```
Set AKZO_CATALOG and DATABRICKS_WAREHOUSE_ID (and optionally DATABRICKS_CONFIG_PROFILE) before running this loader.
```

The loader is **idempotent** — safe to re-run. It creates schemas/volumes if missing, re-uploads
the parquet, recreates the tables (`CREATE OR REPLACE`), uploads the PDFs, and prints row counts
at the end so you can confirm the load.

---

## What this loader does NOT do

Two pieces of setup live elsewhere, on purpose:

- **Genie spaces** — created by `../genie/create_genie_spaces.py` (or by hand in the UI). See
  [`../genie/README.md`](../genie/README.md). Run it after this loader, since the spaces attach
  the tables this loader creates.
- **The document vector index** — built inside `../L200-capabilities/05_document_intelligence.py`
  from the PDFs this loader uploads. It needs a Vector Search endpoint.

See [`../SETUP.md`](../SETUP.md) for the full provision-once order across all of these.

---

## The connected narrative

The three domains are engineered to tell one story for **Q2 2026** — AkzoNobel's *Paints EMEA*
gross margin falls ~8.9pp, and the cause traces across all three:

1. **Finance** — Paints EMEA gross margin drops **39.6% → 30.7%**, decomposing into price erosion,
   adverse FX, and a raw-material cost spike; volume flat.
2. **SCM** — the upstream cause: the `Rotterdam-NL->EMEA-DACH` lane lead time steps 5 → 9 days,
   dragging OTIF to ~88.9% and EMEA service to ~90.6% in May, with two key EMEA SKUs stocking out.
3. **Commercial** — the downstream effect: three EMEA Architectural accounts (ACC0001/0002/0003)
   cross `churn_score > 0.7` by June, revenue falling from ~€375k to ~€169k.

A multi-domain supervisor over these three domains connects *margin → service → churn* end to end.
The same "Paints EMEA" lens maps differently per domain (different join keys) — that mapping is the
single source of truth in [`../genie/README.md`](../genie/README.md).

---

## Optional: regenerate the data

The committed parquet/PDFs are deterministic (fixed seeds), so you rarely need this. To rebuild:

```bash
python3 data/generate_finance.py      # 5 finance parquet tables (seed 42)
python3 data/generate_scm.py          # 4 scm parquet tables (seed 43)
python3 data/generate_commercial.py   # 4 commercial parquet tables (seed 44)
python3 data/generate_docs.py         # 8 SDS + 6 contract PDFs  (needs: pip install reportlab)
```

The finance/scm/commercial generators need `numpy`, `pandas`, and `pyarrow`; the docs generator
needs `reportlab`. Each writes into `output/<domain>/` and refreshes that domain's `README.md`.
