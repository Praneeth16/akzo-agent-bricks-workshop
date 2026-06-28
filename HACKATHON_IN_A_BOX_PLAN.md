# Hackathon-in-the-Box — Build Plan

**Created:** 2026-06-28
**Goal:** One unified, world-class **Databricks-light-theme** app that combines everything already built (10 notebooks, 8 starter tracks, 5 deployed apps, demos, data, Genie spaces) into a single pane attendees can browse AND run — *plus* full hackathon-running features (Register / Teams / Judge / Leaderboard). Dogfood our own stack: built **on Databricks AppKit** so the app itself is a demo of the platform.

Reference: colleague's "Hackathon-in-the-Box" (Run a Databricks Data + AI Hackathon — Overview/Challenges/How-to-run-it, Register/Teams/Judge/Leaderboard, Resources/Materials/Organizer).

## Locked decisions (from user)
1. **Stack: Databricks AppKit** (TypeScript SDK + `@databricks/appkit-ui` = Shadcn/Radix/Tailwind + ECharts). Native plugins: `server`, `genie`, `agents` (beta), `lakebase`, `vectorSearch`, `modelServing`, `jobs`, `files`, `analytics`. This *is* the dogfood story.
2. **Scope: full hackathon-running app** — launcher + live agent surfaces + organizer features (Register/Teams/Judge/Leaderboard) backed by live Lakebase state.
3. **Deploy: workspace `fe-vm-lakebase-praneeth`**, **Databricks LIGHT theme**, codex-review every code-bearing step.
4. Reuse existing infra: catalog `serverless_lakebase_praneeth_catalog` + `akzo_*` schemas, 3 Genie spaces, Lakebase instance `graphrag-spike` / db `databricks_postgres` / schema `akzo`, warehouse `4d39ac2e32b72a3a`, vector index `…akzo_docs.chunks_idx`, models `databricks-claude-opus-4-7` / `databricks-qwen3-embedding-0-6b`.

## Placement & naming
- Project dir: `apps/hackathon-hub/` (AppKit project; own `package.json`, `server.ts`, `config/`, `app.yaml`, `build/`).
- Databricks app name: **`akzo-hackathon-hub`**.
- Lakebase hackathon state: **new `hack_*` tables** in existing `akzo` Postgres schema (additive, no collision with `actions`/`agent_*`/`quotes`).

## Toolchain (verified)
Node v26 ✓ · npm 11 ✓ · Databricks CLI v0.298 (`apps init` AppKit-aware) ✓ · profile `fe-vm-lakebase-praneeth` ✓ · codex 0.142 ✓.
- Scaffold (non-interactive): `databricks apps init --name akzo-hackathon-hub --output-dir apps/hackathon-hub --features <from-manifest> --auto-approve -p fe-vm-lakebase-praneeth`
- Local: `DATABRICKS_CONFIG_PROFILE=fe-vm-lakebase-praneeth npm run dev`
- Deploy: `databricks apps deploy` (+ SP grants).

## Light theme
Shadcn/Tailwind = CSS-variable theming. Apply Databricks light tokens (reverse of `apps/DESIGN_BRIEF.md` dark): bg `#ffffff`/panel `#f7f8fa`/border `#e4e7ec`, text `#11171f`/muted `#5b6472`, **keep teal accent `#00b39f`**, link `#2563eb`. Status colors (light-tuned): proposed `#6b7280`, approved `#2563eb`, executing `#d97706`, executed `#059669`, rejected/failed `#dc2626`, escalated `#7c3aed`. Reuse component vocabulary (StatusBadge, LadderMeter, Timeline, GuardrailChips, TracePanel, DataTable) restyled light.

## Lakebase hackathon schema (`akzo.hack_*`, additive)
- `hack_teams` (id, team_name, track, created_at, members_count)
- `hack_members` (id, team_id, name, email, role)
- `hack_registrations` (id, team_id, email, registered_at)  — registration audit
- `hack_submissions` (id, team_id, track, title, summary, artifact_url, artifact_kind[notebook|app|genie|agent], submitted_at, status[draft|submitted])
- `hack_rubric` (id, criterion, weight, max_score, description) — seeded judging rubric
- `hack_scores` (id, submission_id, judge_email, criterion, score, comment, scored_at) — expert choice
- `hack_votes` (id, submission_id, voter_email, voted_at) — people's choice (one per voter per submission)
Seed: rubric rows, 3–4 sample teams across tracks, 1–2 sample submissions for a populated demo.

## Information architecture (pages / left-nav, mirrors reference)
- **Overview** — hero "Run an AkzoNobel Agent Bricks Hackathon"; What teams deliver / Awards (Expert Choice on rubric + People's Choice peer vote) / Format (cross-functional, 2 days, shared Databricks env); embedded 2-day agenda (Day-1 7 layers, Day-2 pick-a-track).
- **Challenges** — the 8 starter tracks as challenge cards (goal, ship target, 5 golden Qs, links to `starters/<track>/`), plus the 10 reference notebooks as a "learning path" rail.
- **How to run it** — facilitator playbook (See→Tweak→Return, Day-2 sprints) from `WORKSHOP_AGENDA.md`/`VIBE_CODING_SESSION.md`.
- **Register** — team registration form → `hack_teams`/`hack_members`/`hack_registrations`.
- **Teams** — roster: team, members, chosen track, submission status.
- **Submit** — submission form (artifact link + kind + summary) → `hack_submissions`.
- **Judge** — rubric scoring per submission → `hack_scores`; people's-choice vote → `hack_votes`.
- **Leaderboard** — ranked: weighted expert score + people's-choice tally.
- **Try it live (dogfood)** — embedded live surfaces: `<GenieChat>` for finance/scm/commercial; supervisor **agent chat** (agents plugin, sub-agents → genie tools); doc-intelligence **RAG search** (vectorSearch plugin over `chunks_idx`); **Action queue** (lakebase `actions` + HITL approval card).
- **Resources** — AI Dev Kit, Databricks Docs, repo links.
- **Materials** — rendered workshop docs (agenda/plan/demo).
- **Organizer (internal)** — gallery of the 5 deployed apps (status + live URL + "what it shows"), smoke results, deploy status.

## Build order, units, verification, subagents, codex gates
Each code-bearing unit ends with a **codex review** (`codex exec --sandbox read-only --skip-git-repo-check "<prompt>"`); fix findings before next unit. Critical path = U0→U1; pages/surfaces fan out via subagents after.

| Unit | What | Depends | Subagent | Verify |
|---|---|---|---|---|
| **U0** | Scaffold AppKit (`apps init`), wire plugins (genie 3 spaces, lakebase, vectorSearch, modelServing, agents, jobs, files, analytics), apply LIGHT theme tokens + app shell (left-nav like reference) | — | main | `npm run dev` boots; `/` renders light shell; health OK |
| **U1** | Lakebase `hack_*` DDL + seed (rubric, sample teams/submissions); typed file-based queries + server routes (CRUD) | U0 | main | tables exist in `akzo`; seed rows; `/api` returns teams |
| **U2** | Overview + Materials + How-to-run pages (hero, agenda, awards/format, render docs) | U0 | sub-A | pages render; agenda from data |
| **U3** | Challenges page (8 track cards + 10-notebook learning path) | U0 | sub-B | cards from a typed `challenges` source |
| **U4** | Register + Teams pages (form → Lakebase; roster list) | U1 | main | register team round-trip; appears in Teams |
| **U5** | Submit page (submission form → `hack_submissions`) | U1,U4 | sub-C | submit artifact round-trip |
| **U6** | Judge page (rubric scoring → `hack_scores`; vote → `hack_votes`; separation: judge≠own team) | U1,U5 | main | score + vote persist |
| **U7** | Leaderboard (weighted expert + people's-choice tally, ranked) | U6 | sub-C | ranking reflects scores |
| **U8** | Try-it-live: `<GenieChat>` ×3, supervisor agent chat, doc RAG search, action approval queue | U0,U1 | main | live Genie answer; agent routes; RAG chunk; approval round-trip |
| **U9** | Organizer + deployed-apps gallery (5 apps, status, URLs, smoke) | U0 | sub-B | links resolve; status shown |
| **U10** | Deploy to `fe-vm-lakebase-praneeth` + SP grants (genie spaces, lakebase role, warehouse, vector index, serving) + full live smoke | all | main | app ACTIVE/SUCCEEDED; every page + live surface verified live |

## Subagent / workflow strategy
- **Phase 1 (serial, main):** U0 scaffold → U1 schema. Foundations everything imports; do not parallelize.
- **Phase 2 (fan-out workflow):** U2, U3, U9 (independent read-only/content pages) in parallel subagents; codex-review each on completion.
- **Phase 3 (serial-ish, main):** U4→U5→U6→U7 (shared hackathon-state data model; sequence to avoid Lakebase schema races) — U7 can fan to a subagent once U6 lands.
- **Phase 4 (main):** U8 live surfaces (highest-value dogfood; needs care with OBO/SP) → codex review.
- **Phase 5 (main):** U10 deploy + live smoke.

## Risks & mitigations
- **AppKit `agents` plugin is beta** → if API drifts, fall back to a thin server route calling existing supervisor logic; Genie chat (`genie` plugin, stable) is the must-have live surface.
- **OBO via genie plugin** needs the app SP granted on the 3 Genie spaces + `CAN USE` warehouse → handle in U10 grants; smoke under SP.
- **Lakebase plugin runs as SP** (not OBO) → hackathon writes are SP-scoped + audited (consistent with existing write-governance story); never expose `lakebase.query` as an autonomous agent tool.
- **CLI v0.298 < docs' v1.0** → `apps init` already works; pin `--version` if scaffold errors.
- **Light theme regressions** on Shadcn → snapshot via `/browse` during U2/U8, codex + a quick visual pass.
- **Deploy SP grants** are the usual failure (seen with the 5 apps) → reuse `deploy/` grant patterns; grant vector index + serving + genie up front.

## Definition of done
`akzo-hackathon-hub` live ACTIVE/SUCCEEDED on `fe-vm-lakebase-praneeth`, light theme; all pages functional; Register→Teams→Submit→Judge→Leaderboard round-trips on live Lakebase; ≥1 live Genie answer + agent route + RAG result + action approval demonstrated in-app; Organizer gallery links the 5 apps; each code-bearing unit codex-reviewed and findings fixed; `WORKSHOP_MATERIALS.md` gains a §9 pointing here.
