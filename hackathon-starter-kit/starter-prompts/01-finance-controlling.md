# Starter Prompt: Finance Controlling Copilot

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 01: Finance Controlling Copilot in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/01-finance-controlling/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-genie-space
3. add-mcp-tool only if needed for a KPI lookup
4. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create a finance Genie or notebook scaffold that answers:
"Why did EMEA decorative paints margin fall versus plan last month?"

Use the Akzo Finance Genie space and the provided tables in <TEAM_CATALOG>.akzo_finance
(products, margin_actuals, margin_budget, fx_rates, cost_drivers). Generate:
- Genie instructions for variance, margin, cost, price, volume, mix, and FX analysis
- 5 sample finance questions
- one notebook or code cell that verifies the catalog, warehouse, and Finance Genie space
- a small 5-row eval set with expected driver categories
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- mask personal fields if present
- cite generated SQL, metrics, or source rows
- say "not enough evidence" when data is missing

Return the files or notebook cells to create, plus a 3-minute demo script.
```

