# L100 · Build the No Code Agent Bricks Agents

In `00_sql_ai_functions` you called AI from SQL. Now you build agents in the Agent Bricks UI, with no code, on the same synthetic AkzoNobel coatings data. By the end you will have created one of every single purpose Agent Bricks type.

This is a guided lab. Each section is a short set of clicks in the Databricks UI, plus a checkpoint that tells you what a working result looks like. The data setup (`../data/load_to_uc.py`) already created the tables and the document volume, so you can focus on the agents. The document **vector index** that the Knowledge Assistant reads is built in L200 chapter 5 — run it first if you want to do Section 2 end to end.

You do not have to click. Section 8 shows how to create the Genie spaces from code (`../genie/create_genie_spaces.py`) and where the Knowledge Assistant's vector index comes from — the repeatable path you would use in a real project.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.

---

## The seven Agent Bricks types

Open the workspace and choose **New** then **Agent**. The **Create new Agent** dialog is your menu of agent types.

The filter tabs across the top — **All · Chat · Functions · Structured · Unstructured · Custom** — group the types by how you interact with them. That grouping is the fastest way to understand what each type is *for*:

| Tab | Means | Types under it |
|---|---|---|
| **Chat** | conversational, you ask in plain language | Genie Space, Knowledge Assistant, Supervisor Agent |
| **Functions** | a single AI primitive you call on input | Information Extraction, Document Parsing, Text Classification |
| **Structured** | works over **structured** data (your tables) | Genie Space |
| **Unstructured** | works over **unstructured** data (text, PDFs) | Knowledge Assistant, Information Extraction, Document Parsing, Text Classification |
| **Custom** | you write the agent code yourself | Code your own agent |

The seven types, each mapped to the SQL AI function it wraps (the ones you ran in `00_sql_ai_functions`) and where you build it:

| Type | What it does (from the dialog) | Wraps | You build it in |
|---|---|---|---|
| **Genie Space** | Turn your tables into an expert AI chatbot with natural language to SQL conversion | (text2SQL) | Section 1 |
| **Knowledge Assistant** | Turn your docs into an expert AI chatbot with intelligent document Q&A | retrieval + `ai_query` | Section 2 |
| **Information Extraction** | Pull specific data points, entities, and fields from unstructured text | `ai_extract` | Section 3 |
| **Document Parsing** | Extract structured content from documents — text, tables, metadata | `ai_parse_document` | Section 4 |
| **Text Classification** | Categorize text into predefined or dynamic labels | `ai_classify` | Section 5 |
| **Code your own agent** | Build with OSS libraries and the Agent Framework | (any) | Section 6 + `L100-agent-langgraph/` |
| **Supervisor Agent** | Combine Genie Spaces, other agents, and MCP tools for complex workflows | (orchestrates the rest) | Section 7 + `04_multi_agent_supervisor` |

How to read this ladder:

- The three **Functions** types (Extraction, Parsing, Classification) are the simplest: one input → one AI call → structured output. They are the UI face of the `ai_*` functions, and each one is the seed of a hackathon track.
- The three **Chat** types are conversational. Genie chats with your **tables**; Knowledge Assistant chats with your **documents**; the Supervisor chats across **everything**, delegating to the others.
- **Code your own agent** is the escape hatch — when no managed type fits, you drop to the Agent Framework. It is the bridge to L200.
- The **Supervisor** is the flagship you assemble in L300, and it reuses the agents you build here.

---

## Prerequisites

Run the shared data setup first (`../data/load_to_uc.py`). It provisions the **tables and the document volume** below, flat inside your one personal schema (most lab workspaces, e.g. Vocareum, only grant that one pre-provisioned schema per user — no `CREATE SCHEMA` needed). Shown here as `<catalog>.<schema>`:

| Resource | Location | Created by |
|---|---|---|
| Finance tables | `<catalog>.<schema>` (products, margin_actuals, margin_budget, fx_rates, cost_drivers) | `../data/load_to_uc.py` |
| Supply chain tables | `<catalog>.<schema>` (otif, inventory, lanes, service_levels) | `../data/load_to_uc.py` |
| Commercial tables | `<catalog>.<schema>` (accounts, pipeline, sales_actuals, churn_signals) | `../data/load_to_uc.py` |
| Document volume | `/Volumes/<catalog>/<schema>/docs_raw` (sds, contracts) | `../data/load_to_uc.py` |
| Vector index | `<catalog>.<schema>.chunks_idx` on endpoint `akzo_workshop_vs` | `../L200-capabilities/05_document_intelligence.py` (run before Section 2) |

> The vector index is **not** part of `data/load_to_uc.py` — it is built in L200 chapter 5. Run that notebook first if you want to do the Knowledge Assistant (Section 2) end to end. Genie spaces are created separately too (`../genie/`).

---

## 1. Genie Space, natural language to SQL

**Type:** Chat · Structured. A Genie Space turns your **tables** into a chat experience. Business users ask in plain language and Genie writes the SQL.

**How it works.** Genie does not guess against raw column names. You ground it with three things: the **tables** in scope, an **instructions** block (the grain, the units, which column is the certified metric), and **example NL→SQL pairs** (sample/trusted questions). On each question Genie retrieves that grounding, generates a Spark SQL query, runs it on your warehouse under your identity (so Unity Catalog row filters apply), and returns both the SQL and the result table. The more precise the instructions and examples, the more reliably it picks the right columns — that grounding is exactly what `../genie/*_space.md` pre-load for the three workshop domains.

1. Open **Genie** from the left navigation, then **New**.
2. Add tables from your schema: start with `margin_actuals`, `products`, and `fx_rates`.
3. Name the space `Finance Controlling`.
4. In the instructions, paste a short primer: the grain is one row per SKU, region, and month, amounts are in euros, and gross margin percent is `gross_margin_pct`.
5. Ask: *Which product line had the lowest gross margin percent in EMEA last quarter?*

**Checkpoint:** Genie returns a SQL query and a table of results. If it picks the wrong column, refine the instructions and ask again. This same space becomes the Finance domain in the L300 supervisor.

---

## 2. Knowledge Assistant, document Q and A

**Type:** Chat · Unstructured. Where Genie chats with your tables, a Knowledge Assistant chats with your **documents**. It turns a pile of PDFs into an expert chatbot with citations.

> **Free Edition:** Knowledge Assistant is on Databricks' unsupported-features list for Free Edition. Alternative: build the same retrieval-and-answer loop in code using [`../L200-capabilities/05_document_intelligence.py`](../L200-capabilities/05_document_intelligence.py)'s Vector Search index (`<catalog>.<schema>.chunks_idx`) plus a manual `ai_query` call over the top-k retrieved chunks — same governed-citation outcome, no no-code UI wizard required.

**How it works (RAG).** This is retrieval-augmented generation. The documents are chunked and embedded into a **vector index** (built in L200 chapter 5 — run it first). On each question the assistant embeds the question, retrieves the most similar chunks from the index, and passes them to the chat model as grounding — so the answer comes from *your* documents, not the model's memory. The **citation** back to the source chunk is the proof the answer is grounded, not invented. This is the one type that needs a Vector Search endpoint.

1. In the Create new Agent dialog, choose **Knowledge Assistant**.
2. Point it at the vector index `<catalog>.<schema>.chunks_idx` on endpoint `akzo_workshop_vs`.
3. Give it a name like `Coatings Document Assistant` and a short description: it answers questions about safety data sheets and supplier contracts.
4. Ask: *What is the flash point and the main hazard listed on the safety data sheet for the Interpon powder coatings?*

**Checkpoint:** the assistant answers with a citation back to the source document. Citations are the signal that the answer is grounded, not invented.

---

## 3. Information Extraction, fields from text

**Type:** Functions · Unstructured. Wraps **`ai_extract`**. You define a **schema** — the named fields you want — and the agent pulls those values out of free text into structured columns.

**How it works.** Unlike classification (which picks a label) or parsing (which structures a whole document), extraction is **targeted**: you say *exactly* which fields you want (`product`, `flash_point`, `supplier`, ...) and the model returns just those, typed and named. Give it messy text in, get clean columns out — the bridge from unstructured documents to a queryable table. It is the same call as the `ai_extract` you ran in SQL, with the schema defined in the UI.

1. In the Create new Agent dialog, choose **Information Extraction**.
2. Define the fields to pull, for example `product`, `flash_point`, `hazardous_substances`, and `supplier`.
3. Paste a safety data sheet excerpt, or point the agent at the `sds` documents in the volume.
4. Run it.

**Checkpoint:** the agent returns the fields as structured values. This is the UI version of the `ai_extract` call you ran in `00_sql_ai_functions`. The doc extraction hackathon track builds on this.

---

## 4. Document Parsing, structure a PDF

**Type:** Functions · Unstructured. Wraps **`ai_parse_document`**. Where extraction pulls a few named fields, parsing structures the **whole document** — text, section headers, tables, and metadata — into machine-readable elements.

**How it works.** A raw PDF is just pixels and layout to a database. Parsing reconstructs its structure: it returns the document as ordered elements (headings, paragraphs, tables) so downstream steps can index or query it. This is almost always **step one** of a document pipeline — you parse the PDF, then chunk + embed the result for a Knowledge Assistant, or feed specific sections to Information Extraction. Parse → then extract or retrieve.

1. In the Create new Agent dialog, choose **Document Parsing**.
2. Point it at one PDF in `/Volumes/<catalog>/<schema>/docs_raw/sds`.
3. Run it.

**Checkpoint:** the PDF comes back as structured elements, including the section headers and the product identification table. This is the UI version of `ai_parse_document`, and it is the first step of any document pipeline that feeds a Knowledge Assistant.

---

## 5. Text Classification, sort into labels

**Type:** Functions · Unstructured. Wraps **`ai_classify`**. You give it a set of **labels** and it sorts each input into one (or more) of them.

**How it works.** Labels can be **predefined** (you list them: `automotive`, `marine`, `architectural`, ...) or **dynamic** (the model proposes them from the data). No training set, no fine-tuning — the model classifies zero-shot from the label names plus your instructions. This is the routing primitive: triage inbound email to the right team, tag accounts by segment, bucket support tickets by urgency. It is the same `ai_classify` from the SQL notebook, and the seed of the ticket/email triage hackathon track.

1. In the Create new Agent dialog, choose **Text Classification**.
2. Define labels that fit a coatings business, for example `automotive`, `marine`, `architectural`, `industrial`, and `aerospace`.
3. Feed it account names from your `accounts` table, or sample inbound emails.
4. Run it.

**Checkpoint:** each input gets a label. This is the UI version of `ai_classify`, and it is the core of the ticket and email triage hackathon track.

---

## 6. Code your own agent

**Type:** Custom. When the no-code types do not fit — custom control flow, a tool the managed types do not offer, a framework you already use — you write the agent yourself with OSS libraries and the **Agent Framework**.

**How it works.** You bring any framework (LangGraph, CrewAI, the OpenAI Agents SDK) and wrap it in the MLflow **`ResponsesAgent`** interface. That wrapper is the contract: once your agent speaks `ResponsesAgent`, it gets AI Playground, Agent Evaluation, MLflow tracing, and Model Serving **for free** — same as the managed types. The starter in `L100-agent-langgraph/` is exactly this: a small LangGraph agent, wrapped as a `ResponsesAgent`, that answers questions and calls one read-only managed MCP tool. Follow that folder's README to run it locally and deploy it.

**Checkpoint:** the agent answers a coatings question and the trace shows it calling the MCP tool. This is your entry to the MCP spine, which you extend in L200 by building your own MCP server.

---

## 7. Supervisor Agent (build it in `04_multi_agent_supervisor`)

**Type:** Chat. The Supervisor is the top of the ladder: it does not answer directly, it **orchestrates** — given a cross-domain question, it decides which Genie Spaces, other agents, and MCP tools to consult, runs them, and fuses one answer.

**How it works.** Each subagent carries a **routing description** (what it is good at). The supervisor reads the question plus those descriptions, routes to the right subagents (e.g. Finance + SCM + Commercial for a margin-and-service question), collects their structured results, and composes a single answer with a visible routing trace. Because it runs with the **caller's** Unity Catalog permissions (OBO), the same governance that scopes each Genie space scopes the supervisor too. Keeping it in view now explains *why* you ground each domain agent well: the supervisor is only as good as the agents it routes to.

**Build it next.** [`04_multi_agent_supervisor.ipynb`](04_multi_agent_supervisor.ipynb) walks you through assembling a Supervisor over the three Akzo Genie spaces in the **no-code UI**, then driving it from code with the **Supervisor API** (call the deployed endpoint, and verify each subagent from the Genie Conversation API). You revisit the same route → run → fuse loop in pure Python in L200 chapter 1, and ship it as an app in **L300** (`../apps/supervisor/`).

---

## 8. Programmatic setup, the same resources from code

Clicking is fine for learning. In a real project you create these resources from code so the setup is repeatable and reviewable.

### Genie spaces from code

[`../genie/create_genie_spaces.py`](../genie/create_genie_spaces.py) creates the three domain Genie spaces with the Genie Spaces API. Each space is grounded with table descriptions, an instruction block, example SQL, and sample questions (the configs live in `../genie/*_space.md`). It is idempotent and writes the space ids to `../genie/space_ids.json`.

```bash
AKZO_CATALOG=<catalog> AKZO_SCHEMA=<schema> python3 ../genie/create_genie_spaces.py
```

Paste each printed id into the L200 supervisor widgets, or use the space directly in the UI. Full walkthrough: [`../genie/README.md`](../genie/README.md).

### Knowledge Assistant backbone from code

The document **vector index** a Knowledge Assistant reads is built in [`../L200-capabilities/05_document_intelligence.py`](../L200-capabilities/05_document_intelligence.py): it parses the PDFs (`ai_parse_document`), chunks + embeds them, and creates the Vector Search index on endpoint `akzo_workshop_vs`. Run that notebook once (it needs Vector Search enabled), then point a Knowledge Assistant at the resulting `<catalog>.<schema>.chunks_idx`. On Free Edition, where Knowledge Assistant itself is unsupported (Section 2), this same notebook plus a manual `ai_query` retrieval step is the code-only alternative.

**Checkpoint:** you created the Genie spaces from code and know where the Knowledge Assistant's vector index comes from. This is the repeatable pattern the L300 supervisor builds on.

---

## What you built

You created one of every single purpose Agent Bricks type, in the UI and from code, all grounded in the same coatings data. Each one maps to a SQL AI function you already met and to a hackathon track.

### Next
Continue to `02_agent_evaluation.ipynb` to measure agent quality, then `03_short_term_memory.ipynb`. After L100, move up to `../L200-capabilities/` to add tools, an MCP server you build, and the first agent that takes an action behind a human approval gate.
