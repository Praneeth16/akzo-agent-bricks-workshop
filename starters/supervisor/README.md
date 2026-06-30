# Starter — Supervisor Agent (flagship, track #3)

Route a cross-domain question across **Finance / SCM / Commercial** Genie spaces under OBO, fuse one
governed answer, show the routing trace, and log the session to Lakebase. This is the *composition* of
the focus-5 — its legs are the Finance, SCM, and Commercial tracks.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: LLM router -> domain legs (text2SQL) -> fuser, + Lakebase session/feedback write, + a judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case (copy of `eval/supervisor.yaml`). |
| `README.md` | This file. |

Pre-wired: a working governed call (the router+legs+fuser over UC tables), the Lakebase write pattern
(`agent_sessions` / `agent_feedback`), MLflow-style judge, sample-data refs, 5 golden questions.

## Measurable value

Cross-domain "why" investigation that normally pulls 3 analysts (finance, supply, sales) into a war
room → **one supervisor query fusing all three domains with a routing trace in 5–10 min.**

## Verified primary query (this workspace)

The flagship question routes to **Finance + SCM**. Finance: Paints EMEA gross margin **39.6% (Q1) →
30.7% (Q2)**. SCM: Rotterdam-NL→EMEA-DACH lane **OTIF 94.5% (Apr) → 88.9% (May, stockout) → 93.0%
(Jun)**. The fuse concludes the problem is *both* a margin/cost issue *and* a supply/service issue.

## 5 golden questions

1. Paints EMEA gross margin dropped ~8% in Q2 2026 — is it price, volume, or a supply/service issue, and what should I do?
2. Connect the dots: is the EMEA churn risk related to the margin and service problems we are seeing?
3. Give me one EMEA Paints situation report covering financial impact, supply status, and customer risk.
4. What is the single biggest root cause behind the Paints EMEA problems this quarter?
5. Which domains did you consult to answer the EMEA margin question, and what did each contribute?

(Full text + expected facts + failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — tweak, swap, extend

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — TWEAK (the router).** `# TODO (Day-2) SPRINT 1` on `ROUTING_DESCRIPTION`. Edit the
  per-subagent description lines to your domains/persona; narrow one and widen another, re-run BEAT 1,
  and watch which legs get called change. Routing is configuration, not code.
- **Sprint 2 — SWAP/ACT (Lakebase).** `# TODO (Day-2) SPRINT 2` near the `agent_sessions` write. Move
  from only logging a session to staging a governed **action** (a `pending` row in `scm_interventions`
  or `commercial_actions`) and approving it — see `starters/forecast` for the full write+approve loop.
- **Sprint 3 — EXTEND (eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add your own cross-domain
  golden question to `eval.yaml` and re-run the judge cell.

## Ship target

A working notebook + a live routing trace + a Lakebase `agent_sessions` row. Deployable React+FastAPI
version: **`apps/supervisor/`** (clone, don't author). Upgrade path: register the three Akzo Genie
spaces as subagents of an Agent Bricks Multi-Agent Supervisor — the per-subagent description field IS
`ROUTING_DESCRIPTION`. Reference MAS endpoint in this workspace: `<your-mas-endpoint>`.
