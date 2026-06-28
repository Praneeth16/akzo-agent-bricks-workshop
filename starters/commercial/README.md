# Starter — Commercial action assistant (track #5)

Rank at-risk accounts over governed commercial data, tie the churn to its upstream cause (the EMEA service
shock, not pricing), recommend ONE next-best-action, and stage that save play as a governed Lakebase write
for human approval. This is the supervisor's Commercial leg, standalone.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: governed text2SQL over `akzo_commercial` -> churn root-cause + next-best-action reasoning -> Lakebase `commercial_actions` write + approval -> `ai_query` judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case + the measurable-value claim (copy of `eval/commercial.yaml`). |
| `README.md` | This file. |

Pre-wired: the Akzo Commercial Genie instructions as the system prompt, a working governed call, the
`churn_score > 0.7` rule, the Lakebase write + approval pattern, an MLflow-style judge, sample-data refs,
and 5 golden questions. **Day-2 = tweak, swap, extend** — not stand one up.

## Measurable value

> Churn-risk account review: 30 min of manual CRM/sales-report cross-checking per account → 5-10 min ranked
> at-risk list with root cause and a recommended next action.

## Verified primary query (this workspace)

Three at-risk EMEA Decorative ("Paints") accounts in Jun 2026, all churn_score > 0.7:
**ACC0001 Rhine Valley Decor Distributors (0.865), ACC0002 Benelux PaintPro (0.827), ACC0003 Nordic Coatings
Supply (0.80)** — each with rising complaint_count and negative NPS. Combined revenue fell ~EUR 375k (Jan) →
~EUR 169k (Jun). The churn is downstream of the May EMEA service/OTIF shock, not a pricing failure.

## 5 golden questions

1. Which EMEA accounts are at risk of churn in Q2 2026?
2. What signals are driving the churn risk for Rhine Valley Decor Distributors?
3. How much revenue is at risk across the three at-risk EMEA accounts?
4. Why are these accounts churning — is it a commercial problem or something upstream?
5. What action should the rep take for the top at-risk account?

(Full text + expected facts + failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — make it your own / make it act + measurable / ship

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — make it your own (TWEAK the instruction).** `# TODO (Day-2) SPRINT 1` on `COM_INSTRUCTIONS`.
  Edit one CERTIFIED RULE (e.g. the `churn_score > 0.7` threshold) or add one example `Q:/SQL:` pair, then
  re-run BEAT 1 and watch the generated SQL — and the at-risk list — change.
- **Sprint 2 — make it act + measurable (SWAP the action).** `# TODO (Day-2) SPRINT 2` on `stage_action`.
  Change the `action_type` / `detail` / which account it targets (e.g. `retention_outreach` →
  `service_recovery_QBR`); re-run and watch the new `pending` row land and flip to `approved`.
- **Sprint 3 — ship (EXTEND the eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add your own golden
  question to `eval.yaml` (e.g. pipeline-at-risk by product line) and re-run the judge cell.

## Ship target

A working notebook + a live trace + a Lakebase `commercial_actions` row. The Commercial leg also ships
inside the deployable **`apps/supervisor/`** (clone, don't author). Upgrade path: point `text2sql` at the
real Akzo Commercial Genie space via the Genie Conversation API — the system prompt in `starter.py` is the
space's Instructions block.
