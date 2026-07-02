# Starter Prompt: Celonis-Driven Exception Resolution Agent

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 16: Celonis-Driven Exception Resolution Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/16-process-exception-agent/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for fact_process_events and an actions lookup table
3. add-connector for the approval-gated action proposal
4. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create
fact_process_events (process instance id, step, timestamp, expected
duration, status) and an actions lookup table (step, standard
resolution) in <TEAM_CATALOG>.<your-personal-schema>. There is no live
Celonis connector on Free Edition — feed the agent this synthetic table
instead of attempting a live connection.

Build a Genie space over fact_process_events, define exception logic
explicitly (a step is "stuck" if its duration exceeds expected duration
by a stated threshold, for example 2x), and add an action-proposal step
that looks up the standard resolution and drafts it for human approval.
Generate:
- the fact_process_events and actions schema and generation logic
- exception-detection instructions with the explicit threshold
- a small eval set with expected exception classification and resolution category
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- every proposed action stays in a draft/proposed state until explicitly approved
- flag "needs manual review" instead of proposing an action for an uncovered exception type

Return the files or notebook cells to create, plus a 3-minute demo script.
```
