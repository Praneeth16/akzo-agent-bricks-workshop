# Starter Prompt: Sustainability And ESG Questionnaire Agent

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 18: Sustainability And ESG Questionnaire Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/18-esg-questionnaire-agent/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for an ESG evidence library and a questionnaire table
3. add-genie-space only if needed for questionnaire-status queries
4. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create a
synthetic ESG evidence library (sustainability policy excerpts,
emissions summaries, certifications) and a questionnaire table
(question text, category, required evidence type) in
<TEAM_CATALOG>.<your-personal-schema>. Build a Knowledge Assistant over
the evidence library with citation instructions, then build a
batch-run step that loops over every row of the questionnaire table and
produces a cited answer or a "not enough evidence" flag for each.

This is a batch-run requirement, not a single-question demo — the
agent must process the full questionnaire table in one pass and report
a completion summary. Generate:
- the evidence library and questionnaire schema and generation logic
- batch-run instructions with the citation and gap-flagging requirement
- a small eval set of 10 questions including at least 2 with no supporting evidence
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- every answer cites its source document
- flag "not enough evidence" explicitly rather than inferring an unsupported ESG claim

Return the files or notebook cells to create, plus a 3-minute demo script.
```
