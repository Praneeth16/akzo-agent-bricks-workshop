# Track 13: SAP BW And SSAS Migration Assistant

## Use Case And Target User

- **Use case:** #9 SAP BW and SSAS migration assistant
- **Primary users:** data engineers, BI migration teams, platform architects
- **Business question:** What is in our legacy BW cubes and SSAS models, and what does it take to move each measure to Databricks SQL?
- **Success signal:** A legacy cube's measures and MDX logic get translated into documented, working Databricks SQL with a clear dependency chain.

## Hackathon Goal

Build a migration assistant that reads legacy BW/SSAS cube metadata, converts representative MDX measures into Databricks SQL, and documents the dependency chain for a migration backlog.

## Starter Architecture

- **Agent pattern:** Code-Your-Own agent plus Knowledge Assistant over migration notes
- **Data plane:** synthetic BW/SSAS metadata table (cubes, measures, dimensions, MDX snippets)
- **Tool plane:** `ai_query` for MDX-to-SQL translation, dependency-chain builder
- **Control plane:** human review of translated SQL before it is treated as authoritative

## Data And Resources

- **Team-built tables (in your own personal schema):** synthetic BW/SSAS cube metadata (10-15 cubes with measures, dimensions, and MDX snippets). Not in the shared setup — create with `generate-synthetic-data`.
- **Documents:** none provided; migration notes are team-authored if you want a Knowledge Assistant layer.
- **Genie spaces:** optional, for querying the cube-metadata table itself.
- **Vector Search:** optional, only if you add migration-notes retrieval.
- **Free Edition note:** there is no live SAP BW or SSAS connector on Free Edition. Simulate the source system entirely with the synthetic metadata table above — do not attempt a live connection.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L200-capabilities/06_custom_agents_and_mcp.py` for the code-your-own agent pattern.
2. Generate 10-15 synthetic BW cubes with `generate-synthetic-data`, each with measures, dimensions, and one representative MDX snippet.
3. Build an agent that takes one MDX measure and converts it into equivalent Databricks SQL.
4. Have the agent document the dependency chain: source cube, dimensions used, and any downstream report that depends on the measure.
5. Evaluate translated SQL for correctness against a hand-checked expected result for at least 3 cubes.

## MCP, Tools, And Action Hooks

- **MCP tools:** cube-metadata lookup, dependency lookup
- **SQL AI Functions:** `ai_query`, `ai_summarize`
- **Action-plane hooks:** optional migration-ticket draft per translated measure
- **Approval model:** human review of every translated SQL statement before it is marked migration-ready

## Evaluation And Governance

- **Eval set:** 5-8 MDX-to-SQL translation pairs with expected SQL logic.
- **Judges:** translation correctness, dependency-chain completeness.
- **Governance:** every translation cites the source cube and MDX snippet it came from.
- **Failure behavior:** flag a measure as "needs manual review" instead of guessing at ambiguous MDX logic.

## Demo Script

1. Show the synthetic BW cube metadata table.
2. Pick one cube and ask the agent to translate its primary measure.
3. Show the generated Databricks SQL side by side with the original MDX.
4. Show the documented dependency chain.
5. Close with a migration-backlog summary across all cubes.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Addresses a real, costly legacy-BI migration problem |
| Agent quality | 25 | Correct MDX-to-SQL translation with dependency mapping |
| Governance | 20 | Source citation and human review before migration-ready status |
| Demo completeness | 20 | Legacy cube to translated, documented SQL |
| Reuse | 10 | Translation pattern reusable across additional cubes |

## Stretch Goals

- Batch-translate an entire cube's measure set in one pass.
- Add a migration-effort score per cube (measure count, MDX complexity).
- Add a rollback note for measures that cannot be cleanly translated.
