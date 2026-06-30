# Track 01: Finance Controlling Copilot

## Use Case And Target User

- **Use case:** #1 Finance controlling copilot
- **Primary users:** controllers, FP&A analysts, finance business partners
- **Business question:** Why did margin, cost, FX, price, or variance move, and what should the controller do next?
- **Success signal:** A finance question that takes 20-30 minutes manually can be answered with drivers, evidence, and next actions in one chat.

## Hackathon Goal

Build a finance assistant that answers one margin or variance question over the synthetic finance tables, explains the drivers, cites the source rows or generated SQL, and recommends a controller action.

## Starter Architecture

- **Agent pattern:** Genie Space plus optional code-your-own wrapper
- **Data plane:** `akzo_finance` tables and Finance Genie space
- **Tool plane:** `ai_query`, `ai_summarize`, optional finance KPI lookup MCP tool
- **Control plane:** MLflow trace, groundedness judge, UC table permissions

## Data And Resources

- **Provided tables (`<catalog>.akzo_finance`):** `products` (incl. `list_price_eur`, `standard_cost_eur`), `margin_actuals`, `margin_budget`, `fx_rates`, `cost_drivers`
- **Documents:** none required; the document volume holds safety sheets and contracts, not finance policy
- **Genie spaces:** Akzo Finance
- **Vector Search:** not needed for this track

## Agent Bricks Build Path

1. Start from `../../L100-foundations/01_agent_bricks_types.md`.
2. Reuse the Finance Genie space created by `../../data/setup/setup_genie_spaces.py`.
3. Add instructions for variance decomposition, driver ranking, and confidence language.
4. Add 5 sample questions covering price, volume, mix, cost, and FX.
5. Evaluate answers with correctness and groundedness questions in MLflow.

## MCP, Tools, And Action Hooks

- **MCP tools:** read-only KPI lookup, policy lookup
- **SQL AI Functions:** `ai_query`, `ai_summarize`, `ai_mask`
- **Action-plane hooks:** optional email or Teams draft to notify a business owner
- **Approval model:** read-only by default, propose-only for follow-up messages

## Evaluation And Governance

- **Eval set:** 8 finance questions with expected business driver categories.
- **Judges:** groundedness, SQL relevance, explanation quality.
- **Governance:** UC permissions, masked personal fields, trace capture.
- **Failure behavior:** state when the question needs a different domain or missing plan period.

## Demo Script

1. Ask: "Why did Paints EMEA gross margin drop in Q2 2026 - is it price, volume, FX, or cost?"
2. Show the generated finance query or Genie trace.
3. Show the ranked drivers and cited metrics.
4. Show one eval row and groundedness score.
5. Close with the recommended controller action.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Clear controller workflow and decision support |
| Agent quality | 25 | Correct variance drivers with grounded SQL or citations |
| Governance | 20 | UC permissions, masking, and trace evidence |
| Demo completeness | 20 | End-to-end finance question to recommended action |
| Reuse | 10 | Uses the Finance Genie space and L100 evaluation pattern |

## Stretch Goals

- Add multi-turn follow-up questions.
- Add policy citations for controller guidance.
- Add a Teams draft action with human approval.

