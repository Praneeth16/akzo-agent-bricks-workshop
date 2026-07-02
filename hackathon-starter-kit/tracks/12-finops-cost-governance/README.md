# Track 12: FinOps And AI Cost Governance Copilot

## Use Case And Target User

- **Use case:** #8 FinOps and AI cost governance copilot
- **Primary users:** platform engineering, FinOps analysts, engineering leads
- **Business question:** Why did our Databricks and Genie spend change, and are we tracking to budget?
- **Success signal:** A spend question that takes a manual spreadsheet pull gets answered with drivers, forecast, and a budget-status flag in one chat.

## Hackathon Goal

Build a FinOps copilot that explains usage and cost movement across workspaces, SKUs, and teams, flags budget overages against policy, and answers "why did cost change?" with grounded evidence.

## Starter Architecture

- **Agent pattern:** Genie Space plus optional Knowledge Assistant over a FinOps runbook
- **Data plane:** usage/cost fact table and budget policy table
- **Tool plane:** `ai_query`, `ai_summarize`, overage-check UC function
- **Control plane:** MLflow trace, groundedness judge, budget-policy citation requirement

## Data And Resources

- **Team-built tables (in your own personal schema):** `fact_usage` (~30,000 rows: `date`, `workspace`, `sku`, `dbus`, `cost`, `budget`, `team`) and `dim_budget_policy`. Neither is in the shared setup — create both with `generate-synthetic-data`.
- **Documents:** optional short FinOps runbook (overage escalation steps) if you want a Knowledge Assistant layer.
- **Genie spaces:** new "Akzo FinOps" space over `fact_usage` and `dim_budget_policy`.
- **Vector Search:** only needed if you add the runbook Knowledge Assistant.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L100-foundations/01_agent_bricks_types.md`.
2. Generate `fact_usage` and `dim_budget_policy` with `generate-synthetic-data` into your personal schema.
3. Create the Akzo FinOps Genie space over both tables.
4. Write instructions that define overage logic explicitly: cost vs. budget by team and month, with a clear threshold for "overage" (for example, greater than 10% over budget).
5. Add 5 sample questions covering month-over-month change, team ranking, and a forecasted-overage question.
6. Evaluate answers for correct overage classification and cited numbers.

## MCP, Tools, And Action Hooks

- **MCP tools:** budget-policy lookup, team-cost lookup
- **SQL AI Functions:** `ai_query`, `ai_summarize`, `ai_forecast` for a spend trend
- **Action-plane hooks:** optional Teams or email alert draft when a team crosses its budget threshold
- **Approval model:** read-only by default; alert drafts are propose-only

## Evaluation And Governance

- **Eval set:** 8 spend questions with expected driver categories (SKU mix, workspace growth, one-time job, team change).
- **Judges:** groundedness, overage-classification correctness, explanation quality.
- **Governance:** budget-policy citation on every overage claim; trace capture.
- **Failure behavior:** state when the requested period has no usage data instead of guessing a trend.

## Demo Script

1. Ask: "Why did our Genie and serverless spend increase last month, and are we over budget?"
2. Show the generated query or Genie trace over `fact_usage`.
3. Show the ranked cost drivers by team and SKU.
4. Show the budget-policy check and overage flag.
5. Close with a forecasted next-month spend range.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Clear FinOps workflow and low-risk internal starter |
| Agent quality | 25 | Correct overage logic with grounded cost figures |
| Governance | 20 | Explicit budget-policy citations and trace evidence |
| Demo completeness | 20 | Spend question to budget-status answer |
| Reuse | 10 | Reusable overage-detection pattern for any cost table |

## Stretch Goals

- Add a forecasted-overage alert before month-end.
- Add a per-team cost-optimization recommendation.
- Add a dashboard view of the same Genie space results.
