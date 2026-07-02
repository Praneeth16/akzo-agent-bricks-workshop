#!/usr/bin/env bash
# Deploy the 3 AkzoNobel React+FastAPI Databricks Apps to your workspace, wire all
# resource grants, and smoke-test.
#
# Idempotent + re-runnable: `apps create` is skipped if the app exists, grants are
# additive (GRANT is a no-op if already held), and sync/deploy always push the
# current source. Configure with environment variables, then run from the repo root:
#
#   DATABRICKS_CONFIG_PROFILE=<your-profile> WORKSPACE_USER=<you@example.com> \
#   DATABRICKS_WAREHOUSE_ID=<id> AKZO_CATALOG=<catalog> AKZO_SCHEMA=<your-personal-schema> \
#   LAKEBASE_INSTANCE=<instance> ./deploy/deploy_apps.sh
#
# Requires: databricks CLI v0.298+, python3 with psycopg[binary] + databricks-sdk,
# node 26 (only if you need to rebuild a frontend; prebuilt dist/ is committed).
set -euo pipefail

PROFILE="${DATABRICKS_CONFIG_PROFILE:-<your-profile>}"
WORKSPACE_USER="${WORKSPACE_USER:-<you@example.com>}"
WAREHOUSE_ID="${DATABRICKS_WAREHOUSE_ID:-<your-warehouse-id>}"
CHAT_ENDPOINT="${DATABRICKS_CHAT_ENDPOINT:-databricks-claude-opus-4-8}"  # FOUNDATION_MODEL_API (pay-per-token)
CATALOG="${AKZO_CATALOG:-<catalog>}"
SCHEMA="${AKZO_SCHEMA:?set AKZO_SCHEMA to your personal schema}"
LAKEBASE_INSTANCE="${LAKEBASE_INSTANCE:-<your-lakebase-instance>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# app dir -> app name
declare -A APPS=(
  [quote-agent]=akzo-quote-agent
  [supervisor]=akzo-supervisor
  [finance-copilot]=akzo-finance-copilot
)

dbx() { databricks "$@" -p "$PROFILE"; }

echo "==> 1. Create apps (skip if they exist) and capture service principals"
declare -A SP_CLIENT_ID   # app name -> SP client_id (used by UC + warehouse + Lakebase grants)
for dir in "${!APPS[@]}"; do
  name="${APPS[$dir]}"
  if dbx apps get "$name" -o json >/dev/null 2>&1; then
    echo "    $name already exists"
  else
    echo "    creating $name"
    dbx apps create "$name" --no-wait >/dev/null
  fi
done

echo "==> 2. Wait for compute ACTIVE and read SP client_ids"
for dir in "${!APPS[@]}"; do
  name="${APPS[$dir]}"
  for _ in $(seq 1 30); do
    state=$(dbx apps get "$name" -o json | python3 -c "import sys,json;print((json.load(sys.stdin).get('compute_status') or {}).get('state'))")
    [ "$state" = "ACTIVE" ] && break
    sleep 10
  done
  cid=$(dbx apps get "$name" -o json | python3 -c "import sys,json;print(json.load(sys.stdin).get('service_principal_client_id'))")
  SP_CLIENT_ID[$name]="$cid"
  echo "    $name -> compute ACTIVE, SP client_id=$cid"
done

echo "==> 3a. Unity Catalog grants (USE CATALOG / USE SCHEMA / SELECT) via SQL statements"
runsql() {
  databricks api post /api/2.0/sql/statements -p "$PROFILE" \
    --json "$(python3 -c 'import json,sys;print(json.dumps({"warehouse_id":sys.argv[1],"statement":sys.argv[2],"wait_timeout":"30s"}))' "$WAREHOUSE_ID" "$1")" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);s=(d.get('status') or {});print('      ',s.get('state'), (s.get('error') or {}).get('message',''))"
}
for name in "${APPS[@]}"; do
  sp="${SP_CLIENT_ID[$name]}"
  echo "    $name ($sp)"
  runsql "GRANT USE CATALOG ON CATALOG \`$CATALOG\` TO \`$sp\`"
  runsql "GRANT USE SCHEMA ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$sp\`"
  runsql "GRANT SELECT ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$sp\`"
done

echo "==> 3b. Warehouse CAN_USE (PATCH permissions; additive)"
WH_ACL=$(python3 -c "import json,sys;print(json.dumps({'access_control_list':[{'service_principal_name':c,'permission_level':'CAN_USE'} for c in sys.argv[1:]]}))" "${SP_CLIENT_ID[@]}")
databricks api patch "/api/2.0/permissions/warehouses/$WAREHOUSE_ID" -p "$PROFILE" --json "$WH_ACL" >/dev/null
echo "    warehouse $WAREHOUSE_ID -> CAN_USE granted to 3 SPs"

# NOTE on the serving endpoint:
#   databricks-claude-opus-4-8 is a FOUNDATION_MODEL_API (pay-per-token) system endpoint.
#   It has no per-endpoint numeric id, so the per-SP CAN_QUERY permissions API rejects it
#   ('not a valid Inference Endpoint ID'). FM API endpoints are queryable by all workspace
#   principals by default, so no explicit grant is required (and live ai_query/ai_extract
#   calls from each app SP succeed — see smoke tests). If access is ever locked down, set
#   CAN_QUERY via the Serving UI or the AI Gateway, not the CLI.

echo "==> 3c. Lakebase ($LAKEBASE_INSTANCE) Postgres roles + akzo schema privileges"
# Register each app SP as a Postgres role on the instance (role name == SP client_id,
# which is exactly what WorkspaceClient.current_user().user_name returns inside an App).
for name in "${APPS[@]}"; do
  sp="${SP_CLIENT_ID[$name]}"
  databricks api post "/api/2.0/database/instances/$LAKEBASE_INSTANCE/roles" -p "$PROFILE" \
    --json "{\"name\":\"$sp\",\"identity_type\":\"SERVICE_PRINCIPAL\",\"attributes\":{\"bypassrls\":false,\"createdb\":false,\"createrole\":false}}" \
    >/dev/null 2>&1 && echo "    role added: $sp" || echo "    role exists: $sp"
done
# Grant the roles privileges on the akzo schema (connect as the instance superuser).
DATABRICKS_CONFIG_PROFILE="$PROFILE" LAKEBASE_INSTANCE="$LAKEBASE_INSTANCE" python3 - "${SP_CLIENT_ID[@]}" <<'PY'
import os, sys, psycopg
from databricks.sdk import WorkspaceClient
sps = sys.argv[1:]
instance = os.environ["LAKEBASE_INSTANCE"]
w = WorkspaceClient()
inst = w.database.get_database_instance(name=instance)
me = w.current_user.me().user_name
tok = w.database.generate_database_credential(instance_names=[instance]).token
conn = psycopg.connect(host=inst.read_write_dns, port=5432, dbname="databricks_postgres",
                       user=me, password=tok, sslmode="require", autocommit=True)
with conn.cursor() as cur:
    for sp in sps:
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
# IMPORTANT: .gitignore excludes frontend/dist/, but FastAPI serves it as the static
# frontend, so we force-include it and exclude the heavy node_modules. dist/ is prebuilt
# and committed; rebuild with `cd apps/<app>/frontend && npm install && npm run build`
# only if you change the frontend.
for dir in "${!APPS[@]}"; do
  name="${APPS[$dir]}"
  dst="/Workspace/Users/$WORKSPACE_USER/akzo-apps/$name"
  echo "    sync $dir -> $dst"
  dbx sync "$REPO_ROOT/apps/$dir" "$dst" \
    --include "frontend/dist/**" --exclude "frontend/node_modules/**" >/dev/null
  echo "    deploy $name"
  dbx apps deploy "$name" --source-code-path "$dst" --no-wait >/dev/null
done

echo "==> 5. Wait for deployments SUCCEEDED"
for name in "${APPS[@]}"; do
  for _ in $(seq 1 30); do
    st=$(dbx apps get "$name" -o json | python3 -c "import sys,json;print(((json.load(sys.stdin).get('active_deployment') or {}).get('status') or {}).get('state'))")
    [ "$st" = "SUCCEEDED" ] && { echo "    $name: SUCCEEDED"; break; }
    [ "$st" = "FAILED" ] && { echo "    $name: FAILED"; break; }
    sleep 15
  done
  url=$(dbx apps get "$name" -o json | python3 -c "import sys,json;print(json.load(sys.stdin).get('url'))")
  echo "      url: $url"
done

echo "==> 6. Smoke test /api/health (uses your OAuth token; apps require workspace SSO)"
TOKEN=$(databricks auth token -p "$PROFILE" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
for name in "${APPS[@]}"; do
  url=$(dbx apps get "$name" -o json | python3 -c "import sys,json;print(json.load(sys.stdin).get('url'))")
  code=$(curl -s -m 30 -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$url/api/health")
  echo "    $name /api/health -> HTTP $code"
done

echo "==> DONE. See deploy/SMOKE_RESULTS.md for the full per-app smoke matrix."
