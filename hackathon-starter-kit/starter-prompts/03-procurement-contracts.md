# Starter Prompt: Procurement Contract Intelligence

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 03: Procurement Contract Intelligence on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/03-procurement-contracts/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-genie-space only if supplier or spend context is needed
3. add-mcp-tool for a read-only clause standard lookup
4. deploy after extraction eval passes

Provided documents: 6 supplier contracts in /Volumes/<TEAM_CATALOG>/<your-personal-schema>/docs_raw/contracts/,
with ground-truth fields in data/output/docs/README.md. Score extraction against that table.

Build the first runnable loop for one supplier contract. Use ai_parse_document and ai_extract to produce a clause table.

Extract the real contract fields:
- supplier_name
- category
- annual_spend_eur
- payment_terms_net_days
- price_escalation_clause
- termination_notice_days
- liability cap and governing law
- risk label and rationale (flag non-standard payment terms over EUR 1M spend)

Create:
- parsing and extraction notebook cells
- expected schema for extracted clauses
- eval set over the 6 contracts using data/output/docs/README.md ground truth
- citation requirement for every flagged clause
- negotiation guidance draft for human review

Governance requirements:
- mark missing clauses as "not found"
- do not invent legal terms
- cite page, section, or chunk for each risk flag
- keep output review-ready, not auto-sent

Return the notebook cells, extraction schema, eval set, and demo script.
```

