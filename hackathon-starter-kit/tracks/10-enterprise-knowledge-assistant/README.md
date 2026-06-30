# Track 10: Enterprise Knowledge Assistant

## Use Case And Target User

- **Use case:** #10 Enterprise knowledge assistant over SharePoint and process docs
- **Primary users:** business users, operations teams, support teams
- **Business question:** What do approved policies, SOPs, and technical documents say, and where is the evidence?
- **Success signal:** Users get cited answers from governed documents without searching manually.

## Hackathon Goal

Build a Knowledge Assistant over the synthetic policy, SOP, safety, and contract documents with citations and access-aware answers.

## Starter Architecture

- **Agent pattern:** Knowledge Assistant
- **Data plane:** document volume and Vector Search index
- **Tool plane:** document retrieval, `ai_summarize`, optional SharePoint-style metadata filter
- **Control plane:** citations, document permissions, groundedness eval

## Data And Resources

- **Documents (provided):** 8 safety data sheets and 6 supplier contracts in `/Volumes/<catalog>/akzo_docs/raw/`
- **Team-added documents:** SOPs and policies are not provided; add and re-index them if your demo needs them
- **Genie spaces:** optional for structured follow-up questions
- **Vector Search:** endpoint `akzo_workshop_vs`, index `akzo_docs.chunks_idx`

## Agent Bricks Build Path

1. Start from `../../L100-foundations/01_agent_bricks_types.md`.
2. Point a Knowledge Assistant at the Vector Search index.
3. Add instructions for citations and "not found" behavior.
4. Add metadata filters for domain, region, or document type if available.
5. Evaluate answer groundedness and citation accuracy.

## MCP, Tools, And Action Hooks

- **MCP tools:** document metadata lookup, source URL lookup
- **SQL AI Functions:** `ai_summarize`, `ai_mask`, `ai_query`
- **Action-plane hooks:** optional ticket draft when a policy gap is found
- **Approval model:** read-only by default

## Evaluation And Governance

- **Eval set:** 10 document questions with expected source documents.
- **Judges:** groundedness, citation correctness, refusal correctness.
- **Governance:** UC volume permissions and citation requirement.
- **Failure behavior:** say when evidence is missing rather than infer policy.

## Demo Script

1. Ask a question answerable from the provided docs, e.g. "What PPE and flash point apply to the Interthane 990 topcoat?"
2. Show cited answer.
3. Ask a question not covered by documents.
4. Show refusal or escalation behavior.
5. Show groundedness eval.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Reduces time spent finding approved answers |
| Agent quality | 25 | Accurate cited answers and good refusal behavior |
| Governance | 20 | Document permissions and citations |
| Demo completeness | 20 | Knowledge question to cited answer |
| Reuse | 10 | Uses Knowledge Assistant and Vector Search setup |

## Stretch Goals

- Add SharePoint-style metadata filters.
- Add multilingual document answers.
- Add feedback capture for bad citations.

