# Starter Prompt: SAP BW And SSAS Migration Assistant

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 13: SAP BW And SSAS Migration Assistant on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/13-sap-bw-ssas-migration/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. generate-synthetic-data for synthetic BW/SSAS cube metadata
3. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Generate 10-15
synthetic BW cubes in <TEAM_CATALOG>.<your-personal-schema>, each with
measures, dimensions, and one representative MDX snippet. There is no
live SAP BW or SSAS connector on Free Edition — this synthetic table is
the source system for the whole track.

Then convert one representative MDX measure per cube into equivalent
Databricks SQL, and document the dependency chain (source cube,
dimensions used, downstream report if any). Generate:
- the synthetic cube-metadata schema and generation logic
- a code-your-own agent or notebook that performs the MDX-to-SQL translation
- a small eval set of 5-8 MDX-to-SQL pairs with expected SQL logic
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- cite the source cube and MDX snippet for every translation
- flag a measure as "needs manual review" instead of guessing at ambiguous MDX logic

Return the files or notebook cells to create, plus a 3-minute demo script.
```
