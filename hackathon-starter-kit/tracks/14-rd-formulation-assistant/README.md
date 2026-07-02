# Track 14: R&D Formulation And Research Assistant

## Use Case And Target User

- **Use case:** #11 R&D formulation and research assistant
- **Primary users:** R&D scientists, formulation chemists, research leads
- **Business question:** What have we already tried in past experiments, and what do our formulation documents say about a given approach?
- **Success signal:** A formulation question gets a grounded answer combining structured experiment history and unstructured research documents in one response.

## Hackathon Goal

Build a Supervisor that routes formulation questions to a Genie space over structured experiment data and a Knowledge Assistant over formulation research documents, combining both into one grounded answer.

## Starter Architecture

- **Agent pattern:** Supervisor combining Genie Space and Knowledge Assistant
- **Data plane:** `fact_experiments` table and formulation research documents
- **Tool plane:** experiment lookup, document retrieval, `ai_summarize`
- **Control plane:** groundedness judge, source-type citation (structured vs. document), trace capture

## Data And Resources

- **Team-built tables (in your own personal schema):** `fact_experiments` (experiment id, formulation, ingredient list, test result, date, researcher). Not in the shared setup — create with `generate-synthetic-data`.
- **Team-built documents:** a small set of synthetic formulation research PDFs (methodology notes, past findings). Generate with `generate-synthetic-data` and place in a UC volume.
- **Genie spaces:** new "Akzo R&D Experiments" space over `fact_experiments`.
- **Vector Search:** new index over the generated formulation documents.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L100-foundations/04_multi_agent_supervisor.ipynb` for the Supervisor pattern.
2. Generate `fact_experiments` and a small formulation-document set with `generate-synthetic-data`.
3. Build the Akzo R&D Experiments Genie space over `fact_experiments`.
4. Build a Knowledge Assistant over the generated formulation documents with a Vector Search index.
5. Wire both under a Supervisor that routes structured questions to Genie and document questions to the Knowledge Assistant, and can combine both for mixed questions.
6. Evaluate routing accuracy and combined-answer groundedness.

## MCP, Tools, And Action Hooks

- **MCP tools:** experiment lookup, ingredient lookup
- **SQL AI Functions:** `ai_query`, `ai_summarize`
- **Action-plane hooks:** optional draft of a new experiment proposal based on gaps found
- **Approval model:** read-only by default; experiment proposals are propose-only

## Evaluation And Governance

- **Eval set:** 8 formulation questions, mixing structured-only, document-only, and combined questions, with expected routing behavior.
- **Judges:** routing correctness, groundedness, citation-type accuracy (structured vs. document).
- **Governance:** every answer states whether it came from experiment data, documents, or both.
- **Failure behavior:** say when neither source has evidence rather than inferring a formulation outcome.

## Demo Script

1. Ask a structured question: "What formulations have we tested with ingredient X in the last year?"
2. Show the Genie-routed answer with experiment citations.
3. Ask a document question: "What does our research say about curing time for that formulation family?"
4. Show the Knowledge-Assistant-routed answer with document citations.
5. Ask a combined question and show the Supervisor merging both sources.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Speeds up finding prior-experiment context for new research |
| Agent quality | 25 | Correct routing and grounded combined answers |
| Governance | 20 | Clear source-type citation on every answer |
| Demo completeness | 20 | Structured, document, and combined question all answered |
| Reuse | 10 | Supervisor pattern reusable for any structured-plus-document domain |

## Stretch Goals

- Add a similarity search across past experiments for a new formulation idea.
- Add a research-gap summary (topics with little experiment coverage).
- Add citation deep-links back to the source document page.
