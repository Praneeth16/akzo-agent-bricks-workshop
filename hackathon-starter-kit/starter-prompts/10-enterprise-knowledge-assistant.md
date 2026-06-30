# Starter Prompt: Enterprise Knowledge Assistant

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 10: Enterprise Knowledge Assistant in Vocareum.

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/10-enterprise-knowledge-assistant/README.md

Use ai-dev-kit skills in this order:
1. scaffold-copilot
2. add-mcp-tool only for document metadata lookup if useful
3. deploy after citation eval passes

Provided documents in /Volumes/<TEAM_CATALOG>/akzo_docs/raw: 8 safety data sheets (sds/)
and 6 supplier contracts (contracts/), indexed by akzo_docs.chunks_idx on endpoint akzo_workshop_vs.
SOPs and policies are not provided; add and re-index them only if your demo needs them.

Build the first runnable loop: a Knowledge Assistant over the provided safety sheets and contracts.

Create:
- Knowledge Assistant instructions requiring citations
- document scope and metadata filter plan
- 10-question eval set with expected source document names
- refusal behavior for unsupported questions
- one notebook or code check that confirms the Vector Search index is ready

Governance requirements:
- answer only from retrieved evidence
- include citations for every answer
- say "not found in approved documents" when evidence is missing
- preserve UC volume permissions

Return the assistant instructions, index check, eval set, and demo script.
```

