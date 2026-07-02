# Starter Prompt: Compliance And Audit Evidence Agent

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 19: Compliance And Audit Evidence Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/19-compliance-audit-agent/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for a controls table and audit evidence documents
3. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create a
controls table (control id, description, required evidence type,
deterministic rule) and synthetic audit evidence documents (control
test results, sign-off records) in
<TEAM_CATALOG>.<your-personal-schema>. Write the rule engine as a
deterministic UC function: given a control id, check whether the
required evidence exists and matches the rule, and return pass/fail
plus the evidence reference.

The rule engine must be a deterministic UC function, never an LLM
judgment call. Build a Knowledge Assistant over the evidence documents
for citation and explanation, and wire the agent to call the rule
engine for the decision, using the LLM only to summarize and cite —
never to override or re-derive the pass/fail call. Generate:
- the controls schema, the deterministic UC function, and the evidence documents
- agent instructions that route the decision through the UC function only
- a small eval set of 8 controls with expected pass/fail outcome and evidence reference
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- the LLM's stated outcome must always match the deterministic function's output
- return "insufficient evidence" from the rule engine rather than letting the LLM infer compliance

Return the files or notebook cells to create, plus a 3-minute demo script.
```
