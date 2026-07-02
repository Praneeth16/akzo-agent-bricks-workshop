# Starter Prompt: HR And SuccessFactors Assistant

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 15: HR And SuccessFactors Assistant on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/15-hr-successfactors-assistant/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for fact_headcount, dim_employee, and HR policy documents
3. add-genie-space for the Akzo HR space
4. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create
fact_headcount and dim_employee, plus a small set of synthetic HR
policy documents (leave policy, promotion criteria), in
<TEAM_CATALOG>.<your-personal-schema>. Build a Genie space over the
tables with ai_mask applied to employee-identifying fields, and a
Knowledge Assistant over the policy documents.

Mask any employee-identifying field. The SuccessFactors connector is
not available on Free Edition — simulate entirely with the generated
tables, not a live connection. Also implement one governance-simulation
method to stand in for role-based access on this single-user workspace:
either a persona-parameter column driving an RLS-style view, or two
scoped Genie spaces routed by a Supervisor. Generate:
- the fact_headcount/dim_employee schema and generation logic, plus policy documents
- masking and governance-simulation instructions
- a small eval set covering headcount, policy, and masking-behavior questions
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- mask employee-identifying fields in every headcount answer
- refuse to reveal individual employee identity even if asked directly

Return the files or notebook cells to create, plus a 3-minute demo script.
```
