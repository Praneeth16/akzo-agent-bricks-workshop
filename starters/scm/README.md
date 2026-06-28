# Starter — SCM control-tower copilot (track #2)

Diagnose an OTIF / service drop over governed supply-chain data, find the root cause (lead time + stockout
+ service/backorder), recommend ONE intervention, and stage it as a governed Lakebase write for human
approval. This is the supervisor's SCM leg, standalone.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: governed text2SQL over `akzo_scm` -> root-cause reasoning -> Lakebase `scm_interventions` write + approval -> `ai_query` judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case + the measurable-value claim (copy of `eval/scm.yaml`). |
| `README.md` | This file. |

Pre-wired: the Akzo SCM Genie instructions as the system prompt, a working governed call, the
volume-weighted OTIF rule, the Lakebase write + approval pattern, an MLflow-style judge, sample-data refs,
and 5 golden questions. **Day-2 = tweak, swap, extend** — not stand one up.

## Measurable value

> Service-disruption root-cause triage: 30-45 min of cross-referencing OTIF, lane, and inventory reports by
> hand → 5-10 min copilot answer linking lead-time, stockout, and service-level evidence.

## Verified primary query (this workspace)

The `Rotterdam-NL->EMEA-DACH` lane OTIF **96.0% (Jan-Mar) → 94.5% (Apr) → 88.9% (May 2026) → 93.0% (Jun)** —
the disrupted EMEA lane. Root cause: lead time stepped 5 → 9 days; key Decorative SKUs (DEC-1000, DEC-1004)
stocked out at Rotterdam in May (days_of_supply ~1); EMEA service dipped to **90.6%** with **~2,258**
backorders.

## 5 golden questions

1. What happened to OTIF on the Rotterdam to EMEA-DACH lane in May 2026?
2. Why did that lane's OTIF fall — what is the root cause?
3. Which SKUs hit a stockout at Rotterdam in May 2026?
4. What was the EMEA customer service level and backorder volume in May 2026?
5. Was the May 2026 service problem EMEA-specific or global across all plants and regions?

(Full text + expected facts + failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — make it your own / make it act + measurable / ship

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — make it your own (TWEAK the instruction).** `# TODO (Day-2) SPRINT 1` on `SCM_INSTRUCTIONS`.
  Edit one CERTIFIED RULE or add one example `Q:/SQL:` pair (e.g. normalize lead time by transport mode so
  sea lanes don't dominate), then re-run BEAT 1 and watch the SQL change.
- **Sprint 2 — make it act + measurable (SWAP the action).** `# TODO (Day-2) SPRINT 2` on
  `stage_intervention`. Change the `intervention_type` / `detail` / `expected_impact` (e.g.
  `expedite_reroute` → `safety_stock_increase`); re-run and watch the new `pending` row land and flip to
  `approved`.
- **Sprint 3 — ship (EXTEND the eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add your own golden
  question to `eval.yaml` (e.g. a lane cost-per-unit comparison) and re-run the judge cell.

## Ship target

A working notebook + a live trace + a Lakebase `scm_interventions` row. The SCM leg also ships inside the
deployable **`apps/supervisor/`** (clone, don't author). Upgrade path: point `text2sql` at the real Akzo SCM
Genie space via the Genie Conversation API — the system prompt in `starter.py` is the space's Instructions
block.
