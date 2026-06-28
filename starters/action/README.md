# Starter — Agents That Act (Action track)

The "can agents *act*?" build. An agent action travels the whole governed plane:
**propose** a governed action → **`evaluate`** it against policy guardrails → a human **approve**s →
**`execute`** it into an external system through the Unity Catalog HTTP connection `akzo_external_systems` →
the action reaches **`executed`** with a real **`external_ref`** + a receipt in `akzo.external_system_log`,
full lineage in `akzo.action_events`. Plus the **breach → escalate** path that stops an over-cap action
before it acts. Reads governed by OBO; **writes/executions governed by identity + policy + approval + audit.**

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: propose → `evaluate` (guardrail chips) → approve → `execute` (calls the mock through the governed UC connection) → show `external_ref` + receipt + lineage; the breach→escalate path; an L4 auto-approve-within-policy variant; a judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden "did it actually act?" questions + the failing case (copy of `eval/action.yaml`). |
| `README.md` | This file. |

Pre-wired: the shared `apps/_shared/action_plane` plane (`ActionPlane`, `evaluate`, `execute`, `ROUTING`),
the Lakebase tables (`actions`, `action_events`, `action_policies`), the seeded policies, the governed UC
HTTP connection `akzo_external_systems` → the Mock External Systems app, the `ai_query` judge, and the 5
golden questions. **No team stands the plane up — Day 2 is tweak / swap / extend a working one.**

## Measurable value

Cross-system action execution: **hours of manual system updates** (open the CRM, draft + send the email,
key the PO into the ERP, chase the audit trail across four systems) → **one governed click** that executes
into the external systems and is **fully audited** end-to-end (`external_ref` + `external_system_log`
receipt + `proposed→approved→executed` lineage), with policy guardrails that **auto-escalate anything over
cap before it can act.**

## The 5 golden "did it actually act?" questions

1. Take the staged `quote_send` action through to completion — what status does it reach, and how do I know
   it actually acted? *(→ action reached status `executed`)*
2. Where is the evidence that the action reached the external system — is there an `external_ref` and a
   receipt? *(→ `external_ref` present + receipt in `external_system_log`)*
3. Show me the audit lineage for the executed action — who did what, when? *(→ `proposed→approved→executed`)*
4. We staged an `scm_reorder` for €205k against a €100k cap and approved it. Did it execute? *(→ breach
   escalated, **not** executed)*
5. When this agent acts on an external system, what makes that call governed and auditable? *(→ UC HTTP
   connection + policy guardrails + `action_events` / `external_system_log` audit)*

**Failing case:** stage + approve + execute a €205k `scm_reorder` against the €100k cap — it must **NOT**
execute; `execute()` re-runs the guardrails at the gate and escalates instead of raising the PO.

(Full text + expected facts + failing case + measurable value in `eval.yaml`.)

## Sprint 1 / 2 / 3 / 4 — tweak, swap, extend

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — TWEAK (the action).** `# TODO (Day-2) SPRINT 1` on `ACTION_TYPE` + `PAYLOAD`. Swap in the
  action your team acts on. The `action_type` must be routable (a key of `ROUTING`) and have a policy row;
  the payload fields your connector + guardrail read live here.
- **Sprint 2 — SWAP (the guardrail).** `# TODO (Day-2) SPRINT 2` at the `evaluate()` call. The policy is a
  row in `akzo.action_policies`, not code — `UPDATE` a cap (`max_discount_pct`, `max_spend_eur`,
  `allowed_regions`) and re-run to watch the chips flip pass → breach.
- **Sprint 3 — EXTEND (the connector).** `# TODO (Day-2) SPRINT 3` at the `execute()` call. The
  `action_type → connector` route is `ROUTING` in `executor.py` (e.g. `forecast_override → teams`,
  `scm_reorder → erp_po`, `scm_reroute → teams,ticket`). Target a different external system, or add a new
  connector under `apps/_shared/action_plane/connectors/` + a `ROUTING` entry.
- **Sprint 4 — AUTONOMOUS (L4).** `# TODO (Day-2) SPRINT 4` on `act_autonomously`. Auto-approve-within-policy
  and escalate-on-breach is wired; extend it to a real trigger (e.g. OTIF < 90% on a lane) + a verify step.
  The full detect → act → verify → escalate loop is `notebooks/10_autonomous_closed_loop.py`.

## Running it

In the workspace, `apps/_shared` is synced beside your repo; the setup cell adds it to `sys.path`. Locally:

```bash
DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth python -c "import sys; sys.path.insert(0,'apps/_shared'); ..."
```

The starter asserts the primary path live: an action goes `proposed → approved → executed` with a real
`external_ref` + an `external_system_log` receipt, and the over-cap breach escalates.

## Ship target

A **working action that executes externally + is audited** — status `executed`, a real `external_ref`, a
receipt in `akzo.external_system_log`, and the `proposed→approved→executed` lineage in `akzo.action_events`
— **OR** the deployed **Action Center** app. The full React+FastAPI Action Center (cross-agent action queue,
approve/execute, per-action lineage + external effect, maturity-ladder viz) lives at **`apps/action-center/`**
— clone and deploy it, don't author it. This notebook is its logic spine.
