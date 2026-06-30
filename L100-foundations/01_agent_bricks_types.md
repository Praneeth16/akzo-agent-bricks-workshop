# L100 · Build the No Code Agent Bricks Agents

In `00_sql_ai_functions` you called AI from SQL. Now you build agents in the Agent Bricks UI, with no code, on the same synthetic AkzoNobel coatings data. By the end you will have created one of every single purpose Agent Bricks type.

This is a guided lab. Each section is a short set of clicks in the Databricks UI, plus a checkpoint that tells you what a working result looks like. The data setup (`../data/load_to_uc.py`) already created the tables and the document volume, so you can focus on the agents. The document **vector index** that the Knowledge Assistant reads is built in L200 chapter 5 — run it first if you want to do Section 2 end to end.

You do not have to click. Section 8 shows how to create the Genie spaces from code (`../genie/create_genie_spaces.py`) and where the Knowledge Assistant's vector index comes from — the repeatable path you would use in a real project.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.

---

## The seven Agent Bricks types

Open the workspace and choose **New** then **Agent**. The **Create new Agent** dialog is your menu of agent types.

![Create new Agent dialog](images/agent_bricks_create_new_agent.png)
> *Image: `images/agent_bricks_create_new_agent.png` — the Create new Agent picker. Prompt to regenerate it is in the [image prompts appendix](#appendix-image-prompts).*

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
| **Supervisor Agent** | Combine Genie Spaces, other agents, and MCP tools for complex workflows | (orchestrates the rest) | Built in L300 |

How to read this ladder:

- The three **Functions** types (Extraction, Parsing, Classification) are the simplest: one input → one AI call → structured output. They are the UI face of the `ai_*` functions, and each one is the seed of a hackathon track.
- The three **Chat** types are conversational. Genie chats with your **tables**; Knowledge Assistant chats with your **documents**; the Supervisor chats across **everything**, delegating to the others.
- **Code your own agent** is the escape hatch — when no managed type fits, you drop to the Agent Framework. It is the bridge to L200.
- The **Supervisor** is the flagship you assemble in L300, and it reuses the agents you build here.

---

## Prerequisites

Run the shared data setup first (`../data/load_to_uc.py`). It provisions the **tables and the document volume** below into the Unity Catalog you choose. On a lab environment such as Vocareum that is your assigned catalog, so set the `catalog` widget in the notebooks to match. Shown here as `<catalog>`:

| Resource | Location | Created by |
|---|---|---|
| Finance tables | `akzo_finance` (products, margin_actuals, margin_budget, fx_rates, cost_drivers) | `../data/load_to_uc.py` |
| Supply chain tables | `akzo_scm` (otif, inventory, lanes, service_levels) | `../data/load_to_uc.py` |
| Commercial tables | `akzo_commercial` (accounts, pipeline, sales_actuals, churn_signals) | `../data/load_to_uc.py` |
| Document volume | `/Volumes/<catalog>/akzo_docs/raw` (sds, contracts) | `../data/load_to_uc.py` |
| Vector index | `<catalog>.akzo_docs.chunks_idx` on endpoint `akzo_workshop_vs` | `../L200-capabilities/05_document_intelligence.py` (run before Section 2) |

> The vector index is **not** part of `data/load_to_uc.py` — it is built in L200 chapter 5. Run that notebook first if you want to do the Knowledge Assistant (Section 2) end to end. Genie spaces are created separately too (`../genie/`).

---

## 1. Genie Space, natural language to SQL

**Type:** Chat · Structured. A Genie Space turns your **tables** into a chat experience. Business users ask in plain language and Genie writes the SQL.

**How it works.** Genie does not guess against raw column names. You ground it with three things: the **tables** in scope, an **instructions** block (the grain, the units, which column is the certified metric), and **example NL→SQL pairs** (sample/trusted questions). On each question Genie retrieves that grounding, generates a Spark SQL query, runs it on your warehouse under your identity (so Unity Catalog row filters apply), and returns both the SQL and the result table. The more precise the instructions and examples, the more reliably it picks the right columns — that grounding is exactly what `../genie/*_space.md` pre-load for the three workshop domains.

![Genie Space chat](images/agent_bricks_genie_space.png)
> *Image: `images/agent_bricks_genie_space.png` — see the [appendix](#appendix-image-prompts).*

1. Open **Genie** from the left navigation, then **New**.
2. Add tables from `akzo_finance`: start with `margin_actuals`, `products`, and `fx_rates`.
3. Name the space `Finance Controlling`.
4. In the instructions, paste a short primer: the grain is one row per SKU, region, and month, amounts are in euros, and gross margin percent is `gross_margin_pct`.
5. Ask: *Which product line had the lowest gross margin percent in EMEA last quarter?*

**Checkpoint:** Genie returns a SQL query and a table of results. If it picks the wrong column, refine the instructions and ask again. This same space becomes the Finance domain in the L300 supervisor.

---

## 2. Knowledge Assistant, document Q and A

**Type:** Chat · Unstructured. Where Genie chats with your tables, a Knowledge Assistant chats with your **documents**. It turns a pile of PDFs into an expert chatbot with citations.

**How it works (RAG).** This is retrieval-augmented generation. The documents are chunked and embedded into a **vector index** (built in L200 chapter 5 — run it first). On each question the assistant embeds the question, retrieves the most similar chunks from the index, and passes them to the chat model as grounding — so the answer comes from *your* documents, not the model's memory. The **citation** back to the source chunk is the proof the answer is grounded, not invented. This is the one type that needs a Vector Search endpoint.

![Knowledge Assistant answer with citations](images/agent_bricks_knowledge_assistant.png)
> *Image: `images/agent_bricks_knowledge_assistant.png` — see the [appendix](#appendix-image-prompts).*

1. In the Create new Agent dialog, choose **Knowledge Assistant**.
2. Point it at the vector index `<catalog>.akzo_docs.chunks_idx` on endpoint `akzo_workshop_vs`.
3. Give it a name like `Coatings Document Assistant` and a short description: it answers questions about safety data sheets and supplier contracts.
4. Ask: *What is the flash point and the main hazard listed on the safety data sheet for the Interpon powder coatings?*

**Checkpoint:** the assistant answers with a citation back to the source document. Citations are the signal that the answer is grounded, not invented.

---

## 3. Information Extraction, fields from text

**Type:** Functions · Unstructured. Wraps **`ai_extract`**. You define a **schema** — the named fields you want — and the agent pulls those values out of free text into structured columns.

**How it works.** Unlike classification (which picks a label) or parsing (which structures a whole document), extraction is **targeted**: you say *exactly* which fields you want (`product`, `flash_point`, `supplier`, ...) and the model returns just those, typed and named. Give it messy text in, get clean columns out — the bridge from unstructured documents to a queryable table. It is the same call as the `ai_extract` you ran in SQL, with the schema defined in the UI.

![Information Extraction schema + result](images/agent_bricks_information_extraction.png)
> *Image: `images/agent_bricks_information_extraction.png` — see the [appendix](#appendix-image-prompts).*

1. In the Create new Agent dialog, choose **Information Extraction**.
2. Define the fields to pull, for example `product`, `flash_point`, `hazardous_substances`, and `supplier`.
3. Paste a safety data sheet excerpt, or point the agent at the `sds` documents in the volume.
4. Run it.

**Checkpoint:** the agent returns the fields as structured values. This is the UI version of the `ai_extract` call you ran in `00_sql_ai_functions`. The doc extraction hackathon track builds on this.

---

## 4. Document Parsing, structure a PDF

**Type:** Functions · Unstructured. Wraps **`ai_parse_document`**. Where extraction pulls a few named fields, parsing structures the **whole document** — text, section headers, tables, and metadata — into machine-readable elements.

**How it works.** A raw PDF is just pixels and layout to a database. Parsing reconstructs its structure: it returns the document as ordered elements (headings, paragraphs, tables) so downstream steps can index or query it. This is almost always **step one** of a document pipeline — you parse the PDF, then chunk + embed the result for a Knowledge Assistant, or feed specific sections to Information Extraction. Parse → then extract or retrieve.

![Document Parsing output](images/agent_bricks_document_parsing.png)
> *Image: `images/agent_bricks_document_parsing.png` — see the [appendix](#appendix-image-prompts).*

1. In the Create new Agent dialog, choose **Document Parsing**.
2. Point it at one PDF in `/Volumes/<catalog>/akzo_docs/raw/sds`.
3. Run it.

**Checkpoint:** the PDF comes back as structured elements, including the section headers and the product identification table. This is the UI version of `ai_parse_document`, and it is the first step of any document pipeline that feeds a Knowledge Assistant.

---

## 5. Text Classification, sort into labels

**Type:** Functions · Unstructured. Wraps **`ai_classify`**. You give it a set of **labels** and it sorts each input into one (or more) of them.

**How it works.** Labels can be **predefined** (you list them: `automotive`, `marine`, `architectural`, ...) or **dynamic** (the model proposes them from the data). No training set, no fine-tuning — the model classifies zero-shot from the label names plus your instructions. This is the routing primitive: triage inbound email to the right team, tag accounts by segment, bucket support tickets by urgency. It is the same `ai_classify` from the SQL notebook, and the seed of the ticket/email triage hackathon track.

![Text Classification labels](images/agent_bricks_text_classification.png)
> *Image: `images/agent_bricks_text_classification.png` — see the [appendix](#appendix-image-prompts).*

1. In the Create new Agent dialog, choose **Text Classification**.
2. Define labels that fit a coatings business, for example `automotive`, `marine`, `architectural`, `industrial`, and `aerospace`.
3. Feed it account names from `akzo_commercial.accounts`, or sample inbound emails.
4. Run it.

**Checkpoint:** each input gets a label. This is the UI version of `ai_classify`, and it is the core of the ticket and email triage hackathon track.

---

## 6. Code your own agent

**Type:** Custom. When the no-code types do not fit — custom control flow, a tool the managed types do not offer, a framework you already use — you write the agent yourself with OSS libraries and the **Agent Framework**.

**How it works.** You bring any framework (LangGraph, CrewAI, the OpenAI Agents SDK) and wrap it in the MLflow **`ResponsesAgent`** interface. That wrapper is the contract: once your agent speaks `ResponsesAgent`, it gets AI Playground, Agent Evaluation, MLflow tracing, and Model Serving **for free** — same as the managed types. The starter in `L100-agent-langgraph/` is exactly this: a small LangGraph agent, wrapped as a `ResponsesAgent`, that answers questions and calls one read-only managed MCP tool. Follow that folder's README to run it locally and deploy it.

![Code your own agent — ResponsesAgent + Agent Framework](images/agent_bricks_code_your_own.png)
> *Image: `images/agent_bricks_code_your_own.png` — see the [appendix](#appendix-image-prompts).*

**Checkpoint:** the agent answers a coatings question and the trace shows it calling the MCP tool. This is your entry to the MCP spine, which you extend in L200 by building your own MCP server.

---

## 7. Supervisor Agent (preview here, built in L300)

**Type:** Chat. The Supervisor is the top of the ladder: it does not answer directly, it **orchestrates** — given a cross-domain question, it decides which Genie Spaces, other agents, and MCP tools to consult, runs them, and fuses one answer.

**How it works.** Each subagent carries a **routing description** (what it is good at). The supervisor reads the question plus those descriptions, routes to the right subagents (e.g. Finance + SCM + Commercial for a margin-and-service question), collects their structured results, and composes a single answer with a visible routing trace. You do not build it here — it reuses the Genie spaces and agents from this lab — but you assemble it in **L300** (`../apps/supervisor/`). Keeping it in view now explains *why* you ground each domain agent well: the supervisor is only as good as the agents it routes to.

![Supervisor Agent routing](images/agent_bricks_supervisor.png)
> *Image: `images/agent_bricks_supervisor.png` — see the [appendix](#appendix-image-prompts).*

---

## 8. Programmatic setup, the same resources from code

Clicking is fine for learning. In a real project you create these resources from code so the setup is repeatable and reviewable.

### Genie spaces from code

[`../genie/create_genie_spaces.py`](../genie/create_genie_spaces.py) creates the three domain Genie spaces with the Genie Spaces API. Each space is grounded with table descriptions, an instruction block, example SQL, and sample questions (the configs live in `../genie/*_space.md`). It is idempotent and writes the space ids to `../genie/space_ids.json`.

```bash
AKZO_CATALOG=<catalog> DATABRICKS_WAREHOUSE_ID=<id> python3 ../genie/create_genie_spaces.py
```

Paste each printed id into the L200 supervisor widgets, or use the space directly in the UI. Full walkthrough: [`../genie/README.md`](../genie/README.md).

### Knowledge Assistant backbone from code

The document **vector index** a Knowledge Assistant reads is built in [`../L200-capabilities/05_document_intelligence.py`](../L200-capabilities/05_document_intelligence.py): it parses the PDFs (`ai_parse_document`), chunks + embeds them, and creates the Vector Search index on endpoint `akzo_workshop_vs`. Run that notebook once (it needs Vector Search enabled), then point a Knowledge Assistant at the resulting `<catalog>.akzo_docs.chunks_idx`.

**Checkpoint:** you created the Genie spaces from code and know where the Knowledge Assistant's vector index comes from. This is the repeatable pattern the L300 supervisor builds on.

---

## What you built

You created one of every single purpose Agent Bricks type, in the UI and from code, all grounded in the same coatings data. Each one maps to a SQL AI function you already met and to a hackathon track.

### Next
Continue to `02_agent_evaluation.ipynb` to measure agent quality, then `03_short_term_memory.ipynb`. After L100, move up to `../L200-capabilities/` to add tools, an MCP server you build, and the first agent that takes an action behind a human approval gate.

---

## Appendix: image prompts

The images referenced above are explainer diagrams, not Databricks screenshots (except the first, which mirrors the real **Create new Agent** dialog). Generate each with an image model (ChatGPT / DALL·E), save it to `L100-foundations/images/` under the exact filename, and it renders inline.

Shared style for all of them, so the set looks consistent:

> Clean, modern flat vector diagram. Light background (#F7F8FA), Databricks-style accent in orange-red (#FF3621) with secondary slate-grey and teal. Rounded rectangles, thin connector arrows, generous whitespace, no photorealism, no clutter. Sans-serif labels, legible at slide size. 16:9.

| File | Prompt (append to the shared style above) |
|---|---|
| `agent_bricks_create_new_agent.png` | "A 'Create new Agent' picker UI mockup. A row of filter pills at top: All, Chat, Functions, Structured, Unstructured, Custom. Below, a 2-column grid of seven cards, each with a small icon, a title and a one-line description: Supervisor Agent, Information Extraction, Knowledge Assistant, Document Parsing, Code your own agent, Text Classification, Genie Space. Chat-type cards use a speech-bubble icon; function-type cards use a document icon." |
| `agent_bricks_genie_space.png` | "A diagram of natural-language-to-SQL. Left: a person asking 'Which product line had the lowest gross margin in EMEA?' Middle: a 'Genie Space' box grounded by three labelled inputs — Tables, Instructions, Example Q→SQL pairs. Right: a generated SQL query and a small result table. An arrow shows the query running on a SQL warehouse 'under your identity (row filters apply)'." |
| `agent_bricks_knowledge_assistant.png` | "A retrieval-augmented-generation (RAG) flow. Left: a stack of PDF documents → 'chunk + embed' → a Vector Index cylinder. A user question embeds and retrieves the top matching chunks (highlighted), which feed a chat model that returns an answer with a citation badge pointing back to the source document. Label the loop 'retrieve → ground → answer with citation'." |
| `agent_bricks_information_extraction.png` | "A targeted field-extraction diagram. Left: a block of messy unstructured text (a safety data sheet excerpt). Middle: an 'ai_extract' box with a small schema list: product, flash_point, hazardous_substances, supplier. Right: a clean structured table with those exact columns filled in. Caption: 'messy text in → typed columns out'." |
| `agent_bricks_document_parsing.png` | "A document-structuring diagram. Left: a raw PDF page (pixels/layout). Middle: an 'ai_parse_document' box. Right: the same document broken into ordered structured elements — Heading, Paragraph, and a Table block with rows/columns, plus a metadata tag. An arrow continues right labelled 'then: chunk+embed (Knowledge Assistant) or extract fields'. Caption: 'parse first, then extract or retrieve'." |
| `agent_bricks_text_classification.png` | "A zero-shot text-classification diagram. Left: several short inputs (account names / inbound emails). Middle: an 'ai_classify' box showing a set of labels: automotive, marine, architectural, industrial, aerospace. Right: each input routed to its label bucket with a colored tag. A small note: 'predefined OR dynamic labels — no training set'." |
| `agent_bricks_code_your_own.png` | "A 'bring your own framework' diagram. Left: three framework logos-as-boxes (LangGraph, CrewAI, OpenAI Agents SDK) all flowing into a single wrapper box labelled 'MLflow ResponsesAgent'. From the wrapper, four arrows fan out to capability badges it unlocks for free: AI Playground, Agent Evaluation, MLflow Tracing, Model Serving. Caption: 'any framework → one interface → governed for free'." |
| `agent_bricks_supervisor.png` | "A multi-agent supervisor routing diagram. Center-top: a 'Supervisor Agent' box receiving a cross-domain question. It reads three 'routing descriptions' and fans out to three subagents — Finance (Genie), SCM (Genie), Commercial (Genie) — plus an MCP tool. Their structured results flow back up and merge into one fused answer with a small 'routing trace' tag. Caption: 'route → run subagents → fuse one answer'." |

> Tip: the first card image can also just be a cropped screenshot of your real workspace dialog — that is the most authentic. The rest are concept diagrams that a screenshot cannot capture.
