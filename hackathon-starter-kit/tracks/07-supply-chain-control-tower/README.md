# Track 07: Supply Chain Control Tower Copilot

## Use Case And Target User

- **Use case:** #2 Supply chain control tower copilot
- **Primary users:** planners, logistics leads, control-tower teams
- **Business question:** Why did OTIF, inventory, or service move, and what intervention should the planner make?
- **Success signal:** A planner gets a root-cause explanation and recommended intervention from the SCM data.

## Hackathon Goal

Build an SCM assistant that answers one OTIF or inventory exception question, identifies likely drivers, and proposes a next action.

## Starter Architecture

- **Agent pattern:** Genie Space
- **Data plane:** SCM Genie space and SCM tables
- **Tool plane:** `ai_query`, `ai_summarize`, optional exception lookup
- **Control plane:** trace, groundedness judge, read-only permissions

## Data And Resources

- **Provided tables (`<catalog>.akzo_scm`):** `otif`, `inventory`, `lanes`, `service_levels`
- **Documents:** none provided for SCM; SOPs are team-supplied if needed
- **Genie spaces:** Akzo SCM
- **Vector Search:** not needed for this track

## Agent Bricks Build Path

1. Start from the SCM Genie space.
2. Add instructions for OTIF, inventory, and logistics driver analysis.
3. Add sample questions for late shipment, low service, and excess inventory.
4. Add a read-only intervention recommendation.
5. Evaluate groundedness and driver correctness.

## MCP, Tools, And Action Hooks

- **MCP tools:** exception lookup, SOP retrieval
- **SQL AI Functions:** `ai_query`, `ai_summarize`
- **Action-plane hooks:** ticket or Teams proposal
- **Approval model:** propose-only for interventions

## Evaluation And Governance

- **Eval set:** 8 SCM exception questions.
- **Judges:** driver correctness and groundedness.
- **Governance:** read-only by default, action approval for notifications.
- **Failure behavior:** state when the data cannot isolate root cause.

## Demo Script

1. Ask: "Why did OTIF for Paints EMEA drop in May 2026?"
2. Show the SCM query or Genie trace.
3. Show ranked drivers.
4. Propose an intervention.
5. Show groundedness eval.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Clear supply-chain decision support |
| Agent quality | 25 | Correct drivers and grounded answers |
| Governance | 20 | Read-only answer and approved action proposal |
| Demo completeness | 20 | Exception to intervention story |
| Reuse | 10 | Uses SCM Genie and L100 evaluation |

## Stretch Goals

- Add multi-echelon inventory explanation.
- Add logistics carrier comparison.
- Add an approval-center intervention queue.

