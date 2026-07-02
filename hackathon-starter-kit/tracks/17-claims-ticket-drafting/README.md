# Track 17: Claims, Ticket, And Response Drafting Agent

## Use Case And Target User

- **Use case:** #16 Claims, ticket, and response drafting agent
- **Primary users:** customer service reps, claims handlers, support teams
- **Business question:** Given an incoming ticket or claim, what is a grounded, on-brand draft response, and does it need human review before it goes out?
- **Success signal:** A raw ticket becomes a cited, ready-to-review draft response in seconds instead of minutes.

## Hackathon Goal

Build an agent that reads an incoming ticket, retrieves relevant response templates and customer context, and drafts a response for human review before sending.

## Starter Architecture

- **Agent pattern:** Knowledge Assistant over response templates plus MCP tool for customer/ticket lookup
- **Data plane:** synthetic tickets table and response-templates document set
- **Tool plane:** ticket lookup, template retrieval, `ai_summarize`
- **Control plane:** human review before any response is sent, citation of template used

## Data And Resources

- **Team-built tables (in your own personal schema):** synthetic `tickets` table (ticket id, customer, category, description, status). Not in the shared setup — create with `generate-synthetic-data`.
- **Team-built documents:** synthetic response-template documents (one per ticket category). Generate with `generate-synthetic-data` and place in a UC volume.
- **Genie spaces:** optional, for querying ticket volume or category trends.
- **Vector Search:** new index over the generated response-template documents.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L100-foundations/01_agent_bricks_types.md`.
2. Generate the `tickets` table and response-template documents with `generate-synthetic-data`.
3. Build a Knowledge Assistant over the response-template documents.
4. Add an MCP tool for ticket and customer lookup.
5. Build the drafting flow: read ticket, retrieve the matching template, draft a response citing the template used.
6. Evaluate draft quality and template-match correctness.

## MCP, Tools, And Action Hooks

- **MCP tools:** ticket lookup, customer lookup, template lookup
- **SQL AI Functions:** `ai_summarize`, `ai_classify` for ticket categorization
- **Action-plane hooks:** draft response held for human review; optional CRM update once approved
- **Approval model:** human review and edit before any response is sent to a customer

## Evaluation And Governance

- **Eval set:** 8 tickets across different categories with expected template match and key facts to include.
- **Judges:** template-match correctness, groundedness, tone/brand-fit review.
- **Governance:** every draft cites the template it used; no draft is auto-sent.
- **Failure behavior:** flag "no matching template" instead of inventing a response for an uncategorized ticket.

## Demo Script

1. Pick an incoming ticket from the synthetic table.
2. Show the agent classifying it and retrieving the matching template.
3. Show the drafted response with the template citation.
4. Show the human-review/edit step.
5. Show the approved response and, if built, the CRM update.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Cuts response-drafting time in a real customer-service workflow |
| Agent quality | 25 | Correct template match and grounded, on-brand draft |
| Governance | 20 | Citation of template used and human review before send |
| Demo completeness | 20 | Ticket to reviewed, ready-to-send draft |
| Reuse | 10 | Template-retrieval pattern reusable across ticket categories |

## Stretch Goals

- Add batch drafting across a queue of tickets.
- Add sentiment detection to flag high-priority tickets.
- Add a customer-history summary alongside the draft.
