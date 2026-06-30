# Starter — AI governance & policy agent (track #4)

Demonstrate the two governance planes AkzoNobel cares about for a 2,000-user rollout: **per-user read truth**
(UC RLS/ABAC under OBO) and the **governed model front door** (AI Gateway routes / rate limits / spend caps /
UC-native payload logging). Unlike the domain tracks, the "act" here is *flipping a persona* and *changing a
gateway control* — not a Lakebase action write.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: `personas` + RLS visibility (controller vs planner vs rep) -> persona-flip "act" -> one live AI Gateway control change (+ restore) -> UC payload-log chargeback view -> a policy-explainer agent + `ai_query` judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case (a credential-surfacing request it must decline) + the measurable-value claim (copy of `eval/governance.yaml`). |
| `README.md` | This file. |

Pre-wired: the `akzo_ops.personas` ABAC table + `fn_region_rls` row filter, your AI Gateway
endpoint (set `DATABRICKS_GATEWAY_ENDPOINT`), the preseeded `akzo_gateway.payload_logs` audit table, a policy-explainer agent, an MLflow-style
judge, and 5 golden questions. **Day-2 = tweak, swap, extend** — not stand one up.

## Measurable value

> Access-governance assurance: proving per-user data scoping + auditability moves from a manual security
> review (days) to a live, in-product demonstration (controller vs planner returns different rows) in minutes.

## Verified primary query (this workspace)

The **same** `margin_actuals` query returns different rows per persona — **controller → 4 regions** (EMEA,
Americas, APAC, China); **planner / rep → 1 region (EMEA)**. Enforced by the persona scope under OBO, not by
the agent. Gateway audit view: cost/usage by user-group (Finance, SCM, Commercial, Procurement) is a plain
`SELECT` over `akzo_gateway.payload_logs`.

## 5 golden questions

1. Same question, run as a controller and as a planner — why do they get different rows?
2. A regional planner asks for global Paints margin across all regions — what happens?
3. Where can I see who asked what and what the model returned for audit?
4. How do we cap spend and prevent one team from exhausting the model endpoint?
5. Can the quote agent write a price directly to the production table on its own authority?

(Full text + expected facts + the credential-surfacing failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — make it your own / make it act + measurable / ship

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — make it your own (TWEAK the persona model).** `# TODO (Day-2) SPRINT 1` on the `personas`
  seed. Add a role/region scope (e.g. an `apac_planner`) or change a scope, then re-run the BEAT-1 visibility
  check and watch rows-per-persona change.
- **Sprint 2 — make it act + measurable (SWAP the gateway control).** `# TODO (Day-2) SPRINT 2` on
  `NEW_USER_LIMIT`. Change the per-user rate limit (or switch to a model-route shift / spend-cap), re-run, and
  read it back on the live endpoint. The cell restores the shared endpoint afterward.
- **Sprint 3 — ship (EXTEND the eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add a governance golden
  question to `eval.yaml` (e.g. "can a rep see another segment's accounts?", "where is PII redaction
  enforced?") and re-run the judge cell.

## Ship target

A working notebook + a live persona-toggle trace + the UC payload-log chargeback view. The governance layer
ships across the deployed apps' OBO + the gateway endpoint (clone, don't author).

**Honest scope:** OBO/RLS govern **reads**; **writes** are a separate plane (Postgres roles + app identity +
approval + audit); UC-registered Lakebase is **read-only**. Keeping the two planes distinct is the governance
story, not a limitation to hide.
