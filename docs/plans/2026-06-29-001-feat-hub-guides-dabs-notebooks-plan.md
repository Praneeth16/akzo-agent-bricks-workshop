---
title: "feat: Hub guides, deployability, and teaching-grade notebooks"
date: 2026-06-29
type: feat
depth: deep
target_repo: akzo-agent-bricks-workshop (github.com/Praneeth16/akzo-agent-bricks-workshop)
---

# feat: Hub guides, deployability, and teaching-grade notebooks

## Summary

Next iteration of the AkzoNobel Agent Bricks workshop, centered on the Hackathon-in-the-Box hub (`apps/hackathon-hub/akzo-hackathon-hub`, Databricks AppKit, light theme) plus the reference notebooks and deployability. Make the materials self-serve: a newcomer can read a notebook and understand the why, an attendee can open the hub and follow a per-track guide that uses Genie Code to build, and the whole thing deploys from one bundle. Restyle the repo README in a polished open-source style.

Scope is **notebooks + hub** (per user): DABs cover the notebooks workflow + the hub app only; the other 4 agent apps keep their existing per-app deploy scripts.

## Problem Frame

Today the repo is complete but not fully self-serve: notebooks have markdown cells but not teaching-grade depth; the hub lists the 8 tracks but gives no in-app how-to-start; there is no curated resources list or ai-dev-kit/skills onboarding; only the hub has a `databricks.yml`; the README is functional but not polished; and the hub's use cases have not been reconciled against the source slides deck.

## Requirements traceability (from the user request)

- R1 Teaching-grade explanations in every notebook (deepen, keep code intact).
- R2 Reconcile hub `TRACKS` against the slides deck; fix differences.
- R3 Restyle root `README.md` in omniagents open-source style; no em dashes.
- R4 In-app reference to our demos.
- R5 DABs so notebooks + hub deploy via `databricks bundle deploy`.
- R6 Curated Resources tab.
- R7 Per-track in-app guide: what / how to start / seamless Genie Code setup steps.
- R8 In-app ai-dev-kit + skills setup (`databricks experimental aitools install` / `skills`) + other open-source skills (gstack, compound-engineering).
- R9 Review each step with codex; brainstorm with codex.

## Key Technical Decisions

- **Guides as data + a route.** Track guides live as structured data in `client/src/content.ts` (new `GUIDES` keyed by track) and render via a new `/guide/:track` route. Keeps the 8 guides consistent and lets the Challenges cards deep-link. Rationale: data-driven keeps tone uniform and is trivially extendable.
- **DABs: one root bundle, two resource groups.** A root `databricks.yml` defines a `jobs` resource (a multi-task workflow running notebooks 01..10) and references the existing hub app. The hub keeps its own `apps/hackathon-hub/akzo-hackathon-hub/databricks.yml` for `databricks apps deploy`; the root bundle adds an `apps` resource pointing at the hub source so `databricks bundle deploy` provisions both. Rationale: user scoped DABs to notebooks + hub; avoid disturbing the 4 working apps.
- **Notebook explanations are additive markdown only.** Only `# MAGIC %md` cells are added or expanded; no code cell changes. Rationale: preserve verified-working notebooks.
- **README style without copying.** Apply the polished-OSS-README conventions (hero line, badges, feature bullets, quickstart, architecture, layout, links). Fetch the omniagents README during execution for tone reference; if unreachable, apply the conventions directly. No em dashes (enforced by a grep gate).
- **Genie Code steps are the spine of each guide.** Each guide's "how to start" is concrete Genie Code prompts (the side-pane agent) against the relevant `akzo_*` schema, so attendees build by prompting, not from scratch.

## High-Level Technical Design

Hub information architecture after this work:

```
Sidebar
  Overview · Challenges ─┬─> /guide/:track (NEW: per-track guide)
  How to run it          │
  Build setup (NEW) ─────┘   ai-dev-kit + skills onboarding
  Demos (NEW)                links to demo/ + AKZONOBEL_DEMO_PLAN narratives
  Register · Teams · Submit · Judge · Leaderboard · Try it live
  Resources (ENRICHED) · Materials · Organizer
```

DAB shape:

```
databricks.yml (root, NEW)
  resources.jobs.akzo_workshop_notebooks  -> tasks: notebook 01..10 (serverless)
  resources.apps.akzo_hackathon_hub       -> source_code_path: apps/hackathon-hub/akzo-hackathon-hub
  targets.dev (profile fe-vm-lakebase-praneeth)
```

## Implementation Units

### U1. Teaching-grade notebook explanations
**Goal:** Deepen `# MAGIC %md` narration in all notebooks so a newcomer understands code + why.
**Files:** `notebooks/01_*`..`notebooks/10_*` + `09a`, `09b` (12 files), markdown cells only.
**Approach:** Per notebook, add/expand: a top "What you'll learn + prerequisites + how to run" intro; before each code cell a short why/what; after key cells an interpretation of the result; a closing "what you changed / next layer" note. Parallelizable: one subagent per notebook. Keep all `COMMAND` and code lines byte-identical.
**Verification:** Each notebook opens with an intro cell; every code cell has a preceding explanation; `git diff` shows only `# MAGIC %md` line changes (no code-line diffs).

### U2. Track guide data model
**Goal:** Structured guide content for all 8 tracks.
**Files:** `apps/hackathon-hub/akzo-hackathon-hub/client/src/content.ts` (add `GUIDES`).
**Approach:** For each track key: `whatItIs`, `whyItMatters`, `prerequisites`, `genieCodeSteps[]` (ordered, copy-pasteable Genie Code prompts against the track's schema), `shipTarget`, `evalNote`, `links` (starter, eval, relevant notebook). Reuse `TRACKS` for name/domain.
**Verification:** `GUIDES` has an entry per `TRACK_KEYS`; typecheck passes.

### U3. Per-track Guide page + route
**Goal:** `/guide/:track` route rendering U2 data; deep-link from Challenges cards.
**Files:** `client/src/pages/Guide.tsx` (new), `client/src/App.tsx` (route), `client/src/pages/Challenges.tsx` (add "Open guide" link per card).
**Approach:** Numbered step list with copy buttons for Genie Code prompts; sections for what/why/prereqs/ship/eval; sidebar nav unaffected (guide reached via Challenges). Light theme, kit components.
**Verification:** `/guide/finance` renders steps; Challenges card "Open guide" navigates; loading/empty handled for unknown track.

### U4. Build setup page (ai-dev-kit + skills)
**Goal:** In-app onboarding for the Databricks ai-dev-kit + skills + open-source skills.
**Files:** `client/src/pages/BuildSetup.tsx` (new), `App.tsx` (nav item "Build setup"), `content.ts` (`SETUP_STEPS`, `SKILLS`).
**Approach:** Steps: install CLI + profile, `databricks experimental aitools install`, `databricks experimental aitools skills ...`, point an agent (Claude Code / Cursor) at the workspace, then build with Genie Code. Plus a curated open-source skills list (gstack, compound-engineering) with one-line value + links.
**Verification:** Page renders ordered setup steps + skills list; nav item present.

### U5. Resources tab enrichment
**Goal:** Curated reference list for attendees.
**Files:** `client/src/pages/Resources.tsx`, `content.ts` (`RESOURCES` expanded).
**Approach:** Group links: Agent Bricks, AppKit, Genie + Genie Code, Lakebase, AI Gateway, MLflow eval, Vector Search, `ai_*` functions, docs MCP, ai-dev-kit. Keep the existing workspace-facts table.
**Verification:** Resources page shows grouped curated links + workspace facts.

### U6. Demos reference in hub
**Goal:** In-app pointer to our demos.
**Files:** `client/src/pages/Demos.tsx` (new) or a section on Overview/Organizer; `App.tsx`; `content.ts` (`DEMOS`).
**Approach:** Cards for the demo narratives (from `demo/agents_that_act.md` + `AKZONOBEL_DEMO_PLAN.md`): title, one-line, the stacked capabilities, link to the doc in-repo (`REPO_BASE`).
**Verification:** Demos surface renders; links resolve to repo docs.

### U7. Databricks Asset Bundle (notebooks workflow + hub)
**Goal:** `databricks bundle deploy` provisions the notebooks job + the hub app.
**Files:** `databricks.yml` (root, new); optionally `resources/*.yml`.
**Approach:** Root bundle: a `jobs` resource with one task per notebook (or a sequential workflow) on serverless, profile target `fe-vm-lakebase-praneeth`; an `apps` resource referencing the hub source. Validate with `databricks bundle validate`. Do not break the hub's own `databricks.yml` / `databricks apps deploy` path.
**Verification:** `databricks bundle validate -p fe-vm-lakebase-praneeth` passes; `bundle deploy` dry path documented; notebooks job appears in the workspace.

### U8. Slides cross-check (DEPENDENT)
**Goal:** Reconcile hub `TRACKS`/`GUIDES` against the source deck.
**Dependency:** Google Drive MCP auth (user runs `/mcp` → authenticate "claude.ai Google Drive"), or user pastes the deck use cases.
**Files:** `content.ts` (TRACKS/GUIDES edits if differences found), note in `WORKSHOP_MATERIALS.md`.
**Approach:** Read the deck via Google MCP; diff its use cases vs the 8 tracks; add/rename/adjust to match; record the reconciliation.
**Verification:** Every deck use case maps to a track (or is consciously out of scope, noted); differences fixed.

### U9. README restyle (omniagents style, no em dashes)
**Goal:** Polished open-source root README.
**Files:** `README.md`.
**Approach:** Hero + one-line pitch, badges (build/app/live), crisp feature bullets, quickstart, architecture diagram, repo layout, links to hub/notebooks/guides, contributing/license note. Keep content truthful (private repo, synthetic data). Fetch omniagents README for tone; apply conventions regardless.
**Verification:** `grep -nE '—|–' README.md` returns nothing; renders with hero/features/quickstart/architecture sections.

### U10. Review, deploy, publish
**Goal:** Verify, redeploy the hub, push to GitHub.
**Files:** n/a (build + git).
**Approach:** typecheck + lint + ast-grep + local boot of the hub; codex review each code-bearing unit (attempt; if the gateway 403s, substitute rigorous self-review + note it); rebuild + `databricks apps deploy` the hub (lockfile already public-npm; SP re-grant if rotated); commit + push to `Praneeth16/akzo-agent-bricks-workshop`.
**Verification:** Hub deploy SUCCEEDED + live smoke (root 200, guide route renders); repo updated.

## Sequencing & parallelization

- Phase A (parallel subagents): U1 (per-notebook), and content scaffolding U2.
- Phase B (after U2): U3, U4, U5, U6 are independent page files → parallel subagents; each also touches `App.tsx`/`content.ts` so serialize the shared-file edits or have one agent own `App.tsx`+`content.ts` and others own their page files.
- Phase C: U7 DABs (independent).
- Phase D: U9 README (independent).
- Phase E: U8 slides cross-check when auth unblocks.
- Phase F: U10 review + deploy + push.

## Risks

- **Shared-file contention** (`App.tsx`, `content.ts`) across page units → have a single owner make the nav + content additions, page agents only write their own `pages/*.tsx`.
- **DAB notebook tasks** need the notebooks importable as workspace files; serverless job + correct paths; validate before deploy.
- **codex gateway 403** (seen this session) → self-review fallback, noted.
- **SP rotation** on hub redeploy → re-grant per `apps/hackathon-hub/README.md`.
- **Slides auth** is a hard external dependency → U8 deferred, not blocking.

## Verification (definition of done)

All notebooks have teaching intros + per-cell explanations (code unchanged); hub has per-track Guide pages, a Build-setup page, enriched Resources, and a Demos reference, deployed live; root `databricks.yml` validates and deploys the notebooks job + hub; README restyled with zero em dashes; slides reconciled (or explicitly deferred with reason); changes pushed to `Praneeth16/akzo-agent-bricks-workshop`.
