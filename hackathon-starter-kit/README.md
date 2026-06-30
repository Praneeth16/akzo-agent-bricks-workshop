# Hackathon Starter Kit

This kit turns the workshop into forkable team tracks. Each track starts from the same template so teams can compare builds, reuse the L100-L300 assets, and demo a working Agent Bricks pattern by the end of the hackathon.

The expected build environment is **Vocareum plus Databricks**. Teams should use their assigned Vocareum workspace, catalog, and SQL warehouse, then lean on Databricks Genie code generation for the first draft of notebooks, SQL, tool functions, and agent instructions. The ai-dev-kit skills in this folder give Genie code the right scaffold and guardrails instead of starting from a blank prompt.

The first six tracks are the priority use cases. The remaining tracks are top-value workshop use cases plus a document-extraction cluster.

> All data is synthetic. Product names, customers, suppliers, contracts, and documents are invented for the workshop.

---

## What Is In The Kit

| Path | Purpose |
|---|---|
| `.claude/skills/` | ai-dev-kit skills: `scaffold-copilot`, `add-genie-space`, `add-mcp-tool`, `add-connector`, `deploy`, `deploy-to-databricks-apps` (Asset Bundle path: avoids the 4 real Apps deploy crashes), and `generate-synthetic-data` |
| `starter-prompts/` | One ready-to-use prompt per track |
| `tracks/` | Forkable team guides using the required track template |
| `TRACK_TEMPLATE.md` | The template every track README follows |
| [`hackathon-hub/`](./hackathon-hub/) | The AppKit event hub app: Register / Teams / Submit / Judge / Leaderboard on Lakebase. See its README to configure env vars and run it. |

---

## Track Catalog

### Priority Tracks

| Track | Use case | Starting point | Best demo outcome |
|---|---|---|---|
| `01-finance-controlling` | #1 Finance controlling copilot | Finance Genie space + SQL AI Functions | Controller asks a variance question and gets drivers, evidence, and recommended next steps |
| `02-multi-domain-supervisor` | #3 Finance/SCM/Commercial supervisor | L300 supervisor pattern | One chat routes across Finance, SCM, and Commercial with governed answers |
| `03-procurement-contracts` | #7 Procurement contract intelligence | Knowledge Assistant + document parsing | Supplier contract clauses are extracted, risk-scored, and turned into negotiation guidance |
| `04-access-provisioning` | #14 Access provisioning and entitlement agent | action plane + policy guardrails | User access request is checked, approved, provisioned, and audited |
| `05-forecast-planner-mmf` | #6 Forecast planner copilot on MMF | `ai_forecast` on an SCM series + team-built forecast tables | Planner compares versions, sees forecast drivers, and drafts an override recommendation |
| `06-pricing-quote-generation` | #18 Pricing and quote-generation agent | text extraction + pricing tool + action approval | Inbound request becomes a draft quote package with human approval |

### Additional Tracks

| Track | Use case | Starting point | Best demo outcome |
|---|---|---|---|
| `07-supply-chain-control-tower` | #2 Supply chain control tower copilot | SCM Genie space | Planner asks why OTIF dropped and gets root-cause drivers plus interventions |
| `08-ai-governance-policy` | #4 AI governance and policy agent | LLMOps spine + AI Gateway | Policy question returns the allowed action, controls, and audit trail |
| `09-commercial-action` | #5 Commercial action assistant | Commercial Genie space + action plane | Account signal turns into a next-best action proposal |
| `10-enterprise-knowledge-assistant` | #10 Enterprise knowledge assistant | Vector Search + Knowledge Assistant | User asks policy/SOP questions and gets governed cited answers |
| `11-doc-extraction-cluster` | #15 product/safety, #16 claims, #17 ESG | `ai_parse_document`, `ai_extract`, `ai_classify` | Document-heavy work is converted into structured outputs and review-ready drafts |

---

## Provided Data vs Build-It-Yourself

The shared `../data/` setup provisions a fixed set of resources. Know what is provided before you start so you do not look for tables that are not there.

**Provided by `../data/` setup:**

- Finance tables in `<catalog>.akzo_finance`: `products`, `margin_actuals`, `margin_budget`, `fx_rates`, `cost_drivers`
- SCM tables in `<catalog>.akzo_scm`: `otif`, `inventory`, `lanes`, `service_levels`
- Commercial tables in `<catalog>.akzo_commercial`: `accounts`, `pipeline`, `sales_actuals`, `churn_signals`
- Documents in `/Volumes/<catalog>/akzo_docs/raw/`: 8 safety data sheets (`sds/`) and 6 supplier contracts (`contracts/`), with a ground-truth field table in `../data/output/docs/README.md`
- Three Genie spaces (Akzo Finance, Akzo SCM, Akzo Commercial), ids in `../data/setup/space_ids.json`
- Vector Search endpoint `akzo_workshop_vs` and index `akzo_docs.chunks_idx`
- Empty schemas for your own tables: `akzo_ops`, `akzo_gateway`

**Build-it-yourself tracks.** Some tracks need data the setup does not ship: access provisioning (04), AI governance (08), forecast planner (05), and pricing (06). Each track README marks which resources are team-built. Use the `generate-synthetic-data` skill to create them in `akzo_ops` or `akzo_gateway`, following the same parquet-to-Unity-Catalog pattern as the provided data.

---

## The Shared Narrative

The provided data is one connected story across the three domains. Pin your demo questions to it so every query returns a clear result.

- **Finance:** Paints EMEA gross margin falls from ~39.6% (Q1 2026) to ~30.7% (Q2 2026), driven by price erosion, FX, and raw-material cost.
- **SCM:** the `Rotterdam-NL->EMEA-DACH` lane OTIF drops from ~95.9% to ~88.9% in May 2026, with two EMEA SKUs stocking out and backorders spiking.
- **Commercial:** accounts ACC0001, ACC0002, ACC0003 cross churn risk (score > 0.7) by June 2026, with revenue falling ~EUR 375k to ~EUR 169k.

Margin pressure, then a service shock, then customer churn. The multi-domain supervisor track (02) should make this cross-domain thread explicit; the single-domain tracks each own one chapter of it.

---

## Required Track Template

Every track README follows `TRACK_TEMPLATE.md`:

1. Use case and target user
2. Hackathon goal
3. Starter architecture
4. Data and resources
5. Agent Bricks build path
6. MCP, tools, and action-plane hooks
7. Evaluation and governance
8. Demo script
9. Judging rubric
10. Stretch goals

---

## Suggested Hackathon Flow

1. In Vocareum, confirm your team catalog, warehouse, and Databricks workspace URL.
2. Run the shared setup in `../data/` using your assigned catalog.
3. Pick one track from `tracks/`.
4. Open the matching file in `starter-prompts/`.
5. Paste the prompt into Databricks Genie code or the ai-dev-kit coding assistant.
6. Use `scaffold-copilot` first, then add `add-genie-space`, `add-mcp-tool`, `add-connector`, and `deploy` only as needed.
7. If your track needs data the setup does not provide, run `generate-synthetic-data` into `akzo_ops` or `akzo_gateway`.
8. Add one governed data source, one tool or MCP call, and one evaluation set.
9. Demo with the script in the track README.

Teams should bias toward a thin working loop: answer or extract, cite evidence, evaluate quality, then add action approval only where the use case needs it.

---

## Team Working Model

Each team should assign four lightweight roles:

| Role | Owns | Uses |
|---|---|---|
| Product lead | user story, demo script, judging fit | track README |
| Data lead | tables, documents, Genie space grounding | `add-genie-space`, Genie code |
| Agent lead | agent instructions, tools, MCP calls | `scaffold-copilot`, `add-mcp-tool` |
| Governance lead | eval set, citations, approvals, audit | `add-connector`, `deploy` |

The roles can overlap, but the team should avoid everyone editing the same artifact. Keep one shared "demo path" question and make every build choice serve that path.

---

## Genie Code Prompting Rules

When using Databricks Genie code, always include:

- Your assigned `catalog`, schema, and warehouse.
- The track folder name and use-case rank.
- The exact Agent Bricks pattern you want: Genie Space, Knowledge Assistant, Supervisor, document extraction, classification, or code-your-own.
- The required governance behavior: citations, masking, AI Gateway, MLflow tracing, or human approval.
- A small eval set before adding extra features.

Avoid asking Genie code to build the full app in one shot. Ask for a first runnable loop, run it in Vocareum, then add tools and actions in small steps.

---

## Judging Model

| Category | Weight | What judges look for |
|---|---:|---|
| Business fit | 25 | Clear AkzoNobel user, real workflow pain, high-value decision or time saving |
| Agent quality | 25 | Correct routing, grounded responses, citations, good tool use, no obvious hallucination |
| Governance | 20 | UC permissions, AI Gateway or guardrails, human approval where actions mutate state, auditability |
| Demo completeness | 20 | End-to-end story works in one flow with a visible result |
| Reuse and extensibility | 10 | Uses workshop patterns so another team can extend it after the hackathon |

