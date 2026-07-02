# Starter Prompt: Access Provisioning And Entitlement Agent

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 04: Access Provisioning And Entitlement Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/04-access-provisioning/README.md

No entitlement, user, or audit tables are provided. The access targets are the
provided domain tables (flat in your personal schema).

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for users, groups, entitlement requests, audit log, and access-policy docs in your own personal schema
3. add-mcp-tool for user context and entitlement policy lookup
4. add-connector for a dry-run provisioning action
5. deploy only after approval and audit flow works

Build the first runnable loop:
"Give Priya access to Finance margin data for Paints EMEA planning."

Create:
- a request classifier for grant, change, revoke, or deny
- a policy lookup over your generated access-policy documents or tables
- a least-privilege recommendation
- an action proposal that stops at human approval
- an audit event table in your own personal schema
- 8 eval scenarios covering allow, deny, escalate, and revoke

Governance requirements:
- all grants require human approval
- mask personal details in logs where possible
- escalate if manager, purpose, or domain is missing
- never execute a real UC grant unless the connector is explicitly dry-run

Return the agent scaffold, tool schemas, connector stub, eval set, and demo script.
```

