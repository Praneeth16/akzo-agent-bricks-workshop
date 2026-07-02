# Track 09: Commercial Action Assistant

## Use Case And Target User

- **Use case:** #5 Commercial action assistant
- **Primary users:** sales teams, account managers, commercial leaders
- **Business question:** Which account or market signal needs action, and what should the commercial team do next?
- **Success signal:** A commercial signal becomes a grounded next-best action proposal.

## Hackathon Goal

Build an assistant that summarizes account performance, identifies a risk or opportunity, and proposes a human-approved action.

## Starter Architecture

- **Agent pattern:** Commercial Genie Space plus action-plane connector
- **Data plane:** Commercial account, customer, product, and opportunity tables
- **Tool plane:** account lookup, `ai_summarize`, action proposal
- **Control plane:** approval before customer-facing action, trace and audit

## Data And Resources

- **Provided tables (`<catalog>.<your-personal-schema>`):** `accounts`, `sales_actuals` (revenue, margin), `churn_signals`, `pipeline`
- **Documents:** none provided; account notes or playbooks are team-supplied
- **Genie spaces:** Akzo Commercial
- **Vector Search:** optional playbook retrieval
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from the Commercial Genie space.
2. Add account signal summarization instructions.
3. Add a next-best action framework: retain, upsell, price review, service recovery.
4. Add an email or CRM action proposal behind approval.
5. Evaluate action relevance and groundedness.

## MCP, Tools, And Action Hooks

- **MCP tools:** account lookup, playbook lookup
- **SQL AI Functions:** `ai_query`, `ai_summarize`, `ai_classify`
- **Action-plane hooks:** CRM task, email draft, Teams notification
- **Approval model:** human approval before customer-facing action

## Evaluation And Governance

- **Eval set:** 8 account scenarios with expected signal and action category.
- **Judges:** action relevance, groundedness, customer-risk handling.
- **Governance:** approval trail and customer data masking where needed.
- **Failure behavior:** recommend review instead of action when signal confidence is low.

## Demo Script

1. Ask: "Which Paints EMEA accounts are at churn risk in June 2026 and why?"
2. Show the account signal and supporting metrics.
3. Generate a next-best action.
4. Show proposed CRM/email action in approval state.
5. Show trace and audit record.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Connects insight to commercial action |
| Agent quality | 25 | Correct account signal and relevant action |
| Governance | 20 | Approval before customer-facing communication |
| Demo completeness | 20 | Account signal to proposed action |
| Reuse | 10 | Uses Commercial Genie and action-plane patterns |

## Stretch Goals

- Add competitor signal or market text.
- Add sales playbook citations.
- Add multi-account prioritization.

