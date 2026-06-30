# Starter Prompt: Commercial Action

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 09: Commercial Action Assistant in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/09-commercial-action/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-genie-space for Commercial grounding
3. add-mcp-tool for account lookup if needed
4. add-connector for CRM task, email draft, or Teams notification in proposed state

Build the first runnable loop:
"Which Paints EMEA accounts are at churn risk in June 2026, why, and what should the account manager do?"

Provided Commercial tables in <TEAM_CATALOG>.akzo_commercial: accounts, pipeline, sales_actuals, churn_signals.
The at-risk accounts are ACC0001, ACC0002, ACC0003.

Create:
- Commercial Genie instructions for account health, churn, margin, and opportunity analysis
- next-best action categories
- account signal summary
- proposed action payload
- 8-scenario eval set

Governance requirements:
- no customer-facing action without approval
- cite account metrics and Commercial Genie answers
- mask sensitive customer details if present
- recommend review when confidence is low

Return the Genie instructions, connector stub, eval set, and demo script.
```

