# Track 08: AI Governance And Policy Agent

## Use Case And Target User

- **Use case:** #4 AI governance and policy agent across models, agents, and tools
- **Primary users:** AI platform owners, governance teams, security, compliance
- **Business question:** Is this AI action allowed, what controls apply, and how is it audited?
- **Success signal:** A policy question returns a clear decision, required controls, and traceable evidence.

## Hackathon Goal

Build a governance agent that answers policy questions across models, prompts, tools, budgets, and action permissions using approved policy documents and control metadata.

## Starter Architecture

- **Agent pattern:** Knowledge Assistant plus policy classifier
- **Data plane:** policy documents, tool registry, model registry, budget table
- **Tool plane:** policy lookup, risk classifier, budget check
- **Control plane:** AI Gateway, audit trace, compliance judge

## Data And Resources

- **Team-built tables (in `akzo_gateway`):** model endpoints, tools, budgets, guardrail rules, audit events are not provided. Create them with `generate-synthetic-data`.
- **Team-built documents:** AI policy, tool approval policy, data handling guidance. Generate and index for retrieval.
- **Provided signal:** real AI Gateway logs and UC permissions from the workshop are the authoritative governance artifact; reference them.
- **Genie spaces:** optional team-built governance space
- **Vector Search:** index your generated policy documents

## Agent Bricks Build Path

1. Start from the Knowledge Assistant pattern.
2. Generate policy/control documents and registry tables with `generate-synthetic-data`, then index them.
3. Add a classifier for policy request type.
4. Add a budget or tool-approval lookup.
5. Evaluate policy compliance and citation quality.

## MCP, Tools, And Action Hooks

- **MCP tools:** model registry lookup, tool registry lookup, budget lookup
- **SQL AI Functions:** `ai_classify`, `ai_summarize`, `ai_mask`
- **Action-plane hooks:** approval request for a new tool or model endpoint
- **Approval model:** human approval for policy exceptions

## Evaluation And Governance

- **Eval set:** 10 policy scenarios with expected allow, deny, or escalate outcomes.
- **Judges:** policy compliance, citation quality, refusal correctness.
- **Governance:** AI Gateway logging, UC policy docs, audit trail.
- **Failure behavior:** escalate when policy evidence is missing or conflicting.

## Demo Script

1. Ask whether an agent may call a tool with customer data.
2. Show cited policy evidence.
3. Show allow, deny, or escalate decision.
4. Show AI Gateway or trace evidence.
5. Close with required controls.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Makes AI governance actionable for builders |
| Agent quality | 25 | Correct policy decisions with citations |
| Governance | 20 | Controls, logs, and escalation paths |
| Demo completeness | 20 | Policy question to governed decision |
| Reuse | 10 | Uses Knowledge Assistant and LLMOps spine |

## Stretch Goals

- Add policy exception workflow.
- Add cost forecast for a proposed agent.
- Add control dashboard output.

