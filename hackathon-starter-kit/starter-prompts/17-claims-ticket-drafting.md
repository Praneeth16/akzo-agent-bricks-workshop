# Starter Prompt: Claims, Ticket, And Response Drafting Agent

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 17: Claims, Ticket, And Response Drafting Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/17-claims-ticket-drafting/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for a tickets table and response-template documents
3. add-mcp-tool for ticket and template lookup
4. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create a
synthetic tickets table (ticket id, customer, category, description,
status) and a response-template document per ticket category in
<TEAM_CATALOG>.<your-personal-schema>. Build a Knowledge Assistant over
the templates and an MCP tool for ticket/customer lookup, then wire the
drafting flow: read ticket, retrieve the matching template, draft a
response citing the template used.

Generate:
- the tickets schema and template documents
- drafting instructions including the citation requirement
- a small eval set across ticket categories with expected template match and key facts
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- every draft cites the template it used
- no draft is auto-sent; flag "no matching template" instead of inventing a response

Return the files or notebook cells to create, plus a 3-minute demo script.
```
