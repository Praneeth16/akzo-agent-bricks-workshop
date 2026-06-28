# Databricks notebook source
# MAGIC %md
# MAGIC # L4 — Autonomous Closed-Loop: detect → act → verify → escalate
# MAGIC
# MAGIC *The bold finish to the "can your agents **act**?" question — and the honest one.*
# MAGIC
# MAGIC `09_agents_that_act.py` walked one action up the ladder L1→L3, but **L3 still required a human to
# MAGIC approve**. This notebook removes that step — *only when policy allows it*. A trigger fires, the
# MAGIC agent picks an intervention, and if it is **within the policy guardrails** it auto-approves and
# MAGIC executes with **no human in the approval loop**. The moment an action breaches policy, it
# MAGIC **escalates to a human gate** instead of acting. Same plane, same audit, same guardrails — the
# MAGIC approval gate just becomes *conditional on the policy verdict*.
# MAGIC
# MAGIC ### The L4 frame — autonomy you can sign off on
# MAGIC An exec will not sign off on "the agent does whatever it wants". They *will* sign off on this:
# MAGIC
# MAGIC - **Autonomous only WITHIN policy.** Every candidate action is checked by `evaluate()` against
# MAGIC   `akzo.action_policies` (spend cap, region scope, action-type allowed) **before** anything runs.
# MAGIC   In-policy → auto-approve + execute. Out-of-policy → **escalate, never execute**.
# MAGIC - **Human-on-the-loop, not in-the-loop.** The human is not in the per-action approval path while
# MAGIC   the agent stays in-policy — but a guardrail breach pulls the action straight back to a human
# MAGIC   gate (`escalated`). The human watches the audit trail and owns the breaches.
# MAGIC - **It only ever calls the mock systems.** Every external effect goes through the same governed
# MAGIC   connectors as L3 (`erp_po`, `teams`, `ticket`) → the Mock External Systems app via the UC HTTP
# MAGIC   connection `akzo_external_systems`. No real PO is raised, no real email sent. The *path* is
# MAGIC   production-shaped; the *targets* are mocked for the workshop.
# MAGIC - **Fully audited.** Every transition (proposed → approved → executing → executed | escalated)
# MAGIC   appends an `akzo.action_events` row; external effects land a receipt in
# MAGIC   `akzo.external_system_log`. The whole autonomous run is reconstructable from those two tables.
# MAGIC
# MAGIC ### The loop (this notebook, on the seeded Rotterdam OTIF breach)
# MAGIC ```
# MAGIC  DETECT  ── query akzo_scm.otif for lanes with OTIF < 90% in the latest month
# MAGIC    │         → Rotterdam-NL->EMEA-DACH, ~88.9% in May 2026 (+ DEC-1000/DEC-1004 stockout)
# MAGIC  DECIDE  ── an LLM (databricks-claude-opus-4-7) proposes an intervention given the breach
# MAGIC    │         + the stockout → an scm_reorder to replenish safety stock (amount_eur)
# MAGIC  GUARD   ── ap.propose(level=4) → evaluate() against action_policies
# MAGIC    ├── PASS → auto-approve (actor='autonomous-loop') → execute() → ERP PO raised (mock) + external_ref
# MAGIC    └── BREACH (e.g. amount > €100k cap) → escalate() to a human gate → NO execution
# MAGIC  VERIFY  ── re-read the executed action + external_ref + external_system_log receipt
# MAGIC              → a real loop would re-measure OTIF next cycle to confirm the effect
# MAGIC ```
# MAGIC
# MAGIC We show **both paths**: one in-policy reorder that auto-executes, and one deliberately over-cap
# MAGIC reorder that escalates. Then a **tweak beat** flips one into the other.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — make the shared Action Plane module importable
# MAGIC
# MAGIC Same setup as `09_agents_that_act.py`: the state machine, guardrail engine, and L3 executor live
# MAGIC in **`apps/_shared/action_plane/`** — the *same* Python module the apps import. A notebook reuses
# MAGIC it by putting `apps/_shared` on `sys.path`; nothing is reimplemented here. We also import
# MAGIC `databricks_client` from that folder for the SCM warehouse query (`run_sql`) and the decision LLM
# MAGIC (`chat`), and `lakebase` for the external-receipt read.
# MAGIC
# MAGIC **In the workspace:** sync `apps/_shared` to Workspace files, then:
# MAGIC ```python
# MAGIC import sys
# MAGIC sys.path.append('/Workspace/Users/praneeth.paikray@databricks.com/akzo-apps/_shared')
# MAGIC ```
# MAGIC **Running locally** (verifying against live Lakebase + warehouse, outside Databricks):
# MAGIC ```bash
# MAGIC export DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth
# MAGIC pip install 'psycopg[binary]' 'databricks-sdk>=0.96'
# MAGIC ```
# MAGIC ```python
# MAGIC import sys; sys.path.insert(0, 'apps/_shared')   # repo-relative
# MAGIC ```

# COMMAND ----------

import sys

# In-workspace path (sync apps/_shared here first). Adjust the user folder to yours.
WORKSPACE_SHARED = "/Workspace/Users/praneeth.paikray@databricks.com/akzo-apps/_shared"
# Repo-relative path (local runs / Databricks Git folders).
LOCAL_SHARED = "apps/_shared"

for _p in (WORKSPACE_SHARED, LOCAL_SHARED):
    if _p not in sys.path:
        sys.path.append(_p)

import json

import databricks_client
import lakebase
from action_plane import ActionPlane, evaluate, execute, ROUTING

ap = ActionPlane()

# Catalog/schema for the SCM source data (read via the serverless warehouse).
SCM = "serverless_lakebase_praneeth_catalog.akzo_scm"
LLM_ENDPOINT = "databricks-claude-opus-4-7"
LOOP_ACTOR = "autonomous-loop"           # the service identity acting in the loop
OTIF_THRESHOLD = 90.0                    # the trigger: lane OTIF below this fires the loop

print("Action Plane ready. scm_* action routes:")
for action_type in ("scm_reorder", "scm_reroute"):
    print(f"  {action_type:14s} → {', '.join(ROUTING[action_type])}")
print(f"\nTrigger: lane OTIF < {OTIF_THRESHOLD}% in the latest breached month. SCM source: {SCM}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## DETECT — find the breached lane in the latest month that has a breach
# MAGIC
# MAGIC The loop's trigger is data, not a human. We compute the certified volume-weighted OTIF per lane
# MAGIC per month (`SUM(perfect)/SUM(orders)`, never the average of `otif_pct`) and pick the **most recent
# MAGIC month that still contains an unresolved breach** (a lane below the threshold). That is exactly what
# MAGIC an unattended loop should act on — the latest open problem, not necessarily the calendar-latest
# MAGIC month (a month with no breach is nothing to do). On the seeded data this surfaces
# MAGIC **`Rotterdam-NL->EMEA-DACH` at ~88.9% in May 2026** — the embedded narrative (June recovered to
# MAGIC ~93%, so it is not flagged).

# COMMAND ----------

DETECT_SQL = f"""
WITH lane_month AS (
  SELECT lane, MAX(region) AS region, month,
         ROUND(SUM(ROUND(otif_pct * orders)) / SUM(orders) * 100, 1) AS otif_pct,
         SUM(orders) AS orders
  FROM {SCM}.otif
  GROUP BY lane, month
),
breaches AS (SELECT * FROM lane_month WHERE otif_pct < {OTIF_THRESHOLD}),
latest_breach AS (SELECT MAX(month) AS m FROM breaches)
SELECT b.lane, b.region, b.month, b.otif_pct, b.orders
FROM breaches b, latest_breach
WHERE b.month = latest_breach.m
ORDER BY b.otif_pct ASC
"""

detect = databricks_client.run_sql(DETECT_SQL)
breached = detect["rows"]
print(f"DETECT — lanes below {OTIF_THRESHOLD}% OTIF in the latest breached month: {len(breached)}")
for r in breached:
    print(f"  ⚠️  {r['lane']:28s} {r['region']:10s} {r['month']}  OTIF={r['otif_pct']}%  orders={r['orders']}")

assert breached, "expected the seeded Rotterdam OTIF breach — is akzo_scm.otif populated?"
TARGET = breached[0]                       # the worst lane = Rotterdam-NL->EMEA-DACH
print(f"\nTarget lane → {TARGET['lane']}  ({TARGET['otif_pct']}% OTIF, {TARGET['month']})")

# COMMAND ----------

# MAGIC %md
# MAGIC **Why did it break?** A service dip is only actionable if we know the cause. We join the breach
# MAGIC to `akzo_scm.inventory` for the **same month at the origin plant** to find the stocked-out SKUs —
# MAGIC this is the evidence the decision LLM reasons over. On the seeded data, **DEC-1000 and DEC-1004**
# MAGIC stock out at Rotterdam in May with days-of-supply ~1.

# COMMAND ----------

ORIGIN_PLANT = TARGET["lane"].split("->")[0]    # "Rotterdam-NL"
# Breach identity — what makes the loop idempotent across scheduled runs.
#   PROD_BREACH_KEY (lane|month) is the production key: stable per breach, so the
#   hourly job acts once and every later run de-dupes against it.
#   For this *teaching* notebook we suffix a per-run id so it can be re-run without a
#   manual reset; the idempotency LOGIC (PATH C below) is identical either way.
import uuid
PROD_BREACH_KEY = f"{TARGET['lane']}|{TARGET['month']}"
BREACH_KEY = f"{PROD_BREACH_KEY}|demo-{uuid.uuid4().hex[:8]}"

def _sql_lit(value) -> str:
    """Escape a value for safe embedding as a single-quoted SQL literal (these values
    come from our own data, but never interpolate unescaped)."""
    return str(value).replace("'", "''")

STOCKOUT_SQL = f"""
SELECT sku, on_hand_units, safety_stock, ROUND(days_of_supply, 1) AS days_of_supply
FROM {SCM}.inventory
WHERE plant = '{_sql_lit(ORIGIN_PLANT)}' AND month = DATE'{_sql_lit(TARGET['month'])}'
  AND stockout_flag = 1
ORDER BY days_of_supply ASC
"""

stockouts = databricks_client.run_sql(STOCKOUT_SQL)["rows"]
print(f"DETECT — stockouts at {ORIGIN_PLANT} in {TARGET['month']}: {len(stockouts)}")
for r in stockouts:
    print(f"  📦 {r['sku']:10s} on_hand={r['on_hand_units']:>6}  safety={r['safety_stock']:>6}  "
          f"days_of_supply={r['days_of_supply']}")

STOCKOUT_SKUS = [r["sku"] for r in stockouts]

# COMMAND ----------

# MAGIC %md
# MAGIC ## DECIDE — an LLM proposes the intervention
# MAGIC
# MAGIC The agent does not hard-code the fix. We hand the breach + the stockout evidence to
# MAGIC **`databricks-claude-opus-4-7`** and ask it to choose a governed intervention. We constrain it to
# MAGIC the action types the plane actually routes (`scm_reorder`, `scm_reroute`) and ask for a strict
# MAGIC JSON payload — including `amount_eur`, the field the spend-cap guardrail checks. The LLM's job is
# MAGIC to turn evidence into a *structured, policy-shaped proposal*; the guardrails decide whether it may
# MAGIC run.

# COMMAND ----------

def decide_intervention(target: dict, stockout_skus: list[str], stockout_rows: list[dict]) -> dict:
    """Ask the decision LLM for a governed SCM intervention. Returns a parsed payload dict
    {action_type, subject, why, amount_eur, payload:{...}}. Falls back to a deterministic
    reorder if the model output cannot be parsed (the loop must never stall on the LLM)."""
    evidence = {
        "lane": target["lane"], "region": target["region"],
        "month": str(target["month"]), "otif_pct": float(target["otif_pct"]),
        "otif_threshold": OTIF_THRESHOLD,
        "origin_plant": target["lane"].split("->")[0],
        "stockouts": [
            {"sku": r["sku"], "on_hand_units": r["on_hand_units"],
             "safety_stock": r["safety_stock"], "days_of_supply": r["days_of_supply"]}
            for r in stockout_rows
        ],
    }
    system = (
        "You are AkzoNobel's autonomous supply-chain agent. Given an OTIF breach and the "
        "stocked-out SKUs behind it, choose ONE governed intervention to restore service. "
        "You may ONLY use these action types: "
        "'scm_reorder' (raise a replenishment PO for the stocked-out SKUs) or "
        "'scm_reroute' (switch the lane to a faster mode). Prefer 'scm_reorder' when there are "
        "stockouts. Reply with STRICT JSON only, no prose, of the form: "
        '{"action_type": "scm_reorder", "subject": "<short>", "why": "<one sentence>", '
        '"supplier": "<supplier>", "skus": ["DEC-1000"], "qty": 4000, "amount_eur": 92000.0}. '
        "Size amount_eur sensibly for the qty (roughly EUR 20-25 per unit of decorative paint)."
    )
    user = "OTIF breach + stockout evidence:\n" + json.dumps(evidence, indent=2)
    raw = databricks_client.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        endpoint=LLM_ENDPOINT, max_tokens=600,
    )
    decision = _parse_decision(raw, stockout_skus)
    decision["_llm_raw"] = raw
    return decision


def _parse_decision(raw: str, stockout_skus: list[str]) -> dict:
    """Extract the JSON object the model returned; fall back to a safe in-policy reorder."""
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    parsed: dict = {}
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
        except (ValueError, TypeError):
            parsed = {}

    action_type = parsed.get("action_type")
    if action_type not in ("scm_reorder", "scm_reroute"):
        action_type = "scm_reorder"   # deterministic fallback — loop never stalls on the LLM

    skus = parsed.get("skus") or stockout_skus or ["DEC-1000"]
    qty = int(parsed.get("qty") or 4000)
    amount_eur = float(parsed.get("amount_eur") or (qty * 23.0))
    supplier = parsed.get("supplier") or "TiO2 Supplier NL"
    subject = parsed.get("subject") or f"Autonomous {action_type} — {', '.join(skus)}"
    why = parsed.get("why") or "Restore OTIF on the breached lane by replenishing safety stock."
    return {
        "action_type": action_type, "subject": subject, "why": why,
        "amount_eur": amount_eur,
        "payload": {
            "supplier": supplier, "skus": skus, "sku": skus[0],
            "qty": qty, "amount_eur": amount_eur,
            "reason": why, "lane": TARGET["lane"],
        },
    }


decision = decide_intervention(TARGET, STOCKOUT_SKUS, stockouts)
print("DECIDE — LLM-chosen intervention:")
print(f"  action_type : {decision['action_type']}")
print(f"  subject     : {decision['subject']}")
print(f"  why         : {decision['why']}")
print(f"  amount_eur  : €{decision['amount_eur']:,.0f}")
print(f"  payload     : {json.dumps(decision['payload'])}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The autonomous step — one function, the whole guardrail gate
# MAGIC
# MAGIC This is the heart of L4. Given a candidate intervention it: `propose()`s at **level=4**, runs
# MAGIC `evaluate()`, and branches:
# MAGIC - **PASS** → `approve()` *autonomously* (actor `autonomous-loop`, no human) → `execute()` →
# MAGIC   the connector route fires (ERP PO + Teams alert through the mock) → returns the executed action.
# MAGIC - **BREACH** → `escalate()` to a human gate with the breach reasons → **never executes**.
# MAGIC
# MAGIC The same `evaluate()`/`execute()` the human-gated L3 used — the only difference is *who* approves.

# COMMAND ----------

def _already_handled(breach_key: str) -> dict | None:
    """Idempotency guard: has this breach (lane|month) already been acted on by a
    prior run? Returns the existing action row if one is in-flight or executed, so a
    re-fired scheduled run does NOT raise a second PO for the same breach. Only a
    `rejected`/`failed` prior attempt is considered un-handled (safe to retry)."""
    rows = lakebase.query(
        "SELECT id, status FROM actions "
        "WHERE payload->>'breach_key' = %s "
        "AND status IN ('proposed','approved','executing','executed','escalated') "
        "ORDER BY id DESC LIMIT 1",
        (breach_key,),
    )
    return rows[0] if rows else None


def autonomous_step(decision: dict, region: str) -> dict:
    """Run one candidate intervention through the guardrail-gated autonomous loop.

    Returns {"action_id", "path": "auto_executed"|"escalated"|"skipped_duplicate", ...}.
    Idempotent per `payload.breach_key`: a breach already handled by a prior run is
    skipped (no duplicate external side effect) — the anti-spam guard for the schedule.
    """
    breach_key = decision["payload"].get("breach_key")
    if breach_key:
        existing = _already_handled(breach_key)
        if existing:
            print(f"\n  ⏭️  breach '{breach_key}' already handled by action "
                  f"id={existing['id']} (status={existing['status']}) — skipping, no duplicate PO.")
            return {"action_id": existing["id"], "path": "skipped_duplicate",
                    "verdict": None, "action": ap.get(existing["id"])}

    proposed = ap.propose(
        agent=LOOP_ACTOR,
        action_type=decision["action_type"],
        subject=decision["subject"],
        payload=decision["payload"],
        region=region,
        requested_by=LOOP_ACTOR,
        level=4,                       # L4 — autonomous closed-loop
    )
    action_id = proposed["id"]

    verdict = evaluate(proposed)
    print(f"\n  action id={action_id} [{decision['action_type']}]  "
          f"€{decision['payload'].get('amount_eur'):,.0f}  → guardrails passed={verdict['passed']}")
    for chk in verdict["checks"]:
        if chk["applicable"]:
            mark = "✅" if chk["passed"] else "❌"
            print(f"      {mark} {chk['rule']:20s} {chk['detail']}")

    if verdict["passed"]:
        # IN POLICY → autonomous approve (no human) then execute through the connectors.
        ap.approve(action_id, approver=LOOP_ACTOR)
        executed = execute(action_id, ap=ap)
        print(f"      → AUTO-EXECUTED status={executed['status']!r} "
              f"external_ref={executed.get('external_ref')!r} (no human in the loop)")
        return {"action_id": action_id, "path": "auto_executed",
                "verdict": verdict, "action": executed}

    # OUT OF POLICY → escalate to a human gate; do NOT execute.
    reason = "; ".join(verdict["breaches"]) or "guardrail breach"
    escalated = ap.escalate(action_id, reason=reason, actor=LOOP_ACTOR)
    print(f"      → ESCALATED to human gate (reason: {reason}). NO external system called.")
    return {"action_id": action_id, "path": "escalated",
            "verdict": verdict, "action": escalated}

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATH A — the in-policy reorder that auto-executes
# MAGIC
# MAGIC The LLM's intervention sizes the spend below the **€100k `scm_reorder` cap** for an EMEA lane, so
# MAGIC every guardrail passes and the loop auto-approves and executes with **no human approval**. The
# MAGIC `scm_reorder` route is `erp_po` → a purchase order is raised on the mock ERP and a receipt lands
# MAGIC in `akzo.external_system_log`. (We clamp the LLM's amount just under the cap so the demo's PATH A
# MAGIC is reliably in-policy regardless of how the model sized it.)

# COMMAND ----------

# Ensure PATH A is in-policy for a reliable demo: cap the autonomous reorder at €92k (< €100k).
inpolicy = json.loads(json.dumps(decision))   # deep copy
if inpolicy["payload"]["amount_eur"] >= 100000.0:
    inpolicy["payload"]["amount_eur"] = 92000.0
inpolicy["action_type"] = "scm_reorder"
inpolicy["subject"] = f"Autonomous safety-stock reorder — {', '.join(STOCKOUT_SKUS or ['DEC-1000'])} (Rotterdam)"
inpolicy["payload"]["amount_eur"] = min(inpolicy["payload"]["amount_eur"], 92000.0)
inpolicy["payload"]["breach_key"] = BREACH_KEY     # idempotency: one reorder per breach

print("PATH A — in-policy autonomous reorder")
result_a = autonomous_step(inpolicy, region=TARGET["region"])

assert result_a["path"] == "auto_executed", "expected the in-policy reorder to auto-execute"
assert result_a["action"]["external_ref"], "expected a real external_ref from the ERP PO"
AUTO_ID = result_a["action_id"]
AUTO_REF = result_a["action"]["external_ref"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATH B — the over-cap reorder that escalates (no execution)
# MAGIC
# MAGIC Now the bound that lets an exec trust autonomy. Same lane, same intent — but the agent proposes a
# MAGIC **€205k** reorder, over the €100k `scm_reorder` cap. `evaluate()` returns a breach, so the loop
# MAGIC **escalates to a human gate and does NOT execute**. No PO is raised. The breach + reason are
# MAGIC recorded in `action_events` for the human who picks it up. This is the difference between
# MAGIC "autonomous" and "uncontrolled".

# COMMAND ----------

overcap = {
    "action_type": "scm_reorder",
    "subject": "Autonomous bulk reorder — Rotterdam safety stock (OVER CAP)",
    "why": "Large pre-buy to fully rebuild safety stock across the stocked-out SKUs.",
    "amount_eur": 205000.0,
    "payload": {
        "supplier": "TiO2 Supplier NL",
        "skus": STOCKOUT_SKUS or ["DEC-1000", "DEC-1004"],
        "sku": (STOCKOUT_SKUS or ["DEC-1000"])[0],
        "qty": 9000, "amount_eur": 205000.0,    # 205k > 100k cap → breach
        "reason": "bulk pre-buy", "lane": TARGET["lane"],
        # Distinct breach_key so this illustrative over-cap variant is not deduped
        # against PATH A (in production there is ONE intervention per breach).
        "breach_key": f"{BREACH_KEY}#illustrative-overcap",
    },
}

print("PATH B — over-cap autonomous reorder")
result_b = autonomous_step(overcap, region=TARGET["region"])

assert result_b["path"] == "escalated", "expected the over-cap reorder to escalate"
assert result_b["action"].get("external_ref") is None, "escalated action must NOT have executed"
ESCALATED_ID = result_b["action_id"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATH C — the schedule re-fires: idempotency (no duplicate PO)
# MAGIC
# MAGIC This is the guard an exec asks about: *"if it runs every hour, does it raise a new PO each time?"*
# MAGIC The job is scheduled, so the SAME May Rotterdam breach is still in the data next run. The loop is
# MAGIC **idempotent per `breach_key`** — re-running PATH A finds the already-executed action and **skips**
# MAGIC without proposing or calling any external system. The breach is acted on exactly once until it is
# MAGIC genuinely resolved (and a `rejected`/`failed` prior attempt is still retryable).

# COMMAND ----------

print("PATH C — re-fire the same breach (simulates the next scheduled run)")
result_c = autonomous_step(inpolicy, region=TARGET["region"])
assert result_c["path"] == "skipped_duplicate", "re-fire on a handled breach must be a no-op"
assert result_c["action_id"] == AUTO_ID, "skip should point at the original executed action"
print(f"  ✅ idempotent: re-run skipped, no new PO (still action id={AUTO_ID}, ref={AUTO_REF})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## VERIFY — the executed effect + the receipt
# MAGIC
# MAGIC The loop closes by confirming the effect. We re-read the auto-executed action and pull the
# MAGIC matching row from `akzo.external_system_log` — the mock-side receipt for the PO the loop raised,
# MAGIC attributed to the mock app's service principal. The same `external_ref` appears on both sides.
# MAGIC
# MAGIC > In a *real* loop, VERIFY would also re-measure OTIF on the next planning cycle to confirm the
# MAGIC > reorder actually lifted service back over the threshold — and only then mark the breach resolved.
# MAGIC > Here the source data is fixed, so we verify the *action's effect* (the PO + receipt) rather than
# MAGIC > a future OTIF reading; the re-measure step is where the loop would otherwise iterate.

# COMMAND ----------

def show_events(action_id: int) -> None:
    """Print the ordered action_events lineage for one action."""
    action = ap.get(action_id)
    print(f"action {action_id}  [{action['action_type']}]  status={action['status']}")
    for ev in action["events"]:
        ts = ev["ts"].strftime("%H:%M:%S") if hasattr(ev["ts"], "strftime") else ev["ts"]
        print(f"  {ts}  {ev['event']:14s} by {ev['actor']:20s} {ev['detail'] or ''}")


executed_action = ap.get(AUTO_ID)
print(f"VERIFY — auto-executed action {AUTO_ID}: status={executed_action['status']}, "
      f"external_ref={executed_action['external_ref']}")

connectors_fired = (executed_action.get("result") or {}).get("connectors", [])
print("\nConnectors fired (governed path each):")
for c in connectors_fired:
    print(f"  {c['system']:8s} ref={c['ref_id']:14s} via={c.get('via')}")

refs = [c["ref_id"] for c in connectors_fired] or [AUTO_REF]
receipts = lakebase.query(
    "SELECT id, ts, system, ref_id, created_by "
    "FROM external_system_log WHERE ref_id = ANY(%s) ORDER BY id",
    (refs,),
)
print("\nexternal_system_log receipts (the mock-side proof the PO was raised):")
for r in receipts:
    ts = r["ts"].strftime("%H:%M:%S") if hasattr(r["ts"], "strftime") else r["ts"]
    print(f"  {ts}  {r['system']:8s} ref={r['ref_id']:14s} created_by={r['created_by']}")

print("\n— Full lineage, PATH A (auto-executed) —")
show_events(AUTO_ID)
print("\n— Full lineage, PATH B (escalated, no execution) —")
show_events(ESCALATED_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## See → Tweak → Return
# MAGIC
# MAGIC ### TWEAK — flip auto-execute ↔ escalate
# MAGIC
# MAGIC The whole L4 lesson is that **policy, not code, decides whether the agent may act on its own**.
# MAGIC Two knobs flip a reorder between auto-execute and escalate:
# MAGIC 1. the **reorder amount** (`TWEAK_AMOUNT_EUR`) — the agent's proposal, or
# MAGIC 2. the **policy cap** (`akzo.action_policies.max_spend_eur` for `scm_reorder`).
# MAGIC
# MAGIC Below we change the amount and re-run `evaluate()` — exactly the check the loop gates on. Set it
# MAGIC under €100k → it would auto-execute; over → it would escalate. (To flip via the *policy* instead,
# MAGIC `UPDATE akzo.action_policies SET max_spend_eur = 250000 WHERE action_type='scm_reorder'` and the
# MAGIC same €205k reorder would auto-execute — the agent's behaviour changes with no code change.)

# COMMAND ----------

TWEAK_AMOUNT_EUR = 120000.0   # try 92000 (auto-executes) vs 120000 (escalates, > €100k cap)

tweaked = {
    "action_type": "scm_reorder",
    "region": TARGET["region"],
    "payload": {"supplier": "TiO2 Supplier NL", "sku": "DEC-1000",
                "qty": 5000, "amount_eur": TWEAK_AMOUNT_EUR},
}
tv = evaluate(tweaked)
decision_word = "AUTO-EXECUTE" if tv["passed"] else "ESCALATE"
print(f"amount_eur=€{TWEAK_AMOUNT_EUR:,.0f}  →  guardrails passed={tv['passed']}  →  loop would {decision_word}")
for chk in tv["checks"]:
    if chk["rule"] == "max_spend_eur":
        mark = "✅" if chk["passed"] else "❌"
        print(f"  {mark} {chk['detail']}")
if tv["breaches"]:
    print("  breaches:", tv["breaches"])

# COMMAND ----------

# MAGIC %md
# MAGIC ### RETURN — autonomy, bounded by policy, audited end to end
# MAGIC
# MAGIC **Verified live on this workspace** (`fe-vm-lakebase-praneeth`, warehouse `4d39ac2e32b72a3a`,
# MAGIC Lakebase schema `akzo`):
# MAGIC
# MAGIC - **DETECT** — queried `akzo_scm.otif` and found `Rotterdam-NL->EMEA-DACH` below the 90% OTIF
# MAGIC   threshold in the latest *breached* month (~88.9%, May 2026; June recovered to ~93% so is not
# MAGIC   flagged), with DEC-1000/DEC-1004 stocked out at Rotterdam.
# MAGIC - **DECIDE** — `databricks-claude-opus-4-7` proposed a governed `scm_reorder` to replenish the
# MAGIC   stocked-out SKUs, with a spend amount the guardrails check.
# MAGIC - **PATH A (auto-execute)** — in-policy reorder → auto-approved by `autonomous-loop` (no human) →
# MAGIC   `execute()` raised a PO on the mock ERP → real `external_ref` + a receipt in
# MAGIC   `akzo.external_system_log`.
# MAGIC - **PATH B (escalate)** — over-cap reorder (€205k > €100k) → `evaluate()` breach → `escalate()` to
# MAGIC   a human gate, **no external system called**, breach recorded in `action_events`.
# MAGIC - **VERIFY** — re-read the executed action + matched the receipt; a real loop would re-measure OTIF.
# MAGIC
# MAGIC Same governed plane as L1–L3 — identity, guardrails, approval, audit — with the approval gate made
# MAGIC *conditional on the policy verdict*. That is L4: **autonomous within policy, human-on-the-loop on
# MAGIC breach, only ever calling the mock systems.** Schedule it (next cell / `deploy/job_autonomous_scm.json`)
# MAGIC and the agent watches the lanes and acts on its own — within the bounds an exec signed off on.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scheduling — run the loop on a Databricks Job
# MAGIC
# MAGIC This notebook is the task body of the **`akzo-autonomous-scm`** job (`deploy/job_autonomous_scm.json`),
# MAGIC scheduled hourly on serverless compute. Each run re-detects breached lanes and acts within policy —
# MAGIC that is the "trigger → act → verify → escalate" cycle running unattended.
# MAGIC
# MAGIC Create / update the job from the repo root (CLI v0.2+):
# MAGIC ```bash
# MAGIC databricks jobs create --json @deploy/job_autonomous_scm.json -p fe-vm-lakebase-praneeth
# MAGIC ```
# MAGIC The job's `notebook_task.notebook_path` points at the synced workspace copy of this notebook; the
# MAGIC job runs as its owner/service principal (the write identity), and every action it takes is governed
# MAGIC by the same plane + audited in `akzo.action_events`.

# COMMAND ----------

# MAGIC %md
# MAGIC **Summary of this run** (the IDs an operator / the Action Center app would pick up):

# COMMAND ----------

print("AUTONOMOUS LOOP — run summary")
print(f"  detected breach : {TARGET['lane']}  OTIF={TARGET['otif_pct']}%  ({TARGET['month']})")
print(f"  stockout SKUs   : {', '.join(STOCKOUT_SKUS) or '(none)'}")
print(f"  PATH A (auto)   : action id={AUTO_ID}  external_ref={AUTO_REF}")
print(f"  PATH B (escald) : action id={ESCALATED_ID}  status=escalated (no execution)")
print("\nLADDER COUNTS (level × status) after this run:")
for row in ap.ladder_counts():
    print(f"  L{row['level']}  {row['status']:12s} {row['count']}")
