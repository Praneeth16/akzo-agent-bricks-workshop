# AkzoNobel Agent Bricks Workshop

A complete, runnable 2-day Databricks **Agent Bricks** workshop for AkzoNobel, plus a unified **Hackathon-in-the-Box** app that combines everything into one UI. Everything here runs live on a real Databricks workspace: Unity Catalog data, Genie/eval configs, 10 reference notebooks, 8 forkable starter tracks, 5 deployed React + FastAPI agent apps, and an AppKit light-theme hub.

> Note: the synthetic data is fictional coatings data. The planning documents and infrastructure identifiers (workspace, warehouse, service-principal IDs) are internal. Treat this repo accordingly.

## The flagship: Hackathon-in-the-Box

A single Databricks AppKit app (light theme) that surfaces the whole workshop and runs the event end to end (Register, Teams, Submit, Judge, Leaderboard) on live Lakebase state, with a "Try it live" tab that queries the real `akzo_*` tables.

- Live: https://akzo-hackathon-hub-7474654904882204.aws.databricksapps.com
- Source + run/deploy notes: [`apps/hackathon-hub/`](apps/hackathon-hub/)
- Built on Databricks AppKit (`@databricks/appkit` + `@databricks/appkit-ui`), so the app itself dogfoods the stack.

## The 5 deployed agent apps

| App | What it shows |
|---|---|
| **akzo-supervisor** | Cross-domain routing (Finance / SCM / Commercial) plus a fused answer and a per-user (OBO) trace |
| **akzo-finance-copilot** | Variance decomposition (price / volume / FX / cost bridge) plus a recommended action |
| **akzo-quote-agent** | read, reason, act, write, approve: parse an RFQ, price it, write a Lakebase quote, queue for approval |
| **akzo-action-center** | The exec single screen: cross-agent action queue, Action Maturity Ladder, guardrail verdicts, approve/execute |
| **akzo-mock-systems** | Governed external target (email / teams / crm / erp / sharepoint / ticket) that agents call; logs receipts |

Source under [`apps/`](apps/). Live URLs and smoke results in [`WORKSHOP_MATERIALS.md`](WORKSHOP_MATERIALS.md) and [`deploy/`](deploy/).

## Repository layout

```
notebooks/   10 Day-1 reference notebooks (one per agenda layer + doc intelligence + agents-that-act)
starters/    8 Day-2 forkable hackathon tracks (finance, scm, commercial, supervisor, governance, forecast, quote, action)
apps/        5 deployed agent apps + the hackathon-hub + shared backend modules (_shared)
data/        Deterministic synthetic-data generators + Unity Catalog loader
genie/       Genie space configs (finance, scm, commercial)
eval/        Golden-question eval sets (one YAML per track) for the MLflow judge
demo/        Demo talk tracks
deploy/      Deploy scripts + smoke results
```

### Key documents

- [`WORKSHOP_MATERIALS.md`](WORKSHOP_MATERIALS.md): master index of everything built, with live URLs and workspace facts.
- [`AKZONOBEL_WORKSHOP_PLAN.md`](AKZONOBEL_WORKSHOP_PLAN.md): strategy, scope, and the focus-5 use cases.
- [`WORKSHOP_AGENDA.md`](WORKSHOP_AGENDA.md): Day-1 and Day-2 run of show.
- [`AKZONOBEL_DEMO_PLAN.md`](AKZONOBEL_DEMO_PLAN.md): the numbered demo narratives.
- [`VIBE_CODING_SESSION.md`](VIBE_CODING_SESSION.md): Genie Code mechanics and the build loop.
- [`AGENTS_THAT_ACT_PLAN.md`](AGENTS_THAT_ACT_PLAN.md): the Action Maturity Ladder (L1 to L4), architecture, and guardrails.
- [`HACKATHON_IN_A_BOX_PLAN.md`](HACKATHON_IN_A_BOX_PLAN.md): the build plan for the unified hub.
- [`BUILD_PLAN.md`](BUILD_PLAN.md): the original workshop build spec.

## Day-1 reference notebooks ([`notebooks/`](notebooks/))

Pedagogy is fast.ai style: show the whole game first, then peel back one layer at a time.

1. `01_domain_agent_finance` - the domain agent: Finance over governed data (Genie + UC metric views + text2SQL)
2. `02_per_user_truth_uc_obo` - per-user truth: Unity Catalog RLS/ABAC + OBO
3. `03_scm_commercial_legs` - more domain legs: SCM + Commercial
4. `04_supervisor_agent` - the supervisor itself (routing across three Genie spaces)
5. `05_lakebase_memory_action` - memory + action with Lakebase write-back and approval
6. `06_mlflow_eval_judge` - trust: MLflow eval + an LLM judge
7. `07_ai_gateway_govern` - govern at scale: AI Gateway (spend caps, rate limits, payload logs)
8. `08_doc_intelligence_qwen` - document intelligence: ai_parse_document to ai_extract to auto-chunk to Qwen embed to Vector Search to RAG
9. `09_agents_that_act` - the Action Maturity Ladder (L1 to L4)
10. `10_autonomous_closed_loop` - detect, act, verify, escalate (idempotent)

## Day-2 starter tracks ([`starters/`](starters/))

Eight self-contained, forkable tracks: `finance`, `scm`, `commercial`, `supervisor`, `governance`, `forecast`, `quote`, `action`. Each ships a slim `starter.py` (pre-wired governed call + Lakebase/approval + judge with TODO tweak markers), an `eval.yaml`, and a `README.md` with a Sprint 1/2/3 plan.

## Synthetic data ([`data/`](data/))

Deterministic generators (`generate_finance.py`, `generate_scm.py`, `generate_commercial.py`, `generate_docs.py`) plus an idempotent Unity Catalog loader (`load_to_uc.py`). The data encodes one connected narrative:

- Finance: Paints EMEA gross margin 39.6% (Q1) to 30.7% (Q2 2026), down 8.9pp, from price erosion + adverse FX + raw-material spike.
- SCM: Rotterdam to EMEA-DACH OTIF 96% to 88.9% (May 2026), from lead-time drift + stockouts.
- Commercial: three at-risk EMEA accounts (churn score > 0.7).
- Docs: SDS + supplier contracts, with non-standard greater-than-1M-EUR terms flagged.

## Workspace facts

- Workspace: `fevm-serverless-lakebase-praneeth.cloud.databricks.com` (CLI profile `fe-vm-lakebase-praneeth`)
- Catalog: `serverless_lakebase_praneeth_catalog`; schemas `akzo_finance`, `akzo_scm`, `akzo_commercial`, `akzo_docs`, `akzo_ops`, `akzo_gateway`
- SQL warehouse: `4d39ac2e32b72a3a`
- Lakebase: instance `graphrag-spike`, db `databricks_postgres`, schema `akzo`
- Vector Search: endpoint `akzo_workshop_vs`, index `...akzo_docs.chunks_idx` (Qwen embeddings)
- Models: chat `databricks-claude-opus-4-7` / `databricks-gpt-5-5`; embed `databricks-qwen3-embedding-0-6b`

## Run the hub locally

```bash
cd apps/hackathon-hub/akzo-hackathon-hub
DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth npm run dev   # http://localhost:8000
```

## Deploy the hub

```bash
cd apps/hackathon-hub/akzo-hackathon-hub
databricks apps deploy --force -p fe-vm-lakebase-praneeth
```

### Deploy gotchas (learned the hard way, documented so you do not repeat them)

1. **npm tarball 404s in the Apps build container.** The build container fetches from `npm-proxy.cloud.databricks.com`, whose mirror 404s many tarballs (the pg tree, even `@opentelemetry/resources`), but it can reach public npm. A corporate dev machine is the opposite (public npm blocked, `~/.npmrc` forces the proxy), so a locally generated lockfile carries proxy URLs the container cannot fetch. Fix: generate `package-lock.json` via the proxy locally, then rewrite every `resolved` host `npm-proxy.cloud.databricks.com` to `registry.npmjs.org` (same path and integrity hash, so it validates). Do not add a project `.npmrc` pinning the proxy.
2. **Build-time typegen.** `prebuild` runs `appkit generate-types`, which describes queries against the warehouse; make it non-fatal (`npm run typegen || true`) since the committed `shared/appkit-types/*.d.ts` is enough.
3. **The app service principal rotates across redeploys.** Re-read `service_principal_client_id` from `databricks apps get` and re-grant UC SELECT + warehouse CAN_USE + Lakebase role + `akzo` DML before runtime data works.
4. **pg is CommonJS.** Use `import pg from 'pg'` (default) plus `import type { Pool }`; a named `import { Pool }` throws at ESM runtime.

## Tech stack

- Notebooks and data: Databricks (Unity Catalog, Genie, Lakebase, AI Gateway, MLflow, Vector Search, `ai_*` SQL functions, Model Serving).
- Agent apps: React + Vite + TypeScript frontends served by FastAPI backends; shared modules in `apps/_shared/`.
- Hackathon hub: Databricks AppKit (Node + React 19 + Tailwind 4 + Shadcn), Lakebase via `pg`, analytics via the AppKit analytics plugin.

## Status

Hub deployed and verified live: root 200, the full Register to Judge to Leaderboard loop on Lakebase (separation of duties enforced), and live `akzo_*` analytics, all under the app service principal. All 5 agent apps active. See [`WORKSHOP_MATERIALS.md`](WORKSHOP_MATERIALS.md) for the full status.
