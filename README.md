<div align="center">

# AkzoNobel Agent Bricks Workshop

### Build production grade AI agents on Databricks, one tier at a time.

A progressive, hands on workshop that takes you from calling AI in SQL to a governed multi domain supervisor, on synthetic AkzoNobel coatings data. It ends with a hackathon starter kit your teams can fork.

</div>

---

## What this is

A practical guide to building real AI agents on Databricks, not toy demos. You climb three tiers, and every tier carries the same lifecycle: build, evaluate, govern, deploy, improve. The three capabilities that matter most deepen as you go: the Agent Bricks agent types, the Model Context Protocol (MCP), and agents that take real actions.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop. Nothing in this repo is tied to one workspace; every notebook, starter, and app reads its catalog, warehouse, and endpoints from widgets or environment variables.

---

## The ladder

| Tier | Folder | You build |
|---|---|---|
| L100 Foundations | `L100-foundations/` | AI from SQL, the no code Agent Bricks types, your first coded agent, evaluation, and memory |
| L200 Capabilities | `L200-capabilities/` | Tool calling, an MCP server you build, Lakebase memory, deployment, and the first agent that acts behind a human approval gate |
| L300 Use case | `apps/supervisor/` + `starters/supervisor/` | The flagship multi domain supervisor across Finance, Supply Chain, and Commercial, with the full action ladder and production monitoring |
| Hackathon kit | `hackathon-starter-kit/` | Forkable tracks, starter prompts, ai dev kit skills |

Each tier is self contained. Start at L100, or jump in where you need to.

---

## The three spines

The workshop is organized around three capabilities that grow tier over tier.

| Spine | L100 | L200 | L300 |
|---|---|---|---|
| Agent Bricks types | Build the single purpose types | Add tools to a coded agent | Supervisor composes them all |
| MCP | Consume one read only tool | Build and register a server | Wire the full fleet |
| Agents that act | None, read only | One or two connectors with human approval | All connectors, an approval ladder, and an audit trail |
| LLMOps | Evaluation, one judge, tracing | Judge suite, AI Gateway, guardrails | Production monitoring, lineage, advanced evaluation |

---

## Get started

### 1. Clone this repo into your Databricks workspace

The whole workshop runs from a Databricks **Git folder** (Repos), so you get the
notebooks, data generators, and starter kit in one place and can pull updates as
new tiers land.

**Option A — UI (recommended)**

1. In your Databricks workspace sidebar, click **Workspace → Users → your user**.
2. Click **Create → Git folder** (top right).
3. Paste the repo URL and confirm the details:
   - **Git repository URL:** `https://github.com/Praneeth16/akzo-agent-bricks-workshop.git`
   - **Git provider:** GitHub
   - **Branch:** `main`
4. Click **Create Git folder**. The repo clones to
   `/Workspace/Users/<you>/akzo-agent-bricks-workshop`.
5. To get later updates, open the Git folder and click **⋯ → Git… → Pull**.

> Private repo? Add a GitHub Personal Access Token first under
> **Settings → Linked accounts (Git integration)**, then clone.

**Option B — Databricks CLI (from your laptop)**

```bash
databricks repos create \
  --url https://github.com/Praneeth16/akzo-agent-bricks-workshop.git \
  --provider gitHub \
  --path /Workspace/Users/<you>/akzo-agent-bricks-workshop
```

> On a lab environment such as **Vocareum**, you don't clone — the course bundle
> is preloaded. Start from the first L100 lab.

### 2. Run the workshop

1. Run the shared data setup once. See `data/`. It loads the coatings tables, the document volume, the Genie spaces, and the vector index into your Unity Catalog. Set `AKZO_CATALOG` and `DATABRICKS_WAREHOUSE_ID` to your own values first.
2. Open `L100-foundations/` and follow its README. The notebooks default the catalog to your current catalog; you paste your Genie space IDs from the UI where prompted.
3. Climb the ladder.

---

## Prerequisites

- Databricks workspace with serverless SQL compute and Unity Catalog
- Foundation Model API access (for example Llama 3.3 70B or Claude Sonnet)
- Vector Search, Lakebase, and Databricks Apps enabled
- Permission to read and write your workshop catalog

---

## What's included

The workshop is built tier by tier. Each tier is runnable end to end on a Databricks workspace.

| Item | What it gives you |
|---|---|
| `data/` generators and `load_to_uc.py` | The shared coatings dataset across Finance, SCM, and Commercial |
| `genie/create_genie_spaces.py` | Three Genie spaces, one per domain |
| `L100-foundations/00_sql_ai_functions.ipynb` | AI from SQL: `ai_query`, `ai_forecast`, `ai_extract`, and more |
| `L100-foundations/01_agent_bricks_types.md` | The no-code Agent Bricks types, UI and programmatic paths |
| `L100-foundations/02_agent_evaluation.ipynb` | Evaluation with MLflow judges |
| `L100-foundations/03_short_term_memory.ipynb` | Conversation memory on Lakebase |
| `L100-foundations/L100-agent-langgraph/` | Your first coded agent: LangGraph + managed MCP, deployable on Databricks Apps |
| `L200-capabilities/` | Tool calling, an MCP server you build, Lakebase memory, deployment, and the first agent that acts behind a human approval gate |
| `apps/supervisor/` + `starters/supervisor/` | The L300 flagship: the multi-domain supervisor with the full action ladder and production monitoring |
| `apps/` | Five deployable agent apps (finance-copilot, supervisor, action-center, quote-agent, mock-systems) + shared backend (`_shared`) |
| `eval/` | Golden-question eval sets, one per track |
| `hackathon-starter-kit/` | Forkable tracks, starter prompts, and ai-dev-kit skills |

To deploy a coded agent on Databricks Apps, pass your catalog at deploy time and grant the app's service principal access to the data it reads. Each app's README has the exact env vars and commands.

---

## Repository layout

```
L100-foundations/   Tier 1: AI from SQL, no-code Agent Bricks types, first coded agent
L200-capabilities/  Tier 2: tool calling, MCP server, Lakebase memory, deploy, action gate
apps/               5 deployable agent apps + shared backend (_shared)
starters/           8 forkable copilot starters (one per use case)
data/               Deterministic synthetic-data generators + Unity Catalog loader
genie/              Genie space configs + creation script (finance, scm, commercial)
eval/               Golden-question eval sets (one YAML per track)
demo/               Demo talk tracks
deploy/             Per-app deploy scripts
hackathon-starter-kit/  Forkable tracks, starter prompts, ai-dev-kit skills
databricks.yml      Root Asset Bundle (L200 notebooks workflow)
```

---

## Tech stack

Databricks Agent Bricks · Genie + Genie Code · Unity Catalog (RLS/OBO) · Lakebase · AI Gateway · MLflow evaluation · Vector Search · `ai_*` functions · Databricks Apps · Asset Bundles.

---

## License

Internal AkzoNobel x Databricks workshop material. Not for redistribution.
