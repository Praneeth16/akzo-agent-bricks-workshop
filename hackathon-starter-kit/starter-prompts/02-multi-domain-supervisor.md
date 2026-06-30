# Starter Prompt: Multi-Domain Supervisor

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 02: Multi-Domain Supervisor in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/02-multi-domain-supervisor/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-genie-space for any missing domain grounding
3. add-mcp-tool for a read-only domain routing helper if useful
4. deploy after routing eval passes

Build the first runnable loop: a supervisor that routes across Finance, SCM, and Commercial Genie spaces.

Create:
- supervisor instructions with routing rules and out-of-scope behavior
- registration/config placeholders for Finance, SCM, and Commercial Genie space ids
- a mixed 12-question routing eval set
- sample questions for finance margin, SCM OTIF, commercial churn, ambiguous cross-domain, and out-of-scope cases
- a trace checkpoint that shows which domain was selected

Governance requirements:
- preserve UC permissions by domain
- do not answer from the wrong domain when confidence is low
- ask a clarifying question for ambiguous cross-domain prompts
- show route selection in the trace

Return the agent scaffold, routing instructions, eval set, and 3-minute demo script.
```

