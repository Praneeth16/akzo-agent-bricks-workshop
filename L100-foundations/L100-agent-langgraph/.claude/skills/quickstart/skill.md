---
name: quickstart
description: "Set up the L100 LangGraph agent for local development on Databricks. Use when: (1) first-time setup, (2) configuring Databricks authentication, (3) the user says 'quickstart', 'set up', 'authenticate', or 'configure databricks', (4) no .env file exists."
---

# Quickstart & Authentication

Sets up auth, an MLflow experiment, and `.env` for the L100 LangGraph agent. This agent
has **no Lakebase dependency** — there is no Lakebase step.

## Prerequisites

- **uv** (Python package manager)
- **nvm** with Node 20+ (for the built-in chat UI)
- **Databricks CLI v0.283.0+** — check with `databricks -v`, upgrade with `brew upgrade databricks`

## Run Quickstart

```bash
uv run quickstart
```

**Options:**
- `--profile NAME` — use a specified profile (non-interactive)
- `--host URL` — workspace URL for initial setup
- `-h, --help` — show help

**Examples:**
```bash
uv run quickstart                     # Interactive (prompts for profile)
uv run quickstart --profile DEFAULT   # Non-interactive with an existing profile
uv run quickstart --host https://your-workspace.cloud.databricks.com   # New workspace
```

## What Quickstart Configures

Creates/updates `.env` with:
- `DATABRICKS_CONFIG_PROFILE` — selected CLI profile
- `MLFLOW_TRACKING_URI` — `databricks://<profile-name>` for local auth
- `MLFLOW_EXPERIMENT_ID` — auto-created (or reused) experiment ID

Updates `databricks.yml`: sets `experiment_id` in the app's experiment resource.

## Portability — nothing is hardcoded

The agent config resolves from the environment:
- `AKZO_CATALOG` — optional; falls back to `current_catalog()` (your assigned lab catalog on
  Vocareum). No silent `main` fallback — if neither resolves, the agent fails fast.
- `AKZO_SCHEMA` — required, your personal schema holding the finance tables.
- `LLM_ENDPOINT` — **required** (no default), so the agent never silently calls a model you
  did not choose. Set it in `.env` or `app.yaml`, e.g. `databricks-meta-llama-3-3-70b-instruct`.

Set `AKZO_CATALOG` only if your coatings data lives in a non-current catalog.

## Idempotency

Re-running quickstart is safe: if `MLFLOW_EXPERIMENT_ID` is already in `.env` and the
experiment still exists, it is reused (no duplicate created).

## Manual Authentication (fallback)

If quickstart fails:
```bash
databricks auth login --host https://your-workspace.cloud.databricks.com
databricks auth profiles   # verify
```
Then copy `.env.example` to `.env` and fill in the profile + experiment ID by hand.

## Next Steps

1. `uv run start-app` to run the agent locally (see the **run-locally** skill).
2. `uv run preflight` before deploying.
