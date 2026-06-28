# Starter — Finance controlling copilot (track #1)

Answer a gross-margin variance question over governed finance data, decompose it four ways
(**price / volume / FX / cost**), recommend ONE action, and stage that recommendation as a governed
Lakebase write for human approval. This is the supervisor's Finance leg, standalone.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: governed text2SQL over `akzo_finance` -> four-way variance reasoning -> Lakebase `forecast_overrides` write + approval -> `ai_query` judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case + the measurable-value claim (copy of `eval/finance.yaml`). |
| `README.md` | This file. |

Pre-wired: the Akzo Finance Genie instructions as the system prompt, a working governed call, the
certified-metric rule (`SUM(gross_margin_eur)/SUM(revenue_eur)`), the Lakebase write + approval pattern,
an MLflow-style judge, sample-data refs, and 5 golden questions. **Day-2 = tweak, swap, extend** — not
stand one up.

## Measurable value

> Margin-variance root-cause investigation: 20-30 min of manual cube slicing and bridge-building →
> 5-10 min copilot answer with a cited four-way price/volume/FX/cost decomposition.

## Verified primary query (this workspace)

Paints EMEA (Decorative Paints × EMEA) gross margin **39.6% (Q1 2026) → 30.7% (Q2 2026)** — a **~8.9pp**
drop; realized price/unit erodes **34.54 → 32.73**. Bridge: price ~−3pp, raw-material cost ~−3pp, FX ~−2pp
(USD 0.926 → 0.879), volume ~flat.

## 5 golden questions

1. What happened to Paints EMEA gross margin in Q2 2026 versus Q1 2026?
2. Decompose the Paints EMEA Q2 2026 margin drop into price, volume, FX, and cost effects.
3. Which cost driver is responsible for the COGS increase in Paints EMEA in Q2 2026?
4. How much did adverse FX contribute to the Paints EMEA margin miss, and which currencies drove it?
5. Is the Q2 2026 margin problem specific to Paints EMEA or is it company-wide?

(Full text + expected facts + failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — make it your own / make it act + measurable / ship

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — make it your own (TWEAK the instruction).** `# TODO (Day-2) SPRINT 1` on
  `FINANCE_INSTRUCTIONS`. Swap in your tables/persona, edit one CERTIFIED RULE or add one example `Q:/SQL:`
  pair, then re-run BEAT 1 and watch the generated SQL — and the answer — change.
- **Sprint 2 — make it act + measurable (SWAP the action).** `# TODO (Day-2) SPRINT 2` on `stage_override`.
  Change what the copilot stages (override magnitude, a price-floor review, a margin-recovery target);
  re-run and watch the new `pending` row land in Lakebase and flip to `approved`.
- **Sprint 3 — ship (EXTEND the eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add your own golden
  question to `eval.yaml` (e.g. budget-vs-actual variance) and re-run the judge cell.

## Ship target

A working notebook + a live trace + a Lakebase `forecast_overrides` row. Deployable React+FastAPI version:
**`apps/finance-copilot/`** (clone, don't author). Upgrade path: point `text2sql` at the real Akzo Finance
Genie space via the Genie Conversation API — the system prompt in `starter.py` is the space's Instructions
block.
