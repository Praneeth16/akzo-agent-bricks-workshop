# L100: Foundations, AI on Databricks for AkzoNobel

Start here. Learn to call AI from SQL and build the no code Agent Bricks agents, using only managed Databricks services over synthetic AkzoNobel coatings data. No agent code required at this tier.

---

## What You Will Build

| Capability | Powered By |
|---|---|
| AI from pure SQL (classify, extract, parse, summarize, mask, forecast) | SQL AI Functions |
| Natural language data queries | Genie Space |
| Document Q and A over safety sheets and policies | Knowledge Assistant |
| Field extraction and PDF parsing | Information Extraction, Document Parsing |
| Ticket and email triage | Text Classification |
| Your first coded agent that calls a tool | OpenAI Agents SDK plus one MCP tool |
| Cross-domain orchestration over your Genie spaces | Supervisor Agent + Supervisor API |
| Quality evaluation and human feedback | MLflow Tracing, LLM Judges, Review App |

---

## The Three Spines (and where L100 sits)

The workshop deepens three capabilities across L100, L200, and L300. At L100 you meet the starting point of each.

| Spine | L100 (here) |
|---|---|
| Agent Bricks types | Build the single purpose types: Genie, Knowledge Assistant, Extraction, Parsing, Classification, a coded agent — and the **Supervisor Agent** that orchestrates them (`04`) |
| MCP | Consume one read only MCP tool from a coded agent |
| Agents that act | None yet. Everything here is read only. Actions arrive in L200 |
| LLMOps | MLflow evaluation, one LLM judge, tracing, and `ai_mask` for governance |

---

## Get Started

Work through the materials in order.

1. `00_sql_ai_functions.ipynb` Call AI from SQL alone. The lowest barrier entry point and the reference for every function used later.
2. `01_agent_bricks_types.md` Build the no code Agent Bricks agents in the UI, on the same tables and documents.
3. `02_agent_evaluation.ipynb` Evaluate an agent with MLflow and a single LLM judge.
4. `03_short_term_memory.ipynb` Give an agent short term memory backed by Lakebase.
5. `04_multi_agent_supervisor.ipynb` Build the flagship **Supervisor Agent** over your three Genie spaces in the no code UI, then drive it from code with the **Supervisor API**.
6. `L100-agent-langgraph/` Your first coded agent. A LangGraph agent wrapped as an MLflow ResponsesAgent that answers questions and consumes one read only managed MCP tool.

The shared data setup in the repo root `data/` folder must run once before this tier. It creates the `akzo_*` schemas, the coatings tables, and the document volume. Genie spaces are created separately (see `../genie/`); the vector index is built in L200 chapter 5. See `../SETUP.md` for the full order.

---

## Prerequisites

- Databricks workspace with serverless SQL compute
- Foundation Model API access (for example Llama 3.3 70B or Claude Sonnet)
- Unity Catalog with permission to read the workshop catalog
- Vector Search and Databricks Apps enabled
- Shared data setup completed (see `../data/`)

Nothing to install locally for the SQL and UI labs. The coded agent uses `uv`.

---

## How the Notebooks Run

Every query is driven from Python through `spark.sql(...)` with the catalog and model endpoint read from notebook widgets. Nothing is hardcoded, the catalog and endpoint are validated before use, and the same notebook runs identically in an interactive session and as a scheduled job. Set the `catalog` and `llm_endpoint` widgets at the top, then run top to bottom. The supervisor notebook (`04`) additionally uses the Databricks SDK and the Supervisor API — it reads Genie space ids and a deployed-endpoint name from its own widgets.

---

## Configure Your Own IDs

Nothing in this tier is tied to one workspace. Set these before you run, all from your own workspace.

1. **Catalog.** Leave the `catalog` widget blank to use your current catalog (`current_catalog()`), or type your workshop catalog name. Run the shared `../data/` loader once first so the `akzo_*` schemas and tables exist.
2. **Model endpoint.** Set the `llm_endpoint` widget to a Foundation Model endpoint you can query (for example `databricks-claude-opus-4-8` or `databricks-llama-4-maverick`).
3. **Genie space (the no-code lab).** Create your Genie space in the UI: **New → Genie space**, attach the `akzo_finance` / `akzo_scm` / `akzo_commercial` tables, and ground it with the instructions from `../genie/`. The no-code lab works in the space directly. You can also create the spaces from code with `../genie/create_genie_spaces.py`, which prints the ids. Keep each space's id (the last URL segment of `/genie/rooms/<space_id>`) — you paste it into the widgets at L200 (the supervisor).

---

## Folder Contents

| Path | Purpose |
|------|---------|
| `00_sql_ai_functions.ipynb` | AI from SQL: query, classify, extract, parse, summarize, mask, forecast |
| `01_agent_bricks_types.md` | Guided build of the no code Agent Bricks types |
| `02_agent_evaluation.ipynb` | MLflow evaluation with an LLM judge |
| `03_short_term_memory.ipynb` | Short term memory on Lakebase |
| `04_multi_agent_supervisor.ipynb` | Build the Supervisor Agent in the UI, then drive it with the Supervisor API |
| `L100-agent-langgraph/` | First coded agent (LangGraph + ResponsesAgent), with one MCP tool |
| `L100_Architecture.drawio` | Architecture diagram for this tier (editable draw.io source; export to `L100_Architecture.png` to embed) |

---

## Next

Move up to `../L200-capabilities/` to add tools, memory, an MCP server you build yourself, and the first agent that takes an action behind a human approval gate.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.
