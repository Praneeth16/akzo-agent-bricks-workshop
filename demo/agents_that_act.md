# Agents That Act — Exec Demo Script + Slide Outline

> **Audience:** Head of AkzoNobel (+ exec staff). **The question:** *"Can your agents actually take action?"*
> **Run time:** 5 minutes live + 3-4 Q&A. **Presenter:** drives the deployed apps + replays CH3 (03_autonomous_loop).
> **Workspace:** your workspace (CLI profile `<your-profile>`), Lakebase `<your-lakebase-instance>` / schema `akzo`.
> Every claim below maps to a built, live-verified artifact (app, notebook, or table). App URLs are filled in at deploy time / live in the workspace.

---

## 1. The one-sentence answer

**Yes — our agents act. And every level of action is governed on one plane.**

We don't ship "agents that call APIs." We ship the **Action Maturity Ladder** — four rungs an exec can sign off on:

| Level | Name | What the agent does | Built artifact |
|---|---|---|---|
| **L1** | **Recommend** | Answers + proposes a next-best-action. Nothing written, nothing happens. | every agent (supervisor, finance-copilot, quote-agent) |
| **L2** | **Stage & approve** | Writes a *governed action record*, guardrails check it, a human approves. | `akzo.actions` + `akzo.action_events`; domain apps |
| **L3** | **Execute externally** | On approval, pushes the action into real systems (email / CRM / ERP-PO) via a governed UC HTTP connection. | Action Center + connectors |
| **L4** | **Autonomous closed-loop** | Trigger → pick an action within policy → execute → verify → escalate only on breach. | CH3 (03_autonomous_loop) + `akzo-autonomous-scm` job |

Every rung travels the **same governed plane**, and that is the whole point:

- **Identity** — the action records who/what proposed it and who approved it.
- **Policy guardrails** — `evaluate()` checks discount cap, spend cap, region scope, action-type allowed **before** anything executes.
- **Approval gate** — nothing executes until `approved` (a human at L1-L3; policy itself at L4 *only when in-policy*).
- **Audit / lineage** — every state transition appends an `action_events` row; external effects land a receipt in `external_system_log`. UC-native lineage end to end.
- **AI Gateway logs** — the recommendation LLM calls flow through the governed gateway; prompt/response payloads are logged.

**The honest line on OBO:** OBO governs the *reads* the agent did to form its recommendation. **Writes and executions are governed by app/service identity + policy + approval + audit — not OBO.** That is the truthful, defensible story.

---

## 2. The 5-minute live flow (presenter runbook)

> Have these tabs open before you start: **akzo-supervisor**, **akzo-finance-copilot**, **akzo-quote-agent**, **akzo-action-center**, **akzo-mock-systems**, and notebook **`03_autonomous_loop.py`** (already run, outputs visible). Same Paints EMEA story runs through all of it.

### Step 0 — Frame (15 sec)
> "You asked if agents can act. Let me walk you up a ladder — recommend, stage, execute into your systems, and run on their own — and show you that every rung is governed."

### Step 1 — L1 Recommend, then L2 Stage & approve (in a domain app) — ~90 sec
1. Open **akzo-finance-copilot**. Show the Paints EMEA Q2 variance: gross margin **39.6% → 30.7% (−8.9pp)** — price erosion + adverse FX + TiO₂/resin cost. The agent ends with a **recommended action** (price-recovery quote). *Say: "That's L1 — it reasoned, it recommends. Nothing has happened yet."*
2. Click **"Stage action"** on the recommendation. *Say: "Now it acts — but only into the governed plane."* The Actions panel writes an `actions` row in status `proposed`.
3. Point at the **guardrail chips** that render: discount ≤ 15% cap ✅, spend ≤ cap ✅, region EMEA in scope ✅, action-type allowed ✅. *Say: "Policy checked this before any human even looked."*
4. Click **Approve**. The record moves `proposed → approved`, stamps `approved_by`. *Say: "That's L2 — staged, guardrailed, human-approved, fully audited. Still nothing has left Databricks."*

### Step 2 — L3 Execute externally (in the Action Center) — ~90 sec
5. Switch to **akzo-action-center**. *Say: "This is the single screen for an exec — every agent's actions, governed, in one place."* The approved quote action is in the queue.
6. Open the action's **detail panel**. Show the **GuardrailChips** (live `evaluate()` verdict) re-checked as the final gate, then click **Execute**.
7. The action runs its connector route `email → crm` **through the UC HTTP connection `akzo_external_systems`**, drives `approved → executing → executed`, and returns an **`external_ref`**. *Say: "It just sent the revised quote and opened the CRM follow-up — through a Unity-Catalog-governed connection."*
   - **Real verified evidence:** `quote_send` fires `email` then `crm` → returns an `EMAIL-####` ref + a `CRM-####` ref, both via `uc_connection`.
8. Show the **Timeline** in the detail panel: `proposed → approved → executing → connector(email) → connector(crm) → executed`, with the external refs embedded. *Say: "That's the audit lineage — who did what, when, why, from one table."*
9. Flip to **akzo-mock-systems** (`/api/log` or its status page). Show the matching **receipt** row in `external_system_log` for the same `EMAIL-####` / `CRM-####` ref, attributed to the mock app's service principal. *Say: "And here's the proof on the receiving system — same ref, governed end to end."*

### Step 3 — L4 Autonomous closed-loop (replay 03_autonomous_loop) — ~90 sec
10. Open notebook **`03_autonomous_loop.py`** (already run). *Say: "At the top of the ladder, the agent acts on its own — but only within policy."*
11. **DETECT:** point at the output — the loop queried the `otif` table and found **`Rotterdam-NL->EMEA-DACH` at ~88.9% OTIF in May 2026** (below the 90% threshold), with **DEC-1000 / DEC-1004 stocked out**.
12. **PATH A (auto-execute):** an in-policy `scm_reorder` (≤ €100k cap) → **auto-approved by `autonomous-loop` (no human)** → `execute()` raised a **PO on the mock ERP** → real `external_ref` (`PO-####`) + a receipt in `external_system_log`. *Say: "In-policy, so it acted on its own — and logged everything."*
13. **PATH B (escalate):** the over-cap reorder (**€205k > €100k cap**) → `evaluate()` breach → **escalated to a human gate, NO external system called, no PO raised**. *Say: "This is the moment that lets you sign off on autonomy. The instant it would breach policy, it stops and hands it to a human. Human-on-the-loop, not in-the-loop."*

### Step 4 — Close on the ladder — ~30 sec
14. Back to **akzo-action-center**. Point at the **LadderMeter** — live counts across L1 → L2 → L3 → L4, including the L3 executions and L4 autonomous actions you just generated. *Say:* read the §8 one-liner.

---

## 3. Governance callouts (the honest story)

Say these out loud — they are the difference between "a demo" and "a thing your risk team will approve":

- **OBO governs reads, not writes.** The supervisor's *reads* to form a recommendation run on-behalf-of the user (UC row-level security applies — a controller and a planner see different data). **Writes and executions are governed by app/service identity + policy + approval + audit** — because UC-registered Lakebase is read-only on-behalf-of. We say this plainly; it is the defensible architecture, not a workaround.
- **Policy, not code, decides what executes.** The guardrail engine reads `akzo.action_policies` (discount cap, spend cap, region scope, action-type allowed). Change the policy row and the agent's behavior changes with **no code change** — e.g. raising the `scm_reorder` cap to €250k would let the same €205k reorder auto-execute.
- **External calls flow through a governed UC HTTP connection.** Every connector calls the mock systems **through `akzo_external_systems`** (created via `CREATE CONNECTION ... TYPE HTTP`), so the call path is catalog-governed and lineage-traced. Fallback (if the connection is unavailable): connectors call the deployed URL directly under the app service principal — still authenticated, still logged in `external_system_log` + the Action Plane.
- **UC-native lineage, end to end.** One action is reconstructable from `akzo.action_events` (every transition: who/what/when/why) joined to `akzo.external_system_log` (the receiving-system receipt with the same `external_ref`). Source data → recommendation → staged action → approval → execution → external effect, on one plane.
- **Targets are mocked for the workshop; the pattern is production-shaped.** No real email/PO/ticket is ever sent — every connector hits `akzo-mock-systems`, which lands an auditable receipt. Swapping the connection's base URL to a real ERP/CRM endpoint is the only change for production; the governance, audit, and guardrails are identical.

---

## 4. Honest Foundry contrast

**One governed plane over the lakehouse data AND the actions taken on it, with UC-native lineage.**

- **Don't say** "Foundry can't orchestrate" — it can stitch Logic Apps / Power Automate and call APIs. That is not the win, and claiming it invites a rebuttal.
- **Do compete on the plane.** With Azure AI Foundry, the *data* lives in Azure SQL / Fabric / AI Search, the *actions* run in Logic Apps, and the *audit* lives in Purview — separate planes you stitch and reconcile. With us, the governed data, the agent that reasons over it, the staged action, the policy guardrail, the approval, the execution, and the receipt all land on **one Unity Catalog–governed plane with one lineage graph.**
- **The crisp framing:** *governed data + governed action + lineage on one plane.* The exec can trace a single thread from "why did Paints EMEA margin drop" all the way to "what PO did the agent raise, under what policy, approved by whom" — without leaving the platform or joining three audit systems.

---

## 5. Slide outline (6-8 slides)

1. **Title — "Can your agents act? Yes — and every level is governed."**
   - The Action Maturity Ladder, four rungs, one plane.
   - Built on the AkzoNobel workshop kit; verified live.

2. **The Action Maturity Ladder**
   - L1 Recommend → L2 Stage & approve → L3 Execute externally → L4 Autonomous.
   - Every rung: identity + policy guardrails + approval gate + audit/lineage + AI Gateway logs.

3. **The governed Action Plane (architecture, one diagram)**
   - agent → propose Action → guardrail engine → approval gate → executor → UC HTTP connection → external systems → audit/lineage.
   - `akzo.actions` (state machine) · `akzo.action_events` (audit) · `akzo.action_policies` (guardrails) · `akzo.external_system_log` (receipts).

4. **L2 in a domain app — stage & approve**
   - Paints EMEA variance → "Stage action" → green guardrail chips → human approve.
   - Screenshot: finance-copilot Actions panel.

5. **L3 in the Action Center — execute into your systems**
   - `quote_send` → EMAIL ref + CRM ref via `akzo_external_systems` → Timeline audit → receipt in mock systems.
   - Screenshot: Action Center detail panel (GuardrailChips + Timeline + external_ref).

6. **L4 Autonomous — bounded by policy**
   - OTIF breach detected (Rotterdam ~88.9%, May) → in-policy reorder auto-executes (PO ref) → over-cap reorder **escalates**.
   - Human-on-the-loop, not in-the-loop. It only ever calls the mock systems.

7. **Governance — the honest story**
   - OBO governs reads; writes/executions governed by identity + policy + approval + audit.
   - External calls via governed UC HTTP connection. UC-native lineage end to end. Targets mocked; pattern production-shaped.

8. **The plane Foundry can't put on one slide (close)**
   - Governed data + governed action + lineage on one plane.
   - **One-liner:** *"Our agents don't just answer — they act: recommend, stage for approval, execute into your real systems, and at the top of the ladder run autonomously within policy guardrails — every step governed by Unity Catalog, every action audited and lineage-traced on one plane. That's the sentence Foundry can't finish."*

---

## 6. Talk track + Q&A

**Q: "Is it actually autonomous, or is a human always clicking?"**
> L1-L3 keep a human in the approval loop by design — staged, guardrailed, approved, then executed. L4 removes the human from the per-action approval path **only while the action stays within policy** — that's the autonomous closed-loop in CH3 (03_autonomous_loop): it detected the Rotterdam OTIF breach, sized an in-policy reorder, and raised the PO on its own. The moment an action would breach policy, it escalates to a human. So: autonomous within policy, human-on-the-loop on breach.

**Q: "What stops an agent from doing something dumb — a huge order, a crazy discount?"**
> The guardrail engine. Before anything executes, `evaluate()` checks the action against `akzo.action_policies`: discount cap, spend cap, region scope, allowed action types. You saw it live — the €205k reorder breached the €100k cap and **escalated instead of executing; no PO was raised.** And the cap is data, not code: you change the policy row, the behavior changes, with full audit of who changed it.

**Q: "Is this real, or is it mocked?"**
> The action plane, the guardrails, the approval flow, the audit lineage, and the UC HTTP connection are all real and verified live on this workspace. The **external targets** — email, CRM, ERP — are mocked for the workshop, so no real PO or email goes out. Swapping the connection's base URL to your real ERP/CRM is the only change for production; everything governing the action stays identical. The pattern is production-shaped on purpose.

**Q: "How is this different from what we'd build on Azure AI Foundry?"**
> Foundry can call APIs too — that's not the difference. The difference is the plane. On Foundry your data is in Azure SQL / Fabric / AI Search, your actions run in Logic Apps, your audit is in Purview — three planes you stitch and reconcile. Here the governed data, the agent, the staged action, the policy guardrail, the approval, the execution, and the receipt all sit on **one Unity Catalog plane with one lineage graph.** You can trace a single thread from "why did margin drop" to "what PO did the agent raise, under what policy, approved by whom." That's governed data + governed action + lineage, on one plane.

**Q (likely follow-up): "Who is the agent acting as when it writes?"**
> Reads run on-behalf-of the user, so Unity Catalog row-level security applies — a controller and a planner literally see different data. Writes and executions run as the app/service identity, governed by policy + approval + audit. We're explicit about that split because it's the architecture your risk team will actually sign off on.

---

## 7. Fallback (if a live call lags)

If an app is slow or a connector call hangs mid-demo, do not wait on the spinner — switch to pre-verified evidence:

1. **Pre-seeded actions in the Action Center.** The queue and LadderMeter are already populated from prior verified runs (L1-L4 counts). Open an already-`executed` action's detail panel to show GuardrailChips + Timeline + `external_ref` — same story, no live call needed.
2. **Notebook outputs.** Both `02_agents_that_act.py` and `03_autonomous_loop.py` are run-verified with outputs saved. Walk the L1→L4 cells in CH2, or the DETECT → PATH A (auto-execute, PO ref) → PATH B (escalate) → VERIFY cells in CH3. The printed `external_ref`s and `external_system_log` receipts are right there.
3. **Mock systems log.** `akzo-mock-systems` `/api/log` shows the receipt history (`EMAIL-####`, `CRM-####`, `PO-####`) independent of a fresh execute — proof the external effects landed.
4. **Screenshots.** Keep stills of: finance-copilot Stage-action + guardrail chips; Action Center detail (Timeline + external_ref); CH3 PATH A auto-execute and PATH B escalate; the LadderMeter. Drop straight to these if the network is hostile.

> **Golden rule:** the story is the ladder + governance, not the spinner. If anything lags, narrate the ladder over a screenshot and move on — the verified evidence carries it.
