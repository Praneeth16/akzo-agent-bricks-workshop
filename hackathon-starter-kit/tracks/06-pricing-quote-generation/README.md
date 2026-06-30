# Track 06: Pricing And Quote-Generation Agent

## Use Case And Target User

- **Use case:** #18 Pricing and quote-generation agent
- **Primary users:** sales operations, commercial teams, pricing analysts
- **Business question:** What does the customer request require, what price applies, and what quote package should be drafted?
- **Success signal:** Inbound request details are extracted, price logic is called, and a draft quote is prepared for human approval.

## Hackathon Goal

Build a quote agent that reads an inbound request, extracts quote parameters, calls a pricing or margin lookup tool, and drafts a quote response with approval required before sending.

## Starter Architecture

- **Agent pattern:** text classification plus code-your-own tool-calling agent
- **Data plane:** Commercial account, product, pricing, and margin tables
- **Tool plane:** `ai_extract`, pricing lookup, margin guardrail, quote draft action
- **Control plane:** human approval, commercial guardrails, audit trail

## Data And Resources

- **Provided tables:** `<catalog>.akzo_finance.products` (`list_price_eur`, `standard_cost_eur`) for price and margin floor; `<catalog>.akzo_commercial.accounts` and `sales_actuals` for customer context
- **Team-built tables (in `akzo_ops`):** price lists, margin bands, and quote history are not provided. Create them with `generate-synthetic-data` if your demo needs them.
- **Documents:** team-supplied inbound request emails and a terms template
- **Genie spaces:** Akzo Commercial
- **Vector Search:** optional quote template retrieval

## Agent Bricks Build Path

1. Start from `../../L100-foundations/01_agent_bricks_types.md` for extraction/classification.
2. Extract customer, product, volume, region, requested date, and terms.
3. Look up price and cost from `akzo_finance.products`, or a generated price list.
4. Apply a margin floor from `standard_cost_eur` and discount guardrails.
5. Draft a quote action that requires human approval.

## MCP, Tools, And Action Hooks

- **MCP tools:** customer lookup, product lookup, price lookup
- **SQL AI Functions:** `ai_extract`, `ai_classify`, `ai_summarize`, `ai_mask`
- **Action-plane hooks:** email draft, CRM quote draft
- **Approval model:** human approval before sending or CRM update

## Evaluation And Governance

- **Eval set:** 6 inbound requests with expected extracted fields and price bands.
- **Judges:** extraction completeness, price-source grounding, guardrail compliance.
- **Governance:** discount thresholds, margin floor, approval audit.
- **Failure behavior:** request missing required fields triggers a clarification draft.

## Demo Script

1. Paste an inbound customer request.
2. Show extracted quote parameters.
3. Show pricing lookup and margin guardrail result.
4. Show draft quote email in proposed state.
5. Approve or reject the action and show audit.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Reduces quote turnaround while protecting margin |
| Agent quality | 25 | Accurate extraction and grounded price logic |
| Governance | 20 | Discount guardrails and approval before send |
| Demo completeness | 20 | Request to proposed quote package |
| Reuse | 10 | Uses extraction, Commercial data, and action-plane patterns |

## Stretch Goals

- Add quote template retrieval.
- Add multi-currency conversion.
- Add competitor or customer history context.

