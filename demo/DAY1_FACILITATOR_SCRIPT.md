# Day 1 — Facilitator Script

**Workshop:** AkzoNobel × Databricks Agentic AI Workshop
**Day 1 theme:** "The whole game, peeled." Show one finished agent, then peel it layer by layer — from AI in SQL up to a coded agent that acts behind an approval gate.
**Audience:** 15–20 AkzoNobel builders, in person, Pune. **They use Azure AI Foundry extensively** — so every section anchors the new capability against what they already know, and the Q&A is pre-loaded with Foundry comparisons.
**You:** leading from the front off a **pre-provisioned reference workspace** (everything already loaded and verified). Attendees build in **their own workspaces, in parallel** — they live-clone the repo and self-provision as the day goes.

> **The one-line frame to repeat all day:** *"Foundry is where you build the agent. Databricks is where the agent lives next to your governed data — with the lineage, row-level security, and audit that a controller will actually sign off on."* Land this in the intro, then let each section prove one slice of it.

> ## ⚠️ READ FIRST — the delivery model changed
> **Vocareum loads nothing.** No preloaded notebooks, no preloaded data. Every attendee **clones this repo into their own Databricks workspace and provisions their own resources live**, in parallel with you. You teach from a reference workspace that is already green; they build theirs as you go.
>
> This has one hard consequence: **the slow provisions (data load, Genie, Lakebase, Vector Search, mock-systems app) must be kicked off early and bake in the background** while you teach the fast stuff. The morning is sequenced so that by the time a block *needs* a resource, it finished provisioning two blocks ago. The **"Provisioning relay"** below is the single most important thing to run on time — if it slips, the afternoon blocks have no Lakebase / no mock app and you're narrating, not demoing.
>
> **Golden rule:** *you* always demo from the green reference workspace so the room never waits on a cold-start. Attendees' own builds are the hands-on; a few will lag and that's fine — they catch up at the breaks and over lunch.

---

## Before the room fills (T-30 min) — YOUR reference workspace

You demo from a workspace that is **already fully provisioned and verified green** (the one used to dry-run every L200 chapter). Confirm it's still green so you never cold-start on the projector.

| Check | Command / action | Pass looks like |
|---|---|---|
| Catalog + schema set | `echo $AKZO_CATALOG $AKZO_SCHEMA $DATABRICKS_WAREHOUSE_ID` | all non-empty |
| Data loaded | open `<schema>.margin_actuals` in Catalog Explorer | 13 tables flat in your personal schema exist |
| FM endpoint queryable | run cell 4 of `00_sql_ai_functions` (the `OK` probe) | returns `OK` |
| Genie spaces live | open `genie/space_ids.json`, click the Finance space | space opens, tables attached |
| Vector index built | Catalog Explorer → `<schema>.chunks_idx` | index = ONLINE (needed for Knowledge Assistant live) |
| Lakebase up | Compute → Database instances | one instance AVAILABLE |
| Mock systems app | open the app URL | health page loads (needed for the afternoon action demo) |
| Finished agent open | supervisor app / `quote-agent` in a browser tab | loads, ready for the cold-open |

**Tabs to have open and parked** (so you never fumble a URL on the projector):
1. The finished supervisor (or quote) app — the cold open.
2. `L100-foundations/00_sql_ai_functions.ipynb`
3. The **New → Agent** dialog (Agent Bricks picker).
4. A Genie space (Finance).
5. `02_agent_evaluation.ipynb` and `03_short_term_memory.ipynb`
6. MLflow experiment UI (empty, will fill during eval).
7. Terminal in `L100-agent-langgraph/` ready for `uv run start-app`.
8. The L200 notebooks `01`, `02`, `06`.

---

## The Provisioning Relay — what ATTENDEES run, and WHEN

Because Vocareum loads nothing, each attendee provisions their own workspace live. The trick: **start the slow things first so they finish before the block that needs them.** Project this table and drive it from the front — call each "kick off step N now" at the wall-clock marker. Steps are the `SETUP.md` checklist, re-ordered for parallelism and pinned to the agenda.

| When | Attendees kick off | Bakes for | Ready in time for |
|---|---|---|---|
| **09:00 welcome** | **Clone repo** (Git folder) + set `AKZO_CATALOG`, `DATABRICKS_WAREHOUSE_ID`; **start `data/load_to_uc.py`** (3 schemas, 13 tables, 14 PDFs — runs a few min) | ~5–8 min | L100 SQL block (09:30) |
| **09:00, same breath** | **Enable Lakebase** → create instance (slow to go AVAILABLE); **enable Vector Search** endpoint `akzo_workshop_vs`; **enable Databricks Apps** | 10–20 min | Lakebase → memory (11:40); VS → KA (10:15) + L200 ch5 |
| **09:30 (during SQL block)** | Confirm data load finished; **create the 3 Genie spaces** (`genie/create_genie_spaces.py` — fast) | ~2 min | no-code Genie build (10:15) |
| **10:15 (during no-code block)** | Kick off **`05_document_intelligence`** once VS is up, to build `chunks_idx` (so KA has an index) | ~10 min | KA section live + afternoon ch5 |
| **11:00 break** | **Deploy mock-systems app** (`deploy/deploy_mock_systems.sh`) — needs Apps enabled | ~5–10 min | action plane (14:00) |
| **lunch** | Catch-up buffer: anyone whose Lakebase / mock app / index lagged finishes here | — | L200 afternoon |

> **You don't wait on any of this.** Every demo *you* run is on the green reference workspace. The relay is for the attendees' own builds; the timeline guarantees their resource is ready by the time they (and you) reach the block that uses it. When you start a block, ask "who's got their X green?" — if most do, they follow hands-on; stragglers watch your screen and catch up at the next break.

> **Provisioning gotchas to pre-empt** (call these out at 09:00 so they don't derail mid-morning):
> - **Wrong catalog** is still the #1 issue — leave the `catalog` widget blank to use `current_catalog()`, or set it to the catalog they ran `load_to_uc.py` into. Mismatch = "table not found."
> - **Lakebase is the long pole** — if they don't enable it at 09:00, memory (11:40) and the whole afternoon action plane have nothing to write to. Push it hard at minute one.
> - **Vector Search before the index** — `05_document_intelligence` can't build `chunks_idx` until the VS endpoint exists. Enable VS at 09:00.
> - **Apps enabled before the mock deploy** — the action plane's external calls need the mock-systems app, which needs Apps enabled. Flag at 09:00, deploy at the break.
> - **Permissions** — they need `CREATE SCHEMA/VOLUME/CONNECTION` in their catalog and `CAN_USE` on a serverless warehouse. An attendee without these can pair with a neighbor and still do every hands-on.

---

## The arc of the day (what each block proves)

```
TEACH (you, on the green reference workspace)        PROVISION (attendees, baking in parallel)
09:00  Welcome + cold open + setup                    ▶ clone · start data load · enable Lakebase+VS+Apps
09:30  L100 AI from SQL                                ▶ data load finishes · create Genie spaces
10:15  L100 no-code types (Genie, KA, ...)            ▶ kick off doc-intel → chunks_idx (~10m)
11:00  break                                           ▶ deploy mock-systems app · confirm Lakebase AVAILABLE
11:15  L100 eval/memory/MCP                            ▶ Lakebase now used for memory
12:15  lunch                                           ▶ CATCH-UP buffer: any lagging resource finishes here
13:00  L200 tools + MCP server                         ▶ Genie ids + UC functions in play
14:00  L200 action plane (act: stage→approve→exec)     ▶ Lakebase + mock app both needed now
14:50  L200 memory (short+long-term)/deploy/AI Gateway  ▶ deploy own agent as a Databricks App
15:30  Hackathon kickoff                               ▶ pick track · fork README
```

The left column is what *you* demo (always green, never waits). The right column is each attendee's own provisioning, sequenced so the resource a block needs finished one or two blocks earlier. **The relay is the spine of the day — miss a kickoff and that attendee's afternoon block has nothing to run on.**

The whole day is one story: **Paints EMEA gross margin fell ~8.9pp in Q2 2026** (39.6% → 30.7%). Finance sees the margin drop, SCM holds the cause (a Rotterdam→DACH lane lead-time spike crushing OTIF), Commercial holds the effect (three EMEA accounts crossing churn risk). Every demo question pins to this thread so results are always clean and the narrative compounds.

---

# 09:00–09:30 · Welcome, cold open, setup

**Slides:** 1 (cover), 2 (welcome/Pune), 3 (objectives). Hold slide 3 up while you talk.

### Talk track (≈4 min)
"Two days. By tomorrow evening your team ships a governed agent that acts on coatings data — deployed, traced, demo-ready. Today we learn the whole stack by taking one finished agent and peeling it layer by layer. You'll see there's no magic — just a few primitives, composed."

### Cold open (≈5 min) — show the finished thing FIRST
Switch to the parked supervisor/quote app tab. Don't explain architecture yet. Just **use it**:
- Ask: *"Why did Paints EMEA margin fall in Q2, and which accounts are now at risk?"*
- Let it route across Finance + SCM + Commercial and return one fused answer with citations and a routing trace.
- One line: "That's where we're going. Now let's tear it down to the smallest piece it's built from."

> **Why cold-open the finished agent:** this audience builds in Foundry already. They're not impressed by "a chatbot." They're impressed by *governed, cross-domain, traced, and it acts*. Show the destination so every primitive after this has an obvious home.

### Setup checkpoint + kick off the provisioning relay (≈15 min)
**This is the most time-critical block of the day.** Nothing is preloaded — everyone provisions live, so the slow resources must start baking *now* or the afternoon has nothing to run on. Project the **Provisioning Relay** table and drive it from the front:

1. **Clone the repo** into their workspace as a **Git folder** (Workspace → Create → Git folder, URL from the README). ~1 min.
2. **Set the two values everything reads:** `AKZO_CATALOG` (a catalog they can write to) and `DATABRICKS_WAREHOUSE_ID` (a serverless warehouse).
3. **Start the data load now — don't wait for it:** run `data/load_to_uc.py`. It takes a few minutes; it bakes while we do the SQL block. (Creates the `akzo_*` schemas, 13 tables, 14 PDFs.)
4. **In the same breath, enable the long-pole services** so they're AVAILABLE by the afternoon: **Lakebase** (create an instance), **Vector Search** (endpoint `akzo_workshop_vs`), **Databricks Apps**. These take 10–20 min to come up — that's exactly why we start them at minute one.
5. Open `00_sql_ai_functions.ipynb`, run cell 1 + cell 4 (the `OK` probe). Green probe = their model endpoint works even while data still loads.

Helpers sweep the room for red. **Don't block the agenda on stragglers** — you teach the SQL block from the green reference workspace regardless; anyone whose load is still running watches and catches up. The only thing that *must* land here: everyone has **kicked off** the data load and **enabled** Lakebase + Vector Search + Apps. If those three aren't enabled by the time you leave this block, the afternoon degrades to narration.

### Anticipated questions
- **"We already orchestrate agents in Azure AI Foundry. Why move?"** → "You don't have to move your models or your IDE. The pitch isn't 'better orchestration' — it's *where the agent runs*. Foundry agents reach into your data over connectors; here the agent runs inside the governance boundary, so row-level security, lineage, and audit are automatic, not bolted on. We'll prove that concretely three times today."
- **"Is this Databricks' answer to Foundry / Copilot Studio?"** → "Overlapping but different layer. Agent Bricks is the managed agent surface; the moat is Unity Catalog underneath — one permission model for tables, models, functions, and agents."
- **"Which models can we use?"** → "Any Foundation Model endpoint, plus external models (including Azure OpenAI) fronted through the AI Gateway. No lock-in — we'll show the Gateway this afternoon."

---

# 09:30–10:15 · L100 — AI from SQL

**Slides:** Day 1 section break (4), then drop to the notebook. This block is 90% notebook, 10% slide.
**Notebook:** `L100-foundations/00_sql_ai_functions.ipynb`. Run top to bottom, narrating each function.

### The big idea (≈2 min)
"Before any agent, the atom. On Databricks you call an LLM **from SQL** — no endpoint to deploy, no orchestration. The model is just another function over your rows. Everything we build today is these calls, composed."

### Demo flow (run these cells, narrate the bolded point)

| Cell | Function | Say this | Watch for |
|---|---|---|---|
| 4 | `ai_query` probe | "Smoke test — the endpoint answers." | `OK` |
| 6 | `ai_query` over a table | "**Batch inference in pure SQL** — one prompt, every row. This is the workhorse." | 5 positioning notes |
| 8 | `ai_classify` | "Zero-shot labels, no training set. This is the Text Classification Agent Brick, naked." | accounts → segments |
| 10 | `ai_extract` | "Named fields out of messy text → typed columns. This becomes Information Extraction." | product/flash_point/etc |
| 12, 14 | `ai_parse_document` | "Raw PDF → structured elements. Step one of every doc pipeline." | exploded elements table |
| 16 | `ai_summarize` | "Long → headline a controller can scan." | 20-word summary |
| 18 | `ai_mask` | "**Governance before the prompt** — PII never reaches the model. Remember this; it's the spine that deepens all day." | masked name/email/phone |
| 20 | `ai_forecast` | "A time series forecast in one call. This seeds the Forecast Planner hackathon track." | forecast + confidence band |

### Land the wrap-up (cell 21)
Project the function→Agent Brick→track mapping table. "Every one of these maps to a no-code agent type you'll build in 45 minutes, and to a hackathon track. Hold that mapping."

> **🔁 RELAY — call this before you leave the block:** "Data load done? Good — **create your 3 Genie spaces now** (`genie/create_genie_spaces.py`, ~2 min) so they're ready for the no-code block. And check your **Vector Search** endpoint is up — we'll need it for the document index next." This keeps the relay one step ahead of the agenda.

### Anticipated questions
- **"In Foundry we'd call Azure OpenAI from code / Prompt Flow. Why SQL?"** → "Because the data's already here and so is the governance. `ai_query` runs under your Unity Catalog identity, on the warehouse, with the result auditable. No data leaves the boundary to reach a model behind a connector. For a 13-table batch job, that's the difference between a governed pipeline and an export."
- **"What model is behind `ai_query`?"** → "Whatever endpoint you name — a Databricks Foundation Model, or an external one (Azure OpenAI included) via the Gateway. The SQL doesn't change when you swap models."
- **"`ai_mask` — is the unmasked text ever sent to the model?"** → "No. Masking happens before the prompt is built. That's the point: private by construction."
- **"Cost of running `ai_query` over millions of rows?"** → "Pay per token like any inference; for big batches you'd pick a smaller/cheaper endpoint and the Gateway gives you rate + spend caps. We show that in the governance block."
- **"`ai_forecast` vs a real forecasting model?"** → "It's a strong one-call baseline for the demo and the planner track. For production you'd benchmark it against MMF / a trained model — but it gets a planner to a first answer in one line."

---

# 10:15–11:00 · L100 — No-code Agent Bricks types

**Guide:** `L100-foundations/01_agent_bricks_types.md`. This block is **UI-driven** — you click, they follow.
**Slides:** none; the **New → Agent** dialog *is* the slide.

### The framing (≈3 min)
Open **New → Agent**. Project the picker. "Five primitives you just ran in SQL, now as managed agents — plus the escape hatch and the supervisor." Walk the filter tabs:
- **Chat** (Genie, Knowledge Assistant, Supervisor) — you ask in plain language.
- **Functions** (Extraction, Parsing, Classification) — one AI call on input.
- **Custom** — code your own.

Map each type to the SQL function from the last block. "Same atom, managed wrapper — you get a UI, an endpoint, eval, and tracing for free."

> **🔁 RELAY — start of this block:** "Vector Search up? **Kick off `05_document_intelligence` now** to build your `chunks_idx` — it takes ~10 min, so start it before we build the Knowledge Assistant and it'll be ready by the time you try it yourself." You build KA live on the reference workspace either way.

### Live builds (pick 2 to build fully, name the rest)
Time is tight — **build Genie + one Function type end to end; narrate the others.** Attendees build *their own* Genie space alongside you (it's fast and needs only the loaded tables). The Function types (extract/parse/classify) also work the moment their data load finished — encourage them to point-and-build one while you narrate.

**1. Genie Space (build it — this is the keystone).**
- New → Genie space, attach `margin_actuals`, `products`, `fx_rates` from your personal schema. Name it `Finance Controlling`.
- Paste the grounding primer (grain = SKU×region×month, EUR, certified metric `gross_margin_pct`).
- Ask the golden question: *"Which product line had the lowest gross margin percent in EMEA last quarter?"*
- **Show the generated SQL**, not just the answer. "Genie writes SQL, runs it on the warehouse **under your identity** — so row filters apply. This becomes the Finance domain of the supervisor you saw at 9am."

**2. Knowledge Assistant (you build it on the reference workspace; attendees' own may still be indexing).**
- New → Agent → Knowledge Assistant, point at `<catalog>.<schema>.chunks_idx`.
- Ask: *"What is the flash point and the main hazard on the SDS for the Interpon powder coatings?"*
- **Click the citation.** "The citation is the proof the answer is grounded in *your* document, not the model's memory. That's RAG."
- **Attendees:** their `chunks_idx` is only ready if they kicked off `05_document_intelligence` at the start of this block (the relay). Most won't have it yet — that's fine, they watch yours and build their own KA after lunch when the index is ONLINE. Don't stall the room waiting on indexes.

**3–5. Information Extraction / Document Parsing / Text Classification (narrate fast).**
"These three are the UI face of `ai_extract`, `ai_parse_document`, `ai_classify` — you just ran all three in SQL. Each is the seed of a hackathon track: doc extraction, the parse-first pipeline, and ticket/email triage."

**6 + 7. Code-your-own + Supervisor (preview only).**
"When no managed type fits, you drop to code — that's after lunch. And the Supervisor on top orchestrates all of these — that's tomorrow's flagship. The supervisor is only as good as the domain agents it routes to, which is why we ground Genie carefully."

### Anticipated questions
- **"This is like Foundry's agent catalog / Prompt Flow templates. What's different?"** → "Two things. One: each type is wired to Unity Catalog data and inherits its permissions — no separate data connection to secure. Two: Genie isn't a generic RAG-over-tables; it's grounded with certified metrics so it uses *your* definition of gross margin, not one it guessed. That grounding is the difference between a demo and something Finance trusts."
- **"Can we ground Genie on our real semantic model / metric definitions?"** → "Yes — that's exactly the Instructions + certified-metric block. In production you'd pull these from your existing definitions. We pre-loaded them from `genie/*_space.md`."
- **"Knowledge Assistant vs Azure AI Search RAG?"** → "Same RAG shape. Difference is the index lives in Unity Catalog with the source docs, the chunks, and the lineage in one governed place — and the assistant is queryable, evaluable, and serveable from the same platform."
- **"Do these no-code agents lock us in?"** → "No — type 6 is 'bring your own framework,' and everything wraps the same MLflow interface. We prove that after lunch by hand-coding one."
- **"How do non-engineers build these?"** → "Genie and Knowledge Assistant are genuinely no-code — a controller can build and ground a Genie space. The Function types are point-and-fill. That's the adoption story for your business users."

---

# 11:00–11:15 · Break

Leave the Genie space and a citation on screen. Tell them where we go next: "Three things after the break — make it *trustworthy*, make it *remember*, and write our *first* line of agent code."

> **🔁 RELAY — the break is when the mock-systems app gets deployed.** Before people scatter: "If you want to run the *action* labs yourself this afternoon, **deploy the mock-systems app now** (`deploy/deploy_mock_systems.sh`, needs Apps enabled) — it bakes over the break. Also confirm your **Lakebase instance is AVAILABLE**; memory is the very next thing after the break and the whole afternoon writes to it." Anyone whose Lakebase isn't up yet: this break is their last clean chance before it's on the critical path.

---

# 11:15–12:15 · L100 — Eval, memory, first coded agent (MCP)

Three notebooks back to back. Tightest L100 block — keep momentum.

## 11:15–11:40 · Evaluation with MLflow judges
**Notebook:** `02_agent_evaluation.ipynb`.

### Frame (≈2 min)
"A controller won't trust an answer because a chatbot said so. **No AI without measurable value.** This is the LLMOps spine — it deepens every tier. Here: trace an agent, score it with LLM judges."

### Demo flow
- Cell 2: `%pip install mlflow` + restart (warn them it restarts Python — expected).
- Cell 5: the tiny `@mlflow.trace` agent. "One decorator = every call recorded, inputs and outputs."
- Cell 7: the eval set with `expected_facts`. "Correctness checks facts, not wording."
- Cell 9: `mlflow.genai.evaluate` with **Correctness, RelevanceToQuery, Safety, + a custom Guidelines (conciseness) judge.** Read the aggregate aloud.
- Cell 11: open the per-row table. "Here's *why* each answer passed or failed — the rationale. That's the signal you act on."
- Open the MLflow experiment UI on the projector — show the run landed.

### Anticipated questions
- **"We evaluate in Foundry with its evaluation flows / groundedness metrics. Difference?"** → "Conceptually the same — LLM-as-judge plus reference facts. Difference is the eval runs *in MLflow alongside the model registry, traces, and the serving endpoint*, so the same eval set becomes a regression gate in CI and then production monitoring on live traffic. One lineage from dev to prod. You'll see prod monitoring tomorrow."
- **"Judge marking its own homework?"** → "Good instinct — in L200 the judge is a *different* model than the agent under test. Here it's one model for simplicity."
- **"Can we bring our own metrics?"** → "Yes — the Guidelines judge is a custom natural-language rule. You write the rubric in plain English."

## 11:40–12:00 · Short-term memory on Lakebase
**Notebook:** `03_short_term_memory.ipynb`.

### Frame (≈2 min)
"A single call agent forgets everything between turns. Real assistants remember. We store each turn in **Lakebase** — managed Postgres on Databricks — keyed by thread id."

### Demo flow
- Cell 2: install `psycopg` + restart.
- Cell 4: connect. **Stress the credential:** "Short-lived token minted by the SDK, scoped to my identity. No static password in the notebook."
- Cell 6: the thread table.
- Cell 10: **the money moment.** Turn 1 states "I'm Priya, I manage EMEA finance." Turn 2 asks "Which region do I manage?" — agent recalls EMEA. "Memory works."
- Cell 12: a *different* thread asks the same — agent doesn't know. "Thread isolation. Memory is scoped, not global."
- Cell 14: show the stored rows. "Durable, queryable, low-latency — the same store a production agent reads every request."

### Anticipated questions
- **"Why Lakebase and not Cosmos DB / Postgres we already run?"** → "You could use any Postgres. Lakebase's pitch: serverless, sub-second launch, git-like branching, and it's governed in the same plane as your lakehouse — so agent memory isn't a separate database to secure and operate. For an agent that needs low-latency state next to governed data, it removes a moving part."
- **"Is conversation text encrypted / access-controlled?"** → "This demo stores raw text on synthetic data. In production you add per-user scoping, retention, and access controls — the notebook calls that out explicitly."
- **"Short-term vs long-term memory?"** → "This is thread-scoped short-term — what we just said. L200 ch8 adds **long-term**: durable per-user facts on a Lakebase `pgvector` store, recalled by meaning across sessions. We build it this afternoon; L300 wires it into the deployed supervisor."

## 12:00–12:15 · First coded agent — LangGraph + managed MCP
**Folder:** `L100-foundations/L100-agent-langgraph/`. This is a **terminal + browser** demo, not a notebook.

### Frame (≈2 min)
"No-code got us far. Now the escape hatch: write the agent. A small LangGraph ReAct agent, wrapped in MLflow's `ResponsesAgent`, that answers finance questions through **exactly one read-only tool** — and that tool comes from a **managed MCP server**."

### What MCP is (say it once, clearly)
"MCP = Model Context Protocol. A standard way for an agent to discover and call tools. Databricks exposes your Unity Catalog functions as a managed MCP server — so the agent connects, lists tools, and calls `coatings_data_lookup`, governed by UC. No client-side SQL, read-only by construction."

### Demo flow
- Terminal: `uv run start-app` (you ran `uv run quickstart` in pre-flight).
- Browser → `http://localhost:3000`. Ask: *"What was Paints EMEA gross margin in Q1 vs Q2 2026?"*
- Answer comes back grounded in the tool's SQL result.
- **Show the MLflow trace** — the tool call is visible. "Same `ResponsesAgent` wrapper as the no-code types: tracing, eval, serving for free. Any framework, any model, no lock-in. This wrapper carries the OpenAI Agents SDK in L200 and the LangGraph supervisor in L300 — identical serving plane."

> **If localhost is flaky:** set `AKZO_LOCAL_TOOL=1` for the in-process Spark fallback (real SQL guard, no live MCP needed), or just show the MLflow trace from a prior run. Don't burn 10 min debugging ports on the projector.

### Anticipated questions
- **"MCP vs Foundry's plugins / function calling / OpenAPI tools?"** → "MCP is the open standard doing the same job — tool discovery and invocation — but vendor-neutral, so the same tool server is callable from any MCP-aware client. The Databricks angle: your UC functions *become* MCP tools automatically, governed by the same permissions as the underlying tables. The tool is read-only because the function is."
- **"Why LangGraph and not Foundry's orchestrator / Semantic Kernel?"** → "Bring whichever you like — that's the whole point of the `ResponsesAgent` wrapper. We deliberately mix LangGraph here, OpenAI Agents SDK in L200, LangGraph supervisor in L300 to prove it's framework-agnostic."
- **"Can the tool write/act?"** → "Not this one — read-only by design. Actions are a separate governed plane, which is the first thing after lunch."

### Close the morning
"This morning: AI in SQL → managed agents → trustworthy → remembers → first coded agent with a governed tool. This afternoon we make the agent *act*, build our *own* tool server, deploy it, and govern it at scale."

---

# 12:15–13:00 · Lunch

> **🔁 RELAY — lunch is the catch-up buffer.** This is the designed slack in the timeline. Before people eat, post the afternoon's hard requirements on screen so stragglers self-serve: **(1) Lakebase AVAILABLE, (2) mock-systems app deployed, (3) `chunks_idx` ONLINE.** Have a helper float to unblock anyone red on these — after lunch the L200 blocks assume all three. Everything the afternoon needs should be green by 13:00.

---

# 13:00–14:00 · L200 — Tools + MCP server you build

**Slides:** Day-1 afternoon doesn't need slides; the notebooks carry it. Optionally show the L200 README "three spines" table once.
**Notebooks:** `L200-capabilities/01_governed_supervisor.py` (first half) + `06_custom_agents_and_mcp.py` (Parts A–C).

> **Pacing reality:** you cannot run every L200 cell live in an hour. **Run the highlighted beats; scroll-narrate the rest.** Each notebook has `# Expect ...` comments — read those aloud when you skip a run.

### Beat 1 — Governed reads under your identity (`01`, Parts A–B) ≈20 min
- Frame: "This morning's Genie ran under your identity. Now see *why that matters*. We put a **row filter** on the finance data and ask the same question as two different people."
- Run Part A (the finance domain agent: text2SQL + reasoning over the finance tables). Watch the *Generated SQL*; compare to the `# Expect` comment.
- Run Part B (**OBO + UC row-level security**): same question, different rows per user. "This is the governance plane for **reads**. On-behalf-of auth + row filters — the model never sees rows the user can't."
- Land it: "**This is the Foundry gap we keep naming.** A Foundry agent reaching your data through a connector authenticates as the *connector*, not the *user*. Here the agent inherits the asking user's row-level permissions. That's what lets a controller trust one shared agent across regions."

### Beat 2 — Build & register your own MCP server (`06`, Parts A–C) ≈30 min
- Part A — **Managed MCP:** connect a `DatabricksMCPClient`, list the tools the server exposes, call one. "Your UC functions, exposed as governed tools."
- Part B — **The LangGraph agent:** `create_react_agent(ChatDatabricks, tools)` wrapped as `ResponsesAgent`. "Same wrapper as this morning, more tools."
- Part C — **Log → register → deploy:** `mlflow.log_model(resources=...)` → register to Unity Catalog → (optionally) `agents.deploy()`. "The agent is now a **governed UC asset** — versioned, permissioned, servable, and usable as a supervisor subagent tomorrow."
- (Skip the live `agents.deploy` unless time allows — it's slow. Narrate it; show a pre-deployed endpoint if you have one.)

### Anticipated questions
- **"OBO / row-level security — can Foundry not do this?"** → "Foundry can pass a user token to some connectors, but the *data* permissions still live in whatever store you're hitting, managed separately. Here it's one model: the same UC row filter governs the table, the Genie space, and the agent. One place to reason about 'who sees what.'"
- **"Registering an agent in Unity Catalog — what does that buy us?"** → "Same thing registering a model or table buys you: versioning, access control, lineage, and discoverability. Your agent becomes a first-class governed asset, not a script on someone's laptop."
- **"Can our existing Azure OpenAI deployments be the model behind these agents?"** → "Yes — register them as external endpoints behind the AI Gateway (next block but one) and the agent code doesn't change."
- **"Is the MCP server we 'build' just our UC functions, or a separate service?"** → "For the managed path it's your UC functions exposed automatically — no service to run. You can also stand up a custom MCP server for tools outside UC; that's the extensibility path."

---

# 14:00–14:50 · L200 — The action plane (agents that act)

**Notebook:** `L200-capabilities/02_agents_that_act.py`. **This is the afternoon's centerpiece** — the moment the agent stops talking and starts *doing*. Give it room.
**Prereq live:** Lakebase up + Mock Systems app reachable. On *your* reference workspace both are green. For attendees: Lakebase was enabled at 09:00 and the mock app was deployed over the 11:00 break (the relay) — confirm with a quick "who's got their mock app URL?" before you start. Anyone missing one runs the lab read-only against your screen and wires their own at lunch.

### Frame (≈4 min) — draw the two ladders on the whiteboard
**Action maturity ladder:**
```
L1 Recommend → L2 Stage & approve → L3 Execute externally → L4 Autonomous
```
"This morning everything was read-only. Now the agent acts — but **never by calling a raw API.** Every action travels one governed plane so an exec can sign off on autonomy. We build L1→L3 now; L4 (autonomous loop) is its own notebook."

**Two governance planes — say it plainly:**
```
READS (this morning)              WRITES / ACTIONS (now)
OBO + UC row-level security       app identity + policy guardrails
per-user truth on UC tables       + human approval + full audit trail
                                  on Lakebase (Postgres roles)
```
"'Who can *see* what' and 'who can *change* what' are two different questions. We keep the planes separate on purpose."

### Demo flow (the staged → approve → execute story)
1. **Setup** — show the short-lived DB credential pattern again (the `pg()` context manager). No long-lived secret.
2. **The Action Plane tables** — `actions`, `action_events`, `action_policies`. "A state machine plus a guardrail engine plus an audited executor."
3. **Stage an action** (L1→L2) — the agent *proposes* an action (e.g. raise a price-review ticket / notify the account team). It lands in `actions` as `staged`, evaluated against policy guardrails (spend cap, region, action type).
4. **The approval gate** — show a staged action being **approved by a human**. "Nothing fires without this. This is the line execs care about."
5. **Execute externally** (L3) — approved action POSTs through the **Unity Catalog HTTP connection** `akzo_external_systems` to the Mock Systems app. Show the call land in the mock app.
6. **The audit trail** — query `action_events`. "Every transition logged end to end — staged, approved, executed, by whom, when. That's the auditability that turns 'an agent that acts' from scary into shippable."

### Anticipated questions
- **"Foundry agents can call APIs / Logic Apps / actions too. What's new?"** → "Calling an API is easy anywhere. The hard part is *governing* it: a guardrail engine that blocks actions over a spend cap or outside a region, a mandatory human approval step, and an immutable audit trail — all as managed infrastructure, not custom middleware you write and maintain. That's the difference between a demo action and one your risk team approves."
- **"Why route through a UC HTTP connection instead of calling the API directly?"** → "So the outbound call is a *governed* asset — permissioned, logged, and revocable in one place. The agent can't reach an endpoint the connection doesn't allow. It's the egress equivalent of a row filter."
- **"Writes go to Lakebase, not Unity Catalog — why?"** → "UC-registered Lakebase is read-only; writes go through Postgres directly with Postgres roles. Reads are governed by UC RLS; writes by the action plane. Deliberately separate planes."
- **"Can a human reject, not just approve?"** → "Yes — reject is a state transition like any other, and it's audited. You can also auto-approve under a threshold and escalate above it; that's the policy engine."
- **"What stops the agent from staging a million actions?"** → "Guardrails: rate, spend cap, action-type allowlist — evaluated before anything reaches the approval queue."

---

# 14:50–15:30 · L200 — Memory, deploy, AI Gateway

Three quick beats. **Lighter than the action block** — show the shape, the depth is in the notebooks they'll keep.

### Beat 1 — Memory wired into the coded agent: short-term *and* long-term (≈10 min)
"This morning memory was a standalone notebook — *short-term*, one thread of turns. Same Lakebase store now wired into a coded agent. Then **`08_long_term_memory`** adds the other half: **durable, cross-session memory**."
- The contrast is the point: short-term answers *"what did we just say?"* (keyed by `thread_id`); long-term answers *"who is this user, what do they care about?"* (keyed by `user_id`, recalled by **meaning**).
- The money moment: a **brand-new session** — empty thread — still greets the EMEA controller in their preferred headline+bridge format and remembers what they're chasing. "The conversation is gone; the user model survived. That's `pgvector` semantic search on Lakebase — no separate vector DB."
- One line on governance: "`user_id` is bound server-side, so the model can't recall another user's memories — and `delete_memory` is the right-to-be-forgotten primitive. For prod you'd add a Postgres row-level boundary on top."
- If short on time: skip the live agent loop, just run the Part B search cell (semantic recall scores) and the Part D fresh-session cell.

### Beat 2 — Deploy as a Databricks App (≈12 min)
- Use the L100 LangGraph agent (already built) as the deploy example: `databricks bundle deploy` → `databricks bundle run`.
- "The agent is now a running App with a URL — the same kind you used in the 9am cold open. Its service principal needs `SELECT` on the data it reads; you grant that in UC, it's not baked in."
- If a deploy is too slow live, show a **pre-deployed app** and walk the `app.yaml` env vars instead.

### Beat 3 — AI Gateway: govern at scale (`04`, Part B) ≈12 min
- Frame: "Two questions an exec asks before any agent ships: *how do I know it's right* (eval, this morning) and *how do I govern it at scale* (now)."
- Show the Gateway as **one front door**: routes, rate limits, spend caps, and **UC payload logging** (every request/response logged to a UC table for chargeback and audit).
- "This is also where your **Azure OpenAI** endpoints plug in — front them through the Gateway and every agent gets the same rate, spend, and logging controls regardless of which model is behind it."

### Anticipated questions
- **"AI Gateway vs Azure API Management / Foundry's content filters + quotas?"** → "Same category — a governance front door for model traffic. The Databricks angle: the payload logs land in Unity Catalog next to your data, so model usage is auditable in the same place and lineage as everything else, and spend is attributable per team. One governance plane instead of two."
- **"Can the Gateway route across providers — Azure OpenAI *and* Databricks models?"** → "Yes — that's a core use: one endpoint, multiple backends, with failover and per-route limits. Your app calls one URL; you swap or split traffic behind it."
- **"Deploying as a Databricks App vs Azure App Service / Container Apps?"** → "If your agent only needs Databricks data and models, a Databricks App keeps it inside the governance boundary with the service principal model — fewer network and secret hops. If you need it in your broader Azure estate, the agent's a registered model you can serve anywhere."
- **"What's the run-as identity for a deployed App?"** → "A service principal you grant explicit UC permissions to. The App can't read anything you didn't grant — same governance as a user."

---

# 15:30–16:00 · Hackathon kickoff

**Slides:** 8 (use-case tracks), 12 (judging rubric). Project the rubric and **leave it up** — teams should design to it from minute one.
**Guide:** `hackathon-starter-kit/README.md`.

### Run of show (≈30 min)
1. **Recap the ladder in one breath (2 min):** "You now have every primitive: AI in SQL, the no-code types, eval, memory (short-term *and* durable long-term), coded agents, tools/MCP, the action plane, deploy, Gateway. Tomorrow you compose them into one use case."
2. **Form teams (5 min):** ~4 people. Suggest the four roles from the kit — Product lead, Data lead, Agent lead, Governance lead.
3. **Pick a track (8 min):** walk the catalog. Six priority tracks:
   - `01-finance-controlling`, `02-multi-domain-supervisor` (flagship), `03-procurement-contracts`, `04-access-provisioning`, `05-forecast-planner-mmf`, `06-pricing-quote-generation`.
   - Point at the **shared narrative**: margin → service → churn. Single-domain tracks own one chapter; the supervisor track makes the whole thread explicit.
4. **Fork the README + first prompt (10 min):** open `tracks/<chosen>` and the matching `starter-prompts/` file. "Use Genie code / the ai-dev-kit skills — `scaffold-copilot` first, then add `add-genie-space`, `add-mcp-tool`, `add-connector` only as needed. **Bias to a thin working loop**: answer or extract → cite evidence → evaluate → add action approval only if the use case needs it. Don't ask Genie code to build the whole app in one shot."
5. **Set tomorrow's bar (5 min):** read the judging rubric aloud — business fit 25, agent quality 25, governance 20, demo completeness 20, reuse 10. "Two judging signals: it *works end to end in one flow*, and it's *governed*. The cold-open at 9am this morning is roughly the bar."

### Anticipated questions
- **"Can we use our own data, not the synthetic coatings data?"** → "Tomorrow, keep it synthetic so the narrative lands and judging is fair. After the workshop, the same patterns drop onto your real UC catalog — that's the point of nothing being hardcoded."
- **"Can we build the agent in Foundry and just deploy here?"** → "If your team's fastest path is to author in a framework you know, do it — wrap it in `ResponsesAgent` and it gets the governed serving/eval/trace plane. The judging cares about the governed, end-to-end result, not the IDE."
- **"How far should we get tomorrow?"** → "One governed data source, one tool or MCP call, one eval set, and — if the use case acts — one approval gate. Thin and working beats broad and broken."
- **"What if our track needs data the setup didn't ship?"** → "Tracks 04, 05, 06, 08 build some data themselves — use the `generate-synthetic-data` skill into your own personal schema."

### Close Day 1
"Today we peeled the whole game. Tomorrow you build your slice of it and demo something deployed, traced, and governed. Pick your track tonight, sleep on the demo story, come in scoped."

---

## Appendix A — Timing cheat sheet (keep on your phone)

| Block | Hard stop | If you're behind, cut |
|---|---|---|
| Welcome + cold open | 09:30 | shorten setup sweep; help in the SQL block |
| AI from SQL | 10:15 | skip narrating `ai_summarize`; keep mask + forecast |
| No-code types | 11:00 | build only Genie live; narrate the rest |
| Break | 11:15 | — |
| Eval/memory/MCP | 12:15 | show MCP via trace only, skip live `start-app` |
| Lunch | 13:00 | — |
| Tools + MCP server | 14:00 | scroll-narrate `06` Part C, skip `agents.deploy` |
| Action plane | 14:50 | **protect this block** — it's the centerpiece |
| Memory/deploy/GW | 15:30 | show pre-deployed app; narrate deploy |
| Hackathon kickoff | 16:00 | trim track walk to the 6 priority tracks |

**Protected demos (do not cut):** the 9am cold open, the Genie generated-SQL moment, the memory recall moment (cell 10), the OBO different-rows-per-user moment, and the full stage→approve→execute→audit action flow.

## Appendix B — The Foundry framing, in one table (your fallback for any "why not Foundry" question)

| They have in Foundry | The Databricks difference to name |
|---|---|
| Azure OpenAI / model catalog | Same models usable here + external endpoints via AI Gateway — no lock-in |
| Prompt Flow / orchestration | Bring any framework; `ResponsesAgent` gives one governed serving/eval/trace plane |
| Connectors to data | Agent runs *inside* the governance boundary — OBO + UC row-level security, per-user truth |
| Evaluation flows | Same judges, but eval → registry → serving → prod monitoring share one lineage |
| Plugins / function tools | Open MCP standard; UC functions become governed tools automatically |
| Actions / Logic Apps | A governed action plane: guardrails + mandatory human approval + immutable audit |
| Content filters / quotas | AI Gateway: routes, limits, spend caps, and UC payload logs next to your data |
| App Service deploy | Databricks App inside the boundary with a service-principal permission model |

**The sentence to keep returning to:** *"It's not that Foundry can't do a piece of this. It's that here, every piece shares one governance plane — Unity Catalog — so a controller or a risk team can sign off on the whole agent, not just the chatbot."*

## Appendix C — Failure recovery (when a live demo breaks on the projector)

| Breaks | Recover with |
|---|---|
| FM endpoint slow/erroring | swap `llm_endpoint` widget to a second endpoint you pre-tested |
| `ai_forecast` preview disabled | the notebook prints the SQL — run it from a SQL warehouse, or just read the `# Expect` |
| Vector index not ONLINE | narrate Knowledge Assistant from the `01_agent_bricks_types.md` screenshots; don't build it live |
| `uv run start-app` / ports | `AKZO_LOCAL_TOOL=1` fallback, or show a prior MLflow trace |
| Genie picks wrong column | refine the Instructions live — this is a *feature* to show ("grounding fixes it"), not a failure |
| Lakebase credential error | re-run the connect cell (token is short-lived); confirm the instance is AVAILABLE |
| Mock app unreachable | show the staged action + approval in Lakebase; narrate the external POST |
| `agents.deploy` too slow | show a pre-deployed endpoint/app; never wait on it live |
| Catalog widget wrong (attendee) | most common attendee issue — reset the `catalog` widget to the catalog they ran `load_to_uc.py` into (or leave blank for `current_catalog()`) |
| Attendee data load still running | expected early — they watch your screen; their tables land in a few min. Don't block the room |
| Attendee Lakebase not AVAILABLE | the long pole — if not enabled at 09:00 it won't be ready for memory/action. Have them enable now and pair with a neighbor for the live bit |
| Attendee `chunks_idx` not ONLINE | they skipped the `05_document_intelligence` kickoff; build KA after lunch once it indexes |
| Attendee mock app not deployed | run the action lab read-only against your screen; deploy `deploy_mock_systems.sh` at lunch |
