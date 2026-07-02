# Starter Prompt: Pricing And Quote Generation

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 06: Pricing And Quote-Generation Agent on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/06-pricing-quote-generation/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-genie-space for Commercial data grounding
3. add-mcp-tool for price and customer lookup
4. add-connector for a quote email or CRM draft in proposed state
5. deploy after the quote draft flow works

Provided tables: <TEAM_CATALOG>.<your-personal-schema>.products (list_price_eur, standard_cost_eur)
for price and margin floor, and <your-personal-schema>.accounts / sales_actuals for customer context.
Price lists and quote history are not provided; generate them with generate-synthetic-data if needed.

Build the first runnable loop from one inbound request email. Extract the quote parameters, look up pricing, apply margin guardrails, and draft a quote for approval.

Create:
- extraction schema for customer, product, volume, region, requested date, and terms
- pricing lookup against <your-personal-schema>.products (or a generated price list)
- margin floor from standard_cost_eur
- draft quote response
- 6 eval requests with expected fields and price band

Governance requirements:
- never send the quote automatically
- human approval is required before email or CRM update
- flag missing required fields for clarification
- cite price source or Commercial Genie answer

Return the agent scaffold, tool schemas, connector stub, eval set, and demo script.
```

