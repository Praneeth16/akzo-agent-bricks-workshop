# Starter Prompt: Document Extraction Cluster

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 11: Document Extraction Cluster in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/11-doc-extraction-cluster/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-mcp-tool for template or evidence lookup if needed
3. add-connector only for a reviewer assignment or draft response
4. deploy after extraction eval passes

Provided documents: 8 safety data sheets and 6 supplier contracts in
/Volumes/<TEAM_CATALOG>/akzo_docs/raw, with ground truth in data/output/docs/README.md.
Claims, ESG questionnaires, and quote emails are not provided; add your own or use generate-synthetic-data.

Choose one workflow: product/safety extraction (provided docs), claims response drafting, ESG questionnaire, or pricing request extraction.

Build the first runnable loop:
- parse one document or message
- extract required fields into a table
- classify risk, intent, or completeness
- produce a reviewer-ready output

Create:
- extraction schema
- notebook cells using ai_parse_document, ai_extract, ai_classify, and ai_summarize as needed
- eval set scored against data/output/docs/README.md for provided docs
- reviewer approval step for any outbound draft

Governance requirements:
- mark missing fields instead of guessing
- mask sensitive fields where relevant
- cite evidence chunks for extracted claims
- keep outbound content in draft state

Return the notebook cells, schema, eval set, and demo script.
```

