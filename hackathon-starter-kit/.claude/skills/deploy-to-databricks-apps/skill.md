---
name: deploy-to-databricks-apps
description: Deploy an agent_server app to Databricks Apps via Asset Bundles, and avoid the four crashes that bit earlier teams.
---

# deploy-to-databricks-apps

Use this skill when a team is ready to ship an `agent_server` app to Databricks Apps with a Databricks Asset Bundle (`databricks.yml`). It captures four real failure modes that crashed earlier deployments, plus the service-principal grants and deploy loop you need to get right the first time.

This skill is for the bundle-and-Apps path specifically. For notebook handoffs or a simple `app.yaml`, use the `deploy` skill instead.

## Inputs To Ask For

- App resource name in the bundle (e.g. `agent_app`) and the app's deployed name
- Team catalog and the schemas/functions/tables the agent reads
- Genie space id(s) the agent calls
- Workspace URL and whether the app talks to MCP, Genie, or Lakebase
- Which external clients are built at import time

## The Deploy Loop (get this right first)

`databricks bundle run` alone uses **stale source** — it does not re-upload your code. Always deploy, then run:

```bash
databricks bundle deploy --var catalog=<your_catalog>   # re-uploads source + applies config
databricks bundle run <app_resource_name>               # starts the app from fresh source
```

If a fix does not seem to take effect, you almost certainly ran `bundle run` without a preceding `bundle deploy`.

Read crash logs with:

```bash
databricks apps logs <app_name>
```

Most of the four failures below show up here as a single traceback. Read the actual error before re-deploying.

## The Four Crashes (symptom → fix)

### 1. Wheel build crash

`uv run` builds the project before deploy. With the hatchling backend, if your package directory name does not match the project name, the build fails:

```
ValueError: Unable to determine which files to ship inside the wheel using the following heuristics ...
The most likely cause of this is that there is no directory that matches the name of your project (<project_name>).
```

**Fix** — tell hatchling exactly which dirs to ship. In `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["agent_server", "scripts"]   # list your real source dirs
```

### 2. Catalog unresolved in the Apps runtime

`current_catalog()` (and other SQL-context lookups) do **not** work in the Databricks Apps runtime — there is no SQL context. Symptom:

```
RuntimeError: Could not resolve a Unity Catalog. ...
```

**Fix** — pass the catalog in as a bundle variable through the app's env. Never hardcode it. In `databricks.yml`:

```yaml
variables:
  catalog:
    description: Unity Catalog the agent reads from
    default: <your_catalog>

resources:
  apps:
    agent_app:
      name: <app_name>
      source_code_path: ./agent_server
      config:
        env:
          - name: CATALOG
            value: ${var.catalog}
```

Set it at deploy time:

```bash
databricks bundle deploy --var catalog=<your_catalog>
```

Read it in code with `os.environ["CATALOG"]`.

### 3. Bare host produces a bad MCP/HTTP URL

Databricks Apps inject `DATABRICKS_HOST` as a **bare hostname with no scheme** (e.g. `dbc-xxxx.cloud.databricks.com`), unlike the CLI which uses a full URL. Build a URL from it and you get:

```
httpx.UnsupportedProtocol: Request URL is missing an 'http://' or 'https://' protocol.
```

**Fix** — normalize the host before building any URL:

```python
import os

host = os.environ["DATABRICKS_HOST"]
if not host.startswith(("http://", "https://")):
    host = f"https://{host}"

mcp_url = f"{host}/api/2.0/mcp/..."   # now valid
```

### 4. Startup crash kills the whole server

Building the agent, MCP, Genie, or Lakebase clients at module import means any external-dependency failure crashes the entire app on boot (the platform reports a 502 and the app never serves a request).

**Fix** — never let an import-time external connection take down the server. Wrap it in `try/except` with a logged fallback, or build the client lazily on first use:

```python
import logging

logger = logging.getLogger(__name__)
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        try:
            _agent = build_agent()   # connects to MCP / Genie / Lakebase
        except Exception:
            logger.exception("Agent init failed; will retry on next request")
            raise
    return _agent
```

The server should always boot and surface the real error per request, so `databricks apps logs` shows you a useful traceback instead of a dead app.

## Service Principal Grants

A Databricks App runs as its own **service principal**, not as you. Your personal grants do not carry over, so the agent gets permission errors until the SP is granted access. Get the SP client id:

```bash
databricks apps get <app_name>   # read service_principal_client_id from the output
```

Then grant the SP what the agent needs (parametrize by SP id and catalog — never commit a concrete SP or catalog):

```sql
GRANT USE CATALOG ON CATALOG `<your_catalog>` TO `<sp_client_id>`;
GRANT USE SCHEMA  ON SCHEMA  `<your_catalog>`.`<schema>` TO `<sp_client_id>`;
GRANT EXECUTE     ON FUNCTION `<your_catalog>`.`<schema>`.`<function>` TO `<sp_client_id>`;
GRANT SELECT      ON TABLE    `<your_catalog>`.`<schema>`.`<table>` TO `<sp_client_id>`;
```

For Genie, add the SP as a user on each Genie space (CAN RUN) so the agent can query it. Do this in the Genie space sharing UI, or via the permissions API, keyed on the same `<sp_client_id>`.

## Output Shape

Return:

- The `pyproject.toml` and `databricks.yml` edits
- The host-normalization and lazy-init code changes
- The GRANT statements with placeholders filled from `databricks apps get`
- The exact deploy-then-run commands the team should paste
- How to read logs when it crashes

## Guardrails

- Never hardcode catalog, workspace host, service principal id, or Genie space id — pass them as bundle variables or env, and use placeholders in anything committed.
- Always `bundle deploy` before `bundle run`; `bundle run` alone ships stale source.
- Do not build external clients at import time without a try/except or lazy guard.
- Confirm the app boots and answers one request before declaring it deployed.
