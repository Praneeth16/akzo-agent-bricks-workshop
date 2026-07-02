# Starter Prompt: FinOps And AI Cost Governance Copilot

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 12: FinOps And AI Cost Governance Copilot on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/12-finops-cost-governance/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for fact_usage and dim_budget_policy
3. add-genie-space for the Akzo FinOps space
4. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create fact_usage
(~30,000 rows: date, workspace, sku, dbus, cost, budget, team) and
dim_budget_policy in <TEAM_CATALOG>.<your-personal-schema>, then build
a Genie space that answers:
"Why did our spend increase last month, and are we over budget?"

Define overage logic explicitly in the Genie instructions (for example,
more than 10% over budget by team and month). Generate:
- Genie instructions for spend variance, driver ranking, and overage checks
- 5 sample FinOps questions
- a small eval set with expected driver categories
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- cite generated SQL, metrics, or source rows
- say "not enough evidence" when data is missing

Return the files or notebook cells to create, plus a 3-minute demo script.
```
