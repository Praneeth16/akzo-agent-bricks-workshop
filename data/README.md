# Data — Synthetic AkzoNobel Coatings Dataset + Unity Catalog Loader

This folder holds the shared dataset every tier of the workshop runs on, plus the loader that
lands it in **your** Unity Catalog. Run the loader once before any notebook, starter, or app.

> All data is synthetic. Product names, accounts, suppliers, and documents are invented for the
> workshop. The numbers are engineered so Finance, SCM, and Commercial tell one connected story
> for Q2 2026 (see [the narrative](#the-connected-narrative)).

---

## What you get

The loader lands everything **flat inside your one personal schema** — no `CREATE SCHEMA`
required. That's **13 tables**, **1 volume**, and **14 PDFs**:

| Tables | Holds |
|---|---|
| `products`, `margin_actuals`, `margin_budget`, `fx_rates`, `cost_drivers` | SKU master + monthly P&L, budget, FX, COGS decomposition |
| `otif`, `inventory`, `lanes`, `service_levels` | On-time-in-full, stock, lanes, regional service |
| `accounts`, `pipeline`, `sales_actuals`, `churn_signals` | Accounts, opportunities, realized sales, churn risk |
| (volume `docs_raw`) | 8 safety data sheets + 6 supplier contracts (PDFs) |

Table names are globally unique across the three domains, so they all live side by side in one
schema with no prefix. Per-table column docs live in `output/<domain>/README.md` (finance, scm,
commercial, docs).

---

## Prerequisites

- **A Databricks notebook** (or a serverless/cluster session) — the loader uses `spark.sql()` and
  `dbutils.fs`, which only exist inside a notebook. No CLI, no SQL warehouse, no SDK.
- **A Unity Catalog with a pre-provisioned personal schema** you can write to — the schema itself,
  and `CREATE VOLUME`/`CREATE TABLE` inside it. You do **not** need `CREATE SCHEMA` on the catalog;
  most lab workspaces (e.g. vocareum) only grant one schema per user, named after your email's
  local part, and that's exactly what this loader targets by default.
- **Python 3** with the standard library. The loader itself has no third-party deps.

The parquet and PDF files are **already committed** under `output/`, so you do not need to
generate them. (Regeneration is optional — see [below](#optional-regenerate-the-data).)

---

## Run the loader

Paste `data/load_to_uc.py` into a notebook cell (or `%run data/load_to_uc.py` if the repo is
checked out in your workspace) and run it. No environment variables are required — it
auto-detects your catalog, schema, and staging volume from `current_user()`:

```python
%run ./data/load_to_uc
```

Override any of these with environment variables if the defaults don't fit your workspace:

| Variable | Required | What it is |
|---|---|---|
| `AKZO_CATALOG` | no | Unity Catalog name (default: `dbacademy`) |
| `AKZO_SCHEMA` | no | Target schema (default: local part of your email, e.g. `jane_doe`) |
| `AKZO_STAGING` | no | Staging volume path for the parquet upload (default: auto-detected `/Volumes/<catalog>/ops/<you>`) |

If it can't determine your schema or staging volume, the loader stops with:

```
Could not determine user schema. Set AKZO_SCHEMA env var.
```

The loader is **idempotent** — safe to re-run. It creates the `docs_raw` volume if missing,
re-uploads the parquet, recreates the tables (`CREATE OR REPLACE`), uploads the PDFs, and prints
row counts at the end so you can confirm the load. It never calls `CREATE SCHEMA`.

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
