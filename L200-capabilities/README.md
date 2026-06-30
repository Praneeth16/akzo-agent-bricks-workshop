# L200: Capabilities, Coded Agents That Act

Step up from the no code tier. Here you build coded agents that call tools, hold memory in Lakebase, expose and consume an MCP server, run behind production governance, and take their first real action behind a human approval gate, all over the same synthetic AkzoNobel coatings data.

---

## What You Will Build

| Chapter | You build |
|---|---|
| `01_governed_supervisor.py` | A multi-domain supervisor (Finance + SCM + Commercial) that routes, runs each leg over governed Unity Catalog data with per-user row filtering, and fuses one answer |
| `02_agents_that_act.py` | The first agent that acts: stage → approve → execute a governed external call, logged end to end |
| `03_autonomous_loop.py` | A detect → decide → auto-act-or-escalate loop that runs unattended on a schedule |
| `04_trust_and_governance.py` | MLflow evaluation with an independent LLM judge, plus AI Gateway at scale |
| `05_document_intelligence.py` | Parse and extract PDFs → embed → RAG + SQL over safety sheets and contracts |
| `06_custom_agents_and_mcp.py` | A custom LangGraph agent registered in Unity Catalog, consuming an MCP tool |
| `07_custom_model_serving.py` | Register and serve a custom model on Model Serving |
| `08_long_term_memory.py` | Durable, cross-session memory: semantic recall over a `pgvector` store on Lakebase, with LLM-managed save/search/delete memory tools |

---

## The Three Spines (and where L200 sits)

| Spine | L200 (here) |
|---|---|
| Agent Bricks types | Add tools to a coded agent and compose multiple domains |
| MCP | Build and register a server, then consume it from an agent |
| Agents that act | One or two connectors behind a human approval gate, with an audit trail |
| LLMOps | Judge suite, AI Gateway, and guardrails |
| Memory | Short-term thread memory (L100 ch3) → durable semantic per-user memory on Lakebase (ch8) |

---

## Configure Your Own IDs

Nothing here is tied to one workspace. Each notebook reads its config from widgets at the top, so set these from your own workspace before you run.

1. **Catalog.** Leave the `catalog` widget blank to use your current catalog (`current_catalog()`), or type your workshop catalog. Run the shared `../data/` loader once first so the `akzo_*` schemas and tables exist.
2. **Model endpoints.** Set `llm_endpoint` / `chat_endpoint` / `agent_endpoint` / `judge_endpoint` to Foundation Model or custom endpoints you can query (for example `databricks-claude-opus-4-8`). The long-term-memory chapter also needs an `embedding_endpoint` (for example `databricks-gte-large-en`) to vectorize memories.
3. **Genie space ids** (supervisor chapter). Create each Genie space in the UI: **New → Genie space**, attach the `akzo_finance` / `akzo_scm` / `akzo_commercial` tables, then open the space. The id is the last URL segment of `/genie/rooms/<space_id>`. Paste each id into the `finance_space_id` / `scm_space_id` / `commercial_space_id` widgets. Leave a field blank to use the in-code `ai_query` fallback. You can also create the spaces from code with `../genie/create_genie_spaces.py`, which prints the ids.
4. **Lakebase instance** (action, autonomous, and long-term-memory chapters). Set the `lakebase_instance` widget to your Lakebase database instance name (Compute → Database instances), or leave it blank in ch8 to auto-pick the first AVAILABLE one. Ch8 needs permission to `CREATE EXTENSION vector` + `CREATE TABLE` on the Lakebase `public` schema.
5. **Mock systems app URL** (action + autonomous chapters). After deploying the mock systems app (`../deploy/deploy_mock_systems.sh`), open it and copy its URL into the `mock_app_url` widget.
6. **AI Gateway endpoint** (governance chapter). Set `gateway_endpoint` to your AI Gateway serving endpoint, or skip Part B.

---

## How the Notebooks Run

Every notebook is parametrized through `dbutils.widgets`: the catalog defaults to your current catalog, model endpoints and resource ids are read from widgets, and nothing is hardcoded to one workspace. Set the widgets at the top, then run top to bottom.

The shared data setup in the repo root `../data/` folder must run once before this tier.

---

## Next

The L300 use case wires the full fleet together: see the flagship multi-domain supervisor in `../apps/supervisor/`.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.
