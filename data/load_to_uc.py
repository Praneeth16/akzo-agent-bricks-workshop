#!/usr/bin/env python3
"""Load synthetic data + docs into Unity Catalog on the workshop workspace.

Drives the authed Databricks CLI (statement execution API + `fs cp`).
Idempotent: safe to re-run. No SDK dependency.

Configure with environment variables before running:
  AKZO_CATALOG               your Unity Catalog (required)
  DATABRICKS_WAREHOUSE_ID    your SQL warehouse id (required)
  DATABRICKS_CONFIG_PROFILE  your CLI profile (optional; falls back to the CLI default auth)

Usage: AKZO_CATALOG=<catalog> DATABRICKS_WAREHOUSE_ID=<id> python3 data/load_to_uc.py
"""
import json
import os
import subprocess
import sys
import time

PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE")  # None -> use CLI default auth chain
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID")
# No CREATE CATALOG perm on metastore -> use owned managed catalog + akzo_ schema prefix.
CATALOG = os.environ.get("AKZO_CATALOG")

if not CATALOG or not WAREHOUSE_ID:
    sys.exit(
        "Set AKZO_CATALOG and DATABRICKS_WAREHOUSE_ID (and optionally "
        "DATABRICKS_CONFIG_PROFILE) before running this loader."
    )
PFX = "akzo_"  # schema prefix; qualified name = CATALOG.akzo_<domain>.<table>
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "output")

# parquet table -> domain (schema = PFX+domain)
TABLES = {
    "finance": ["products", "margin_actuals", "margin_budget", "fx_rates", "cost_drivers"],
    "scm": ["otif", "inventory", "lanes", "service_levels"],
    "commercial": ["accounts", "pipeline", "sales_actuals", "churn_signals"],
}
DOMAINS = ["finance", "scm", "commercial", "docs", "ops", "gateway"]
SCHEMAS = [PFX + d for d in DOMAINS]
STAGING = f"/Volumes/{CATALOG}/{PFX}ops/staging"
DOCS_RAW = f"/Volumes/{CATALOG}/{PFX}docs/raw"


def cli(args, capture=True):
    profile_args = ["-p", PROFILE] if PROFILE else []
    return subprocess.run(
        ["databricks", *args, *profile_args],
        capture_output=capture, text=True,
    )


def _retryable(text):
    return "REQUEST_LIMIT_EXCEEDED" in text or "rate limit" in text.lower()


def run_sql(stmt, label=None):
    payload = {"warehouse_id": WAREHOUSE_ID, "statement": stmt, "wait_timeout": "50s"}
    for attempt in range(6):
        r = cli(["api", "post", "/api/2.0/sql/statements", "--json", json.dumps(payload)])
        if r.returncode != 0 and _retryable(r.stderr):
            time.sleep(5 * (attempt + 1)); continue
        break
    if r.returncode != 0:
        print(f"  ! CLI error: {r.stderr[:300]}")
        return False
    d = json.loads(r.stdout)
    sid = d.get("statement_id")
    state = d.get("status", {}).get("state")
    while state in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = cli(["api", "get", f"/api/2.0/sql/statements/{sid}"])
        d = json.loads(r.stdout)
        state = d.get("status", {}).get("state")
    ok = state == "SUCCEEDED"
    tag = label or stmt[:60]
    if ok:
        print(f"  ok  {tag}")
    else:
        err = d.get("status", {}).get("error", {})
        print(f"  FAIL {tag}: {err.get('message','')[:300]}")
    return ok if ok else d


def upload(local, dest):
    for attempt in range(8):
        r = cli(["fs", "cp", "--overwrite", local, dest])
        if r.returncode == 0:
            break
        if _retryable(r.stderr):
            time.sleep(4 * (attempt + 1)); continue
        break
    ok = r.returncode == 0
    print(f"  {'ok ' if ok else 'FAIL'} upload {os.path.basename(local)} -> {dest}")
    if not ok:
        print(f"      {r.stderr[:200]}")
    time.sleep(1)  # gentle pacing between uploads
    return ok


def main():
    print(f"== schemas (catalog={CATALOG}) ==")
    for s in SCHEMAS:
        run_sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{s}")
    print("== volumes ==")
    run_sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{PFX}ops.staging")
    run_sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{PFX}docs.raw")

    print("== upload parquet ==")
    for domain, tables in TABLES.items():
        for t in tables:
            local = os.path.join(OUT, domain, f"{t}.parquet")
            if not os.path.exists(local):
                print(f"  SKIP missing {local}")
                continue
            upload(local, f"dbfs:{STAGING}/{domain}__{t}.parquet")

    print("== create tables ==")
    for domain, tables in TABLES.items():
        for t in tables:
            path = f"{STAGING}/{domain}__{t}.parquet"
            run_sql(
                f"CREATE OR REPLACE TABLE {CATALOG}.{PFX}{domain}.{t} AS "
                f"SELECT * FROM read_files('{path}', format => 'parquet')",
                label=f"{PFX}{domain}.{t}",
            )

    print("== upload docs (PDFs) ==")
    for sub in ("sds", "contracts"):
        d = os.path.join(OUT, "docs", sub)
        if not os.path.isdir(d):
            continue
        cli(["fs", "mkdir", f"dbfs:{DOCS_RAW}/{sub}"])
        for f in sorted(os.listdir(d)):
            if f.endswith(".pdf"):
                upload(os.path.join(d, f), f"dbfs:{DOCS_RAW}/{sub}/{f}")

    print("== row counts ==")
    for domain, tables in TABLES.items():
        for t in tables:
            run_sql(f"SELECT '{PFX}{domain}.{t}' AS tbl, count(*) AS n FROM {CATALOG}.{PFX}{domain}.{t}",
                    label=f"count {PFX}{domain}.{t}")


if __name__ == "__main__":
    main()
