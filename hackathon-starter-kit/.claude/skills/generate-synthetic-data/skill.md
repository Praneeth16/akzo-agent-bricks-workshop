---
name: generate-synthetic-data
description: Generate synthetic tables and documents for a hackathon track that needs data the shared setup does not provide.
---

# generate-synthetic-data

Use this skill when a track needs data that the shared `data/` setup does not ship. The provided setup covers Finance, SCM, and Commercial tables plus safety sheets and supplier contracts. Tracks like access provisioning, AI governance, forecast planning, and pricing need extra tables or documents the team must create.

This skill follows the repo's own data pattern so generated data lands the same way as the provided data: deterministic parquet under `data/output/`, then loaded into Unity Catalog by the same loader.

## When To Use

- The track's "Data And Resources" lists a table or document marked team-built.
- You need an entitlement table, audit log, policy document, forecast series, price list, or quote history.
- You want a small, deterministic dataset that re-runs to the same values for a clean demo.

Do not use it to recreate Finance, SCM, or Commercial data that already exists. Reuse the provided tables instead.

## Inputs To Ask For

- Track folder and the specific tables or documents needed
- Team catalog
- Target schema: reuse `akzo_ops` or `akzo_gateway` for team tables, or a new `akzo_<track>` schema
- Columns, types, and grain for each table
- Row volume and any narrative anchors the demo needs
- Whether documents are needed and in what format (PDF or text)

## Build Steps

1. Read the track README and list only the missing resources. Confirm they are not already provided.
2. For each table, write a small deterministic generator in the repo style:
   - fixed random seed
   - explicit column list and dtypes
   - a few rows that encode the demo narrative
   - write parquet to `data/output/<domain>/<table>.parquet`
3. For documents, follow `data/generate_docs.py`: emit the file plus a ground-truth row so extraction can be scored.
4. Load into Unity Catalog. Either:
   - extend the `TABLES` map and run `data/load_to_uc.py` with `AKZO_CATALOG=<catalog>`, or
   - generate a short, idempotent `CREATE OR REPLACE TABLE ... read_files(...)` for the new parquet using the team catalog and schema.
5. Add a ground-truth note (expected rows or expected extracted fields) for the eval set.
6. Print row counts to confirm non-zero loads.

## Output Shape

Return:

- Generator file(s) to create under `data/`
- Parquet output paths
- Load command or SQL for the team catalog and schema
- A ground-truth table for evaluation
- A one-line verification query

## Guardrails

- Keep all data synthetic and clearly labeled synthetic.
- Use a fixed seed so the demo is reproducible.
- Reuse `akzo_ops` and `akzo_gateway` for team tables; do not collide with the provided schemas.
- Never overwrite the provided Finance, SCM, or Commercial tables.
- Validate the catalog name with the same rule the loader uses: letters, digits, and underscore only.
- Tie generated values to the shared narrative where it helps the demo: Paints EMEA margin drop, Rotterdam OTIF drop in May 2026, and accounts ACC0001/0002/0003 churn risk.
