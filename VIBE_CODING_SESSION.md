# AkzoNobel Hackathon — Vibe-Coding Session Design (v2: Genie Code)

The centerpiece. Everything in the 2-day workshop centers on **vibe-coding with Genie Code** (Databricks' in-workspace agentic engineering tool) so teams scale up fast and ship working agents/apps during the session. Style modeled on real delivered Databricks workshops (the official Hackathon + Agentic Coding plays, APJ Buildathon, SEMEA GenAI Boost, internal Vibe Coding sessions); pedagogy from Code with Claude 2026.

## The implementation tool = Genie Code (in-workspace)
- **What it is:** native agentic engineering inside the Databricks workspace UI (successor to Databricks Assistant). **Agent mode = GA, default.** Plan → approve → run → read output → auto-fix loop. Generates Python/SQL, Lakeflow pipelines, ML + MLflow, AI/BI dashboards. Governed by each user's Unity Catalog permissions.
- **Why we center on it (not Claude Code/Codex):** **zero local setup** — no install, no PAT, no CLI, no Claude subscription per participant. This sidesteps the identity/auth pain that was the #1 time-sink in every external vibe-coding workshop. Fully governed + in-platform. For a room of AkzoNobel data engineers/scientists, it removes all the laptop-tooling friction.
- **THE UNLOCK — `mcp-ai-dev-kit` App:** native Genie Code writes the code for agents but doesn't deploy them by itself. Deploy the **`mcp-ai-dev-kit` Databricks App once per workspace** → it injects skills (`databricks-agent-bricks`, `databricks-vector-search`, `databricks-model-serving`, `databricks-app-python`, `databricks-genie`) so Genie Code can **scaffold and deploy Knowledge Assistants, Supervisor agents, RAG, and Apps** the best-practice way. Participants invoke with `@skill-name`. **Deploy this before Day 1.**
- **Optional advanced path:** teams wanting IDE-based building can use Claude Code/Codex routed through AkzoNobel's **Unity AI Gateway** (coding-agent integration, Beta). Same MCP/skills (open standards), portable. Keep as a stretch lane, not the default.

## The build loop we teach
**Describe → Generate → Test → Refine → Deploy** (the official play's loop; same as Explore→Plan→Implement→Verify). Anchored on one mental model from the conference: keep context lean, give the agent a way to verify itself, and **plan/requirements first**.

## Style we're copying (from real delivered workshops)
1. **Hands-on early, slides late** — official Strategic Framework rule; SEMEA gets hands-on by minute 30. Intro capped ≤90 min.
2. **Open with a live "magic moment"** — build + run something real in Genie Code in front of the room before asking anyone to build (internal sessions pitched "watch an app land in ~17 min").
3. **Build real, not toy** — every format insists on real use cases.
4. **Tight teams** — 3-5 people, deliberately mix functions; name a team lead.
5. **Time-boxed checkpoints + circulating facilitators** — checkpoints at 1h / midpoint / 1h-before-demos; **1 facilitator per 10-15** builders who unblock, not lecture.
6. **Demos = working code, 5-min hard cap, no slides, celebrate every team.** Optional Builder's Choice peer vote for energy.
7. **Wire the next step on the spot** + hand out a leave-behind guide; set a 90-day velocity goal.
8. **Pre-configure everything** (UC grants, datasets, starter assets, mcp-ai-dev-kit App) so zero build time is lost on setup.

---

> **Run-of-show timing lives in `WORKSHOP_AGENDA.md`** (Day-1 layer blocks + Day-2 sprints). This doc is the Genie Code *tool* reference — mechanics, the build loop, the hands-on exercise template, enablement, and facilitation lessons that the agenda's blocks draw on.

### Hands-on exercise template (AkzoNobel-specific)
In Genie Code, build a **coatings SKU / inventory Q&A agent** over a Unity Catalog table:
1. Open Genie Code via the **sparkle icon (side-pane — the stable path; full-page command center is Beta)**. Confirm mcp-ai-dev-kit skills load (fallback: prebuilt notebook if skills don't appear).
2. **Describe** the goal; let Genie Code propose a plan (review before run — ask-before-execute).
3. EDA + a Genie space / SQL over `@akzo.products`; add Vector Search over coatings datasheets/SDS via `@databricks-vector-search`.
4. Scaffold a Knowledge Assistant / tool-calling agent via `@databricks-agent-bricks`; later a mini Multi-Agent Supervisor.
5. **Verify** with 3-5 test questions; **deploy** as a Databricks App via `@databricks-app-python`.

Pre-bake the sample coatings table + a starter prompt/SPEC so non-experts build, not fight data.

### Graduation criteria
- ✅ Built in Genie Code Agent mode from a stated plan, ask-before-execute on.
- ✅ Agent answers ≥3 NL questions correctly over governed data.
- ✅ A verification check exists and passes (shown, not asserted).
- ✅ Deployed/runnable in-workspace (App or dashboard).
- ✅ Participant can state how they'd repeat this for the next use case.

---

## Top practices to drill (each: why it scales teams fast)
1. **Plan / requirements first** — practitioners hit 90-95% automation by writing a plan before generating; "AI makes assumptions — give it a clear plan and quality soars."
2. **Ask-before-execute** — review the agent's plan before it runs cells; the safety + quality habit.
3. **Reference governed context with `@table` / `@skill`** — Genie Code is platform-native; lean on UC metadata + mcp-ai-dev-kit skills instead of hand-writing API calls.
4. **Give it a verifiable check** — test questions / eval cases close the loop.
5. **Cut losses early** — if iteration gets confused, restart fresh rather than fight it.
6. **One concept per block, build real** — toy demos don't transfer.
7. **Treat the agent like an eager junior** — great recall, questionable judgment; you own the outcome, don't ship what you wouldn't sign off.

## Facilitation lessons (what worked / what flopped)
- **Worked:** pre-configure everything; mix teams; plan-first; magic-moment open; circulating facilitators.
- **Flopped (avoid):** identity/PAT/auth setup ate up to a full day in external sessions — **Genie Code in-workspace removes this** (our biggest de-risk; still pre-grant UC + app perms so demos don't 403). Vague short prompts fail. Fixes rarely land first try — budget iteration. **Judging on pitch polish backfires** (SEMEA killed its use-case contest because polished pitches won over real value) — weight judging to working substance + business value.

## Enablement checklist (admin, before Day 1)
- [ ] **Partner-powered AI features enabled** at BOTH account + workspace level (required for Agent mode).
- [ ] Workspace in **Azure West Europe** (EU Data boundary) — Genie Code Available, no cross-geo needed.
- [ ] **Deploy `mcp-ai-dev-kit` Databricks App** once; grant catalog/schema; (optional) add under Genie Code Settings → MCP Servers.
- [ ] Unity Catalog grants (SELECT on demo catalog/schema) for all participants — Genie Code is bounded by their perms.
- [ ] Serverless compute available.
- [ ] **Set Genie budgets / cost controls** (Genie products move to PAYGO + per-user free allowance on 2026-07-06; a busy room could hit allowance caps).
- [ ] Pre-test participant data access; pre-grant App `CAN_USE` to all users (forgetting this = 403 for coworkers).

## How this maps onto the 2-day plan (see `WORKSHOP_AGENDA.md` for timing)
- **Pre-read** — light: confirm workspace + Genie Code access (no local install). Admin runs the enablement checklist below.
- **Day 1 (whole game, peeled)** — every layer's "tweak" beat is a Genie Code edit on prebuilt infra (the build loop + practices below). The magic-moment open uses the live-build style here.
- **Day 2 hackathon** — teams run describe→generate→test→refine→deploy in Genie Code on a pre-wired starter; checkpoints; 5-min working-code demos.

## Sources
Genie Code docs (learn.microsoft.com/azure/databricks/genie-code; designated-services Geos); "Introducing Genie Code" + DAIS 2026 blogs; mcp-ai-dev-kit (databricks-field-eng) + AI-Dev-Kit→Genie-Code Confluence 6192562230. Workshop styles: Hackathon Workshop play FE/6005030992; Agentic Coding Workshop FE/5981831335; Learning Path FE/6004473914; Strategic Framework FE/5983109159; go/ai/coding UN/5237899336; GenAI Boost SEMEA FE/6295093321; Vibe Coding Setup Guide UN/6287328128; APJ Buildathon kickoff (GDrive); Code with Claude 2026.

> Caveats (Codex review): native Genie Code doesn't deploy agents/models without the mcp-ai-dev-kit skills — deploy the App first, and it's an internal FE App (not productized) so have **fallback notebooks** ready. **Full-page Genie Code = Beta** → use the side-pane. **On-behalf-of user authorization = Public Preview** → smoke-test whoami/RLS before relying on it. **MemAlign** numbers (~40s/~$0.03/2-10 labels) are Databricks benchmark claims — verify in the target MLflow version; keep it an optional showcase, not the core lab. Concurrent rate limits for the room are unpublished — confirm + set budgets. Avoid Foundry-can't-orchestrate claims; compete on UC-native data governance.
