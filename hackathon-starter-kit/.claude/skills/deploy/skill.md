---
name: deploy
description: Package a hackathon demo for Databricks Apps or a notebook-based handoff.
---

# deploy

Use this skill after the team has a working demo path and at least one eval or trace.

## Inputs To Ask For

- Demo artifact type: notebook, Agent Bricks agent, Databricks App, or AppKit hub submission
- Team catalog and workspace URL
- Required environment variables
- One verification prompt or document
- Known limitations

## Build Steps

1. Freeze the demo path before packaging.
2. Add a preflight cell or script that checks catalog, warehouse, tables, and document index.
3. Add a runbook with:
   - setup
   - launch
   - demo prompt
   - verification
   - troubleshooting
4. If using Databricks Apps, generate `app.yaml` and a minimal health check.
5. If using notebook handoff, create a top cell with widgets for catalog, warehouse, and model endpoint.

## Output Shape

Return:

- Packaging choice
- Files or notebook cells to add
- Environment variables
- Smoke test
- Demo runbook

## Guardrails

- Do not deploy before the demo path runs once in Vocareum.
- Do not hide failing evals; list known gaps in the runbook.
- Keep secrets out of committed files and prompts.

