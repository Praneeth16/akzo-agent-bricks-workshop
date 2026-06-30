# Starter Prompt: Forecast Planner Copilot On MMF

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 05: Forecast Planner Copilot on MMF in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/05-forecast-planner-mmf/README.md

Provided SCM tables in <TEAM_CATALOG>.akzo_scm: otif, inventory, lanes, service_levels.
There is no demand-history or forecast-version table; build a series from these or generate one.

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for a demand-history and forecast-version table in akzo_ops (or derive a series from akzo_scm)
3. add-mcp-tool for forecast version lookup
4. add-connector only for a propose-only override action
5. deploy after the forecast comparison runs

Build the first runnable loop:
"Why did the forecast increase for a product-region, and should the planner override it?"

Create:
- a monthly series from akzo_scm.service_levels or otif, or a generated demand table
- notebook cells using ai_forecast for a baseline series
- forecast version comparison logic
- driver summary using the series, inventory, OTIF, and any generated exogenous signals
- override recommendation text with confidence
- 6 eval questions with expected driver labels

Governance requirements:
- all overrides are propose-only and require planner approval
- state when series history is too short
- show forecast version, baseline, and evidence
- do not overwrite MMF outputs

Return notebook cells, agent instructions, eval set, and demo script.
```

