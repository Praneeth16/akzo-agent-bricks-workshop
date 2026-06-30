# Track 04: Access Provisioning And Entitlement Agent

## Use Case And Target User

- **Use case:** #14 Access provisioning and entitlement agent
- **Primary users:** data owners, platform admins, managers, business users
- **Business question:** Should this user get access, at what privilege level, and who approved it?
- **Success signal:** Access requests are checked against policy, routed for approval when needed, and fully audited.

## Hackathon Goal

Build an entitlement agent that receives an access request, checks policy and user context, proposes the least-privilege grant, and records the approval trail.

## Starter Architecture

- **Agent pattern:** code-your-own agent with action-plane guardrails
- **Data plane:** policy documents, user-role table, domain entitlement table
- **Tool plane:** policy lookup, entitlement check, provision-access dry run
- **Control plane:** human approval, audit events, UC permissions

## Data And Resources

- **Team-built tables (in `akzo_ops`):** users, groups, domains, entitlement requests, audit log. Create these with `generate-synthetic-data`; they are not in the shared setup.
- **Team-built documents:** access policy and data classification policy. Generate as text or PDF, then index for retrieval.
- **Provided tables:** the three domain schemas (`akzo_finance`, `akzo_scm`, `akzo_commercial`) serve as the access targets to validate domain scope.
- **Genie spaces:** optional Akzo Finance, SCM, Commercial to validate domain scope
- **Vector Search:** index your generated policy documents if you want retrieval

## Agent Bricks Build Path

1. Start from the action-plane pattern described in `../../WORKSHOP_MASTER_PLAN.md`.
2. Generate the entitlement and audit tables with `generate-synthetic-data` into `akzo_ops`.
3. Create a request classifier: new access, change access, revoke access.
4. Add a policy retrieval step for domain and privilege rules.
5. Propose a least-privilege grant with justification.
6. Require human approval before any provisioning action.

## MCP, Tools, And Action Hooks

- **MCP tools:** user context lookup, policy lookup, entitlement dry run
- **SQL AI Functions:** `ai_classify`, `ai_summarize`, `ai_mask`
- **Action-plane hooks:** ticket, Teams approval, UC grant dry run
- **Approval model:** human approval for all grants, L4 only for pre-approved low-risk groups

## Evaluation And Governance

- **Eval set:** 8 access scenarios across allow, deny, escalate, and revoke.
- **Judges:** policy compliance and explanation quality.
- **Governance:** full audit trail, least privilege, masked personal details.
- **Failure behavior:** escalate when manager, purpose, or domain entitlement is missing.

## Demo Script

1. Submit: "Give Priya access to Finance margin data for Paints EMEA planning."
2. Show policy lookup and entitlement recommendation.
3. Show approval queue or proposed action state.
4. Approve and show the audit record.
5. Close with why the grant is least privilege.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Faster access with better control |
| Agent quality | 25 | Correct policy interpretation and least-privilege proposal |
| Governance | 20 | Approval, audit, masking, escalation |
| Demo completeness | 20 | Request to approved entitlement flow |
| Reuse | 10 | Uses action-plane and policy retrieval patterns |

## Stretch Goals

- Add manager override flow.
- Add automatic revocation recommendation.
- Add row-level access examples by domain.

