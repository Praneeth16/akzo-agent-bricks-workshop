# Track 02: Multi-Domain Supervisor

## Use Case And Target User

- **Use case:** #3 Multi-domain supervisor across Finance, SCM, and Commercial
- **Primary users:** business leaders, controllers, planners, commercial teams
- **Business question:** Which domain owns this question, and how do I get one governed answer without choosing the right tool first?
- **Success signal:** One chat routes questions to Finance, SCM, or Commercial and returns a grounded answer with the right access controls.

## Hackathon Goal

Build a supervisor that routes a user question to the correct domain Genie space, returns a single answer, and shows routing evidence in the trace.

## Starter Architecture

- **Agent pattern:** Supervisor
- **Data plane:** Finance, SCM, and Commercial Genie spaces
- **Tool plane:** domain lookup tools and optional MCP routing helper
- **Control plane:** MLflow tracing, routing eval set, UC permissions

## Data And Resources

- **Tables:** `akzo_finance`, `akzo_scm`, `akzo_commercial`
- **Documents:** optional policy or product docs for citations
- **Genie spaces:** Finance, SCM, Commercial
- **Vector Search:** optional for cross-domain policy context

## Agent Bricks Build Path

1. Start from the L300 supervisor pattern in `../../WORKSHOP_MASTER_PLAN.md`.
2. Register the three Genie spaces as sub-agents or callable tools.
3. Write routing instructions with domain boundaries and examples.
4. Add an ambiguity rule: ask a clarifying question or state the assumption.
5. Evaluate routing accuracy with a mixed-domain test set.

## MCP, Tools, And Action Hooks

- **MCP tools:** domain router, read-only data lookup, document retrieval
- **SQL AI Functions:** `ai_query`, `ai_summarize`, `ai_mask`
- **Action-plane hooks:** optional ticket or Teams proposal for follow-up actions
- **Approval model:** read-only for answers, human approval for actions

## Evaluation And Governance

- **Eval set:** 12 questions across Finance, SCM, Commercial, cross-domain, and out-of-scope cases.
- **Judges:** routing correctness, groundedness, answer completeness.
- **Governance:** row-level access by domain and caller entitlement.
- **Failure behavior:** refuse out-of-scope questions and avoid wrong-domain answers.

## Demo Script

1. Ask one finance, one SCM, and one commercial question in the same chat.
2. Show route selection for each turn.
3. Ask an ambiguous cross-domain question and show the assumption or clarification.
4. Show routing eval results.
5. Close with the single governed chat experience.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Removes domain/tool selection from the user |
| Agent quality | 25 | Correct routing and grounded answers |
| Governance | 20 | Domain entitlements and traceable sub-agent calls |
| Demo completeness | 20 | Multi-domain conversation works end to end |
| Reuse | 10 | Reuses the three Genie spaces and supervisor pattern |

## Stretch Goals

- Add a domain confidence score.
- Add cross-domain decomposition.
- Add action proposals from the selected domain.

