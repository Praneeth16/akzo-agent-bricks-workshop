# Track 11: Product And Safety Document Extraction

## Use Case And Target User

- **Use case:** #15 Product and safety document extraction
- **Primary users:** product teams, EHS (environmental health and safety) specialists, customer service
- **Business question:** What do our safety data sheets actually say, and can that be structured data instead of a PDF someone has to re-read every time?
- **Success signal:** Safety data sheets become structured, queryable fields with citations, checked against ground truth.

## Hackathon Goal

Build an extraction pipeline that parses safety data sheets, extracts required regulatory and handling fields into a schema, and produces a reviewer-facing table scored against the provided ground truth.

## Starter Architecture

- **Agent pattern:** Document Parsing plus Information Extraction
- **Data plane:** document volume (`sds/`) and the extracted-field output table
- **Tool plane:** `ai_parse_document`, `ai_extract`, `ai_classify`
- **Control plane:** extraction-completeness eval against ground truth, citations, human review

## Data And Resources

- **Documents (provided):** 8 safety data sheets in `/Volumes/<catalog>/<your-personal-schema>/docs_raw/sds/`, with ground-truth fields in `../../../data/output/docs/README.md`
- **Provided tables:** `<your-personal-schema>.products` for product-name matching context
- **Team-built tables (in your own personal schema):** extracted-field output table (`sds_extract`). Create with `generate-synthetic-data` if you need a starting schema.
- **Genie spaces:** optional Akzo Finance/SCM if you want to join extracted fields to product data
- **Vector Search:** `<your-personal-schema>.chunks_idx` for evidence retrieval on follow-up questions
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L100-foundations/00_sql_ai_functions.ipynb`.
2. Parse a sample safety data sheet with `ai_parse_document`.
3. Extract the real fields with `ai_extract`: product name, hazard classification, flash point, PPE requirements, storage conditions, and first-aid measures.
4. Classify severity or handling category with `ai_classify`.
5. Score extracted fields against `../../../data/output/docs/README.md` and mark misses as not found, not guessed.

## MCP, Tools, And Action Hooks

- **MCP tools:** product lookup, hazard-class reference lookup
- **SQL AI Functions:** `ai_parse_document`, `ai_extract`, `ai_classify`, `ai_summarize`
- **Action-plane hooks:** optional ticket draft when a required field is missing from a sheet
- **Approval model:** human review before the extracted table is treated as authoritative

## Evaluation And Governance

- **Eval set:** the 8 provided safety data sheets with expected field values from `../../../data/output/docs/README.md`.
- **Judges:** extraction completeness, field accuracy, citation quality.
- **Governance:** document access through the UC volume and citations for every extracted field.
- **Failure behavior:** mark missing or ambiguous fields as not found instead of inferring a value.

## Demo Script

1. Select a safety data sheet from the volume.
2. Show parsed sections and the extracted field table.
3. Show the ground-truth comparison and any flagged misses.
4. Ask a follow-up question answered from the same document via Vector Search.
5. Close with the reviewer-ready structured output.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Removes manual re-reading of safety sheets from a real workflow |
| Agent quality | 25 | Accurate field extraction and classification with citations |
| Governance | 20 | Human review and ground-truth scoring |
| Demo completeness | 20 | Document to structured, reviewer-ready output |
| Reuse | 10 | Uses `ai_parse_document`/`ai_extract` patterns reusable across document types |

## Stretch Goals

- Add batch processing across all 8 sheets in one pass.
- Add confidence scores per extracted field.
- Add a Vector Search follow-up question flow over the same documents.
