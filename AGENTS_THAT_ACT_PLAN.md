# PLAN — "Agents That Act" (AkzoNobel exec angle)

**Created:** 2026-06-26
**Origin:** Head of AkzoNobel asked "can agents take *action*?" Builds on the shipped workshop kit (`BUILD_PLAN.md`, `WORKSHOP_MATERIALS.md`).
**Target workspace:** profile `fe-vm-lakebase-praneeth`. Catalog `serverless_lakebase_praneeth_catalog` (schemas `akzo_*`); Lakebase `graphrag-spike` / db `databricks_postgres` / schema `akzo`; warehouse `4d39ac2e32b72a3a`; chat `databricks-claude-opus-4-7`.
**Scope (locked with user):** all three ambition layers (deepen write-back+approval · act on external systems · autonomous closed-loop) across all four surfaces (new Action Center app · deepen existing 3 apps · exec demo script+slides · new hackathon Action track).
**Execution mode:** autonomous `/loop`, build → deploy → verify live.

---

## 1. Problem frame

We already have agents that *act* — but only the **stage-and-approve** flavor (write to Lakebase + human approval). An exec asking "can agents act?" wants to see action that (a) reaches the systems the business actually runs on, and (b) can run with guardrails, not just suggest. The plan closes that gap **without losing the governance story** — every external action flows through a governed UC HTTP connection + AI Gateway logging + an auditable action plane.

## 2. The Action Maturity Ladder (the exec narrative spine)

| Level | Name | What the agent does | Status today |
|------|------|---------------------|--------------|
| **L1** | Recommend | Answers + proposes a next-best-action | ✅ have (all agents) |
| **L2** | Stage & approve | Writes a governed action record, human approves, audit trail | ✅ have (quote/forecast/SCM) |
| **L3** | Execute externally | On approval, pushes the action into real systems (email/Teams, CRM, ERP/PO, SharePoint, ticketing) via a governed UC HTTP connection | 🔨 build |
| **L4** | Autonomous closed-loop | Trigger → pick action within policy → execute → verify effect → escalate only on guardrail breach | 🔨 build |

Every level is **governed by the same plane**: app/service identity + policy guardrails + approval gate (configurable per level) + full audit/lineage + AI Gateway payload logs. OBO governs reads; **writes/executions are governed by identity + policy + approval + audit (not OBO)** — the honest story.

## 3. Architecture — the shared Action Plane

```
agent (recommend) → propose Action ──▶ [Action Plane]
                                         actions table (state machine)
                                         guardrail engine (policy checks)
                                         approval gate (per-level)
                                         executor ──▶ tool connectors ──▶ UC HTTP connection ──▶ Mock Systems App
                                                                              (email/Teams/CRM/ERP-PO/SharePoint/ticket)
                                         action_events (audit + lineage + external refs)
                                         AI Gateway payload logs (akzo_gateway)
```

- **State machine:** `proposed → approved → executing → executed | failed | escalated`. L4 may auto-advance `proposed→approved` when guardrails pass.
- **Guardrail engine:** policy rules (discount ≤ limit, spend ≤ cap, region in scope, action-type allowed) checked *before* execute; breach → `escalated` + human gate.
- **Governed external calls:** all connectors call the Mock Systems App **through a UC HTTP connection** (`akzo_external_systems`) so calls are catalog-governed + logged; demo never sends real email/PO.

## 4. Naming + new objects

- **Lakebase (schema `akzo`):** `actions` (canonical record), `action_events` (audit/lineage), `action_policies` (guardrail rules), `external_system_log` (mock-side receipts). Reuse existing `quote_approvals`/`forecast_overrides`/`scm_interventions` as typed action sources that now feed `actions`.
- **UC HTTP connection:** `akzo_external_systems` → Mock Systems App base URL (created via `CREATE CONNECTION`).
- **Apps:** `akzo-action-center` (new), `akzo-mock-systems` (new, the governed external target). Deepen `akzo-supervisor`/`akzo-finance-copilot`/`akzo-quote-agent`.
- **Notebooks:** `notebooks/09_agents_that_act.py` (L1→L4 ladder), `notebooks/10_autonomous_closed_loop.py` (+ optional Databricks Job `akzo-autonomous-scm`).
- **Starter:** `starters/action/` + `eval/action.yaml`.
- **Demo:** `demo/agents_that_act.md` (script + slide outline + talk track).
- **Shared code:** `apps/_shared/action_plane/` (Python module reused by apps + notebooks): `model.py` (state machine), `guardrails.py`, `executor.py`, `connectors/`.

---

## 5. Implementation units

### U1. Action plane data model + core module
**Goal:** canonical action record + state machine + guardrail engine in Lakebase + a reusable Python module.
**Files:** `apps/_shared/action_plane/{model.py,guardrails.py,__init__.py}`, `notebooks/09a_action_plane_setup.py` (DDL), Lakebase tables `akzo.{actions,action_events,action_policies}`.
**Approach:** `actions(id, agent, action_type, subject, payload jsonb, status, level, region, requested_by, approved_by, created_at, decided_at, executed_at, result jsonb, external_ref)`; `action_events(action_id, ts, event, actor, detail)`; `action_policies(action_type, max_discount_pct, max_spend_eur, allowed_regions, requires_approval bool)`. Guardrail engine evaluates a proposed action against policies → pass/breach + reasons. Seed sensible policies.
**Verify:** propose an action, run guardrails (one pass, one breach), advance state, read `action_events` lineage back. Live round-trip on Lakebase.

### U2. Mock external-systems app + governed UC HTTP connection
**Goal:** a safe, governed external target the agents call.
**Files:** `apps/mock-systems/` (FastAPI: `POST /email`, `/teams`, `/crm/task`, `/erp/po`, `/sharepoint/upload`, `/servicenow/ticket`, each returns a ref id + logs to `akzo.external_system_log`; `GET /api/health`), `app.yaml`, `requirements.txt`, `README.md`; `notebooks/09b_uc_http_connection.py` (`CREATE CONNECTION akzo_external_systems TYPE HTTP ...`).
**Approach:** deploy mock app first, get its URL, create the UC HTTP connection pointing at it. Connectors call via the connection (or `http_request`) so the path is catalog-governed.
**Verify:** deploy mock app ACTIVE/SUCCEEDED; connection created; a governed call to `/email` returns a ref + writes `external_system_log`.

### U3. Tool connectors (L3 execute)
**Goal:** executor dispatches an approved action to the right connector.
**Files:** `apps/_shared/action_plane/executor.py`, `connectors/{email,teams,crm,erp_po,sharepoint,ticket}.py`.
**Approach:** each connector maps an action payload → mock endpoint call through `akzo_external_systems`, records `external_ref` + result on the action, logs an `action_events` row. Executor enforces: only `approved` actions execute; failures → `failed` + event.
**Verify:** approve a quote action → executor sends email + creates CRM task + drafts PO (mock) → external_refs recorded → action `executed`.

### U4. Notebook `09_agents_that_act.py` — the ladder
**Goal:** one runnable narrative showing L1→L4 on the Paints EMEA story.
**Files:** `notebooks/09_agents_that_act.py` (Databricks notebook source).
**Approach:** L1 recommend (reuse supervisor reasoning) → L2 stage+approve (Lakebase) → L3 execute external (connectors) → L4 preview (link to NB10). Each level a cell with markdown + live run; See→Tweak→Return.
**Verify:** runs top-to-bottom; an action travels proposed→executed with external refs; audit lineage shown.

### U5. Notebook `10_autonomous_closed_loop.py` (+ optional Job)
**Goal:** L4 — detect→act→verify→escalate within guardrails.
**Files:** `notebooks/10_autonomous_closed_loop.py`, `deploy/job_autonomous_scm.json` (optional Databricks Job def).
**Approach:** trigger = OTIF<90% on a lane (Rotterdam May) → agent selects an intervention (expedite/reroute/reorder safety stock) **within `action_policies`** → auto-approve if within policy → execute (mock reorder PO + Teams alert) → verify (re-query) → if outside policy (e.g. spend>cap) → `escalated` + human gate. Strong guardrail framing.
**Verify:** run the loop on the seeded OTIF breach → autonomous path executes within policy; force a breach → escalates instead of acting.

### U6. Action Center app `apps/action-center/`
**Goal:** the single screen for an exec — "agents act, governed."
**Files:** `apps/action-center/{backend,frontend,app.yaml,requirements.txt,README.md}` (reuse `apps/_shared/action_plane` + the proven `databricks_client.py`/`lakebase.py`).
**Approach:** backend routes `GET /api/actions` (cross-agent queue, filter by status/level/agent), `POST /api/actions/{id}/approve|reject|execute`, `GET /api/actions/{id}` (audit + lineage + external refs), `GET /api/ladder` (counts by level). Frontend: action queue, per-action detail with the full lineage + external effect, the maturity-ladder viz, guardrail badges.
**Verify:** deploy ACTIVE/SUCCEEDED; live: approve→execute an action through the UI, see external ref + audit; ladder counts populate.

### U7. Deepen the existing 3 apps
**Goal:** every app can act, not just answer.
**Files:** `apps/supervisor/`, `apps/finance-copilot/`, `apps/quote-agent/` — add an `Actions` panel + backend `POST /api/act` wired to `action_plane`.
**Approach:** supervisor recommended-action → "Stage action"; finance variance → "Stage hedge/price-recovery action"; quote already writes — add "Execute on approve" (email customer + CRM). Each panel shows the Act→Approve→Execute→Confirm states.
**Verify:** each app stages an action that appears in Action Center; quote app executes externally on approve.

### U8. Hackathon 'Action' track `starters/action/`
**Goal:** forkable Day-2 starter for agent actions + external tool-calling.
**Files:** `starters/action/{starter.py,eval.yaml,README.md}`, `eval/action.yaml`.
**Approach:** slim `starter.py` — propose action → guardrail → approve → execute via `akzo_external_systems` → audit; `# TODO (Day-2)` markers on action_type, policy, connector. 5 golden "did it act?" questions.
**Verify:** `ast.parse`; primary path executes a mock action live.

### U9. Exec demo script + slides
**Goal:** answer "can agents act?" in 5 minutes.
**Files:** `demo/agents_that_act.md`.
**Approach:** the ladder as the spine; live flow (ask → recommend → stage → approve → external effect → audit → autonomous loop); governance callouts; honest Foundry contrast (one governed plane over the lakehouse data + the actions taken on it, UC-native lineage end to end). Talk track + fallback screenshots.
**Verify:** dry-run the script against the live apps; every claim maps to a working artifact.

### U10. Deploy + smoke
**Goal:** everything live + a results record.
**Files:** `deploy/deploy_action_apps.sh`, `deploy/ACTION_SMOKE_RESULTS.md`.
**Approach:** deploy `akzo-mock-systems` + `akzo-action-center`; grant SPs (UC + warehouse + Lakebase roles + the HTTP connection); deploy autonomous Job; smoke each path live under SP.
**Verify:** both new apps ACTIVE/SUCCEEDED; full L1→L4 smoke green; results written.

---

## 6. Build order + subagents

| Phase | Units | Parallelism |
|------|-------|-------------|
| 1 | U1 (action plane), U2 (mock app + connection) | U1 + U2 parallel (2 subagents) |
| 2 | U3 connectors | depends U1,U2 (1 subagent) |
| 3 | U4 ladder NB, U5 autonomous NB | parallel (2 subagents), depend U3 |
| 4 | U6 Action Center app, U7 deepen 3 apps | parallel (2 subagents), depend U3 |
| 5 | U8 starter, U9 demo | parallel (2 subagents) |
| 6 | U10 deploy + smoke | 1 subagent, depends U6,U7 |

## 7. Risks / fallbacks

- **UC HTTP connection / `http_request` perms or availability** → fallback: connector calls the mock app's URL directly via the app SP (still logged in action plane + AI Gateway), and document the UC-HTTP-connection upgrade. The governance story degrades gracefully but stays auditable.
- **Autonomous loop safety** → it only ever calls the **mock** systems; guardrails enforced pre-execute; breach escalates. Frame explicitly as policy-bounded, human-on-the-loop.
- **Real-action perception** → make clear in UI + demo that external targets are mocked for the workshop; the pattern (governed connection + audit) is production-shaped.
- **Lakebase SP roles** → already solved in `deploy/SMOKE_RESULTS.md`; reuse the grant recipe for new SPs.
- **Scope is large** → the ladder is incremental; L1/L2 already shipped, so even partial completion (through L3) answers the exec. L4 is the bold finish.

## 8. Exec one-liner

"Our agents don't just answer — they **act**: recommend, stage for approval, execute into your real systems, and at the top of the ladder run autonomously within policy guardrails — every step governed by Unity Catalog, every action audited and lineage-traced on one plane. That's the sentence Foundry can't finish."
