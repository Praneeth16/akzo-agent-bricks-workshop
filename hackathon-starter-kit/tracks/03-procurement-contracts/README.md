# Track 03: Procurement Contract Intelligence

## Use Case And Target User

- **Use case:** #7 Procurement contract intelligence assistant
- **Primary users:** procurement managers, category leads, legal reviewers
- **Business question:** What does this supplier contract say, where does it deviate, and what should we negotiate?
- **Success signal:** A contract review produces extracted clauses, risk flags, and negotiation guidance with citations.

## Hackathon Goal

Build a contract assistant that parses supplier contracts, extracts key terms, compares them to standard guidance, and returns review-ready findings.

## Starter Architecture

- **Agent pattern:** Knowledge Assistant plus Information Extraction
- **Data plane:** document volume and Vector Search index
- **Tool plane:** `ai_parse_document`, `ai_extract`, clause-risk lookup tool
- **Control plane:** extraction completeness eval, citations, reviewer approval

## Data And Resources

- **Documents (provided):** 6 supplier contracts in `/Volumes/<catalog>/akzo_docs/raw/contracts/`, with ground-truth extraction fields in `../../data/output/docs/README.md`
- **Provided tables:** none for contracts; `<catalog>.akzo_finance.products` gives spend context if needed
- **Team-built tables:** optional supplier or purchase-order table via `generate-synthetic-data`
- **Genie spaces:** optional Akzo Finance for spend context
- **Vector Search:** `akzo_docs.chunks_idx`

## Agent Bricks Build Path

1. Start from `../../L100-foundations/00_sql_ai_functions.ipynb`.
2. Parse a sample contract with `ai_parse_document`.
3. Extract the real contract fields with `ai_extract`: `supplier_name`, `category`, `annual_spend_eur`, `payment_terms_net_days`, `price_escalation_clause`, `termination_notice_days`, plus liability cap and governing law.
4. Flag deviations: the demo contracts include non-standard payment terms (Net 90/120) on spend over EUR 1M; score against the ground-truth table.
5. Evaluate extracted fields against `../../data/output/docs/README.md`.

## MCP, Tools, And Action Hooks

- **MCP tools:** clause standard lookup, supplier lookup
- **SQL AI Functions:** `ai_parse_document`, `ai_extract`, `ai_summarize`, `ai_classify`
- **Action-plane hooks:** ticket draft or Teams approval request
- **Approval model:** human review before negotiation guidance is sent

## Evaluation And Governance

- **Eval set:** the 6 provided contracts with expected field values from `../../data/output/docs/README.md`.
- **Judges:** extraction completeness, citation quality, risk-label correctness.
- **Governance:** document access through UC volume and citations for every flagged clause.
- **Failure behavior:** mark missing clauses as not found instead of inventing terms.

## Demo Script

1. Upload or select a supplier contract.
2. Show parsed sections and extracted clause table.
3. Ask for deviations from standard terms.
4. Show citations and risk labels.
5. Draft negotiation guidance for human review.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Speeds contract triage and negotiation prep |
| Agent quality | 25 | Accurate clause extraction with citations |
| Governance | 20 | Human review, source citations, document permissions |
| Demo completeness | 20 | Contract to risk summary to draft guidance |
| Reuse | 10 | Uses SQL AI Functions and Knowledge Assistant patterns |

## Stretch Goals

- Add supplier spend context.
- Add side-by-side redline recommendations.
- Add a reviewer queue in the hackathon hub.

