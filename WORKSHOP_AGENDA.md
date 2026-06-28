# AkzoNobel Agentic AI — Detailed Workshop Agenda (fast.ai-style)

**Format:** Async pre-read → Day 1 guided "whole game, peeled" → Day 2 hackathon + ship.
**Audience:** ~15-20 AkzoNobel builders. **Agent-experts, Databricks-newcomers** — teach the *platform*, not agents.
**Build tool:** Genie Code (in-workspace, no local setup).
**Pillars:** Agent Bricks · Genie · Lakebase · Unity Catalog (governance/OBO) · AI Gateway · MLflow.

---

## The design thesis (why this works)

We teach the way **Jeremy Howard teaches fast.ai**: *show the whole game first, then peel one layer at a time, returning to the whole after each layer.* Top-down, code-first, tinker-driven. No bottom-up theory march.

**The "whole game" = the Supervisor Agent (use case #3).** It is not just one of the five focus use cases — it is the *composition* of them:

| Layer of the flagship demo | Akzo focus use case it reveals |
|---|---|
| The supervisor that routes one question | **#3 Multi-domain supervisor** |
| Its Finance domain leg | **#1 Finance controlling copilot** |
| Its SCM domain leg | **#2 Supply chain control tower copilot** |
| Its Commercial domain leg | **#5 Commercial action assistant** |
| Its per-user governance + gateway layer | **#4 AI governance & policy agent** |

So on Day 1 we show one finished thing, and by peeling it the room *meets all five of their priority use cases as layers*. Day 2 they each pick one layer to deepen into a full build.

**Critical delivery rule: hands-on = tweak prebuilt, not build-from-zero.** Everything is **pre-staged by facilitators before Day 0** — all three Genie spaces, the supervisor, Lakebase + approval app, eval sets, gateway routes, traces. In the room, "build a layer" means: **change one thing (an instruction, a metric view, an example SQL, an action definition, a route), then run *one* query** to see your change take effect. This is forced by real platform limits (Genie throughput caps, Beta gateway log latency, OBO previews) — and it makes the fast.ai peel *tighter*: see → tweak → return, not a 45-min build that throttles and stalls.

**What "peel a layer" means, concretely — every layer follows the same 3-beat rhythm:**
1. **See it in the whole** (~5 min): re-open the running supervisor, point at the layer doing its job.
2. **Tweak that layer yourself** (~build min): in Genie Code, change one element of the *prebuilt* layer and run one query/pair.
3. **Return to the whole** (~3 min): re-run the full demo, watch your change light up in context.

The audience never loses the forest while learning a tree, and never waits on a cold build.

---

## L100 placement (the one bottom-up exception)

Pure fast.ai is top-down, but this room has **zero Databricks platform context**. So we open with a **tight 20-min L100 map** — *just enough to navigate*, not a platform course. Its only job: when we peel a layer and say "this runs on serverless, governed by Unity Catalog, called through AI Gateway," those words already mean something. Everything deeper is learned top-down by peeling.

---

## PRE-READ (async, ~1.5h, sent ~4 days ahead)

| Part | Time | Content |
|---|---|---|
| **P1 — Platform 101 (for people who know agents)** | ~35 min | The 7 nouns you'll hear all of Day 1, each tied to the agent capability it unlocks: **Unity Catalog** (one governance plane), **serverless**, **Genie space** (NL→governed SQL), **Agent Bricks** (managed KA / Document Intelligence / **Supervisor Agent + OBO**), **Lakebase** (agent memory + write-back), **MLflow** (tracing + LLM judges), **AI Gateway** (governed model front-door — contrast vs the Foundry gateway), **Genie Code** (the build agent). Ends with a 5-question self-check. |
| **P2 — Access ready-check (validate only, no infra build)** | ~20 min | Confirm workspace + serverless; open Genie Code (sparkle icon); confirm SELECT on the demo catalog; **run a tiny smoke test** (ask the prebuilt Finance Genie space one question) to prove access. **Facilitators have already pre-staged all data, indexes, spaces, and the supervisor** — participants do NOT build infrastructure here. Complete ≥48h before Day 1. |
| **P3 — Scope + context** | ~15 min | Compelling event (Foundry win-back, Celonis/Moveworks, Axalta — *proposed* merger, $600M synergy target); the focus-5 menu; one honest Foundry → Databricks slide (we win on UC-native governance over the lakehouse data agents read/write, **not** "Foundry can't orchestrate"). Each team picks one focus use case, sketches its architecture, confirms its provided synthetic data, writes a one-line measurable-value claim **and its 5 golden eval questions** (defaults provided per track — teams may edit). Teams arrive Day 1 scoped. |

---

## DAY 1 — The Whole Game, Peeled (guided, ~7h)

> Teaching thread: the **Supervisor Agent**. Every block peels one more layer off it, then snaps the layer back in. All infra is prebuilt; hands-on = tweak-one-thing-and-run-one-query.

### 0:00 — Cold open: the finished thing (25 min)
Run the **completed Supervisor Agent live** — but **with a recorded backup + static trace screenshots ready** (the supervisor has many prereqs; never let the flagship moment depend on a live cold call).
- A **controller** asks one deliberately **cross-domain** question: *"Paints EMEA gross margin dropped 8% in Q2 — is it price, volume, or a supply/service issue, and what should I do?"* → the supervisor routes the *finance* part to Finance, the *supply* part to SCM, fuses one governed answer.
- The **same question as an SCM planner** → persona-specific access changes *what data backs the answer* (OBO). Same routing, different governed truth.
- One chat. Cross-domain routing. Per-user governed answers. Every call traced.

Then the promise: **"By 5pm today you will have run, modified, and understood every layer of what you just saw — full from-scratch builds are forkable for Day 2."** Show the layer map (the table above). This is the whole game.

### 0:25 — L100 platform map (20 min)
The one bottom-up beat. The 7 nouns, fast, each pinned to a layer you'll peel today. UC = how the controller and planner saw different data. Genie = how the question became SQL. Genie Code = what you'll tweak with. No deep dives — a navigable map. (Foundry-gateway contrast lands here as one slide.)

### 0:45 — Layer 1: The domain agent (Genie over governed data) — Finance (50 min)
*Reveals use case #1, Finance controlling copilot.*
- **See (5m):** in the running supervisor, the Finance leg answering the margin question.
- **Tweak (40m):** the **Finance Genie space is prebuilt** over synthetic margin/cost/FX tables with **UC metric views** already wired. Each pair: **edit one instruction OR one example SQL OR one metric-view reference, then run ONE query** to see it change the answer. (Genie has workspace throughput caps — ~20 UI Q/min, ~5 API Q/min best-effort — so it's one query per pair, not free-for-all testing.) Observe the reasoning step that turns a number into a variance decomposition + recommended action.
- **Return (5m):** the edited space still serves as the supervisor's Finance leg; re-run.

### 1:35 — Break (15 min)

### 1:50 — Layer 2: Per-user truth (Unity Catalog + OBO/RLS) (45 min)
*Reveals the read-governance half of use case #4, AI governance & policy agent.*
- **See (5m):** controller vs planner, same question, different rows — the cold-open moment, now explained.
- **Tweak (35m):** RLS/ABAC on the Finance tables is **prebuilt**; flip a persona attribute and re-run the `whoami` / RLS smoke test as both personas. **Scope honestly:** OBO + UC/RLS govern **reads** (Genie/Supervisor enforce the caller's UC permissions on data + subagent access). It does **not** automatically cover every write — **Lakebase writes use Postgres roles independently; UC-registered Lakebase is read-only.** Writes are governed in Layer 5 by app/service identity + approval + audit, not by OBO alone. This honesty is the answer to Akzo's 2,000-user-rollout governance fear.
- **Return (5m):** re-run the supervisor as both personas; data changes with the user.

### 2:35 — Lunch (45 min)

### 3:20 — Layer 3: More domain legs — SCM + Commercial (45 min)
*Reveals use cases #2 (SCM control tower) and #5 (Commercial action assistant).*
- **See (5m):** the supervisor routing to SCM and Commercial.
- **Tweak (35m):** **SCM and Commercial Genie spaces are prebuilt** (OTIF/inventory/service; account/customer/market signals). Same recipe as Layer 1 — each pair edits one instruction/example in *one* of the two spaces and runs one query. The room feels the *pattern* repeat across domains — that's the point.
- **Return (5m):** all three legs live under one supervisor.

### 4:05 — Layer 4: The supervisor itself (35 min)
*Reveals use case #3, the flagship.*
- **See (5m):** the routing decision (open a trace; routing is the interesting part).
- **Tweak (25m):** the **Supervisor Agent is prebuilt** over the three Genie spaces. Edit the **routing description / subagent registration** and re-run a cross-domain question to watch routing change. (Supervisor Agent management SDK is Beta; ESC workspaces unsupported — verified on this workspace at Day-0 dry-run.)
- **Return (5m):** one chat, cross-domain, governed per user.

### 4:40 — Layer 5: Memory + action (Lakebase) (40 min)
*The "agents that act" layer — shared by #1/#2/#5/#6.*
- **See (5m):** an override/approval flow in the demo.
- **Tweak (30m):** **Lakebase + the approval Databricks App are prebuilt** (schema, Postgres roles, app, audit all pre-wired — full stand-up is far more than 30 min). Each pair: **write one row through the prepared endpoint OR change one action definition**, then watch it land in Lakebase and surface in the approval app. The agent stops answering and starts *acting* — through a governed app/service identity with an audit trail (the write-governance pattern, not OBO).
- **Return (5m):** the supervisor now reads → reasons → acts → writes → routes to approval.

### 5:20 — Layer 6: Trust (MLflow eval) (35 min)
*How you defend an agent to a controller.*
- **See (5m):** a trace + a judge verdict on a finance answer.
- **Tweak (25m):** **MLflow tracing is prebuilt; one built-in LLM judge** is configured; the **eval set = the 5 golden questions the team wrote in pre-read** (defaults provided). Each pair swaps in their own golden question and re-runs the judge. (Optional 5-min facilitator-only MemAlign teaser — *pre-recorded or version-verified*, never a hands-on dependency.)
- **Return (5m):** re-run with eval gating — the agent is now *measurable*. "No AI without measurable value."

### 5:55 — Layer 7: Govern at scale (AI Gateway) (30 min)
*Completes use case #4, AI governance & policy agent — the Foundry differentiator.*
- **See (5m):** **preseeded gateway logs** from a prior run (Unity AI Gateway is **Beta**; inference-table logs are best-effort and can lag up to ~1h — do NOT promise "today's calls appear now").
- **Tweak (20m):** configure **one** control live — a **model route OR a spend cap OR a rate limit** — and show it take effect; review the preseeded **payload logs in UC**. Honest Foundry-gateway compare: one plane governs **LLM endpoints + agents + coding tools + custom/external APIs**; only claim MCP governance while *showing* the exact MCP/custom-API path. The win is UC-native lineage over the underlying data.
- **Return (5m):** the full supervisor, every layer now understood, every call governed and traced.

### 6:25 — Day-1 close + Day-2 setup (35 min)
Replay the cold-open demo one last time — the room now sees through it to all 7 layers and all 5 use cases. Reveal the hackathon tracks, badge ladder, leaderboard, overnight prompt.

> **On the "packed" agenda:** intentional. fast.ai over-shows on purpose — the room sees the whole game even if a layer is only lightly hands-on. Every layer ships as a forkable reference notebook; anything not absorbed Day 1 is explorable Day 2 or independently. Coverage > completion.

---

## DAY 2 — Hackathon: build + ship one layer deep (~7h)

Teams arrive scoped (pre-event) and equipped (Day 1's 7 layers). Each team takes **one focus use case** and deepens it from a forkable starter into a working, evaluated agent. Build path = Genie Code.

### 0:00 — Kickoff + forkable starters (30 min)
**7 forkable starters** (5 focus tracks: Finance, SCM, Supervisor, Governance, Commercial — plus 2 adjacent: Forecast planner, Pricing & quote). **Every starter ships fully pre-wired** — its Genie space(s), a working governed call, the Lakebase + approval pattern, MLflow tracing + judge, and sample data + 5 default golden questions are already connected. No team integrates from scratch; **Day 2 = tweak, swap, and extend a working agent**, not stand one up. Rules, rubric, badge ladder. "Working code, not slides."

### 0:30 — Build Sprint 1: make it your own (110 min)
Fork your track's pre-wired starter; **swap in your domain data + persona and re-run** until the first governed call answers *your* question well (not integration — the call already works in the starter). Then tune instructions / metric views / routing. **Checkpoint at +60.** Rovers: 1 per ~5-6 builders.

### 2:20 — Break (10 min)

### 2:30 — Build Sprint 2: make it act + measurable (90 min)
The starter's **Lakebase write-back / approval is already wired** — change its action definition or approval logic to fit your use case. **Extend the eval set + judge** with your own golden questions. Optional: enable the starter's **AI Gateway route or external MCP tool** (Celonis/Moveworks/SharePoint mock). **Midpoint checkpoint + lightning round.**

### 4:00 — Lunch (40 min)

### 4:40 — Build Sprint 3 + demo clinic (70 min)
**Ship target (any ONE counts as "shipped"):** a deployed Databricks App **OR** a working endpoint/notebook + a live trace. App deployment is a **pre-wired starter** (clone, don't author) — deploying is not the bar; a working, evaluated, traceable agent is. 60-sec rehearsal to a rover. **Checkpoint 1h-before.**

### 5:50 — Demos + judging (45 min)
4-6 teams × 5 min. Each submits **executable evidence**: app URL *or* endpoint/notebook + trace link, 5 golden Qs, 1 failing case, cost/latency snapshot, measurable-value statement.

### 6:35 — Awards + next steps (25 min)
Named awards; the **Monday Playbook**; which use cases graduate to MAP/POV; follow-up cadence.

### Hackathon tracks (= the focus-5, each a layer they already met)
1. **Finance controlling copilot** (#1) — variance Q&A → recommended action; UC metric views.
2. **SCM control tower copilot** (#2) — OTIF/inventory/service explained → intervention.
3. **Supervisor Agent** (#3) — route Finance/SCM/Commercial under OBO. *(flagship)*
4. **AI governance & policy agent** (#4) — AI Gateway + OBO + payload logging as a controllable layer.
5. **Commercial action assistant** (#5) — account/market signals → next-best-action.
- *Adjacent, allowed:* **#6 Forecast planner (MMF, Paints EMEA)** and **#18 Pricing & quote agent** as the densest act-end-to-end build.

**Every track ships with its own forkable starter + sample data + 5 default golden questions.**

### Judging rubric
| Criterion | Weight |
|---|---:|
| Business value / measurable ROI (ties to a stated Akzo priority) | 30% |
| Technical execution (works end-to-end: deployed app OR working endpoint + trace) | 25% |
| Platform depth used *with intent* (not feature-bingo — governance, routing, eval design) | 20% |
| Innovation (agents that act / external tool-calling) | 15% |
| Demo quality (5-min narrative + executable evidence) | 10% |

---

## Logistics & risks (carried from the master plan)
- **Headcount ~15-20** → 4-6 teams of 3-5. **Roster:** 1 presenter + 1 ops/permissions owner + **1 rover per 5-6 builders** (preview/permission-heavy).
- **Region:** Azure **West Europe** (confirm Akzo's actual workspace region). Per-feature status is mixed GA/Preview — cite status per feature, *don't* claim "fully GA." Avoid UK South.
- **Compliance:** partner-powered AI + hosted LLM judges send data to Azure-OpenAI-class endpoints. **Already acceptable to Akzo** (extensive Azure AI Foundry user) — non-blocker, noted for the record.
- **Build tool = Genie Code (in-workspace).** No local install / PAT. Requires **partner-powered AI enabled** (account + workspace). Use **side-pane** Genie Code (full-page is Beta).
- **`mcp-ai-dev-kit` App is the build critical path AND an unproductized internal FE App.** Pin a known-good commit, pre-install per workspace, pre-record the happy path, make **fallback reference notebooks the default** if its skills don't load by Day 0.
- **Supervisor Agent prereqs (Day-0 gates, verify per participant):** serverless + UC + Model Serving + nonzero serverless budget + supported region + **explicit end-user access to each subagent/tool** (OBO = Public Preview) + **workspace is NOT Enhanced Security & Compliance** (ESC unsupported for Supervisor — confirm with Akzo before relying on the flagship). Management SDK = Beta.
- **Genie throughput:** workspace-level caps (~20 UI Q/min; API free tier ~5 Q/min best-effort). With 15-20 builders, hands-on is one-query-per-pair, never simultaneous load testing.
- **AI Gateway:** Beta; inference-table logs best-effort + lag up to ~1h. Use preseeded logs for the "see" beat; configure only one control live.
- **Lakebase governance:** UC-registered Lakebase is read-only; direct access uses Postgres roles independently. Demo writes via app/service identity + approval + audit, not OBO.
- **Azure throttling:** recurring Akzo cluster/subnet RCAs — pre-stage serverless; Vocareum backup.
- **Genie Code PAYGO** from 2026-07-06 — set room budgets; confirm concurrent rate limits with the account team; prebuilt notebooks as the rate-limit fallback.

## Open items = delivery gates (must close before Day 0)
- [ ] Re-skin `data/` → Akzo coatings (Finance/SCM/Commercial synthetic tables, SDS/contract PDFs, Genie instructions, VS index, eval cases). **Assign owner; 3-5 SA/DE days.** Not a rename.
- [ ] **Pre-stage everything** (facilitator-built before Day 0): 3 Genie spaces + metric views, the Supervisor Agent, RLS/ABAC personas, Lakebase + approval App, MLflow tracing + judge + default golden-question sets, gateway routes + preseeded logs.
- [ ] Build the 7 Day-1 reference notebooks (one per layer) + **one forkable Day-2 starter per track** (all 5 + 2 adjacent), each with sample data + 5 default golden questions.
- [ ] **Day-0 dry-run end-to-end with 2 test personas** (controller + planner): partner-powered AI, Genie Code + preview toggles, mcp-ai-dev-kit skills, Lakebase, Apps perms, VS index, KA/Supervisor, UC/RLS whoami (OBO), **ESC check**, FM quota, Git egress, **recorded cold-open backup + static traces**.
- [ ] Confirm workspace region + serverless capacity (Yves / Tugce).
- [ ] Deploy `mcp-ai-dev-kit` App + enable partner-powered AI + set Genie budgets.
- [ ] Mock Celonis/Moveworks/SharePoint MCP endpoint for the external-tool track.
- [ ] Finalize pre-read doc + distribution channel.
