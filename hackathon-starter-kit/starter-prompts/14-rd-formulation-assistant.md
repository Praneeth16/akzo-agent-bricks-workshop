# Starter Prompt: R&D Formulation And Research Assistant

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 14: R&D Formulation And Research Assistant on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/14-rd-formulation-assistant/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for fact_experiments and a small formulation-document set
3. add-genie-space for the Akzo R&D Experiments space
4. add-mcp-tool only if needed for experiment or ingredient lookup
5. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create
fact_experiments (experiment id, formulation, ingredient list, test
result, date, researcher) and a small set of synthetic formulation
research PDFs in <TEAM_CATALOG>.<your-personal-schema>. Build a Genie
space over fact_experiments and a Knowledge Assistant over the
generated documents, then wire both under a Supervisor that routes
structured questions to Genie and document questions to the Knowledge
Assistant, and can combine both for mixed questions.

Generate:
- the fact_experiments schema and generation logic, plus the document set
- Supervisor instructions for routing and combining sources
- a small eval set mixing structured-only, document-only, and combined questions
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- every answer states whether it came from experiment data, documents, or both
- say when neither source has evidence rather than inferring a formulation outcome

Return the files or notebook cells to create, plus a 3-minute demo script.
```
