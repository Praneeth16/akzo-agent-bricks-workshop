# AkzoNobel Agent Bricks Workshop — Materials Index

Entry point for everything built for the 2-day workshop. Strategy/agenda live in `AKZONOBEL_WORKSHOP_PLAN.md`, `WORKSHOP_AGENDA.md`, `AKZONOBEL_DEMO_PLAN.md`, `VIBE_CODING_SESSION.md`. Build spec: `BUILD_PLAN.md`. Everything below is built, loaded, and verified live on workspace `fevm-serverless-lakebase-praneeth` (CLI profile `fe-vm-lakebase-praneeth`).

## Where everything lives on the workspace
- **Catalog:** `serverless_lakebase_praneeth_catalog` (no CREATE CATALOG perm → schemas prefixed `akzo_`).
- **Schemas:** `akzo_finance`, `akzo_scm`, `akzo_commercial`, `akzo_docs`, `akzo_ops`, `akzo_gateway`.
- **SQL warehouse:** `4d39ac2e32b72a3a`. **Lakebase:** instance `graphrag-spike`, db `databricks_postgres`, schema `akzo`.
- **Vector Search:** endpoint `akzo_workshop_vs`, index `serverless_lakebase_praneeth_catalog.akzo_docs.chunks_idx` (Qwen embeddings).
- **Models:** chat `databricks-claude-opus-4-7` / `databricks-gpt-5-5`; embed `databricks-qwen3-embedding-0-6b`.

## The cross-domain demo narrative (baked into the synthetic data, verified live)
- **Finance:** Paints EMEA (Decorative Paints × EMEA) gross margin **39.6% (Q1) → 30.7% (Q2 2026), −8.9pp** — price erosion + adverse FX + raw-material (TiO₂/resin) spike; volume flat.
- **SCM:** Rotterdam→EMEA-DACH OTIF **96% → 88.9% (May 2026)** — lead-time 5→9 days + DEC-1000/DEC-1004 stockout.
- **Commercial:** 3 at-risk EMEA accounts churn>0.7 — Rhine Valley Decor Distributors (0.865), Benelux PaintPro (0.827), Nordic Coatings Supply (0.80).
- **Docs:** 8 SDS + 6 supplier contracts; non-standard >€1M flagged = Tronox (Net 90, €4.25M) + Allnex (Net 120, €2.9M).

## 1. Synthetic data + docs — `data/`
Deterministic generators (`generate_finance.py`/`generate_scm.py`/`generate_commercial.py`/`generate_docs.py`) + `load_to_uc.py` (idempotent UC loader). Outputs in `data/output/`. 13 tables loaded across 3 domains + 14 PDFs in `/Volumes/.../akzo_docs/raw/`.

## 2. Genie space configs — `genie/`
`finance_space.md`, `scm_space.md`, `commercial_space.md` (tables, joins, certified metrics, instructions, NL→SQL example pairs incl. all golden questions) + facilitator `README.md`.

## 3. Eval golden questions — `eval/`
7 YAMLs (one per track): 5 golden questions + failing case + measurable-value claim each. Used by the MLflow judge and as the Day-2 default eval sets.

## 4. Day-1 reference notebooks — `notebooks/` (one per agenda layer)
`01_domain_agent_finance` · `02_per_user_truth_uc_obo` (RLS/OBO) · `03_scm_commercial_legs` · `04_supervisor_agent` · `05_lakebase_memory_action` · `06_mlflow_eval_judge` · `07_ai_gateway_govern` · **`08_doc_intelligence_qwen`** (ai_parse_document → ai_extract/ai_classify → auto-chunk → Qwen embed → Vector Search → RAG answer + structured/unstructured fusion). All run-verified live; See→Tweak→Return rhythm.

## 5. Day-2 forkable starters — `starters/`
7 self-contained tracks: `finance`, `scm`, `commercial`, `governance`, `supervisor`, `forecast`, `quote`. Each = slim `starter.py` (pre-wired governed call + Lakebase/approval + judge, with `# TODO (Day-2)` tweak markers) + `eval.yaml` + `README.md` (Sprint 1/2/3 tweak-swap-extend + ship target).

## 6. Art-of-possible apps (React + FastAPI, deployed + live)
| App | URL | What it shows |
|---|---|---|
| **akzo-supervisor** | https://akzo-supervisor-7474654904882204.aws.databricksapps.com | Cross-domain routing (Finance/SCM/Commercial) + fused answer + per-user (OBO) trace |
| **akzo-finance-copilot** | https://akzo-finance-copilot-7474654904882204.aws.databricksapps.com | Variance decomposition (price/volume/FX/cost bridge) + recommended action |
| **akzo-quote-agent** | https://akzo-quote-agent-7474654904882204.aws.databricksapps.com | read→reason→act→write→approve: parse RFQ → price → Lakebase quote → approval queue |
Source in `apps/<app>/` (shared backend modules `databricks_client.py` / `lakebase.py` / `text2sql.py`). Local run: `apps/<app>/run_local.sh`.

## 7. Deploy + smoke — `deploy/`
`deploy_apps.sh` (idempotent deploy: create → grant SP → sync → deploy) + `SMOKE_RESULTS.md` (per-app status, SP grants, live round-trip results, bugs fixed). All 3 apps ACTIVE/SUCCEEDED; full read→reason→act→write→approve loops verified live under each app's service principal.

## 8. Agents that ACT — the Action Maturity Ladder (exec angle)
Answers "can agents take action?" — see `AGENTS_THAT_ACT_PLAN.md` + `demo/agents_that_act.md`.
- **Ladder:** L1 Recommend → L2 Stage & approve → L3 Execute externally → L4 Autonomous, all on one governed plane (identity + policy guardrails + approval + audit/lineage + AI Gateway logs).
- **Shared Action Plane** (`apps/_shared/action_plane/`): canonical `akzo.actions` state machine (compare-and-set transitions), `guardrails` policy engine (`akzo.action_policies`), `executor` + `connectors/` (email/teams/crm/erp_po/sharepoint/ticket).
- **Governed external calls** via UC HTTP connection `akzo_external_systems` → **`akzo-mock-systems`** app (safe mock; receipts in `akzo.external_system_log`).
- **`akzo-action-center`** app — cross-agent action queue, LadderMeter, GuardrailChips, audit Timeline, approve/execute. The exec's single screen.
- The 3 domain apps gained an **Actions panel** (Act→Approve→Execute→Confirm).
- Notebooks `09_agents_that_act` (L1→L4) + `10_autonomous_closed_loop` (detect→act→verify→escalate, idempotent) + Job `akzo-autonomous-scm` (paused). Hackathon track `starters/action/`.
- **Guards (verified live):** separation of duties (proposer ≠ approver, identity from `X-Forwarded-Email` not request body), guardrail re-check before any external call (over-cap → escalate), and per-`breach_key` idempotency (no duplicate POs on schedule re-runs).
- **5 apps live:** akzo-supervisor · akzo-finance-copilot · akzo-quote-agent · **akzo-action-center** · **akzo-mock-systems**. Deploy/smoke: `deploy/ACTION_SMOKE_RESULTS.md`.

## 9. Hackathon-in-the-Box — the unified hub (AppKit, light theme)
One app that combines everything above into a single pane and runs the event end to end. Built on **Databricks AppKit** (TypeScript + `@databricks/appkit-ui` Shadcn/Radix/Tailwind) — the app dogfoods the stack. Plan: `HACKATHON_IN_A_BOX_PLAN.md`; project + run/deploy notes: `apps/hackathon-hub/` (`README.md`).
- **Pages:** Overview (run-the-event hero + agenda), Challenges (8 tracks + 10-notebook learning path), How-to-run, **Register / Teams / Submit / Judge / Leaderboard** (live Lakebase `hack_*` state; rubric = Expert Choice + People's Choice vote; separation of duties enforced), **Try it live** (live AppKit `analytics` over `akzo_*` — margin/OTIF/churn — plus deep links to the 5 agent apps), Resources, Materials, Organizer (deployed-apps gallery).
- **Backend:** AppKit `server` + `analytics` plugins; `hack_*` schema in Lakebase `graphrag-spike`/`akzo` via `pg` + OAuth db credential; `/api/hack/*` CRUD + judging.
- **LIVE + verified:** https://akzo-hackathon-hub-7474654904882204.aws.databricksapps.com (deploy SUCCEEDED / compute ACTIVE). Live-smoked: root 200, full Register→Judge→Leaderboard loop on Lakebase (separation-of-duties 403), and `akzo_*` analytics (margin_trend 24 rows) — all under the app SP. Deploy notes + the npm-proxy/SP-rotation gotchas in `apps/hackathon-hub/README.md`.

## Upgrade paths (documented in-notebook/app)
- LLM-text2SQL → native **Genie spaces** (swap a `space_id`); in-code router → native **Agent Bricks Multi-Agent Supervisor** (ref `mas-f14da7dc-endpoint`).
- App writes use Lakebase Postgres roles + app/service identity + approval/audit (NOT OBO; UC-registered Lakebase is read-only) — honest write-governance story.
