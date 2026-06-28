<div align="center">

# Hackathon-in-the-Box

### Run an AkzoNobel Agent Bricks hackathon, end to end, on Databricks.

Ten teaching notebooks. Eight forkable tracks. Five live agent apps. One light-theme hub that ties it together and runs the event, built on Databricks AppKit so the app itself is a demo of the stack.

[![Built on Databricks AppKit](https://img.shields.io/badge/built%20on-Databricks%20AppKit-00b39f)](https://developers.databricks.com/docs/appkit/v0/)
[![App](https://img.shields.io/badge/app-live-059669)](https://akzo-hackathon-hub-7474654904882204.aws.databricksapps.com)
[![Stack](https://img.shields.io/badge/stack-Agent%20Bricks%20%C2%B7%20Genie%20%C2%B7%20Lakebase-2563eb)](#tech-stack)
[![Theme](https://img.shields.io/badge/theme-Databricks%20light-f7f8fa)](#)

[Live hub](https://akzo-hackathon-hub-7474654904882204.aws.databricksapps.com) · [Quickstart](#quickstart) · [Tracks](#hackathon-tracks) · [Notebooks](#day-1-reference-notebooks) · [Architecture](#architecture)

</div>

---

## What this is

A complete, runnable 2-day Databricks Agent Bricks workshop for AkzoNobel (Pune, July 1 to 2, 2026). Day 1 shows one finished, governed agent and peels it layer by layer. Day 2 teams fork a starter and ship their own. The whole thing is wrapped in a single app, Hackathon-in-the-Box, that surfaces the materials and runs Register, Teams, Submit, Judge, and Leaderboard on live Lakebase state.

> [!NOTE]
> The synthetic data is fictional coatings data. The planning documents and infrastructure identifiers (workspace, warehouse, service-principal IDs) are internal. The repo is private; treat it accordingly.

## Features

- **One hub, everything in it.** Browse the agenda, the 8 tracks, the 10 notebooks, and the 5 deployed apps; register a team; submit; judge on the rubric; watch the leaderboard. Light Databricks theme, built on AppKit.
- **Per-track build guides.** Each track has a `/guide/:track` page with a what-it-is, prerequisites, and copy-paste **Genie Code** prompts so attendees build by prompting, not from a blank cell.
- **Try it live.** Live analytics over the governed `akzo_*` Unity Catalog tables (margin, OTIF, churn) right inside the hub, plus deep links to the 5 deployed agent apps.
- **Agents that act.** The Action Maturity Ladder (recommend, stage, approve, execute, escalate) with governance: identity, policy guardrails, approval, and audit lineage.
- **Teaching-grade notebooks.** Ten reference notebooks, each peeling one layer of the platform, written so a newcomer understands the code and the why.
- **Deployable.** A Databricks Asset Bundle ships the notebooks as a workflow; the hub deploys as a Databricks App.

## Quickstart

```bash
# 1. Authenticate the Databricks CLI to the workspace (once)
databricks auth login --host https://fevm-serverless-lakebase-praneeth.cloud.databricks.com --profile fe-vm-lakebase-praneeth

# 2. Run the hub locally
cd apps/hackathon-hub/akzo-hackathon-hub
DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth npm run dev   # http://localhost:8000

# 3. Deploy the hub
databricks apps deploy --force -p fe-vm-lakebase-praneeth

# 4. Deploy the notebooks workflow (Asset Bundle, from repo root)
databricks bundle validate -t dev -p fe-vm-lakebase-praneeth
databricks bundle deploy   -t dev -p fe-vm-lakebase-praneeth
```

New here? Open the hub, go to **Build setup**, run `databricks experimental aitools install` to get your coding agent Databricks-aware, then open any track's **guide** and build with Genie Code.

## Hackathon tracks

Reconciled to the workshop deck: 5 priority use cases, 2 adjacent, plus 1 bonus.

| # | Track | Role |
|---|---|---|
| 01 | Finance controlling copilot | Teaching thread + showcase |
| 02 | SCM control tower copilot | Priority |
| 03 | Multi-domain supervisor | Flagship |
| 04 | AI governance & policy agent | Priority |
| 05 | Commercial action assistant | Priority |
| 06 | Forecast planner copilot (MMF) | Adjacent |
| 18 | Pricing & quote agent | Showcase, the agent acts |
| + | Agents that act (L1 to L4) | Bonus |

Each track ships a forkable starter (`starters/<track>/`), a golden-question eval set (`eval/<track>.yaml`), and an in-app guide.

## Day 1 reference notebooks

The whole game, peeled one layer at a time (`notebooks/`):

1. The domain agent: Finance over governed data
2. Per-user truth: Unity Catalog RLS/ABAC + OBO
3. More domain legs: SCM + Commercial
4. The supervisor itself
5. Memory + action with Lakebase
6. Trust: MLflow eval + an LLM judge
7. Govern at scale: AI Gateway
8. Document intelligence: ai_parse_document to ai_extract to Qwen embed to Vector Search to RAG
9. Agents that act (L1 to L4) + autonomous closed loop

## Architecture

```
                        Hackathon-in-the-Box (Databricks AppKit, light theme)
  Overview · Challenges -> per-track Guide · Build setup · Demos · Try it live
  Register · Teams · Submit · Judge · Leaderboard · Resources · Materials · Organizer
        |                                   |                         |
   Lakebase (hack_* state)         analytics plugin           deep links to
   teams/submissions/scores        over akzo_* tables         5 deployed agent apps
        |                                   |
   graphrag-spike / akzo            SQL warehouse 4d39ac2e32b72a3a
```

- **Notebooks + data:** Unity Catalog, Genie, Lakebase, AI Gateway, MLflow, Vector Search, `ai_*` SQL functions, Model Serving.
- **Hub:** Databricks AppKit (Node + React 19 + Tailwind 4 + Shadcn); Lakebase via `pg` + an OAuth db credential; live analytics via the AppKit analytics plugin.
- **Agent apps:** React + Vite + TypeScript served by FastAPI; shared modules in `apps/_shared/`.

## Repository layout

```
notebooks/   10 Day-1 reference notebooks (one per layer)
starters/    8 Day-2 forkable hackathon tracks
apps/        5 deployed agent apps + the hackathon-hub + shared backend (_shared)
data/        Deterministic synthetic-data generators + Unity Catalog loader
genie/       Genie space configs (finance, scm, commercial)
eval/        Golden-question eval sets (one YAML per track)
demo/        Demo talk tracks
deploy/      Deploy scripts + smoke results
docs/plans/  Implementation plans
databricks.yml   Root Asset Bundle (notebooks workflow)
```

## Tech stack

Databricks Agent Bricks · Genie + Genie Code · Unity Catalog (RLS/OBO) · Lakebase · AI Gateway · MLflow evaluation · Vector Search · `ai_*` functions · Databricks Apps + AppKit · Asset Bundles.

## Workspace

| | |
|---|---|
| Workspace | `fevm-serverless-lakebase-praneeth` (profile `fe-vm-lakebase-praneeth`) |
| Catalog | `serverless_lakebase_praneeth_catalog` |
| Schemas | `akzo_finance` `akzo_scm` `akzo_commercial` `akzo_docs` `akzo_ops` `akzo_gateway` |
| SQL warehouse | `4d39ac2e32b72a3a` |
| Lakebase | `graphrag-spike` / `databricks_postgres` / `akzo` |
| Vector Search | `akzo_workshop_vs` -> `akzo_docs.chunks_idx` (Qwen embeddings) |
| Models | `databricks-claude-opus-4-7` · `databricks-gpt-5-5` · `databricks-qwen3-embedding-0-6b` |

## Deploy gotchas

Documented so you do not repeat them: the Apps build container fetches npm from the Databricks proxy, which can 404 the pg tree; the fix is a public-npm lockfile (rewrite `resolved` hosts to `registry.npmjs.org`). The `prebuild` typegen is made non-fatal. The app service principal rotates across redeploys, so re-grant UC SELECT + warehouse CAN_USE + Lakebase role + `akzo` DML. Details in `apps/hackathon-hub/README.md`.

## License

Internal AkzoNobel x Databricks workshop material. Not for redistribution.
