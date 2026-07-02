# Starter Prompt: Product And Safety Document Extraction

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 11: Product And Safety Document Extraction on Databricks
Free Edition (or Vocareum, if that is your lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/11-product-safety-extraction/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-mcp-tool only if needed for product or hazard-class lookup
3. deploy only after the demo path runs

Build the first runnable loop, not the whole product. Create a notebook or scaffold that:
- parses one safety data sheet from /Volumes/<TEAM_CATALOG>/<your-personal-schema>/docs_raw/sds/
  with ai_parse_document
- extracts product name, hazard classification, flash point, PPE requirements, storage conditions,
  and first-aid measures with ai_extract
- classifies severity or handling category with ai_classify

Use the ground-truth table in data/output/docs/README.md to score extracted fields. Generate:
- an extraction schema for the fields above
- one notebook or code cell that verifies the catalog, warehouse, and the sds volume
- a small eval set scoring extracted fields against the ground-truth table
- MLflow tracing or an equivalent trace checkpoint

Governance requirements:
- no hardcoded catalog except <TEAM_CATALOG>
- cite the source document and section for every extracted field
- mark a field as "not found" instead of guessing when the sheet does not state it

Return the files or notebook cells to create, plus a 3-minute demo script.
```
