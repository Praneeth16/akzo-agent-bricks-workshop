# Databricks notebook source
# MAGIC %md
# MAGIC # Agents That Act — the Action Maturity Ladder (L1 → L4)
# MAGIC
# MAGIC *The answer to the exec question: "can your agents actually **act**?"*
# MAGIC
# MAGIC The supervisor in `04_supervisor_agent.py` **answers** the flagship question — *"Paints EMEA
# MAGIC gross margin dropped ~8% in Q2 — price, volume, or supply, and what should I do?"* — and ends
# MAGIC with a recommended action. This notebook picks up exactly there and walks the **same Paints EMEA
# MAGIC story up four rungs of action maturity**, on one governed plane.
# MAGIC
# MAGIC | Level | Name | What the agent does | Status |
# MAGIC |---|---|---|---|
# MAGIC | **L1** | Recommend | Answers + proposes a next-best-action. No write. | reuse supervisor |
# MAGIC | **L2** | Stage & approve | Writes a governed action record, guardrails check it, a human approves. | this NB |
# MAGIC | **L3** | Execute externally | On approval, pushes the action into real systems (email/CRM/ERP) via a governed UC HTTP connection. | this NB |
# MAGIC | **L4** | Autonomous closed-loop | Trigger → pick action within policy → execute → verify → escalate only on breach. | preview → NB10 |
# MAGIC
# MAGIC ### The governance frame — every action, every rung
# MAGIC The point is not "agents can call APIs". The point is that **every action travels the same
# MAGIC governed plane**, so an exec can sign off on autonomy:
# MAGIC
# MAGIC - **Identity** — the action carries who/what proposed it (`agent`, `requested_by`) and who
# MAGIC   approved it (`approved_by`). Writes/executions are governed by **app/service identity +
# MAGIC   policy + approval + audit** — *not* OBO. (OBO governs the **reads** the supervisor did to
# MAGIC   form the recommendation.)
# MAGIC - **Guardrails** — `evaluate()` checks the proposed action against `akzo.action_policies`
# MAGIC   (discount cap, spend cap, region scope, action-type allowed) **before** anything executes.
# MAGIC - **Approval gate** — a human (or, at L4, policy) moves it `proposed → approved`. Nothing
# MAGIC   executes until it is `approved`.
# MAGIC - **Audit / lineage** — every transition appends an `akzo.action_events` row; the full who/
# MAGIC   what/when/why is reconstructable from one table. External effects land a receipt in
# MAGIC   `akzo.external_system_log`.
# MAGIC - **AI Gateway logs** — the recommendation LLM calls flow through the governed gateway
# MAGIC   (`07_ai_gateway_govern.py`); the prompt/response payloads are logged there.
# MAGIC
# MAGIC **3-beat rhythm (same as every workshop notebook):**
# MAGIC 1. **See** — walk one action up the ladder: recommend → stage → approve → execute externally.
# MAGIC 2. **Tweak** — change the action payload (a discount) and re-run guardrails; watch it flip
# MAGIC    pass → breach.
# MAGIC 3. **Return** — one governed plane, four rungs; the autonomous finish is NB10.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — make the shared Action Plane module importable
# MAGIC
# MAGIC The state machine, guardrail engine, and L3 executor live in **`apps/_shared/action_plane/`** —
# MAGIC the *same* Python module the Action Center app and the three domain apps import. A notebook reuses
# MAGIC it by putting that folder on `sys.path`; nothing is reimplemented here.
# MAGIC
# MAGIC **In the workspace:** sync `apps/_shared` to your Workspace files, then append it to the path:
# MAGIC
# MAGIC ```python
# MAGIC import sys
# MAGIC sys.path.append('/Workspace/Users/praneeth.paikray@databricks.com/akzo-apps/_shared')
# MAGIC ```
# MAGIC
# MAGIC (Sync once, e.g. `databricks sync apps/_shared /Workspace/Users/<you>/akzo-apps/_shared`, or
# MAGIC clone the repo into Workspace files. The module imports `lakebase` and `databricks_client` from
# MAGIC that same folder, so the whole `_shared` dir must be on the path, not just `action_plane`.)
# MAGIC
# MAGIC **Running locally** (verifying the module against live Lakebase, outside Databricks):
# MAGIC
# MAGIC ```bash
# MAGIC export DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth
# MAGIC pip install 'psycopg[binary]' 'databricks-sdk>=0.96'
# MAGIC ```
# MAGIC ```python
# MAGIC import sys; sys.path.insert(0, 'apps/_shared')   # repo-relative
# MAGIC ```
# MAGIC Either way the module authenticates as the app/service write identity (the CLI profile locally,
# MAGIC the app service principal in Apps) and connects to Lakebase `graphrag-spike` / schema `akzo`.

# COMMAND ----------

import sys

# In-workspace path (sync apps/_shared here first). Adjust the user folder to yours.
WORKSPACE_SHARED = "/Workspace/Users/praneeth.paikray@databricks.com/akzo-apps/_shared"
# Repo-relative path (local runs / Databricks Git folders).
LOCAL_SHARED = "apps/_shared"

for _p in (WORKSPACE_SHARED, LOCAL_SHARED):
    if _p not in sys.path:
        sys.path.append(_p)

from action_plane import ActionPlane, evaluate, execute, ROUTING
import lakebase

ap = ActionPlane()
ME = "praneeth.paikray@databricks.com"

print("Action Plane ready. Action-type → connector routes:")
for action_type, route in ROUTING.items():
    print(f"  {action_type:18s} → {', '.join(route)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## L1 — Recommend: the supervisor proposes a next-best-action (no write)
# MAGIC
# MAGIC L1 is what we already have from `04_supervisor_agent.py`: the supervisor routes the flagship
# MAGIC question to Finance + SCM, fuses one answer, and ends with **a concrete recommendation**. That
# MAGIC recommendation is *just text* — nothing has been written, nothing has happened. This is the floor
# MAGIC of the ladder, and where every agent in the kit already sits.
# MAGIC
# MAGIC For this notebook we restate the supervisor's verified conclusion for the Paints EMEA situation
# MAGIC (margin bridge ≈ 8.9pp from price/FX/TiO2 cost **and** the Rotterdam OTIF dip to ~89% in May), and
# MAGIC turn it into a **structured recommended action** the rest of the ladder will act on. In a live run
# MAGIC you would call `supervise(FLAGSHIP)` from NB04 and parse its `answer`; here we make the
# MAGIC recommendation explicit so the ladder is self-contained.

# COMMAND ----------

# The supervisor's recommendation, made structural (this is the L1 output — a proposal, not an action).
RECOMMENDATION = {
    "situation": (
        "Paints EMEA Q2 gross margin down ~8.9pp: price/FX/TiO2-cost squeeze (Finance) "
        "AND Rotterdam->DACH OTIF dipped to ~89% in May (SCM)."
    ),
    "recommended_actions": [
        {
            "action_type": "quote_send",
            "subject": "Paints EMEA price-recovery quote — DACH architectural account",
            "why": "Recover margin on the largest at-risk EMEA account with an in-policy revised quote.",
            "payload": {
                "to": "procurement@dach-account.example",
                "subject": "Revised AkzoNobel quote — Q3 pricing",
                "body": "Updated pricing reflecting TiO2 raw-material cost recovery; "
                        "8% volume discount retained to protect the relationship.",
                "discount_pct": 8.0,
                "amount_eur": 180000.0,
                "account_id": "ACC-DACH-014",
                "sku": "DEC-1008",
            },
            "region": "EMEA",
        },
        {
            "action_type": "scm_reorder",
            "subject": "Rotterdam safety-stock reorder — DEC-1008",
            "why": "Rebuild safety stock on the stocked-out lane so the OTIF dip does not recur.",
            "payload": {
                "supplier": "TiO2 Supplier NL", "sku": "DEC-1008",
                "qty": 4000, "amount_eur": 92000.0,
            },
            "region": "EMEA",
        },
    ],
}

print("L1 RECOMMENDATION (no write yet)")
print("  Situation:", RECOMMENDATION["situation"])
for r in RECOMMENDATION["recommended_actions"]:
    print(f"  → [{r['action_type']}] {r['subject']}")
    print(f"      why: {r['why']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## L2 — Stage & approve: write a governed action record, check guardrails, approve
# MAGIC
# MAGIC Now the agent **acts** for the first time — but only into the governed plane, not the outside
# MAGIC world. `ap.propose(...)` writes the recommended quote as an `actions` row in status `proposed`
# MAGIC and appends the first `action_events` row. Then `evaluate(...)` runs the guardrail policy as
# MAGIC chips you can read, and a human runs `ap.approve(...)`. Still nothing has left Databricks.

# COMMAND ----------

# Take the first recommended action (the in-policy quote) and STAGE it.
quote_rec = RECOMMENDATION["recommended_actions"][0]

proposed = ap.propose(
    agent="quote-agent",
    action_type=quote_rec["action_type"],
    subject=quote_rec["subject"],
    payload=quote_rec["payload"],
    region=quote_rec["region"],
    requested_by=ME,
    level=3,                      # this action is destined for L3 (execute externally)
)
ACTION_ID = proposed["id"]
print(f"L2 STAGED → action id={ACTION_ID}, status={proposed['status']!r}, "
      f"type={proposed['action_type']!r}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Guardrail chips.** `evaluate()` reads `akzo.action_policies` for this action type and returns a
# MAGIC verdict per rule (discount cap, spend cap, region scope, action-type allowed, approval required).
# MAGIC This runs *before* any approval and again as the final gate before execute. Green = within policy.

# COMMAND ----------

verdict = evaluate(proposed)
print(f"GUARDRAILS — passed={verdict['passed']}")
for chk in verdict["checks"]:
    mark = "✅" if chk["passed"] else "❌"
    skip = "" if chk["applicable"] else "  (n/a)"
    print(f"  {mark} {chk['rule']:22s} {chk['detail']}{skip}")
if verdict["breaches"]:
    print("  breaches:", verdict["breaches"])

assert verdict["passed"], "expected the in-policy quote to pass guardrails"

# COMMAND ----------

# MAGIC %md
# MAGIC **The approval gate.** Guardrails passed, so a human approves. `ap.approve` moves the action
# MAGIC `proposed → approved`, stamps `approved_by` + `decided_at`, and appends an `approved` event. This
# MAGIC is the human-in-the-loop control that lets an exec trust the rungs above.

# COMMAND ----------

approved = ap.approve(ACTION_ID, approver=ME)
print(f"APPROVED → status={approved['status']!r}, approved_by={approved['approved_by']!r}")

# COMMAND ----------

# MAGIC %md
# MAGIC **The audit trail so far.** Two transitions, two events — the lineage is already complete and
# MAGIC queryable. This is `akzo.action_events`, the one table that answers "who did what, when, why".

# COMMAND ----------

def show_events(action_id: int) -> None:
    """Print the ordered action_events lineage for one action."""
    action = ap.get(action_id)
    print(f"action {action_id}  [{action['action_type']}]  status={action['status']}")
    for ev in action["events"]:
        ts = ev["ts"].strftime("%H:%M:%S") if hasattr(ev["ts"], "strftime") else ev["ts"]
        print(f"  {ts}  {ev['event']:14s} by {ev['actor']:32s} {ev['detail'] or ''}")

show_events(ACTION_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## L3 — Execute externally: push the approved action into real systems
# MAGIC
# MAGIC This is the new rung. `execute(action_id)` takes the **approved** action, re-runs the guardrails
# MAGIC as a final gate, then dispatches it to its connector route. For `quote_send` that is
# MAGIC **`email → crm`**: it POSTs to the Mock External Systems app (`/email`, then `/crm/task`)
# MAGIC **through the Unity Catalog HTTP connection `akzo_external_systems`** — so the external call is
# MAGIC catalog-governed and lineage-traced — and drives `approved → executing → executed`.
# MAGIC
# MAGIC The action comes back with the first connector's `external_ref`, and every connector logs a
# MAGIC receipt to `akzo.external_system_log`. (The demo never sends real email/PO — the target is a
# MAGIC governed mock — but the *path* is production-shaped.)

# COMMAND ----------

executed = execute(ACTION_ID)
print(f"L3 EXECUTED → status={executed['status']!r}, external_ref={executed.get('external_ref')!r}")

connectors = (executed.get("result") or {}).get("connectors", [])
print("\nConnectors fired (governed path each):")
for c in connectors:
    print(f"  {c['system']:6s} ref={c['ref_id']:12s} via={c.get('via')}")

# COMMAND ----------

# MAGIC %md
# MAGIC **The external receipt.** Each connector landed a row in `akzo.external_system_log` on the mock
# MAGIC side, attributed to the mock app's service principal (`created_by`). This is the external-effect
# MAGIC proof — the same `ref_id`s that came back on the action above.

# COMMAND ----------

refs = [c["ref_id"] for c in connectors]
if refs:
    receipts = lakebase.query(
        "SELECT id, ts, system, ref_id, created_by "
        "FROM external_system_log WHERE ref_id = ANY(%s) ORDER BY id",
        (refs,),
    )
    print("external_system_log receipts for this action:")
    for r in receipts:
        ts = r["ts"].strftime("%H:%M:%S") if hasattr(r["ts"], "strftime") else r["ts"]
        print(f"  {ts}  {r['system']:6s} ref={r['ref_id']:12s} created_by={r['created_by']}")

# COMMAND ----------

# MAGIC %md
# MAGIC **The full lineage, end to end.** The same `action_events` table now shows the complete
# MAGIC journey — proposed → approved → executing → connector(email) → connector(crm) → executed — with
# MAGIC the external refs embedded. One action, fully auditable from a single table.

# COMMAND ----------

show_events(ACTION_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ### L3 — the breach case: a guardrail stops an over-cap action *before* it executes
# MAGIC
# MAGIC The happy path is only half the story. The exec's real question is "what stops it doing
# MAGIC something dumb?" Here we stage an `scm_reorder` whose spend (€205k) **exceeds the €100k cap** in
# MAGIC `action_policies`. It is proposed and even approved — but `execute()` re-runs the guardrails as
# MAGIC the final gate, sees the breach, and **escalates instead of calling any external system**. No PO
# MAGIC is raised. The breach + reason are recorded in `action_events`.

# COMMAND ----------

breach = ap.propose(
    agent="scm-agent",
    action_type="scm_reorder",
    subject="Rotterdam safety-stock reorder — DEC-1008 (OVER CAP)",
    payload={"supplier": "TiO2 Supplier NL", "sku": "DEC-1008",
             "qty": 9000, "amount_eur": 205000.0},   # 205k > 100k cap
    region="EMEA",
    requested_by=ME,
    level=3,
)
BREACH_ID = breach["id"]

bverdict = evaluate(breach)
print(f"BREACH action id={BREACH_ID} — guardrails passed={bverdict['passed']}")
for chk in bverdict["checks"]:
    if not chk["passed"]:
        print(f"  ❌ {chk['rule']}: {chk['detail']}")
print("  breaches:", bverdict["breaches"])

# Approve it anyway — the executor is the backstop that catches the breach at the gate.
ap.approve(BREACH_ID, approver=ME)
bexecuted = execute(BREACH_ID)
print(f"\nexecute() → status={bexecuted['status']!r}, external_ref={bexecuted.get('external_ref')!r}")
print("  → escalated to a human gate; NO external system was called (no PO raised).")

show_events(BREACH_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## L4 — Autonomous closed-loop (preview)
# MAGIC
# MAGIC L3 still required a human to approve. **L4** removes that step *only when policy allows it*: a
# MAGIC trigger fires (e.g. OTIF < 90% on the Rotterdam lane), the agent picks an intervention **within
# MAGIC `action_policies`**, auto-approves and executes if it is in-policy, verifies the effect, and
# MAGIC **escalates to a human only on a guardrail breach**. Same plane, same audit, same guardrails —
# MAGIC the approval gate just becomes conditional on the policy verdict you saw above.
# MAGIC
# MAGIC That is the bold finish, and it has its own notebook: **`notebooks/10_autonomous_closed_loop.py`**
# MAGIC (detect → act → verify → escalate, on the seeded Rotterdam OTIF breach).
# MAGIC
# MAGIC **The ladder, as counts.** `ap.ladder_counts()` groups every action by level + status — this is
# MAGIC the data behind the maturity-ladder viz in the Action Center app. You can see L3 executions and
# MAGIC escalations from this notebook, and the L4 autonomous actions from NB10.

# COMMAND ----------

print("LADDER COUNTS (level × status):")
for row in ap.ladder_counts():
    print(f"  L{row['level']}  {row['status']:12s} {row['count']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## See → Tweak → Return
# MAGIC
# MAGIC ### TWEAK — change the action payload and watch guardrails flip pass → breach
# MAGIC
# MAGIC The whole lesson of the governed plane is that **policy, not code, decides what executes**. Here
# MAGIC we take the *same* `quote_send` shape and only change the discount. At 8% it passes; push it past
# MAGIC the 15% cap and the very same `evaluate()` returns a breach — which is exactly what would stop it
# MAGIC at the L3 execute gate. Edit `TWEAK_DISCOUNT` and re-run.

# COMMAND ----------

TWEAK_DISCOUNT = 18.0   # try 8.0 (passes) vs 18.0 (breaches the 15% quote_send cap)

tweaked_action = {
    "action_type": "quote_send",
    "region": "EMEA",
    "payload": {**quote_rec["payload"], "discount_pct": TWEAK_DISCOUNT},
}
tv = evaluate(tweaked_action)
print(f"discount_pct={TWEAK_DISCOUNT}%  →  guardrails passed={tv['passed']}")
for chk in tv["checks"]:
    if chk["rule"] == "max_discount_pct":
        mark = "✅" if chk["passed"] else "❌"
        print(f"  {mark} {chk['detail']}")
if tv["breaches"]:
    print("  breaches:", tv["breaches"])
    print("  → at the L3 gate this would ESCALATE, not execute. Same plane, policy in control.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### RETURN — one governed plane, four rungs
# MAGIC
# MAGIC **Verified live on this workspace** (`fevm-serverless-lakebase-praneeth`, Lakebase
# MAGIC `graphrag-spike` / schema `akzo`):
# MAGIC
# MAGIC - **L1 Recommend** — the supervisor's Paints EMEA conclusion, made into a structured proposal.
# MAGIC - **L2 Stage & approve** — `propose` → `evaluate` (green chips) → `approve`, all in
# MAGIC   `akzo.actions` + `akzo.action_events`.
# MAGIC - **L3 Execute externally** — `execute` ran `email → crm` **through the UC HTTP connection
# MAGIC   `akzo_external_systems`**, returned an `external_ref`, and landed receipts in
# MAGIC   `akzo.external_system_log`. The over-cap `scm_reorder` **escalated** at the gate with no
# MAGIC   external call.
# MAGIC - **L4 Autonomous** — preview here; full loop in `notebooks/10_autonomous_closed_loop.py`.
# MAGIC
# MAGIC Every rung used the **same** identity + guardrails + approval + audit/lineage, with the
# MAGIC recommendation LLM calls governed by AI Gateway. That is the sentence the exec asked for: our
# MAGIC agents don't just answer — they **act**, governed end to end on one plane.
# MAGIC
# MAGIC **Next:** `10_autonomous_closed_loop.py` — the agent detects, acts, verifies, and escalates only
# MAGIC on a breach, with no human in the approval loop while it stays within policy.
