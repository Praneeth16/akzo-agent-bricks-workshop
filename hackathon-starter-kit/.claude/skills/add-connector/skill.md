---
name: add-connector
description: Add an action-plane connector with guardrails and human approval.
---

# add-connector

Use this skill when a track needs the agent to propose an action, such as email, ticket, Teams, CRM, SharePoint, or ERP PO.

## Inputs To Ask For

- Connector type
- Action payload fields
- Approval level: propose-only, human approval, or L4 within-policy auto-approval
- Guardrails: spend cap, region, role, data class, customer-facing communication
- Audit fields

## Build Steps

1. Start with propose-only behavior.
2. Define the action payload and approval state.
3. Ask Databricks Genie code to generate the connector stub and dry-run executor.
4. Add guardrail checks before execution.
5. Add an audit event for proposed, approved, rejected, executed, failed, and escalated.
6. Add one demo action that stops at human approval.

## Output Shape

Return:

- Connector stub
- Guardrail rules
- Action payload example
- Approval and audit flow
- Demo verification steps

## Guardrails

- Never send customer-facing messages automatically in a hackathon demo.
- Never mutate source systems without a dry-run mode.
- If a guardrail is unclear, escalate to human approval.

