#!/usr/bin/env bash
# Deploy the "Agents That Act" expansion to your workspace, using the proven
# recipe from deploy/deploy_apps.sh + deploy_mock_systems.sh.
#
# This script is idempotent + re-runnable. It:
#   1. Creates akzo-action-center (NEW), captures its SP, applies the full grant recipe
#      (UC read on your personal schema + warehouse CAN_USE + Lakebase Postgres role w/
#      DML+CREATE on schema akzo). The app reads/writes akzo.actions/action_events and
#      calls the L3 executor (http_request via the akzo_external_systems UC connection),
#      so it needs the warehouse + Lakebase + UC read grants.
#   2. Redeploys the 3 deepened apps (akzo-supervisor / akzo-finance-copilot /
#      akzo-quote-agent) — they gained the Actions panel + action_plane + authz/CAS/
#      idempotency fixes. Their SPs already hold grants; we re-confirm DML on schema akzo
#      + warehouse CAN_USE (no-op if held).
#   3. Redeploys akzo-mock-systems (ships the lakebase fix).
#   4. Creates the PAUSED serverless autonomous Job akzo-autonomous-scm and syncs the
#      L200-capabilities/ + apps/_shared to the workspace paths the job + notebook import expects.
#
#   DATABRICKS_CONFIG_PROFILE=<your-profile> WORKSPACE_USER=<you@example.com> \
#   DATABRICKS_WAREHOUSE_ID=<id> AKZO_CATALOG=<catalog> AKZO_SCHEMA=<your-personal-schema> \
#   LAKEBASE_INSTANCE=<instance> ./deploy/deploy_action_apps.sh
set -euo pipefail

PROFILE="${DATABRICKS_CONFIG_PROFILE:-<your-profile>}"
WORKSPACE_USER="${WORKSPACE_USER:-<you@example.com>}"
WAREHOUSE_ID="${DATABRICKS_WAREHOUSE_ID:-<your-warehouse-id>}"
CATALOG="${AKZO_CATALOG:-<catalog>}"
SCHEMA="${AKZO_SCHEMA:?set AKZO_SCHEMA to your personal schema}"
LAKEBASE_INSTANCE="${LAKEBASE_INSTANCE:-<your-lakebase-instance>}"
CONNECTION_NAME="akzo_external_systems"   # governed UC HTTP connection (executor path)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS_BASE="/Workspace/Users/$WORKSPACE_USER/akzo-apps"

# NEW app (action-center) gets the full create+grant recipe.
NEW_DIR="action-center"
NEW_NAME="akzo-action-center"

# Existing deepened apps to redeploy (already created + granted in prior deploys).
# Indexed arrays (macOS ships bash 3.2 with no associative-array support); dir[i] ->
# name[i]. supervisor/finance/quote get the DML+warehouse re-confirm; mock just redeploys.
REDEPLOY_DIRS=(supervisor finance-copilot quote-agent)
REDEPLOY_NAMES=(akzo-supervisor akzo-finance-copilot akzo-quote-agent)

dbx() { databricks "$@" -p "$PROFILE"; }

runsql() {
  databricks api post /api/2.0/sql/statements -p "$PROFILE" \
    --json "$(python3 -c 'import json,sys;print(json.dumps({"warehouse_id":sys.argv[1],"statement":sys.argv[2],"wait_timeout":"30s"}))' "$WAREHOUSE_ID" "$1")" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);s=(d.get('status') or {});print('      ',s.get('state'), (s.get('error') or {}).get('message',''))"
}

get_field() {  # $1=app name  $2=python expr on the get-json bound to `d`
  dbx apps get "$1" -o json | python3 -c "import sys,json;d=json.load(sys.stdin);print($2)"
}

sync_app() {   # $1=dir  $2=name (frontend dist included, node_modules excluded)
  local dir="$1" name="$2" dst="$APPS_BASE/$2"
  echo "    sync $dir -> $dst"
  dbx sync "$REPO_ROOT/apps/$dir" "$dst" \
    --include "frontend/dist/**" --exclude "frontend/node_modules/**" >/dev/null
  echo "    deploy $name"
  dbx apps deploy "$name" --source-code-path "$dst" --no-wait >/dev/null
}

grant_sp() {   # $1=SP client_id : full UC + warehouse + Lakebase recipe (idempotent)
  local sp="$1"
  echo "    UC grants for $sp"
  runsql "GRANT USE CATALOG ON CATALOG \`$CATALOG\` TO \`$sp\`"
  runsql "GRANT USE SCHEMA ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$sp\`"
  runsql "GRANT SELECT ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$sp\`"
  echo "    warehouse CAN_USE for $sp"
  local acl
  acl=$(python3 -c "import json,sys;print(json.dumps({'access_control_list':[{'service_principal_name':sys.argv[1],'permission_level':'CAN_USE'}]}))" "$sp")
  databricks api patch "/api/2.0/permissions/warehouses/$WAREHOUSE_ID" -p "$PROFILE" --json "$acl" >/dev/null
  # USE CONNECTION on the governed UC HTTP connection: the executor runs
  # http_request(conn => 'akzo_external_systems', ...) on the warehouse under this SP.
  # Without it the UC-connection path 403s and the connector falls back to sp_direct.
  echo "    USE CONNECTION on akzo_external_systems for $sp"
  runsql "GRANT USE CONNECTION ON CONNECTION \`$CONNECTION_NAME\` TO \`$sp\`"
  echo "    Lakebase role + akzo schema privileges for $sp"
  databricks api post "/api/2.0/database/instances/$LAKEBASE_INSTANCE/roles" -p "$PROFILE" \
    --json "{\"name\":\"$sp\",\"identity_type\":\"SERVICE_PRINCIPAL\",\"attributes\":{\"bypassrls\":false,\"createdb\":false,\"createrole\":false}}" \
    >/dev/null 2>&1 && echo "      role added: $sp" || echo "      role exists: $sp"
  DATABRICKS_CONFIG_PROFILE="$PROFILE" LAKEBASE_INSTANCE="$LAKEBASE_INSTANCE" python3 - "$sp" <<'PY'
import os, sys, psycopg
from databricks.sdk import WorkspaceClient
sp = sys.argv[1]
instance = os.environ["LAKEBASE_INSTANCE"]
w = WorkspaceClient()
inst = w.database.get_database_instance(name=instance)
me = w.current_user.me().user_name
tok = w.database.generate_database_credential(instance_names=[instance]).token
conn = psycopg.connect(host=inst.read_write_dns, port=5432, dbname="databricks_postgres",
                       user=me, password=tok, sslmode="require", autocommit=True)
with conn.cursor() as cur:
    r = f'"{sp}"'
    cur.execute(f"GRANT USAGE, CREATE ON SCHEMA akzo TO {r}")
    cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA akzo TO {r}")
    cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA akzo TO {r}")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA akzo GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {r}")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA akzo GRANT USAGE, SELECT ON SEQUENCES TO {r}")
    print(f"      akzo schema privileges granted to {sp}")
conn.close()
PY
}

wait_active() {  # $1=name : wait compute ACTIVE
  local name="$1" state
  for _ in $(seq 1 30); do
    state=$(get_field "$name" "(d.get('compute_status') or {}).get('state')")
    [ "$state" = "ACTIVE" ] && break
    sleep 10
  done
  echo "    $name compute: $state"
}

wait_deployed() {  # $1=name : wait deployment SUCCEEDED/FAILED
  local name="$1" st
  for _ in $(seq 1 40); do
    st=$(get_field "$name" "((d.get('active_deployment') or {}).get('status') or {}).get('state')")
    [ "$st" = "SUCCEEDED" ] && { echo "    $name: SUCCEEDED"; break; }
    [ "$st" = "FAILED" ]    && { echo "    $name: FAILED"; break; }
    sleep 15
  done
  echo "      url: $(get_field "$name" "d.get('url')")"
}

# ---------------------------------------------------------------------------
echo "==> 1. NEW app: $NEW_NAME (create -> wait ACTIVE -> capture SP -> grant)"
if dbx apps get "$NEW_NAME" -o json >/dev/null 2>&1; then
  echo "    $NEW_NAME already exists"
else
  echo "    creating $NEW_NAME"
  dbx apps create "$NEW_NAME" --no-wait >/dev/null
fi
wait_active "$NEW_NAME"
NEW_SP=$(get_field "$NEW_NAME" "d.get('service_principal_client_id')")
echo "    $NEW_NAME SP client_id = $NEW_SP"
grant_sp "$NEW_SP"
sync_app "$NEW_DIR" "$NEW_NAME"

echo "==> 2. Redeploy deepened apps + confirm DML/warehouse grants (idempotent)"
for i in "${!REDEPLOY_DIRS[@]}"; do
  dir="${REDEPLOY_DIRS[$i]}"; name="${REDEPLOY_NAMES[$i]}"
  echo "  -- $name"
  wait_active "$name"
  sp=$(get_field "$name" "d.get('service_principal_client_id')")
  echo "    $name SP client_id = $sp"
  grant_sp "$sp"          # re-confirms DML on akzo + warehouse CAN_USE + UC read
  sync_app "$dir" "$name"
done

echo "==> 3. Redeploy mock-systems (ships lakebase fix)"
wait_active akzo-mock-systems
sync_app mock-systems akzo-mock-systems

echo "==> 4. Sync notebooks + _shared to workspace, create autonomous Job (PAUSED)"
# The job notebook_path = $APPS_BASE/L200-capabilities/03_autonomous_loop, and the
# notebook imports apps/_shared via sys.path -> $APPS_BASE/_shared. Sync both.
dbx sync "$REPO_ROOT/L200-capabilities" "$APPS_BASE/L200-capabilities" >/dev/null && echo "    synced L200-capabilities -> $APPS_BASE/L200-capabilities"
dbx sync "$REPO_ROOT/apps/_shared" "$APPS_BASE/_shared" \
  --exclude "frontend/node_modules/**" >/dev/null && echo "    synced _shared -> $APPS_BASE/_shared"
# Create the job only if a job with this name does not already exist.
EXISTING_JOB=$(databricks jobs list -p "$PROFILE" -o json \
  | python3 -c "import sys,json;[print(j['job_id']) for j in json.load(sys.stdin) if j.get('settings',{}).get('name')=='akzo-autonomous-scm']" | head -1)
if [ -n "${EXISTING_JOB:-}" ]; then
  echo "    job akzo-autonomous-scm already exists: job_id=$EXISTING_JOB"
else
  JOB_ID=$(databricks jobs create --json "@$REPO_ROOT/deploy/job_autonomous_scm.json" -p "$PROFILE" -o json \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
  echo "    created job akzo-autonomous-scm: job_id=$JOB_ID"
fi

echo "==> 5. Wait for all deployments SUCCEEDED"
for name in "$NEW_NAME" akzo-supervisor akzo-finance-copilot akzo-quote-agent akzo-mock-systems; do
  wait_deployed "$name"
done

echo "==> 6. Smoke /api/health (OAuth bearer; apps require workspace SSO)"
TOKEN=$(databricks auth token -p "$PROFILE" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
for name in "$NEW_NAME" akzo-supervisor akzo-finance-copilot akzo-quote-agent akzo-mock-systems; do
  url=$(get_field "$name" "d.get('url')")
  code=$(curl -s -m 30 -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$url/api/health")
  echo "    $name /api/health -> HTTP $code"
done

echo "==> DONE. See deploy/ACTION_SMOKE_RESULTS.md for the full smoke matrix."
