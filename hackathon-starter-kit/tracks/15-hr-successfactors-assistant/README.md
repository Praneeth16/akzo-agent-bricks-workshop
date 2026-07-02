# Track 15: HR And SuccessFactors Assistant

## Use Case And Target User

- **Use case:** #12 HR and SuccessFactors assistant
- **Primary users:** HR business partners, people analytics, HR operations
- **Business question:** What does our headcount and policy data say, and can an HR question be answered without exposing employee-identifying details to the wrong audience?
- **Success signal:** An HR question gets a grounded, masked answer with a clear governance-simulation story for who could see what.

## Hackathon Goal

Build an HR assistant over synthetic headcount and employee data plus HR policy documents, with masking on employee-identifying fields and a governance-simulation pattern for role-based access on a single-user workspace.

## Starter Architecture

- **Agent pattern:** Genie Space plus Knowledge Assistant over HR policy documents
- **Data plane:** `fact_headcount` and `dim_employee` tables
- **Tool plane:** `ai_mask`, `ai_query`, `ai_summarize`
- **Control plane:** masking on employee-identifying fields, groundedness judge, governance-simulation note

## Data And Resources

- **Team-built tables (in your own personal schema):** `fact_headcount` (headcount by department, level, month) and `dim_employee` (synthetic employee attributes). Not in the shared setup — create with `generate-synthetic-data`.
- **Team-built documents:** synthetic HR policy documents (leave policy, promotion criteria). Generate with `generate-synthetic-data` and place in a UC volume.
- **Genie spaces:** new "Akzo HR" space over `fact_headcount` and `dim_employee`.
- **Vector Search:** new index over the generated HR policy documents.
- **Free Edition note:** there is no live SuccessFactors connector on Free Edition. Simulate entirely with the generated tables above — do not attempt a live connection.
- **Governance-simulation note:** Free Edition is single-user with no Automatic Identity Management or account-group-based row filtering. Simulate role-based access with either (a) a persona-parameter column driving an RLS-style view (e.g. `viewer_role` filters which departments or fields are visible), or (b) two scoped Genie spaces (HR-generalist vs. HR-business-partner) routed by a Supervisor. Mask employee-identifying fields (name, employee id) with `ai_mask` regardless of which method you pick.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L100-foundations/01_agent_bricks_types.md`.
2. Generate `fact_headcount`, `dim_employee`, and HR policy documents with `generate-synthetic-data`.
3. Build the Akzo HR Genie space over both tables, with `ai_mask` applied to employee-identifying fields.
4. Build a Knowledge Assistant over the HR policy documents.
5. Implement one governance-simulation method (RLS-style view or two scoped spaces + Supervisor) and document which one you chose and why.
6. Evaluate masking correctness and policy-answer groundedness.

## MCP, Tools, And Action Hooks

- **MCP tools:** department lookup, policy lookup
- **SQL AI Functions:** `ai_mask`, `ai_query`, `ai_summarize`
- **Action-plane hooks:** optional HR-ticket draft for a policy exception request
- **Approval model:** read-only by default; ticket drafts are propose-only

## Evaluation And Governance

- **Eval set:** 8 HR questions covering headcount trends, policy lookups, and at least 2 that test masking behavior.
- **Judges:** groundedness, masking correctness, policy-citation accuracy.
- **Governance:** every headcount answer masks employee-identifying fields; every policy answer cites the source document.
- **Failure behavior:** refuse to reveal individual employee identity even if asked directly; state when a policy question has no matching document.

## Demo Script

1. Ask a headcount question: "How has headcount in Paints EMEA changed this year?"
2. Show the masked, aggregated answer.
3. Ask a policy question answered from the generated HR documents.
4. Show the governance-simulation method in action (role-scoped answer difference).
5. Ask a question that would reveal individual identity and show the refusal.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Real HR workflow with a credible governance story |
| Agent quality | 25 | Grounded headcount and policy answers |
| Governance | 20 | Masking and a documented role-based access simulation |
| Demo completeness | 20 | Headcount, policy, and refusal scenario all shown |
| Reuse | 10 | Masking and RLS-simulation pattern reusable elsewhere |

## Stretch Goals

- Add an attrition-risk summary by department.
- Add a promotion-readiness check against policy criteria.
- Add both governance-simulation methods and compare them in the demo.
