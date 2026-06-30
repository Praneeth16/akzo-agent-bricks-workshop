# Track 11: Document Extraction Cluster

## Use Case And Target User

- **Use cases:** #15 Product and safety document extraction, #16 claims/ticket drafting, #17 ESG questionnaire, #18 pricing and quote generation
- **Primary users:** product teams, customer service, sustainability, commercial operations
- **Business question:** How can document-heavy work become structured data or a review-ready draft?
- **Success signal:** PDFs, tickets, questionnaires, or inbound requests become structured outputs with citations and human review.

## Hackathon Goal

Pick one document-heavy workflow and build an extraction pipeline that parses the input, extracts required fields, classifies risk or intent, and produces a structured table or draft response.

## Starter Architecture

- **Agent pattern:** Document Parsing plus Information Extraction and Text Classification
- **Data plane:** document volume, parsed text, extracted field table
- **Tool plane:** `ai_parse_document`, `ai_extract`, `ai_classify`, `ai_summarize`
- **Control plane:** extraction eval, citations, human review

## Data And Resources

- **Documents (provided):** 8 safety data sheets and 6 supplier contracts in `/Volumes/<catalog>/akzo_docs/raw/`, with ground truth in `../../data/output/docs/README.md`
- **Team-supplied documents:** claims, ESG questionnaire snippets, and quote request emails are not provided; add your own or generate them with `generate-synthetic-data`
- **Team-built tables (in `akzo_ops`):** extracted-field output table for your chosen workflow
- **Genie spaces:** optional for structured context
- **Vector Search:** `akzo_docs.chunks_idx` for evidence retrieval

## Agent Bricks Build Path

1. Choose one workflow: product/safety extraction, claims response, ESG questionnaire, or pricing request.
2. Parse the source document or message.
3. Extract required fields into a schema.
4. Classify risk, intent, or completion status.
5. Produce a reviewer-facing table or draft.

## MCP, Tools, And Action Hooks

- **MCP tools:** template lookup, evidence lookup, reviewer queue lookup
- **SQL AI Functions:** `ai_parse_document`, `ai_extract`, `ai_classify`, `ai_summarize`, `ai_mask`
- **Action-plane hooks:** ticket draft, email draft, reviewer assignment
- **Approval model:** human review before outbound responses or submitted answers

## Evaluation And Governance

- **Eval set:** for safety sheets and contracts, score against `../../data/output/docs/README.md`; for team-supplied inputs, build a small expected-field table.
- **Judges:** extraction completeness, classification correctness, citation quality.
- **Governance:** human review and masked sensitive fields.
- **Failure behavior:** mark missing fields and ask for review instead of filling guesses.

## Demo Script

1. Select a document-heavy input.
2. Show parsed text or sections.
3. Show extracted fields and classification.
4. Show the draft response or structured output.
5. Show reviewer approval and eval result.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Removes manual document handling from a real workflow |
| Agent quality | 25 | Accurate extraction, classification, and citations |
| Governance | 20 | Human review and sensitive-field handling |
| Demo completeness | 20 | Document to structured output or draft |
| Reuse | 10 | Uses reusable document extraction patterns |

## Stretch Goals

- Add batch processing.
- Add confidence scores by field.
- Add reviewer corrections feeding an eval set.

