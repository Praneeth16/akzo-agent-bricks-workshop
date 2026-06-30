# L100 · Build the No Code Agent Bricks Agents

In `00_sql_ai_functions` you called AI from SQL. Now you build agents in the Agent Bricks UI, with no code, on the same synthetic AkzoNobel coatings data. By the end you will have created one of every single purpose Agent Bricks type.

This is a guided lab. Each section is a short set of clicks in the Databricks UI, plus a checkpoint that tells you what a working result looks like. The data setup already created every resource you need (the tables, the document volume, the chunked docs, and the vector index), so you can focus on the agents.

You do not have to click. Section 7 shows how to create the Genie spaces and the Knowledge Assistant backbone from Python instead, which is how you would set this up repeatably in a real project. The scripts live in `../data/setup/`.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.

---

## The seven Agent Bricks types

Open the workspace and choose **New** then **Agent**. The Create new Agent dialog shows the types you will work through:

| Type | What it does | You build it in |
|---|---|---|
| Genie Space | Natural language to SQL over your tables | Section 1 |
| Knowledge Assistant | Document Q and A over a vector index | Section 2 |
| Information Extraction | Pull named fields from text | Section 3 |
| Document Parsing | Structure a PDF into text and tables | Section 4 |
| Text Classification | Sort text into labels | Section 5 |
| Code your own agent | Build with the Agent Framework | Section 6 and `L100-agent-langgraph/` |
| Supervisor Agent | Combine Genie, other agents, and MCP tools | Built in L300 |

The first five are no code. Code your own is the bridge to L200. The Supervisor is the flagship you assemble in L300, and it reuses the agents you build here.

---

## Prerequisites

Run the shared data setup first (see `../data/`). It provisions everything below into the Unity Catalog you choose. On a lab environment such as Vocareum that is your assigned catalog, so set the `catalog` widget in the notebooks to match. Shown here as `<catalog>`:

| Resource | Location |
|---|---|
| Finance tables | `akzo_finance` (products, margin_actuals, margin_budget, fx_rates, cost_drivers) |
| Supply chain tables | `akzo_scm` (otif, inventory, lanes, service_levels) |
| Commercial tables | `akzo_commercial` (accounts, pipeline, sales_actuals, churn_signals) |
| Document volume | `/Volumes/<catalog>/akzo_docs/raw` (sds, contracts) |
| Vector index | `<catalog>.akzo_docs.chunks_idx` on endpoint `akzo_workshop_vs` |

---

## 1. Genie Space, natural language to SQL

A Genie Space turns your tables into a chat experience. Business users ask in plain language and Genie writes the SQL.

1. Open **Genie** from the left navigation, then **New**.
2. Add tables from `akzo_finance`: start with `margin_actuals`, `products`, and `fx_rates`.
3. Name the space `Finance Controlling`.
4. In the instructions, paste a short primer: the grain is one row per SKU, region, and month, amounts are in euros, and gross margin percent is `gross_margin_pct`.
5. Ask: *Which product line had the lowest gross margin percent in EMEA last quarter?*

**Checkpoint:** Genie returns a SQL query and a table of results. If it picks the wrong column, refine the instructions and ask again. This same space becomes the Finance domain in the L300 supervisor.

---

## 2. Knowledge Assistant, document Q and A

A Knowledge Assistant answers questions over documents using the vector index built during setup.

1. In the Create new Agent dialog, choose **Knowledge Assistant**.
2. Point it at the vector index `<catalog>.akzo_docs.chunks_idx` on endpoint `akzo_workshop_vs`.
3. Give it a name like `Coatings Document Assistant` and a short description: it answers questions about safety data sheets and supplier contracts.
4. Ask: *What is the flash point and the main hazard listed on the safety data sheet for the Interpon powder coatings?*

**Checkpoint:** the assistant answers with a citation back to the source document. Citations are the signal that the answer is grounded, not invented.

---

## 3. Information Extraction, fields from text

1. In the Create new Agent dialog, choose **Information Extraction**.
2. Define the fields to pull, for example `product`, `flash_point`, `hazardous_substances`, and `supplier`.
3. Paste a safety data sheet excerpt, or point the agent at the `sds` documents in the volume.
4. Run it.

**Checkpoint:** the agent returns the fields as structured values. This is the UI version of the `ai_extract` call you ran in `00_sql_ai_functions`. The doc extraction hackathon track builds on this.

---

## 4. Document Parsing, structure a PDF

1. In the Create new Agent dialog, choose **Document Parsing**.
2. Point it at one PDF in `/Volumes/<catalog>/akzo_docs/raw/sds`.
3. Run it.

**Checkpoint:** the PDF comes back as structured elements, including the section headers and the product identification table. This is the UI version of `ai_parse_document`, and it is the first step of any document pipeline that feeds a Knowledge Assistant.

---

## 5. Text Classification, sort into labels

1. In the Create new Agent dialog, choose **Text Classification**.
2. Define labels that fit a coatings business, for example `automotive`, `marine`, `architectural`, `industrial`, and `aerospace`.
3. Feed it account names from `akzo_commercial.accounts`, or sample inbound emails.
4. Run it.

**Checkpoint:** each input gets a label. This is the UI version of `ai_classify`, and it is the core of the ticket and email triage hackathon track.

---

## 6. Code your own agent

When the no code types do not fit, you write the agent. The starter is in `L100-agent-langgraph/`. It is a small LangGraph agent, wrapped as an MLflow ResponsesAgent, that answers questions and calls one read only managed MCP tool. Follow that folder's README to run it locally and deploy it.

**Checkpoint:** the agent answers a coatings question and the trace shows it calling the MCP tool. This is your entry to the MCP spine, which you extend in L200 by building your own MCP server.

---

## 7. Programmatic setup, the same resources from code

Clicking is fine for learning. In a real project you create these resources from code so the setup is repeatable and reviewable. The `../data/setup/` folder does exactly that, and it was run and verified for this workshop.

### Genie spaces from code

`setup_genie_spaces.py` creates the three domain Genie spaces with the Genie Spaces API. Each space is grounded with table descriptions, an instruction block, example SQL, and sample questions. It is idempotent and writes the space ids to `space_ids.json`.

```bash
python ../data/setup/setup_genie_spaces.py --catalog <catalog>
```

Verify a space answers, using the Conversation API:

```bash
python ../data/setup/query_genie.py --catalog <catalog> --space finance
```

This returns real SQL and results. For example the finance space answered the Paints EMEA gross margin question with 39.3 percent in January, 40.0 in February, and 39.5 in March 2026, generated and run as SQL over the coatings tables.

### Knowledge Assistant backbone from code

`setup_vector_search.py` ensures the Vector Search endpoint and the delta sync index that a Knowledge Assistant reads, then reports when the index is ready.

```bash
python ../data/setup/setup_vector_search.py --catalog <catalog>
```

It prints the endpoint and index to point a Knowledge Assistant at. For this workshop the index reports ready with the document chunks indexed.

**Checkpoint:** you created the Genie spaces and the Knowledge Assistant backbone without touching the UI, and confirmed a Genie space answers a question over the real tables. This is the repeatable pattern the L300 supervisor builds on.

---

## What you built

You created one of every single purpose Agent Bricks type, in the UI and from code, all grounded in the same coatings data. Each one maps to a SQL AI function you already met and to a hackathon track.

### Next
Continue to `02_agent_evaluation.ipynb` to measure agent quality, then `03_short_term_memory.ipynb`. After L100, move up to `../L200-capabilities/` to add tools, an MCP server you build, and the first agent that takes an action behind a human approval gate.
