# Track 18: Sustainability And ESG Questionnaire Agent

## Use Case And Target User

- **Use case:** #17 Sustainability and ESG questionnaire agent
- **Primary users:** sustainability team, ESG reporting analysts, procurement compliance
- **Business question:** Given a customer or regulator ESG questionnaire, what grounded answer can we draft from our evidence library, and where are the gaps?
- **Success signal:** A batch of ESG questionnaire questions gets answered from evidence with citations, and unanswerable questions are flagged instead of guessed.

## Hackathon Goal

Build an agent that answers ESG questionnaire questions in batch from an evidence library, citing the source document for each answer and flagging questions with no supporting evidence.

## Starter Architecture

- **Agent pattern:** Knowledge Assistant over an ESG evidence library plus batch-run orchestration
- **Data plane:** ESG evidence documents and a questionnaire table (question, category)
- **Tool plane:** document retrieval, `ai_summarize`, batch answer generation
- **Control plane:** citation requirement, "not enough evidence" fallback, review before submission

## Data And Resources

- **Team-built documents:** synthetic ESG evidence library (sustainability policy excerpts, emissions summaries, certifications). Not in the shared setup — create with `generate-synthetic-data` and place in a UC volume.
- **Team-built tables (in your own personal schema):** a `questionnaire` table (question text, category, required evidence type). Create with `generate-synthetic-data`.
- **Genie spaces:** optional, for querying questionnaire completion status.
- **Vector Search:** new index over the generated ESG evidence documents.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L100-foundations/01_agent_bricks_types.md`.
2. Generate the ESG evidence library and `questionnaire` table with `generate-synthetic-data`.
3. Build a Knowledge Assistant over the evidence library with citation instructions.
4. Build a batch-run step that loops over every row of `questionnaire` and produces a cited answer or a "not enough evidence" flag.
5. Evaluate answer groundedness and correct identification of unanswerable questions.

## MCP, Tools, And Action Hooks

- **MCP tools:** evidence-document lookup, questionnaire-status lookup
- **SQL AI Functions:** `ai_summarize`, `ai_query`
- **Action-plane hooks:** optional draft flagging unanswered questions for the sustainability team to fill in
- **Approval model:** human review of the full batch before submission to a customer or regulator

## Evaluation And Governance

- **Eval set:** 10 questionnaire questions with expected answer/citation, including at least 2 with no supporting evidence.
- **Judges:** groundedness, citation correctness, correct "not enough evidence" flagging.
- **Governance:** every answer cites its source document; every gap is explicitly flagged, not silently skipped.
- **Failure behavior:** flag "not enough evidence" rather than inferring an ESG claim not backed by the evidence library.

## Demo Script

1. Load the synthetic questionnaire table.
2. Run the batch answer step across all questions.
3. Show a fully-answered, cited question.
4. Show a flagged "not enough evidence" question.
5. Close with the completion-rate summary (answered vs. flagged).

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Speeds up a recurring, evidence-heavy ESG reporting task |
| Agent quality | 25 | Grounded batch answers with correct gap flagging |
| Governance | 20 | Citation on every answer and explicit evidence-gap flags |
| Demo completeness | 20 | Full questionnaire batch run with a completion summary |
| Reuse | 10 | Batch-answer pattern reusable for other compliance questionnaires |

## Stretch Goals

- Add a gap-closure recommendation (what evidence to gather next).
- Add multi-questionnaire comparison (which questions recur across customers).
- Add a confidence score per answered question.
