# Starter — Forecast Planner (adjacent track #6, MMF / Paints EMEA)

Explain a forecast miss from the **actual-vs-budget margin delta**, propose a quantified override, and
write it to Lakebase `akzo.forecast_overrides` (status `pending`) for human approval — answers *and*
actions.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: actual-vs-budget delta -> reasoning -> proposed override -> Lakebase write (pending) -> approve, + a judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case (copy of `eval/forecast.yaml`). |
| `README.md` | This file. |

Pre-wired: the governed actual-vs-budget call over `margin_actuals` vs `margin_budget`, the Lakebase
write+approve pattern (`forecast_overrides`), MLflow-style judge, sample-data refs, 5 golden questions.

## Measurable value

Forecast variance explanation + override drafting: **30–45 min of analyst spreadsheet reconciliation →
5–10 min** copilot delta decomposition with a staged, human-reviewed override.

## Verified primary query (this workspace)

Paints EMEA (Decorative Paints × EMEA), Q2 2026: **actual margin 30.7% vs budget 39.9% = −9.2pp miss**
(Q1 was on-plan, 39.6% vs 39.9%). The budget assumed no shocks; actuals hit price erosion, FX, and a
raw-material spike, with volume service-constrained by the May Rotterdam stockout.

## 5 golden questions

1. Why is the Paints EMEA forecast off in Q2 2026 versus what actually happened?
2. Decompose the forecast delta into demand, price, and cost components.
3. Given the Rotterdam supply disruption, what volume/demand assumption should the Q2 forecast have used?
4. Propose a forecast override for Paints EMEA for the next period and quantify it.
5. Once the Rotterdam lane recovers, how should the forecast adjust back?

(Full text + expected facts + failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — tweak, swap, extend

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — TWEAK (the override logic).** `# TODO (Day-2) SPRINT 1` on the reasoning prompt. Change
  the planning metric (units / revenue / margin % / service-constrained volume) and what the override
  proposes, then re-run BEAT 2.
- **Sprint 2 — SWAP (the write).** `# TODO (Day-2) SPRINT 2` on the `write_forecast_override` call.
  Change the SKU/region/period and override quantity, carry the LLM rationale into `reason`, approve as
  your persona.
- **Sprint 3 — EXTEND (eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add a golden question to
  `eval.yaml` (e.g. an override for a different segment) and re-run the judge.

## Ship target

A working notebook + a Lakebase `forecast_overrides` row (pending → approved) + a live judge run.
Upgrade path: point the actual-vs-budget read at the real Akzo Finance Genie space and back the planner
with MMF version tables instead of `margin_budget`.
