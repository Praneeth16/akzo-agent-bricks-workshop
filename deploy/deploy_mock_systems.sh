#!/usr/bin/env bash
# Deploy the Mock External Systems FastAPI Databricks App (akzo-mock-systems) to the
# fe-vm-lakebase-praneeth workspace, wire all resource grants, and smoke-test.
#
# Mirrors the proven recipe in deploy/deploy_apps.sh (create -> grant SP UC + warehouse
# + Lakebase Postgres role with DML+CREATE on schema akzo -> sync -> deploy -> wait
# ACTIVE/SUCCEEDED). Single app, no frontend (pure API). Idempotent + re-runnable.
#
#   ./deploy/deploy_mock_systems.sh
set -euo pipefail

PROFILE="fe-vm-lakebase-praneeth"
WORKSPACE_USER="praneeth.paikray@databricks.com"
WAREHOUSE_ID="4d39ac2e32b72a3a"
CATALOG="serverless_lakebase_praneeth_catalog"
SCHEMAS=(akzo_finance akzo_scm akzo_commercial akzo_docs akzo_ops akzo_gateway)
LAKEBASE_INSTANCE="graphrag-spike"
APP_DIR="mock-systems"
APP_NAME="akzo-mock-systems"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

dbx() { databricks "$@" -p "$PROFILE"; }

echo "==> 1. Create app (skip if it exists)"
if dbx apps get "$APP_NAME" -o json >/dev/null 2>&1; then
  echo "    $APP_NAME already exists"
else
  echo "    creating $APP_NAME"
  dbx apps create "$APP_NAME" --no-wait >/dev/null
fi

echo "==> 2. Wait for compute ACTIVE and read SP client_id"
for _ in $(seq 1 30); do
  state=$(dbx apps get "$APP_NAME" -o json | python3 -c "import sys,json;print((json.load(sys.stdin).get('compute_status') or {}).get('state'))")
  [ "$state" = "ACTIVE" ] && break
  sleep 10
done
SP=$(dbx apps get "$APP_NAME" -o json | python3 -c "import sys,json;print(json.load(sys.stdin).get('service_principal_client_id'))")
echo "    $APP_NAME -> compute ACTIVE, SP client_id=$SP"

echo "==> 3a. Unity Catalog grants (USE CATALOG / USE SCHEMA / SELECT)"
runsql() {
  databricks api post /api/2.0/sql/statements -p "$PROFILE" \
    --json "$(python3 -c 'import json,sys;print(json.dumps({"warehouse_id":sys.argv[1],"statement":sys.argv[2],"wait_timeout":"30s"}))' "$WAREHOUSE_ID" "$1")" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);s=(d.get('status') or {});print('      ',s.get('state'), (s.get('error') or {}).get('message',''))"
}
runsql "GRANT USE CATALOG ON CATALOG \`$CATALOG\` TO \`$SP\`"
for s in "${SCHEMAS[@]}"; do
  runsql "GRANT USE SCHEMA ON SCHEMA \`$CATALOG\`.\`$s\` TO \`$SP\`"
  runsql "GRANT SELECT ON SCHEMA \`$CATALOG\`.\`$s\` TO \`$SP\`"
done

echo "==> 3b. Warehouse CAN_USE (PATCH permissions; additive)"
WH_ACL=$(python3 -c "import json,sys;print(json.dumps({'access_control_list':[{'service_principal_name':sys.argv[1],'permission_level':'CAN_USE'}]}))" "$SP")
databricks api patch "/api/2.0/permissions/warehouses/$WAREHOUSE_ID" -p "$PROFILE" --json "$WH_ACL" >/dev/null
echo "    warehouse $WAREHOUSE_ID -> CAN_USE granted to $SP"

echo "==> 3c. Lakebase ($LAKEBASE_INSTANCE) Postgres role + akzo schema privileges"
databricks api post "/api/2.0/database/instances/$LAKEBASE_INSTANCE/roles" -p "$PROFILE" \
  --json "{\"name\":\"$SP\",\"identity_type\":\"SERVICE_PRINCIPAL\",\"attributes\":{\"bypassrls\":false,\"createdb\":false,\"createrole\":false}}" \
  >/dev/null 2>&1 && echo "    role added: $SP" || echo "    role exists: $SP"
DATABRICKS_CONFIG_PROFILE="$PROFILE" python3 - "$SP" <<'PY'
import sys, psycopg
from databricks.sdk import WorkspaceClient
sp = sys.argv[1]
w = WorkspaceClient()
inst = w.database.get_database_instance(name="graphrag-spike")
me = w.current_user.me().user_name
tok = w.database.generate_database_credential(instance_names=["graphrag-spike"]).token
conn = psycopg.connect(host=inst.read_write_dns, port=5432, dbname="databricks_postgres",
                       user=me, password=tok, sslmode="require", autocommit=True)
with conn.cursor() as cur:
    r = f'"{sp}"'
    cur.execute(f"GRANT USAGE, CREATE ON SCHEMA akzo TO {r}")
    cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA akzo TO {r}")
    cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA akzo TO {r}")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA akzo GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {r}")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA akzo GRANT USAGE, SELECT ON SEQUENCES TO {r}")
    print(f"    akzo schema privileges granted to {sp}")
conn.close()
PY

echo "==> 4. Sync source to workspace + deploy"
DST="/Workspace/Users/$WORKSPACE_USER/akzo-apps/$APP_NAME"
echo "    sync $APP_DIR -> $DST"
dbx sync "$REPO_ROOT/apps/$APP_DIR" "$DST" >/dev/null
echo "    deploy $APP_NAME"
dbx apps deploy "$APP_NAME" --source-code-path "$DST" --no-wait >/dev/null

echo "==> 5. Wait for deployment SUCCEEDED"
for _ in $(seq 1 30); do
  st=$(dbx apps get "$APP_NAME" -o json | python3 -c "import sys,json;print(((json.load(sys.stdin).get('active_deployment') or {}).get('status') or {}).get('state'))")
  [ "$st" = "SUCCEEDED" ] && { echo "    $APP_NAME: SUCCEEDED"; break; }
  [ "$st" = "FAILED" ] && { echo "    $APP_NAME: FAILED"; break; }
  sleep 15
done
URL=$(dbx apps get "$APP_NAME" -o json | python3 -c "import sys,json;print(json.load(sys.stdin).get('url'))")
echo "      url: $URL"

echo "==> 6. Smoke test /api/health (OAuth bearer; app requires workspace SSO)"
TOKEN=$(databricks auth token -p "$PROFILE" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
code=$(curl -s -m 30 -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$URL/api/health")
echo "    $APP_NAME /api/health -> HTTP $code"

echo "==> DONE. App URL: $URL  SP: $SP"
