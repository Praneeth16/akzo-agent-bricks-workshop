# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — Agents That Act (propose → guardrail → approve → execute externally → audit)
# MAGIC
# MAGIC *Hackathon **Action** track — the "can agents *act*?" build. Forkable Day-2 starter.*
# MAGIC
# MAGIC A **self-contained, forkable** distillation of the Action Maturity Ladder. One agent action travels the
# MAGIC whole governed plane:
# MAGIC
# MAGIC **propose** a governed action (Lakebase `akzo.actions`, status `proposed`) → **`evaluate`** it against the
# MAGIC policy guardrails (`akzo.action_policies`) → a human **approve**s → **`execute`** dispatches it to its
# MAGIC connector, which POSTs to the Mock External Systems app **through the Unity Catalog HTTP connection
# MAGIC `akzo_external_systems`** → the action reaches status **`executed`** with a real **`external_ref`** and a
# MAGIC receipt in `akzo.external_system_log`, full lineage in `akzo.action_events`.
# MAGIC
# MAGIC Then the other half of the story: the **breach → escalate** path. An over-cap action is proposed and even
# MAGIC approved, but `execute()` re-runs the guardrails as the final gate, sees the breach, and **escalates
# MAGIC instead of calling any external system** — nothing leaves Databricks.
# MAGIC
# MAGIC OBO governs *reads*; **writes/executions are governed by identity + policy + approval + audit** — the honest
# MAGIC governance story.
# MAGIC
# MAGIC **You already have a working action plane.** Day-2 is *tweak → swap → extend*. The four `# TODO (Day-2)`
# MAGIC markers are your sprint hooks:
# MAGIC 1. the **action_type + payload** to stage,
# MAGIC 2. the **guardrail policy** to tune,
# MAGIC 3. the **connector / external system** to target,
# MAGIC 4. an **autonomous (L4)** auto-approve-within-policy variant.
# MAGIC
# MAGIC **Ship target:** a working action that executes externally + is audited (`executed` + `external_ref` +
# MAGIC `external_system_log` receipt + `proposed→approved→executed` lineage), **OR** the deployed Action Center app
# MAGIC at `apps/action-center/` (clone, don't author).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — wire in the shared Action Plane
# MAGIC
# MAGIC The starter reuses the *one governed plane* every AkzoNobel agent acts through — the synced
# MAGIC `apps/_shared/action_plane` package (`ActionPlane`, `evaluate`, `execute`, `ROUTING`). In the workspace,
# MAGIC `apps/_shared` is synced next to your repo; add it to `sys.path` and import. Tables (`actions`,
# MAGIC `action_events`, `action_policies`) and the UC HTTP connection are already created by
# MAGIC `L200-capabilities/09a_action_plane_setup.py` + `09b_uc_http_connection.py`.

# COMMAND ----------

import os
import sys

# Add the synced shared package to the path. Locally, run with
#   DATABRICKS_CONFIG_PROFILE=<your-profile>  and the repo root as cwd.
for cand in ("apps/_shared", "../../apps/_shared", "/Workspace/Repos/_shared",
             os.path.join(os.path.dirname(os.path.abspath("__file__")), "..", "..", "apps", "_shared")):
    if os.path.isdir(cand) and cand not in sys.path:
        sys.path.insert(0, cand)

from action_plane import ActionPlane, ROUTING, evaluate, execute  # noqa: E402

ap = ActionPlane()
ME = os.environ.get("ACTION_ACTOR", "sales.manager.emea@akzo.example")
print("Action Plane ready. Routable action types →", {k: v for k, v in ROUTING.items()})

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — PROPOSE: stage a governed action (L2, status `proposed`)
# MAGIC
# MAGIC `# TODO (Day-2)` **SPRINT 1** lives here. `ap.propose(...)` writes the action to Lakebase `akzo.actions` in
# MAGIC status `proposed` and appends the first `action_events` row. Nothing has left Databricks yet. The action
# MAGIC type decides the connector route at execute time (see `ROUTING`).

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — SWAP THE ACTION TO STAGE: change the action_type + payload to the action your team
#   acts on. action_type must be routable (a key of ROUTING) and have a policy row. The payload fields your
#   connector + guardrail read (e.g. discount_pct, amount_eur, to, subject, body) live here. In-policy by design:
#   quote_send cap is 15% discount / €250k spend, region must be EMEA.
ACTION_TYPE = "quote_send"
PAYLOAD = {
    "to": "procurement@rotterdam-projects.example",
    "subject": "AkzoNobel quote — 5,000 u DEC-1008 Textured Exterior Coating",
    "body": ("Net unit price EUR 34.67 (10% volume discount), extended EUR 173,340 for 5,000 units, "
             "post-discount margin 34.2%, payment terms Net 30."),
    "discount_pct": 10.0,
    "amount_eur": 173340.0,
    "account_id": "ACC-EMEA-DEMO",
    "sku": "DEC-1008",
}

proposed = ap.propose(
    agent="quote-agent",
    action_type=ACTION_TYPE,
    subject="Send EMEA exterior-coating quote to Rotterdam Projects",
    payload=PAYLOAD,
    region="EMEA",
    requested_by=ME,
    level=3,                      # destined for L3 — execute externally
)
ACTION_ID = proposed["id"]
print(f"PROPOSED → action id={ACTION_ID}, status={proposed['status']!r}, type={proposed['action_type']!r}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — EVALUATE: the guardrail chips (policy, not code, decides what executes)
# MAGIC
# MAGIC `# TODO (Day-2)` **SPRINT 2** is the policy. `evaluate()` reads `akzo.action_policies` for this action type
# MAGIC and returns a verdict per rule (discount cap, spend cap, region scope, action-type allowed, approval
# MAGIC required). It runs *before* approval and again as the final gate before execute. Green = within policy.

# COMMAND ----------

# TODO (Day-2) SPRINT 2 — TUNE THE GUARDRAIL POLICY: the policy is a row in akzo.action_policies, not code. To
#   tighten/loosen a cap, run (locally via lakebase.execute, or in 09a):
#     UPDATE akzo.action_policies SET max_discount_pct = 12, max_spend_eur = 200000
#       WHERE action_type = 'quote_send';
#   then re-run this cell and watch the chips flip. THIS is the governance dial an exec trusts.
verdict = evaluate(proposed)
print(f"GUARDRAILS — passed={verdict['passed']}")
for chk in verdict["checks"]:
    mark = "PASS" if chk["passed"] else "FAIL"
    skip = "" if chk["applicable"] else "  (n/a)"
    print(f"  [{mark}] {chk['rule']:22s} {chk['detail']}{skip}")
if verdict["breaches"]:
    print("  breaches:", verdict["breaches"])

assert verdict["passed"], "expected the staged in-policy action to pass guardrails"

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — APPROVE: the human-in-the-loop gate
# MAGIC
# MAGIC Guardrails passed, so a human approves. `ap.approve` moves the action `proposed → approved`, stamps
# MAGIC `approved_by` + `decided_at`, and appends an `approved` event. The agent stages; it does **not**
# MAGIC self-approve at L3.

# COMMAND ----------

approved = ap.approve(ACTION_ID, approver=ME)
print(f"APPROVED → status={approved['status']!r}, approved_by={approved['approved_by']!r}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 4 — EXECUTE: push the approved action into the external system (L3)
# MAGIC
# MAGIC `# TODO (Day-2)` **SPRINT 3** is the connector. `execute(action_id)` takes the **approved** action, re-runs
# MAGIC the guardrails as a final gate, then dispatches it to its connector route. For `quote_send` that is
# MAGIC **`email → crm`**: it POSTs to the Mock External Systems app **through the UC HTTP connection
# MAGIC `akzo_external_systems`** — so the call is catalog-governed and lineage-traced — and drives
# MAGIC `approved → executing → executed`. The action comes back with the first connector's `external_ref`, and
# MAGIC every connector logs a receipt to `akzo.external_system_log`.

# COMMAND ----------

# TODO (Day-2) SPRINT 3 — TARGET A DIFFERENT CONNECTOR / EXTERNAL SYSTEM: the action_type → connector route is
#   ROUTING (executor.py). E.g. forecast_override → teams, scm_reorder → erp_po (raise a PO), scm_reroute →
#   teams,ticket. Pick the action_type in SPRINT 1 whose route hits the system you want to act on; add a new
#   connector under apps/_shared/action_plane/connectors/ + a ROUTING entry to reach a brand-new system.
print("Route for this action_type:", ROUTING.get(ACTION_TYPE))

executed = execute(ACTION_ID)
print(f"\nL3 EXECUTED → status={executed['status']!r}, external_ref={executed.get('external_ref')!r}")

connectors_fired = (executed.get("result") or {}).get("connectors", [])
print("\nConnectors fired (governed path each):")
for c in connectors_fired:
    print(f"  {c['system']:6s} ref={c['ref_id']:14s} via={c.get('via')}")

assert executed["status"] == "executed", "expected the in-policy action to reach status executed"
assert executed.get("external_ref"), "expected an external_ref on the executed action"

# COMMAND ----------

# MAGIC %md
# MAGIC ## SHOW — external_ref + the receipt + the full audit lineage
# MAGIC
# MAGIC The proof it actually acted: the executed action carries an `external_ref`; the mock system wrote a receipt
# MAGIC to `akzo.external_system_log`; and `akzo.action_events` holds the complete `proposed → approved → executing
# MAGIC → executed` lineage — the one table that answers "who did what, when, why".

# COMMAND ----------

import lakebase  # the shared write/read module the Action Plane runs on


def show_events(action_id: int) -> None:
    """Print the ordered action_events lineage for one action."""
    action = ap.get(action_id)
    print(f"action {action_id}  [{action['action_type']}]  status={action['status']}  "
          f"external_ref={action.get('external_ref')}")
    for ev in action["events"]:
        ts = ev["ts"].strftime("%H:%M:%S") if hasattr(ev["ts"], "strftime") else ev["ts"]
        print(f"  {ts}  {ev['event']:14s} by {ev['actor']:34s} {ev['detail'] or ''}")


print("AUDIT LINEAGE (akzo.action_events):")
show_events(ACTION_ID)

# The external_ref ties the governed action to the receipt the mock system logged.
receipts = lakebase.query(
    "SELECT id, system, ref_id, created_by, ts FROM external_system_log "
    "WHERE ref_id = %s ORDER BY ts",
    (executed.get("external_ref"),),
)
print("\nRECEIPT (akzo.external_system_log) for external_ref =", executed.get("external_ref"))
for r in receipts:
    print(" ", r)
assert receipts, "expected a receipt row in external_system_log for the external_ref"

# COMMAND ----------

# MAGIC %md
# MAGIC ## THE BREACH PATH — guardrail stops an over-cap action *before* it executes
# MAGIC
# MAGIC The exec's real question is "what stops it doing something dumb?" Here we stage an `scm_reorder` whose spend
# MAGIC (**€205k**) exceeds the **€100k cap** in `action_policies`. It is proposed and even approved — but
# MAGIC `execute()` re-runs the guardrails as the final gate, sees the breach, and **escalates** instead of calling
# MAGIC any external system. No PO is raised. The breach + reason are recorded in `action_events`.

# COMMAND ----------

breach = ap.propose(
    agent="scm-agent",
    action_type="scm_reorder",
    subject="Rotterdam safety-stock reorder — DEC-1008 (OVER CAP)",
    payload={"supplier": "TiO2 Supplier NL", "sku": "DEC-1008", "qty": 9000,
             "amount_eur": 205000.0},   # 205k > 100k cap → must NOT execute
    region="EMEA",
    requested_by=ME,
    level=3,
)
BREACH_ID = breach["id"]

bverdict = evaluate(breach)
print(f"BREACH action id={BREACH_ID} — guardrails passed={bverdict['passed']}")
for chk in bverdict["checks"]:
    if not chk["passed"]:
        print(f"  FAIL {chk['rule']}: {chk['detail']}")
print("  breaches:", bverdict["breaches"])

# Approve it anyway — the executor is the backstop that catches the breach at the gate.
ap.approve(BREACH_ID, approver=ME)
bexecuted = execute(BREACH_ID)
print(f"\nexecute() → status={bexecuted['status']!r}, external_ref={bexecuted.get('external_ref')!r}")
print("  → escalated to a human gate; NO external system was called (no PO raised).")

show_events(BREACH_ID)

assert bexecuted["status"] == "escalated", "over-cap action must escalate, not execute"
assert bexecuted.get("external_ref") is None, "escalated action must have no external_ref"

# COMMAND ----------

# MAGIC %md
# MAGIC ## L4 (autonomous) variant — auto-approve **within policy**, escalate on breach
# MAGIC
# MAGIC `# TODO (Day-2)` **SPRINT 4** lives here. L3 still required a human to approve. **L4** removes that step
# MAGIC *only when policy allows it*: the agent evaluates the action and, **if it passes guardrails**, auto-approves
# MAGIC and executes; **if it breaches**, it escalates to a human gate — never acting outside policy. Same plane,
# MAGIC same audit, same guardrails — the approval gate just becomes conditional on the policy verdict.

# COMMAND ----------

# TODO (Day-2) SPRINT 4 — BUILD/EXTEND THE AUTONOMOUS LOOP: wire this to a real trigger (e.g. OTIF < 90% on the
#   Rotterdam lane → pick an intervention) and a verify step (re-query the effect after execute). The full
#   detect → act → verify → escalate loop on the seeded OTIF breach is L200-capabilities/10_autonomous_closed_loop.py.
def act_autonomously(agent, action_type, subject, payload, region, requested_by, level=4):
    """L4: propose → evaluate → (auto-approve+execute if in-policy | escalate if breach). No human in the loop
    on the happy path; a guardrail breach is the only thing that pulls in a human."""
    action = ap.propose(agent=agent, action_type=action_type, subject=subject,
                        payload=payload, region=region, requested_by=requested_by, level=level)
    aid = action["id"]
    v = evaluate(action)
    if not v["passed"]:
        ap.escalate(aid, reason="; ".join(v["breaches"]) or "guardrail breach", actor="autonomous-agent")
        return ap.get(aid), "escalated (breach → human gate)"
    # In policy → the policy IS the approval. Auto-approve, then execute (which re-checks guardrails).
    ap.approve(aid, approver="autonomous-agent:policy")
    return execute(aid), "auto-executed within policy"


# In-policy autonomous reorder (€80k < €100k cap) → auto-approves + executes, no human.
auto_ok, why = act_autonomously(
    agent="scm-agent", action_type="scm_reorder",
    subject="Autonomous Rotterdam reorder — within €100k cap",
    payload={"supplier": "TiO2 Supplier NL", "sku": "DEC-1008", "qty": 3000, "amount_eur": 80000.0},
    region="EMEA", requested_by="autonomous-agent")
print(f"L4 in-policy  → id={auto_ok['id']} status={auto_ok['status']!r} "
      f"external_ref={auto_ok.get('external_ref')!r} — {why}")

# Out-of-policy autonomous reorder (€205k > cap) → escalates, never acts.
auto_breach, why = act_autonomously(
    agent="scm-agent", action_type="scm_reorder",
    subject="Autonomous Rotterdam reorder — OVER €100k cap",
    payload={"supplier": "TiO2 Supplier NL", "sku": "DEC-1008", "qty": 9000, "amount_eur": 205000.0},
    region="EMEA", requested_by="autonomous-agent")
print(f"L4 over-cap   → id={auto_breach['id']} status={auto_breach['status']!r} — {why}")

assert auto_ok["status"] == "executed", "in-policy autonomous action should auto-execute"
assert auto_breach["status"] == "escalated", "over-cap autonomous action must escalate, not execute"

print("\nLADDER COUNTS (level × status):")
for row in ap.ladder_counts():
    print(f"  L{row['level']}  {row['status']:12s} {row['count']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Eval judge over the 5 golden "did it actually act?" questions
# MAGIC
# MAGIC The same portable `ai_query` judge as the other tracks. The agent answers each golden question from the
# MAGIC live action evidence above (the executed action, its external_ref, the receipt, the lineage, the escalated
# MAGIC breach). Extend `eval.yaml` to add your own "did it act?" cases.

# COMMAND ----------

import re

import yaml

from databricks_client import chat

JUDGE_ENDPOINT = os.environ.get("JUDGE_ENDPOINT", "databricks-claude-opus-4-8")


def _find_eval():
    for c in ["./eval.yaml", "starters/action/eval.yaml", "../../eval/action.yaml", "eval/action.yaml"]:
        if os.path.exists(c):
            return c
    return None


_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else {"golden_questions": []}
QUESTIONS = GOLDEN.get("golden_questions", [])
print("Loaded", len(QUESTIONS), "golden questions from", _p)

# Live evidence the agent answers from — pulled from the actual run above.
ok_action = ap.get(ACTION_ID)
brk_action = ap.get(BREACH_ID)
ACTION_CONTEXT = (
    f"IN_POLICY_ACTION: id={ok_action['id']} type={ok_action['action_type']} status={ok_action['status']} "
    f"external_ref={ok_action.get('external_ref')} "
    f"events={[e['event'] for e in ok_action['events']]} "
    f"connectors_fired={[c['system'] for c in connectors_fired]} "
    f"receipt_in_external_system_log={'yes' if receipts else 'no'} (ref {ok_action.get('external_ref')}). "
    f"BREACH_ACTION: id={brk_action['id']} type={brk_action['action_type']} status={brk_action['status']} "
    f"external_ref={brk_action.get('external_ref')} reason=spend 205000 exceeds 100000 cap "
    f"events={[e['event'] for e in brk_action['events']]} (NO external system called). "
    f"GOVERNANCE: every external call flows through the UC HTTP connection akzo_external_systems; reads via OBO; "
    f"writes/executions via identity+policy+approval+audit; full lineage in akzo.action_events."
)


def action_answer(question: str) -> str:
    return chat([{"role": "user", "content": (
        "You are an AkzoNobel agent that ACTS through a governed action plane. Using ONLY this governed "
        f"evidence (do not invent refs or statuses):\n{ACTION_CONTEXT}\n\nAnswer concisely.\n\n"
        f"QUESTION: {question}\n\nANSWER:")}], endpoint=JUDGE_ENDPOINT, max_tokens=400)


def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = (
        "You are a strict evaluation judge for an action agent. Score the ANSWER against the EXPECTED FACTS.\n"
        f"QUESTION: {question}\nEXPECTED FACTS (small wording/number rounding is fine):\n{expected_str}\n"
        f"GRADING NOTES: {notes}\nANSWER UNDER TEST:\n{answer}\n"
        'Return ONLY JSON: {"correctness": <0..1>, "groundedness": <0..1>, "pass": <true|false>, '
        '"rationale": "<one sentence>"}\npass=true only if correctness>=0.6 AND groundedness>=0.6.')
    raw = chat([{"role": "user", "content": prompt}], endpoint=JUDGE_ENDPOINT, max_tokens=300).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0) if m else raw)
    except Exception:
        v = {"correctness": 0.0, "groundedness": 0.0, "pass": False, "rationale": "unparseable: " + raw[:150]}
    v["correctness"] = float(v.get("correctness", 0.0))
    v["groundedness"] = float(v.get("groundedness", 0.0))
    v["pass"] = bool(v.get("pass", False))
    return v


import json  # noqa: E402  (used by judge above)

n_pass = 0
for q in QUESTIONS:
    v = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""),
              action_answer(q["question"]))
    n_pass += int(v["pass"])
    print(f"[{q['id']}] pass={v['pass']} corr={v['correctness']:.2f} grnd={v['groundedness']:.2f} — {v['rationale']}")
print(f"\nPASS RATE: {n_pass}/{len(QUESTIONS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole + ship
# MAGIC
# MAGIC The agent **proposed** a governed action → **evaluated** it against policy guardrails → a human
# MAGIC **approved** → **executed** it into an external system through the UC HTTP connection →
# MAGIC `external_ref` + receipt + full `proposed→approved→executed` lineage. The breach path **escalated** instead
# MAGIC of acting. The L4 variant **auto-approved within policy** and **escalated on breach**.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** swap the `action_type` + `payload` for the action your team acts on.
# MAGIC - **Sprint 2 (swap):** tune the guardrail policy row in `akzo.action_policies` and watch the chips flip.
# MAGIC - **Sprint 3 (extend):** target a different connector / external system (or add a new one to `ROUTING`).
# MAGIC - **Sprint 4 (autonomous):** wire the L4 loop to a real trigger + verify step.
# MAGIC
# MAGIC **Deployable app:** the full React+FastAPI **Action Center** (cross-agent action queue, approve/execute,
# MAGIC per-action lineage + external effect, the maturity-ladder viz) lives at **`apps/action-center/`** — clone
# MAGIC and deploy it, don't author it. This notebook is its logic spine.
