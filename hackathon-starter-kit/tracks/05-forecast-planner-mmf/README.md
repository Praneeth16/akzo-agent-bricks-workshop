# Track 05: Forecast Planner Copilot On MMF

## Use Case And Target User

- **Use case:** #6 Forecast planner copilot on top of MMF
- **Primary users:** demand planners, supply planners, forecast analysts
- **Business question:** What changed in the forecast, why did it change, and should the planner override it?
- **Success signal:** Planner can compare forecast versions, see drivers, and create a review-ready override recommendation.

## Hackathon Goal

Build a planner copilot that explains forecast movement, uses `ai_forecast` for a baseline or comparison, and drafts an override recommendation with confidence and evidence.

## Starter Architecture

- **Agent pattern:** Genie Space plus SQL AI Functions
- **Data plane:** provided SCM `otif`/`inventory`/`service_levels` series, plus team-built demand/forecast-version tables
- **Tool plane:** `ai_forecast`, forecast version compare, override proposal
- **Control plane:** bias/accuracy metrics, planner approval, trace capture

## Data And Resources

- **Provided tables (`<catalog>.akzo_scm`):** `otif`, `inventory`, `service_levels` give monthly series to forecast; `lanes` for lead-time context
- **Team-built tables (in `akzo_ops`):** demand history, forecast versions, and exogenous signals are not provided. Create them with `generate-synthetic-data`, or derive a baseline series from the SCM tables above.
- **Genie spaces:** Akzo SCM
- **Vector Search:** not needed for this track

## Agent Bricks Build Path

1. Start from `../../L100-foundations/00_sql_ai_functions.ipynb`.
2. Build a monthly series from `akzo_scm.service_levels` or `otif`, or generate a demand series with `generate-synthetic-data`.
3. Use `ai_forecast` on that series.
4. Compare baseline forecast, latest forecast version, and actuals.
5. Add explanation instructions for bias, accuracy, and exogenous drivers.
6. Draft an override recommendation that stops for planner approval.

## MCP, Tools, And Action Hooks

- **MCP tools:** forecast version lookup, exogenous signal lookup
- **SQL AI Functions:** `ai_forecast`, `ai_query`, `ai_summarize`
- **Action-plane hooks:** forecast override proposal, ticket or Teams notification
- **Approval model:** propose-only for overrides, human approval required

## Evaluation And Governance

- **Eval set:** 6 forecast-change questions with known direction and driver labels.
- **Judges:** driver correctness, explanation quality, recommendation reasonableness.
- **Governance:** planner approval and traceable data lineage.
- **Failure behavior:** state when series history is too short or driver evidence is weak.

## Demo Script

1. Ask why forecast increased for a product-region.
2. Show baseline forecast and version comparison.
3. Show drivers and confidence.
4. Draft an override recommendation.
5. Show approval state and eval result.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Helps planners act on forecast exceptions |
| Agent quality | 25 | Correct version comparison and driver explanation |
| Governance | 20 | Human approval before overrides |
| Demo completeness | 20 | Forecast question to override recommendation |
| Reuse | 10 | Uses `ai_forecast` and SCM Genie resources |

## Stretch Goals

- Add bias and forecast value added metrics.
- Add multiple product-region series.
- Add scenario planning with exogenous signals.

