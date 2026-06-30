# Starter Prompt: Supply Chain Control Tower

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 07: Supply Chain Control Tower Copilot in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/07-supply-chain-control-tower/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-genie-space for SCM grounding
3. add-mcp-tool for read-only exception lookup if needed
4. add-connector only for a proposed ticket or Teams notification

Build the first runnable loop:
"Why did OTIF for Paints EMEA drop in May 2026, and what should the planner do?"

Provided SCM tables in <TEAM_CATALOG>.akzo_scm: otif, inventory, lanes, service_levels.
The narrative lane is Rotterdam-NL->EMEA-DACH.

Create:
- SCM Genie instructions for OTIF, inventory, service, logistics, and intervention guidance
- sample SCM questions
- exception driver query or tool
- 8-question eval set
- a grounded intervention recommendation

Governance requirements:
- read-only by default
- proposed interventions require human approval
- state uncertainty when root cause cannot be isolated
- include generated SQL or source metric citations

Return the Genie instructions, notebook checks, eval set, and demo script.
```

