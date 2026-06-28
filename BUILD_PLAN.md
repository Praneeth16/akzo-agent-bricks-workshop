# BUILD_PLAN — AkzoNobel Agent Bricks Workshop Materials

**Created:** 2026-06-25
**Target workspace:** Databricks CLI profile `fe-vm-lakebase-praneeth` (`fevm-serverless-lakebase-praneeth.cloud.databricks.com`) — serverless + Lakebase + Apps verified working.
**Origin docs (this repo):** `AKZONOBEL_WORKSHOP_PLAN.md`, `AKZONOBEL_DEMO_PLAN.md`, `WORKSHOP_AGENDA.md`, `VIBE_CODING_SESSION.md`.
**Execution mode:** autonomous `/loop` — build → deploy → test on the live workspace.

---

## 1. Locked decisions

1. **3 full React+FastAPI "art-of-possible" Databricks Apps:** Supervisor (route Finance/SCM/Commercial under OBO), Finance controlling copilot (variance decomposition + recommended action), Pricing/Quote agent (read→reason→act→write→approve with Lakebase write-back + approval).
2. **Real workspace deploy + test** via profile `fe-vm-lakebase-praneeth`.
3. **Rich coatings-realistic synthetic data:** Finance margin/cost/FX by SKU×region×month; SCM OTIF/inventory/lanes; Commercial accounts/pipeline/churn; SDS + supplier-contract PDFs.
4. **Doc-intelligence showcase:** `ai_parse_document` → `ai_extract`/`ai_classify` → auto-chunking → embed with **Qwen embedding** → Vector Search → semantic search + answer generation.

---

## 2. Naming conventions (single source of truth)

- **Catalog:** `serverless_lakebase_praneeth_catalog` (no CREATE CATALOG perm on metastore → use owned managed catalog with `akzo_` schema prefix).
- **Schemas:** `akzo_finance`, `akzo_scm`, `akzo_commercial`, `akzo_docs`, `akzo_ops` (Lakebase mirror / eval / traces), `akzo_gateway` (preseeded gateway logs).
- **Volumes:** `serverless_lakebase_praneeth_catalog.akzo_docs.raw` (uploaded PDFs), `serverless_lakebase_praneeth_catalog.akzo_docs.parsed`.
- **Vector Search:** endpoint `akzo_workshop_vs`, index `serverless_lakebase_praneeth_catalog.akzo_docs.chunks_idx`.
- **Lakebase:** Postgres database instance `akzo-workshop-lakebase` (reuse existing if present), DB `akzo`, schemas mirror UC; write-back tables `quotes`, `quote_approvals`, `forecast_overrides`, `scm_interventions`, `commercial_actions`, `agent_sessions`, `agent_feedback`.
- **Genie spaces:** `Akzo Finance`, `Akzo SCM`, `Akzo Commercial`.
- **Embedding model:** Qwen embedding served via Model Serving endpoint `akzo-qwen-embed` (fallback: `databricks-gte-large-en` if Qwen unavailable in workspace — record which was used).
- **Repo layout:**
  ```
  data/        generators + UC loader
  genie/       per-domain Genie space instructions + sample SQL
  eval/        golden questions per track (yaml)
  notebooks/   7 day-1 layer notebooks + doc-intel notebook
  starters/    7 day-2 forkable starters
  apps/        supervisor/  finance-copilot/  quote-agent/ (react+fastapi)
  deploy/      databricks.yml bundle, app.yaml per app, setup scripts
  ```

---

## 3. Data model (table list + key columns)

### finance
- `products` — sku, product_name, product_line (Decorative/Performance Coatings), region, currency, list_price_eur, standard_cost_eur.
- `margin_actuals` — sku, region, month, units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct.
- `margin_budget` — sku, region, month, budget_units, budget_revenue_eur, budget_margin_eur.
- `fx_rates` — currency, month, rate_to_eur.
- `cost_drivers` — sku, region, month, raw_material_cost, freight_cost, energy_cost, overhead.
- `metric_views`: `finance.mv_gross_margin` (certified), variance components (price/volume/FX/cost).

### scm
- `otif` — plant, region, lane, sku, month, orders, on_time, in_full, otif_pct.
- `inventory` — plant, sku, month, on_hand_units, safety_stock, days_of_supply, stockout_flag.
- `lanes` — lane_id, origin_plant, dest_region, mode, lead_time_days, cost_per_unit.
- `service_levels` — region, month, service_pct, backorder_units.

### commercial
- `accounts` — account_id, account_name, region, segment, industry, owner_rep.
- `pipeline` — opp_id, account_id, stage, amount_eur, close_month, product_line.
- `sales_actuals` — account_id, month, revenue_eur, volume_units, margin_eur.
- `churn_signals` — account_id, month, churn_score, last_order_days, complaint_count, nps.

### docs (volumes + extracted tables)
- Volume `raw`: ~8 SDS PDFs (coatings products), ~6 supplier-contract PDFs.
- `sds_extracted` — doc_id, product, hazard_class, flash_point_c, voc_g_per_l, storage_temp, ppe.
- `contracts_extracted` — doc_id, supplier, category, annual_spend_eur, payment_terms_days, price_escalation_clause, termination_notice_days, non_standard_flag.
- `chunks` — chunk_id, doc_id, doc_type, chunk_text, embedding (for VS index).

### ops (Lakebase-mirrored / eval / governance)
- `eval_runs`, `eval_results` (MLflow judge outputs).
- RLS personas table `personas` — user/email, role (controller/planner/rep), region scope.

---

## 4. Build order + dependencies (the loop sequence)

| Phase | Deliverable | Depends on | Subagent / skill |
|------|-------------|-----------|------------------|
| **A** | Synthetic data generators (Finance/SCM/Commercial) + SDS/contract PDFs | — | general-purpose subagents (parallel, 1 per domain + 1 docs) |
| **B** | Load to Unity Catalog on workspace; create catalog/schemas/volumes; metric views; RLS | A | databricks skills + Bash CLI |
| **C** | Genie space instructions + sample SQL (3 domains) | B | general-purpose subagent |
| **D** | Eval golden questions (per track) | C | general-purpose subagent |
| **E** | Doc-intelligence notebook (ai_parse→extract→chunk→Qwen embed→VS→answer) | B | databricks-agent skill + subagent |
| **F** | 7 Day-1 reference notebooks (one per agenda layer) | B,C,D | parallel subagents (databricks notebooks) |
| **G** | 7 Day-2 forkable starters | F | parallel subagents |
| **H** | 3 React+FastAPI apps (Supervisor, Finance, Quote) | B,C,E + Lakebase | parallel subagents (frontend+backend each) |
| **I** | Deploy + smoke-test on workspace (data, notebooks, apps, golden Qs, Lakebase write-back/approval) | E,F,G,H | databricks apps deploy + Bash |

Parallelizable: A (4-way), F (7-way batched), G (7-way batched), H (3-way). Use subagents per CLAUDE.md working style.

---

## 5. The 7 Day-1 reference notebooks (one per agenda layer)

1. `01_domain_agent_finance.py` — Genie over governed finance data; instruction/example-SQL/metric-view tweak beat.
2. `02_per_user_truth_uc_obo.py` — UC RLS/ABAC + OBO; controller vs planner whoami/RLS smoke test.
3. `03_scm_commercial_legs.py` — SCM + Commercial Genie spaces; same recipe across domains.
4. `04_supervisor_agent.py` — Multi-Agent Supervisor over the 3 Genie spaces; routing description tweak.
5. `05_lakebase_memory_action.py` — Lakebase write-back + approval; action definition tweak.
6. `06_mlflow_eval_judge.py` — MLflow tracing + LLM judge; golden-question eval; optional MemAlign teaser.
7. `07_ai_gateway_govern.py` — AI Gateway route/spend-cap/rate-limit; preseeded payload logs in UC.

Plus `08_doc_intelligence_qwen.py` — the ai_* + extraction + Qwen-embed + VS showcase (Phase E).

---

## 6. The 7 Day-2 forkable starters

Finance, SCM, Supervisor, Governance, Commercial (focus-5) + Forecast planner, Pricing/Quote (adjacent). Each ships: pre-wired Genie space ref, a working governed call, Lakebase + approval pattern, MLflow tracing + judge, sample data + 5 default golden questions, README with "tweak/swap/extend" steps. Forkable = self-contained folder under `starters/<track>/`.

---

## 7. The 3 React+FastAPI apps

Common stack: FastAPI backend (`databricks-sdk`, Genie Conversation API, Model Serving, Lakebase psycopg), React+Vite frontend, `app.yaml` for Databricks Apps, OBO via app auth. Each app: chat UI + trace/explain panel + data-source attribution.

- **supervisor/** — single chat, routes cross-domain question to Finance/SCM/Commercial Genie spaces, fuses answer, shows routing trace + per-user (OBO) data scope.
- **finance-copilot/** — variance decomposition (price/volume/FX/cost) + recommended action, cites metric views + policy docs (KA).
- **quote-agent/** — inbound request parse (ai_extract) → Genie pricing lookup → draft quote → Lakebase write → human approval queue (read→reason→act→write→approve).

---

## 8. Verification per deliverable

- **Data (B):** row counts > 0 per table; `SELECT` sanity on margin/OTIF/churn; metric view returns variance components; RLS returns different rows for controller vs planner persona.
- **Doc-intel (E):** ai_parse_document returns text for each PDF; ai_extract populates contracts_extracted with non-null payment_terms; VS index `READY`; semantic query returns relevant chunk; answer-gen cites chunk.
- **Notebooks (F):** each runs top-to-bottom on serverless without error; the "tweak + run one query" beat produces a visibly different answer.
- **Starters (G):** fork folder runs standalone; 5 golden Qs answered; Lakebase write lands a row.
- **Apps (H):** local `uvicorn` + `vite` run; deployed app URL returns 200; chat answers a golden Q; quote-agent write appears in Lakebase + approval queue; supervisor shows routing across ≥2 domains.
- **Workspace (I):** `databricks apps list` shows 3 new apps DeploymentStatus SUCCEEDED; golden-question smoke pass logged to `deploy/SMOKE_RESULTS.md`.

---

## 9. Risks / fallbacks

- **Qwen embedding** may not be pre-served → fall back to `databricks-gte-large-en`; record choice.
- **Supervisor Agent / OBO** = preview; if management SDK blocks, implement supervisor routing in FastAPI (LLM router calling 3 Genie spaces) and note OBO as enforced at Genie-call layer.
- **Genie Conversation API** throughput caps → apps cache + serialize calls.
- **Lakebase** write governance = Postgres roles + app identity + approval/audit (NOT OBO); UC-registered Lakebase is read-only. App writes via service identity.
- **AI Gateway** Beta, log lag ~1h → use preseeded logs for the "see" beat.
- No catalog-create permission → fall back to an existing managed catalog with an `akzo_workshop` schema prefix.

---

## 10. Outputs index (built into repo)

`data/`, `genie/`, `eval/`, `notebooks/`, `starters/`, `apps/`, `deploy/` — plus `deploy/SMOKE_RESULTS.md` recording the live-workspace test pass.
