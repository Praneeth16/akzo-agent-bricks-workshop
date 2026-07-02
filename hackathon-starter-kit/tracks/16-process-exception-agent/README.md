# Track 16: Celonis-Driven Exception Resolution Agent

## Use Case And Target User

- **Use case:** #13 Celonis-driven exception resolution agent
- **Primary users:** process excellence teams, operations managers
- **Business question:** Which process instances are stuck or deviating from the expected path, and what action would resolve them?
- **Success signal:** A stuck process instance gets identified, explained, and proposed a resolution action, gated behind approval.

## Hackathon Goal

Build an agent that reads a synthetic process-event table, detects exceptions (stuck steps, deviations, SLA breaches), and proposes a resolution action behind human approval.

## Starter Architecture

- **Agent pattern:** Genie Space plus action-plane connector
- **Data plane:** `fact_process_events` table and an actions lookup table
- **Tool plane:** exception-detection UC function, `ai_query`, action proposal
- **Control plane:** human approval before any resolution action, trace and audit

## Data And Resources

- **Team-built tables (in your own personal schema):** `fact_process_events` (process instance id, step, timestamp, expected duration, status) and an `actions` lookup table (step, standard resolution). Neither is in the shared setup — create both with `generate-synthetic-data`.
- **Documents:** none provided; process-exception runbooks are team-authored if needed.
- **Genie spaces:** new "Akzo Process Exceptions" space over `fact_process_events`.
- **Vector Search:** optional, only if you add a runbook Knowledge Assistant layer.
- **Free Edition note:** there is no live Celonis connector on Free Edition. Feed the agent a synthetic `fact_process_events` table instead of attempting a live connection.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L200-capabilities/02_agents_that_act.py` for the action-plane pattern.
2. Generate `fact_process_events` and the `actions` lookup table with `generate-synthetic-data`.
3. Build the Akzo Process Exceptions Genie space over `fact_process_events`.
4. Define exception logic explicitly: a step is "stuck" if its duration exceeds the expected duration by a stated threshold (for example, 2x).
5. Add an action-proposal step that looks up the standard resolution for the exception's step and drafts it for human approval.
6. Evaluate exception-detection accuracy and action relevance.

## MCP, Tools, And Action Hooks

- **MCP tools:** process-instance lookup, standard-resolution lookup
- **SQL AI Functions:** `ai_query`, `ai_summarize`
- **Action-plane hooks:** resolution-action proposal (ticket or notification draft)
- **Approval model:** human approval required before any resolution action is considered taken

## Evaluation And Governance

- **Eval set:** 8 process scenarios with expected exception classification and expected resolution category.
- **Judges:** exception-detection correctness, action relevance, approval-gate compliance.
- **Governance:** every proposed action stays in a draft/proposed state until explicitly approved; trace capture on every detection.
- **Failure behavior:** flag as "needs manual review" instead of proposing an action when the exception type is not covered by the actions lookup table.

## Demo Script

1. Ask: "Which process instances are stuck or over SLA this week?"
2. Show the detected exceptions with their duration-vs-expected evidence.
3. Show the proposed resolution action for one exception.
4. Show the action sitting in an approval-pending state.
5. Approve it and show the trace/audit record.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Addresses a real process-mining exception-handling workflow |
| Agent quality | 25 | Correct exception detection with explicit threshold logic |
| Governance | 20 | Approval gate before any action and full trace capture |
| Demo completeness | 20 | Exception detection to approved resolution |
| Reuse | 10 | Exception-detection pattern reusable across process types |

## Stretch Goals

- Add a root-cause ranking across multiple stuck instances.
- Add a trend view of exception rate over time.
- Add a second exception type (deviation from expected path, not just duration).
