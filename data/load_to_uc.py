"""Load synthetic data + docs into Unity Catalog on the workshop workspace.

Uses spark.sql() and dbutils.fs - no CLI or SQL warehouse required.
Idempotent: safe to re-run.

Most lab workspaces do not grant CREATE SCHEMA, so all tables are loaded into the
pre-provisioned personal schema (local part of current_user()'s email) inside
the shared dbacademy catalog. The staging volume in dbacademy.ops is also
pre-provisioned per user.

Configure with environment variables (all optional):
  AKZO_CATALOG   Unity Catalog name    (default: dbacademy)
  AKZO_SCHEMA    Target schema         (default: auto-detected from current_user())
  AKZO_STAGING   Staging volume path   (default: auto-detected from current_user())

Run as a Databricks notebook cell (paste the file, or `%run`), not from a local
terminal — it needs `spark` and `dbutils`, which only exist inside a notebook.
"""
import os
import sys

# __file__ is not defined in interactive REPL (e.g. Databricks serverless); fall back to cwd.
try:
    _here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _here = os.getcwd()  # cwd is the data/ folder when run interactively

ROOT = os.path.dirname(_here)
OUT = os.path.join(_here, "output")

CATALOG = os.environ.get("AKZO_CATALOG", "dbacademy")


def _current_user():
    return spark.sql("SELECT current_user()").collect()[0][0]


def _default_schema():
    """Personal schema = local part of the user's email."""
    try:
        return _current_user().split("@")[0]
    except Exception:
        return None


def _default_staging():
    """Pre-provisioned ops volume: email with '.' replaced by '_', '@' preserved.
    e.g. user@vocareum.com -> /Volumes/dbacademy/ops/user@vocareum_com
    """
    try:
        vol = _current_user().replace(".", "_")
        return f"/Volumes/{CATALOG}/ops/{vol}"
    except Exception:
        return None


USER_SCHEMA = os.environ.get("AKZO_SCHEMA") or _default_schema()
if not USER_SCHEMA:
    sys.exit("Could not determine user schema. Set AKZO_SCHEMA env var.")

STAGING = os.environ.get("AKZO_STAGING") or _default_staging()
if not STAGING:
    sys.exit("Could not determine staging volume. Set AKZO_STAGING env var.")

DOCS_RAW = f"/Volumes/{CATALOG}/{USER_SCHEMA}/docs_raw"

# parquet table -> domain. Table names are unique across all domains.
TABLES = {
    "finance": ["products", "margin_actuals", "margin_budget", "fx_rates", "cost_drivers"],
    "scm": ["otif", "inventory", "lanes", "service_levels"],
    "commercial": ["accounts", "pipeline", "sales_actuals", "churn_signals"],
}

FAILURES = []  # (label, message) accumulated across the run


def run_sql(stmt, label=None):
    tag = label or stmt[:60]
    try:
        spark.sql(stmt)
        print(f"  ok  {tag}")
        return True
    except Exception as e:
        msg = str(e)[:300]
        print(f"  FAIL {tag}: {msg}")
        FAILURES.append((tag, msg))
        return False


def upload(local, dest):
    try:
        dbutils.fs.cp(f"file://{local}", dest)
        print(f"  ok  upload {os.path.basename(local)} -> {dest}")
        return True
    except Exception as e:
        msg = str(e)[:200]
        print(f"  FAIL upload {os.path.basename(local)}: {msg}")
        FAILURES.append((f"upload {os.path.basename(local)}", msg))
        return False


def mkdirs(path):
    try:
        dbutils.fs.mkdirs(path)
        print(f"  ok  mkdirs {path}")
        return True
    except Exception as e:
        msg = str(e)[:200]
        print(f"  FAIL mkdirs {path}: {msg}")
        FAILURES.append((f"mkdirs {path}", msg))
        return False


def main():
    print("== config ==")
    print(f"  catalog  : {CATALOG}")
    print(f"  schema   : {USER_SCHEMA}")
    print(f"  staging  : {STAGING}")
    print(f"  docs_raw : {DOCS_RAW}")

    print("\n== volumes ==")
    run_sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{USER_SCHEMA}.docs_raw")

    print("== upload parquet ==")
    for domain, tables in TABLES.items():
        for t in tables:
            local = os.path.join(OUT, domain, f"{t}.parquet")
            if not os.path.exists(local):
                print(f"  SKIP missing {local}")
                continue
            upload(local, f"{STAGING}/{domain}__{t}.parquet")

    print("== create tables ==")
    for domain, tables in TABLES.items():
        for t in tables:
            path = f"{STAGING}/{domain}__{t}.parquet"
            run_sql(
                f"CREATE OR REPLACE TABLE {CATALOG}.{USER_SCHEMA}.{t} AS "
                f"SELECT * FROM read_files('{path}', format => 'parquet')",
                label=f"{USER_SCHEMA}.{t}",
            )

    print("== upload docs (PDFs) ==")
    for sub in ("sds", "contracts"):
        d = os.path.join(OUT, "docs", sub)
        if not os.path.isdir(d):
            continue
        if not mkdirs(f"{DOCS_RAW}/{sub}"):
            continue  # skip uploads if the target directory couldn't be created
        for f in sorted(os.listdir(d)):
            if f.endswith(".pdf"):
                upload(os.path.join(d, f), f"{DOCS_RAW}/{sub}/{f}")

    print("== row counts ==")
    for domain, tables in TABLES.items():
        for t in tables:
            try:
                n = spark.sql(
                    f"SELECT count(*) AS n FROM {CATALOG}.{USER_SCHEMA}.{t}"
                ).collect()[0]["n"]
                print(f"  ok  count {USER_SCHEMA}.{t}: {n:,}")
            except Exception as e:
                msg = str(e)[:200]
                print(f"  FAIL count {USER_SCHEMA}.{t}: {msg}")
                FAILURES.append((f"count {USER_SCHEMA}.{t}", msg))

    if FAILURES:
        summary = "\n".join(f"  - {tag}: {msg}" for tag, msg in FAILURES)
        raise RuntimeError(f"{len(FAILURES)} step(s) failed:\n{summary}")
    print("\n== all steps succeeded ==")


if __name__ == "__main__":
    main()
