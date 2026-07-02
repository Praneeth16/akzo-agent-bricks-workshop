# Starter Prompt: AI Governance And Policy

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 08: AI Governance And Policy Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/08-ai-governance-policy/README.md

No governance tables or policy docs are provided. Use your own personal schema for
team-built tables, and reference real AI Gateway logs and UC permissions as the
authoritative governance signal.

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for policy/control docs and model/tool/budget registry tables in your own personal schema
3. add-mcp-tool for model, tool, or budget lookup
4. add-connector only for policy exception approval
5. deploy after compliance eval passes

Build the first runnable loop:
"Can this agent call a tool with customer data, and what controls are required?"

Create:
- Knowledge Assistant instructions over AI policy and control documents
- policy request classifier
- allow, deny, or escalate decision format
- 10-scenario eval set with expected outcomes
- citations for policy evidence

Governance requirements:
- cite approved policy sources
- escalate when policy evidence is missing or conflicting
- include AI Gateway or trace checkpoint
- do not approve exceptions automatically

Return the assistant instructions, tool schema, eval set, and demo script.
```

