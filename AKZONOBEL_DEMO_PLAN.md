# AkzoNobel — Agent Bricks Demo Plan (art-of-possible scripts)

> **Role of this doc:** the demo *architecture + narrative* reference for the showcases the workshop runs (cold-open + Day-2 starters). For run-of-show timing see `WORKSHOP_AGENDA.md`; for strategy/focus-5 see `AKZONOBEL_WORKSHOP_PLAN.md`.
>
> **Note on alignment:** all **focus-5 tracks now have scripts** — Supervisor #3 (showcase 1), Finance #1 (showcase 4), SCM #2 (showcase 6), Commercial #5 (showcase 7); Governance #4 is realized as the AI Gateway + OBO layer (see agenda Layer 7). Quote/Forecast (showcases 2/3 = adjacent #18/#6) and Contracts (showcase 5, now idea-seed) round out the library. The agenda's flagship is the **Supervisor Agent** whose layers ARE the focus-5 — showcases 4/6/7 double as its Finance/SCM/Commercial legs and as standalone Day-2 starters.

Showcases demonstrating unified Databricks platform power: **Agent Bricks, Lakebase, Genie, Unity Catalog, AI Gateway** — for maximum wow factor and competitive positioning vs Microsoft Azure AI Foundry.

## Selection rationale

- Build on what Akzo already has in motion: Finance kickoff, planned Genie rollouts in Finance/SCM/Commercial, active MMF (Paints EMEA MVP), Procurement in Genie audience, SharePoint integration discussions.
- Cover both structured (Genie text2sql) and unstructured (Knowledge Assistant) data.
- Show agents that **act** (Lakebase write-back, approval workflows), not just answer.
- Every demo counters Azure AI Foundry's stitched-services story (Azure SQL + AI Search + Fabric + Logic Apps + Purview) with one platform, one governance plane.

## The showcases

### 1. Multi-domain supervisor — Finance / SCM / Commercial (use case #3)
*Platform story anchor*

- **Agent Bricks**: Multi-Agent Supervisor brick, routes to domain agents
- **Genie**: 3 Genie spaces (Finance, SCM, Commercial) as routing targets
- **Unity Catalog**: row-level security — same question, controller vs planner, different data. Killer moment for the 2,000-user rollout concern
- **AI Gateway**: all LLM calls through one endpoint — rate limits, payload logging, usage tracking per user group
- **Lakebase**: conversation/session state, feedback store for eval loop

Subsumes use cases #1, #2, #5 in a single chat experience. Precedent: Agent Bricks supervisor + multiple Genie spaces + RLS for thousands of business users.

### 2. Pricing & quote-generation agent (use case #18)
*Densest single demo — agent that acts end to end*

- **Agent Bricks**: Information Extraction (parse inbound request) + orchestrator
- **Genie**: API call for pricing history, customer margin, volume tiers — live text2sql
- **Lakebase** ⭐: quote record, approval workflow state, audit trail; Databricks App for human approval backed by Lakebase
- **Unity Catalog**: governed pricing tables, lineage from quote back to source data
- **AI Gateway**: guardrails on outbound quote draft (no hallucinated discounts), cost tracking per quote

Precedent: hours → minutes turnaround. Foundry counter: they'd need 5+ Azure services stitched.

### 3. Forecast planner copilot on MMF (use case #6)
*Write-back — answers AND actions*

- **Agent Bricks**: planner agent explains forecast deltas, proposes overrides
- **Genie**: API over forecast version tables — "why did Paints EMEA drop 8%?"
- **Lakebase** ⭐: override write-back, transactional, syncs to lakehouse; approval state
- **Unity Catalog**: forecast lineage, who-overrode-what audit
- **AI Gateway**: model fallback (cheap model for explanations, strong model for override reasoning)

Demo tip: fake MMF output as a Delta table — no live MMF dependency. Ties directly to active MMF MVP, Paints EMEA scope, and their forecast accuracy / bias / FVA success metrics.

### 4. Finance controlling copilot (use case #1)
*Akzo's own #1 priority — depth demo*

- **Agent Bricks**: reasoning agent — FX vs volume vs price variance decomposition + recommended action ("Genie answers, agent reasons")
- **Genie**: Finance space, text2sql over margin/cost tables
- **Knowledge Assistant**: accounting policy docs, close-process SOPs cited alongside numbers
- **Unity Catalog**: certified metrics (UC metric views) — agent answers from governed definitions, not raw tables
- **AI Gateway**: payload logging for audit — every finance answer traceable
- **Lakebase**: saved analyses, alert subscriptions for controllers

Precedent: governed NL finance analytics for up to 2,000 controllers; query time 20–30 min → 5–10 min.

### 5. Procurement contract intelligence (use case #7)
*Unstructured counterweight*

- **Agent Bricks**: Knowledge Assistant + clause extraction into structured risk tables
- **Genie**: spend analytics joined to extracted contract terms — "suppliers with non-standard payment terms AND spend >€1M" — structured + unstructured fusion query
- **Unity Catalog**: contracts as governed volumes, extraction outputs as governed tables, ACLs by category
- **AI Gateway**: PII masking guardrail on contract content, per-team budgets
- **Lakebase**: review queue — flagged deviations await procurement sign-off

SharePoint connector angle already in Akzo's integration discussions.

### 6. SCM control tower copilot (use case #2)
*Cross-domain answers → intervention — focus-5 track; doubles as the supervisor's SCM leg*

- **Agent Bricks**: control-tower reasoning agent — explains OTIF / inventory / service-level deltas and recommends an intervention (expedite, reallocate stock, adjust safety stock)
- **Genie**: SCM space, text2sql over OTIF / inventory / logistics / service tables — *"why did OTIF for Paints EMEA drop to 89% last month?"*
- **Lakebase** ⭐: intervention log + watchlist state (flagged SKUs/lanes persist across sessions); recommended-action write-back for planner sign-off
- **Unity Catalog**: governed supply tables; **RLS by region/plant** (a Benelux planner ≠ an APAC planner); KPI-to-source lineage
- **AI Gateway**: cost caps on high-volume planner queries; payload logging for audit

Precedent: cross-domain Genie orchestration for SCM users + supply-chain metadata assistants that cut time-to-insight sharply. Foundry counter: OTIF data spans plants/ERPs — UC unifies it on one governed plane; Foundry stitches Azure SQL + Fabric + AI Search.

### 7. Commercial action assistant (use case #5)
*Genie drives action, not just reporting — focus-5 track; doubles as the supervisor's Commercial leg*

- **Agent Bricks**: reasoning agent — summarizes account / customer / market signals → **next-best-action** (price move, churn-save play, upsell)
- **Genie**: Commercial space, text2sql over account / sales / pipeline / margin tables — *"which Paints EMEA accounts are at churn risk and why?"*
- **Knowledge Assistant** (optional): account plans / sales playbooks cited alongside the numbers
- **Lakebase** ⭐: action queue / CRM-style next-step write-back; saved account views per rep
- **Unity Catalog**: governed commercial tables; **RLS by sales territory/segment**
- **AI Gateway**: guardrails (no fabricated discounts or commitments in drafts), per-team budgets

Precedent: sales assistants combining tool-calling + Genie for account insights and multi-turn commercial analysis. Foundry counter: account data *and* the actions taken on it land on one governed, traceable plane.

## Pillar coverage matrix

| Demo | Agent Bricks | Genie | Lakebase | Unity Catalog | AI Gateway |
|------|:---:|:---:|:---:|:---:|:---:|
| 1. Supervisor | ⭐ MAS | ⭐ 3 spaces | state | ⭐ RLS | logging |
| 2. Quote agent | extraction | API | ⭐ write + app | lineage | guardrails |
| 3. Forecast planner | agent | API | ⭐ write-back | audit | fallback |
| 4. Finance copilot | ⭐ reasoning | ⭐ space | subscriptions | ⭐ metric views | ⭐ audit log |
| 5. Contracts | ⭐ KA | fusion query | queue | volumes + ACL | ⭐ PII mask |
| 6. SCM control tower | ⭐ agent | ⭐ SCM space | ⭐ intervention log | RLS region/plant | cost caps |
| 7. Commercial assistant | ⭐ reasoning | ⭐ Commercial space | action queue | RLS territory | ⭐ guardrails |

**Focus-5 coverage:** #1 Finance (4) · #2 SCM (6) · #3 Supervisor (1) · #4 Governance (AI Gateway+OBO layer) · #5 Commercial (7). Adjacent: #18 Quote (2) · #6 Forecast (3). Idea-seed: #7 Contracts (5).

## Narrative arc (one 45-min session)

1. Open with **supervisor** — business user asks mixed question, routes across domains
2. Drill into **finance copilot** — variance decomposition + recommended action
3. "Cost spike from a supplier?" → **contract intelligence** — clause extraction, deviation flag
4. "Fix the forecast?" → **forecast planner** — override write-back via Lakebase
5. Close with **quote agent** — full loop: read → reason → act → write → approve

Closing line: one platform, one governance plane, every agent traced through AI Gateway, every table governed by Unity Catalog, every action lands in Lakebase. That's the sentence Foundry can't say.

## Deliberately excluded

- **#20 AgentOps factory**: enabler, zero exec wow in demo — keep as slides for the governance conversation (it's the post-workshop win-back motion; see `AKZONOBEL_WORKSHOP_PLAN.md`)
- **#14 Access provisioning agent**: technically strongest Lakebase fit (transactional grants, <30s, audit log) but IT-internal — slide material

*(Note: #4 AI governance is no longer excluded — it's a focus-5 track, demonstrated as the AI Gateway + OBO layer rather than a standalone chat agent.)*
