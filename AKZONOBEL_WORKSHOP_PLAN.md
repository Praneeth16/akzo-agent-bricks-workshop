# AkzoNobel — Agentic AI Workshop + Hackathon: Strategy & Master Plan

**This doc = WHY + WHAT** (strategy, win-back, focus use cases, feature arsenal, positioning).
**Companion docs:**
- **Run-of-show, pedagogy, logistics, delivery gates → `WORKSHOP_AGENDA.md`** (the facilitator doc).
- **Build-tool mechanics (Genie Code), admin enablement, facilitation lessons → `VIBE_CODING_SESSION.md`.**
- **Art-of-possible demo scripts (showcase architectures) → `AKZONOBEL_DEMO_PLAN.md`.**

---

## Compelling event

AkzoNobel runs **200+ agentic use cases on Azure OpenAI / AI Foundry**. Win them back to **ONE governed platform**; connect agents to their **Celonis + Moveworks** landscape. Frame everything against **"no AI without measurable value"** and the **Axalta merger** (*proposed*, expected close late 2026/early 2027; $600M synergy target).

The audience already builds agents (they came off Foundry). So the pitch is **not** "agents are possible" — it's **"the platform underneath is the moat: governed by Unity Catalog, evaluated by MLflow, shipped by Genie Code."**

**Format:** async pre-read → Day 1 guided "whole game, peeled" → Day 2 vibe-coded hackathon + ship.
**Audience:** ~15-20 AkzoNobel builders. **Agent-experts, Databricks-newcomers** → teach the *platform*, not agents.
**Delivery leads:** Suvadeep Sinha (lead) + Shyam Sankararaman, with account team (Yves Kusters AE, Tugce Tosun Bayraktar SA). India-based team per ASQ AR-000122098.

---

## Design principles

1. **Skip what they run; teach what wins.** Genie is LIVE (Finance), UC is their governance plane, MMF MVP active. Don't teach Genie 101 / UC basics. Teach **Supervisor Agent**, **agents that ACT** (Lakebase write-back), **governance + eval** (the Foundry differentiators), and **vibe-coding** to build fast.
2. **Counter Foundry on credible ground only.** Foundry Agent Service HAS OBO, MCP, tracing, eval, Entra RBAC, framework choice (LangGraph etc.), agent optimizer — do NOT claim it "can't orchestrate" or "needs 5+ stitched services." The defensible edge = **UC-native governance over the lakehouse data agents read/write + native Genie/KA/Lakebase/eval on one governed plane**, with lineage.
3. **Bring any framework / any model — no rewrite, no lock-in.** Lead LangGraph; note CrewAI/Agno/Claude Code SDK all work via MLflow `ResponsesAgent`. Directly addresses "we don't use OpenAI SDK." Ports the 200 Foundry use cases without a vendor-SDK rewrite.
4. **Their data.** Synthetic **Finance / SCM / Commercial** business data (coatings is the product domain; the agents are business-function agents).
5. **Vibe-code everything in Genie Code (in-workspace).** Teams build with Genie Code + `mcp-ai-dev-kit` skills against governed data — no local install. Optional external lane: Claude Code/Codex via Unity AI Gateway.

---

## Focus-5 use cases (customer's ranked top-5 = hackathon tracks + teaching spine)

The flagship demo (**Supervisor Agent**) IS the composition of these — peel it and each appears as a layer (see `WORKSHOP_AGENDA.md` design thesis).

| # | Use case | Why it's a fit |
|---|---|---|
| **1** | **Finance controlling copilot** | Finance kickoff + planned Genie Finance rollout + governed access for ~2,000 controllers. Precedent: query time 20-30min → 5-10min. *Teaching thread.* |
| **2** | **SCM control tower copilot** | Genie SCM in forecast; enterprise-scale usage planned. Cross-domain Genie orchestration precedent. |
| **3** | **Multi-domain supervisor (Fin/SCM/Commercial)** | Separate Genie motions planned per domain + scaling worry. Supervisor + multiple Genie spaces + RLS for thousands of users. *Flagship / teaching thread.* |
| **4** | **AI governance & policy agent** | They're discussing one governance model across Databricks + Foundry + Celonis + Moveworks. Managed MCP + OBO + tracing + policy access. |
| **5** | **Commercial action assistant** | Genie Commercial in pipeline; Genie-drives-action stories. Account/market signals → next-best-action. |

**Adjacent, allowed as hackathon tracks:** **#6 Forecast planner on MMF** (Paints EMEA; forecast accuracy/bias/FVA metrics) and **#18 Pricing & quote agent** (densest act-end-to-end; hours→minutes precedent). Full 20-case menu = idea-seed library only.

---

## Source assets

| Asset | Role | Owner |
|---|---|---|
| **`AnanyaDBJ/databricks-ai-workshops`** (L100 / **L300 LangGraph**) | Pattern reference — lifecycle, Lakebase memory, eval, deploy | Ananya (DBJ) |
| `databricks/tmm/bricks-workshop` | No-code L100 fallback (~800 ppl) | Nicolas Pelaez |
| **Genie Code** (in-workspace agentic engineering) | Primary in-session build tool | Databricks |
| **`mcp-ai-dev-kit` App** (skills: Agent Bricks, VS, Model Serving, Apps, Genie) | Unlocks Genie Code to deploy agents/apps | DB Field Eng |
| **Hackathon Workshop play** (FE/6005030992) | Run-of-show we model on | Arthur Dooner |
| `AKZONOBEL_DEMO_PLAN.md` (this repo) | Art-of-possible demo scripts | — |
| `hackathon-in-a-box` skill | Kit generation | FE / Arthur Dooner |
| **"Agentic Coding Workshop"** play (FE/5981831335) + deck (Nethra Ranganathan, GDrive) | Official play (Hackathon mode) + concept slides | Arthur Dooner / Nethra |

---

## DAIS 2026 feature arsenal (the win-back kit)

| Feature | Status | Why it beats Foundry |
|---|---|---|
| **Supervisor Agent** (orchestrates Genie spaces, KAs, UC functions, MCP servers, custom agents from one entry) | **GA** (Feb 2026); **OBO user-auth = Public Preview**; mgmt SDK = Beta; **ESC workspaces unsupported** | Per-user UC-permission enforcement on tool calls (OBO) over the underlying lakehouse data. Smoke-test whoami/RLS + ESC before relying on it. BASF Coatings reference (verify public/approved before live use). |
| **Document Intelligence** (`ai_parse_document` / `ai_extract` / `ai_classify`) | **GA** (✓ WEurope) | Spine of any extraction track (pricing requests, contracts, SDS). Foundry needs separate doc-AI services. |
| **Lakebase** agent memory + write-back | **GA** | Serverless Postgres in the lakehouse; governed memory + transactional write-back. *Write governance = Postgres roles + app/service identity + approval/audit (NOT OBO); UC-registered Lakebase is read-only.* |
| **Lakebase Search** (agent memory recall) | **Beta** — dry-run-gated | Recall for agent memory (not doc retrieval). Doc retrieval = **Vector Search (GA)**. |
| **Unity AI Gateway** | **Beta** | One plane governs LLMs + MCP servers + agents + **coding agents** (Codex/Cursor); real-time guardrails, cross-provider cost caps, audit logs + **ABAC** in UC. Inference-table logs best-effort, lag ~1h → use preseeded logs in demo. |
| **Managed MCP services + UC HTTP connections** | GA (region = Core Model Serving) | Govern external tool-calls (Celonis/Moveworks/SharePoint) through UC. |
| **MemAlign** judge alignment (MLflow, OSS) | OSS — **verify in target MLflow version**; Judge Builder UI = roadmap | Aligns an LLM judge to your quality bar from a few labels. Benchmark: ~40s / ~$0.03 / 2-10 labels (vendor claim). **Optional facilitator-only showcase, pre-recorded/version-verified — never a hands-on dependency.** |
| **Genie One + Conversation APIs** | Conversation APIs = Public Preview | NL→governed-SQL as an agent tool, embeddable in Slack/Teams/SharePoint; Genie Ontology semantic layer. |
| **Model + harness Choice** (Claude/Llama/Kimi/Grok; LangGraph/CrewAI/Claude Code SDK) | Mixed GA/PrPr | Port the 200 Foundry use cases without a vendor-SDK rewrite. |

**Demo/horizon only (not labs):** Genie Agents, Genie ZeroOps (PrPr), App Spaces / Genie App Builder ("coming soon"), Omnigent (alpha). **Excluded** (out of agentic-app scope): Lakeflow, CustomerLake, OpenSharing, MLE-platform.

### Azure EMEA availability (MS Learn feature-region-support, updated 2026-06-11)
AkzoNobel home region = **Azure West Europe (Netherlands)**. ✓ = offered in-region, no cross-geo caveat. **This is regional availability, NOT a GA-vs-preview signal** (preview/beta status is per-feature above).

| Capability | West Europe | North Europe | Note |
|---|:---:|:---:|---|
| Supervisor Agent (MAS) | ✓ | ✓ | UK South only with cross-geo — avoid |
| Knowledge Assistant | ✓ | ✓ | |
| Custom Agents + Agent Evaluation | ✓ | ✓ | |
| Lakebase (Postgres autoscaling) | ✓ | ✓ | |
| Databricks Apps | ✓ | ✓ | |
| Unity AI Gateway | ✓ | ✓ | |
| FM API pay-per-token (Claude/Llama) | ✓ | ✓ | |
| Vector Search (AI Search) | ✓ | ✓ | |
| `ai_*` functions (parse/extract/classify) | ✓ | ✓ | Document Intelligence GA |
| MCP servers + UC HTTP connections | ✓ | ✓ | same regions as Core Model Serving |
| MLflow traces in UC | ✓ | ✓ | |

⚠ **FM Fine-tuning NOT in West Europe** (cross-geo or US). **Avoid UK South** (Model Serving disabled for uksouth workspaces created after 2026-04-30). **MemAlign** = OSS MLflow Python, region-independent. **Compliance:** partner-powered AI + hosted LLM judges send data to Azure-OpenAI-class endpoints — **accepted by AkzoNobel** (extensive Foundry user), non-blocker.

### Internal play alignment
ASQ AR-000122098 = the official FE **"Agentic Coding Workshop"** play (Arthur Dooner; Confluence FE/5981831335; Status Live). Modes: Standard / Custom / **Hackathon** (multi-day). Workflow taught = **describe → generate → test → refine**. Success metrics: apps deployed to Databricks Apps (primary), $1,000+ AI consumption 2 consecutive months, 2-3x dev velocity, >50% adoption in 60 days. FY27 campaign "Accelerate App Growth Through Agentic Coding." **Our plan = the Hackathon mode of this play.**

---

## Win-back follow-through (post-workshop)
The hackathon seeds, but the 200 Foundry use cases need a path: **inventory → archetype → portability assessment → security-gap review → target production pattern (AgentOps factory, #20)**. Land this as the MAP/POV motion after Day 2, not inside it.
