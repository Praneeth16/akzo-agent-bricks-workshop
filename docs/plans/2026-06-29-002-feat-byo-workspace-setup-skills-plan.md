---
title: BYO-workspace setup + per-section ai-dev-kit skills for the hub
date: 2026-06-29
status: planned
author: ce-plan
supersedes: none
related: docs/plans/2026-06-29-001-feat-hub-guides-dabs-notebooks-plan.md
---

# BYO-workspace setup + per-section ai-dev-kit skills

## Problem frame

The Hackathon-in-the-Box hub is written as if every attendee builds in **my** workspace.
Attendees build in **their own** workspaces. So the setup and per-track guides send them to
catalogs, a warehouse, and a login host they cannot reach, and there is no step that loads
the `akzo_*` data into their catalog. Separately, every guide says "build with Genie Code"
but the setup never installs the Genie Code skills, and it conflates two different installs.

Three concrete asks from the user:

1. **Workspace-agnostic setup.** Add proper "set up your own workspace" steps: log into your
   workspace, get the repo, load the synthetic data into your catalog, create Genie spaces.
2. **Per-section ai-dev-kit skills.** In each section (data, build, eval, app) surface the
   relevant ai-dev-kit skills so attendees know which skill to lean on.
3. **Fix the Genie Code skills install.** The correct mechanism is the
   `install_genie_code_skills.py` notebook from `databricks-solutions/ai-dev-kit`, run in the
   workspace. Today's copy points only at `databricks experimental aitools install`, which is a
   different thing.

## Scope

In scope: a new workspace setup notebook (`notebooks/00_setup_load_data.py`), a Genie-space setup
script (`genie/`), `apps/hackathon-hub/akzo-hackathon-hub/client/src/content.ts`, the Build-setup
and Guide pages, the Resources page data, root `README.md` workspace section. (The legacy CLI
loader `data/load_to_uc.py` is superseded by the notebook and needs no work.) Out of scope: the nav-reorder / "Start here" finding from the
prior codex pass (tracked separately, see Related); the 5 agent apps; notebook content.

## Target environment (locked decisions)

- **Platform: Vocareum** managed lab per attendee, **full platform enabled** (Genie, Agent Bricks,
  ai_* functions, Vector Search, AI Gateway, model endpoints). **Free Edition** is the fallback.
- **Attendees self-serve everything** — load data, create Genie spaces, provision Lakebase. No
  organizer pre-bake. So the flow must be bulletproof and step-by-step; the cost of an ambiguous
  step is a stuck attendee burning lab time.
- **Distinct identity per attendee** → OBO / per-user RLS is a real hands-on step (notebook 02,
  supervisor), not just a showcase.
- **Build surface = Genie Code + ai-dev-kit skills installed into the workspace.** The
  `install_genie_code_skills.py` (workspace) install is the hero step — it is the "Genie Code
  powerup." The local coding-agent install (`databricks experimental aitools install`) is the
  optional power path, not required.
- **Browser-only reality:** Vocareum attendees work in the browser workspace. A local-CLI data
  loader is the wrong primary tool for them. The attendee data-load path is a **workspace setup
  notebook** (Spark, no local install). The existing CLI loader stays as the organizer/showcase path.
- **Lakebase: each attendee provisions their own**; a notebook creates the `akzo` schema + tables.
- **Genie spaces: provide both** a setup script/notebook AND click-by-click UI steps.
- **All 8 tracks runnable** given full platform — no capability gating needed.

## Grounding (verified facts)

- `data/load_to_uc.py:14-18` hardcodes `PROFILE`, `WAREHOUSE_ID`, `CATALOG`. It creates
  `CATALOG.akzo_<domain>` schemas + two volumes, then `CREATE OR REPLACE TABLE` from parquet in
  `data/output/`. Idempotent. Drives the authed CLI (no SDK dep).
- `content.ts:374-398` `SETUP_STEPS` step 1 hardcodes the login host + profile; step 2/3 use
  `databricks experimental aitools install` / `skills` (the **local coding-agent** install).
- `content.ts:224` `CAT = 'serverless_lakebase_praneeth_catalog'`; every guide schema and the
  finance prereq warehouse `4d39ac2e32b72a3a` (`content.ts:232`) are showcase-specific.
- The linked notebook `databricks-solutions/ai-dev-kit/databricks-skills/install_genie_code_skills.py`
  runs **in a Databricks notebook** (no clone, no env vars needed), discovers every `SKILL.md`
  under `databricks-skills/` + `mlflow/skills`, downloads them, and uploads to
  `/Workspace/Users/{username}/.assistant/skills/` so **Genie Code** can use them. Config:
  `INSTALL_SKILLS = "all"`, `GITHUB_REF = "main"`.
- ai-dev-kit `databricks-skills/` ships 27 skill dirs (verified via GitHub API). The ones that
  map to this workshop: `databricks-config`, `databricks-unity-catalog`,
  `databricks-synthetic-data-gen`, `databricks-dbsql`, `databricks-metric-views`,
  `databricks-genie`, `databricks-agent-bricks`, `databricks-ai-functions`,
  `databricks-vector-search`, `databricks-mlflow-evaluation`, `databricks-model-serving`,
  `databricks-lakebase-provisioned`, `databricks-lakebase-autoscale`, `databricks-apps-python`,
  `databricks-bundles`, `databricks-unstructured-pdf-generation`.

## Key decision: two skill installs are different things, say so

- `databricks experimental aitools install` → installs Agent Skills into your **local** coding
  agent (Claude Code / Cursor) so it can drive the CLI while you build locally.
- `install_genie_code_skills.py` (notebook) → installs the same skills into your **Databricks
  workspace** (`.assistant/skills/`) so **Genie Code**, the in-workspace side-pane agent the
  guides tell you to build with, can use them.

Attendees building with Genie Code need a **workspace** install. The notebook is one supported
route; the ai-dev-kit also ships `install_skills.sh --install-to-genie` (with profile support).
The hub must present both the local-agent install and the workspace (Genie Code) install,
labeled by where they run and what they unlock, and name the notebook **and** the
`--install-to-genie` flow as the two workspace routes. This is the central correctness fix.

## BYO-workspace setup flow (the new on-ramp)

Restructure Build setup into an ordered, workspace-agnostic flow. Showcase values appear only
as "example" with a visible "swap in your own" callout. New step order:

0. **Open your Vocareum Databricks workspace** (browser). Free Edition is the fallback. Note your catalog name and SQL warehouse. (skills: `databricks-config`)
1. **Add the repo as a Git folder (Repo) in the workspace** — clone in-workspace so the setup notebook + reference notebooks are present. No local install needed.
2. **Run the setup notebook to load your data** — open `notebooks/00_setup_load_data.py` (NEW, U0), set the catalog + warehouse widgets, Run All. It generates the synthetic data and creates `<your-catalog>.akzo_*` schemas + volumes + tables with Spark, entirely in-workspace. (skills: `databricks-synthetic-data-gen`, `databricks-unity-catalog`, `databricks-dbsql`)
3. **Install Genie Code skills (the powerup)** — run `install_genie_code_skills.py` from `databricks-solutions/ai-dev-kit` with `INSTALL_SKILLS="all"` (or `install_skills.sh --install-to-genie`); installs to `/Workspace/Users/<you>/.assistant/skills/`. This is what gives Genie Code its Databricks-native superpowers — the hero step. (skills: all, via Genie Code)
4. **Create your 3 Genie spaces** over `akzo_finance` / `akzo_scm` / `akzo_commercial`. Use the provided setup script for speed **and** the click-by-click UI steps as the explainer/fallback. Substitute your catalog into any `genie/*` instructions before pasting (those are showcase-pinned). (skills: `databricks-genie`)
5. **Provision your Lakebase instance + create the write-back schema** — spin up your own Lakebase instance, then run `notebooks/05_lakebase_memory_action.py` (schema-create section) to make the `akzo` schema + write-back tables (`forecast_overrides`, etc.). The "stage it" steps depend on this. (skills: `databricks-lakebase-provisioned`)
6. **(Optional) Install ai-dev-kit into a local coding agent** — `databricks experimental aitools install` if you also build locally with Claude Code / Cursor. Not required; Genie Code + workspace skills is the main path.
7. **Build by prompting** — open any track's Guide and follow the Genie Code steps. All 8 tracks are runnable on the full-platform lab; OBO (notebook 02) is hands-on since each attendee has a distinct identity.

> Showcase-only caveat (call out in the UI): the forkable `starters/*` and `genie/*` configs
> hardcode the showcase catalog, model endpoints, and Lakebase instance. BYO covers the hub
> copy + setup notebook + Genie Code skills + Genie spaces + Lakebase schema; running a starter
> verbatim additionally requires swapping those literals. Tracked as a known limitation.

## Implementation units

### U0 — Workspace setup notebook for attendees (NEW: `notebooks/00_setup_load_data.py`)
The attendee data-load path. Runs entirely in the Vocareum/Free-Edition browser workspace, no
local CLI. Best-practice for a self-serve hackathon: one notebook, Run All, done.
- Notebook widgets: `catalog` (default to the lab's catalog or current-user catalog), `warehouse`
  (optional; notebook uses Spark, so warehouse is only needed where SQL-warehouse-specific).
- Generate the synthetic data inline by importing/running `data/generate_*.py` from the cloned
  Repo (they already produce the parquet under `data/output/`), then load with Spark:
  `CREATE SCHEMA IF NOT EXISTS`, `CREATE VOLUME IF NOT EXISTS`, write each table with
  `df.write.saveAsTable(...)` / `CREATE OR REPLACE TABLE`. Reuse the `TABLES`/`DOMAINS`/`PFX`
  structure from `data/load_to_uc.py` so the schema layout is identical to the showcase.
- Idempotent + re-runnable (lab sessions reset). Print a verification table (row counts per table)
  and a clear PASS/FAIL summary at the end so an attendee knows setup worked.
- Teaching markdown matching the other notebooks: what each schema is, why `akzo_*`, what to do next.
- Verify: notebook parses; a dry structure check shows every `akzo_*` schema + table created via
  Spark from the committed parquet; final cell prints per-table counts.
- Test scenarios: (a) fresh catalog → all schemas/tables created; (b) re-run → no duplicate/error
  (idempotent); (c) verification cell flags a missing table loudly.

### U1 — (dropped) CLI loader is superseded by the U0 notebook
The local CLI loader `data/load_to_uc.py` was a one-time tool to load the **showcase** workspace,
which is already loaded. The U0 notebook now loads both attendee and (if ever needed) showcase
catalogs, in-workspace, with the identical schema layout. Two loaders would only drift. So:
- **No hardening work** on `data/load_to_uc.py` (the codex F2-F5 findings about argparse /
  validation / fail-closed are moot — we stop depending on it).
- Leave the file as-is as a legacy organizer script, or delete it. Either way it is **out of the
  attendee flow** and not referenced by the hub copy.
- Net effect: one source of truth for data load (U0), less surface to maintain.

### U2 — Workspace config + placeholders in content.ts
- Add a `WORKSPACE` constant block: `showcaseHost`, `showcaseCatalog` (= existing `CAT`),
  `showcaseWarehouse`, plus placeholder tokens (`<your-catalog>`, `<your-warehouse-id>`,
  `<your-workspace-url>`, `<your-profile>`). Keep `CAT`/showcase values for the deployed hub's
  own "Try it live" analytics (that legitimately points at the showcase workspace).
- Add `skills?: string[]` to `Track` (or a parallel `SKILLS_BY_TRACK` map) and a
  `SKILLS_BY_PHASE` map keyed by setup phase. Values are real ai-dev-kit skill dir names from
  Grounding.
- Verify: `npm run typegen` / `tsc` clean; grep shows no new hardcoded `serverless_lakebase_*`
  outside the `WORKSPACE` constant and the "Try it live" path.

### U3 — Rewrite SETUP_STEPS into the BYO on-ramp (`content.ts` + `pages/BuildSetup.tsx`)
- Replace `SETUP_STEPS` with the 7-step flow above. Each step gets `body`, optional `command`
  (with placeholders, not my host), and `skills?: string[]`.
- Add a distinct `GENIE_CODE_SKILLS` callout describing the notebook install vs the local
  install (the central correctness fix). Render both clearly in `BuildSetup.tsx` with a
  one-line "where it runs / what it unlocks" label.
- Render per-step skill chips that deep-link to the ai-dev-kit skill (href pattern
  `https://github.com/databricks-solutions/ai-dev-kit/tree/main/databricks-skills/<skill>`).
- Verify: BuildSetup page renders all 7 steps + both installs labeled; copy buttons still work
  (reuse existing `CopyableCommand`); no `fevm-serverless-lakebase-praneeth` literal in copy.

### U4 — Workspace-agnostic guides + true per-section skills (`content.ts` GUIDES + `pages/Guide.tsx`)
- Replace `${CAT}.akzo_*` schema strings and the finance warehouse prereq with placeholder forms
  (`<your-catalog>.akzo_finance`, `<your-warehouse-id>`); add a standing prereq "Run Build setup
  first: load the data into your catalog, provision Lakebase for write-back, install Genie Code skills."
- Per-section mapping (not just one guide-level chip row — the user asked for skills *in each
  section*). Tag skills at the step group level: **data/ground** steps → `databricks-genie`,
  `databricks-dbsql`, `databricks-unity-catalog`; **write-back/stage-it** steps → 
  `databricks-lakebase-provisioned`; **eval** → `agent-evaluation` (from `mlflow/skills`, the
  judge/eval workflow) and/or `databricks-mlflow-evaluation`; **doc-intelligence** (quote) →
  `databricks-ai-functions`, `databricks-vector-search`, `databricks-unstructured-pdf-generation`;
  **multi-agent** (supervisor) → `databricks-agent-bricks`; **governance** →
  `databricks-model-serving`, `databricks-unity-catalog`; **finance metric views** →
  `databricks-metric-views`. Every track with a "stage it" step (finance, forecast, scm,
  commercial, quote, action) gets a Lakebase skill — they all write back.
- Render a skill chip row per section (or at minimum per guide with section labels) near the
  relevant Genie Code steps.
- Verify: each `/guide/:track` shows placeholders (no showcase catalog), the Build-setup prereq,
  and section-tagged skill chips; chips link to valid ai-dev-kit / mlflow skill dirs.

### U5 — Fix SKILLS list + Resources (`content.ts` **and** `pages/Resources.tsx`)
- Fix the `SKILLS` array: separate "local coding-agent install" from "Genie Code (workspace)
  install"; fix the broken `compound-engineering` href (`https://github.com/` → real repo) and
  the bare `gstack` href if needed.
- Add Resources entries: the ai-dev-kit repo, the `install_genie_code_skills.py` notebook +
  `install_skills.sh --install-to-genie` route, the Genie Code skills doc — under the existing
  "AI dev kit & skills" group.
- **The Workspace table is rendered in `pages/Resources.tsx:7`, not `content.ts`** — clarify
  there that it is the **showcase** workspace, with a "swap in your own" note. Update U5's file
  list accordingly.
- Verify: every Resources/SKILLS href resolves (HTTP 200 or known-good); no bare
  `https://github.com/` remains; Resources page labels the workspace table as showcase.

### U6 — README workspace section (`README.md`)
- Add a "Build in your own workspace" subsection to Quickstart: the BYO order (login your host →
  clone → `WORKSHOP_CATALOG=... python3 data/load_to_uc.py -p ...` → Genie Code skills notebook
  → create Genie spaces). Clarify the existing Workspace table is the **showcase** workspace.
- Verify: 0 em dashes (`grep -c "—" README.md` == 0); BYO commands use placeholders.

## Sequencing & parallelization

- **U0** (setup notebook), **U6** (README), **U7** (Genie-space setup script) are independent of
  the app — can run in parallel via subagents. (U1 dropped — CLI loader superseded by U0.)
- **U2 → U3 → U4 → U5** all touch `content.ts` + pages; run sequentially (or one agent) to avoid
  edit conflicts. U2 first (it defines the constants the others consume).
- After all units: `npm run typegen`/`tsc` + lint + ast-grep clean, then the smoke checks below.
  Deploy is a release step, not a correctness gate (see Verification).

### U7 — Genie-space setup script + UI steps (NEW: `genie/create_genie_spaces.py` or notebook)
"Both" was chosen. Provide a script/notebook that creates the three Genie spaces over the
attendee's catalog (via the Genie/workspace API where available), plus the click-by-click UI
steps rendered in the Build-setup + guide copy as the explainer/fallback.
- Parameterize by catalog; create spaces scoped to `akzo_finance` / `akzo_scm` / `akzo_commercial`.
- If the Genie space API is not available/stable on the lab, the script prints the exact manual
  steps instead of failing — the UI click path is the guaranteed route.
- Verify: script runs against a catalog and either creates the 3 spaces or prints the manual
  fallback cleanly; UI steps in the hub match the current Genie UI.

## Verification (whole)

1. `tsc` / `npm run typegen` clean; lint + ast-grep clean.
2. Showcase-literal sweep across **all** attendee-facing copy, not just `content.ts`:
   `rg -n "fevm-serverless-lakebase-praneeth|serverless_lakebase_praneeth_catalog|4d39ac2e32b72a3a"`
   over `client/src` (incl. `pages/Resources.tsx`) + `README.md`. The literal is allowed only in
   the `WORKSPACE` showcase constant, the "Try it live" path, and the Resources workspace table
   (which is explicitly labeled showcase). `genie/*`, `starters/*`, `eval/*`, and `notebooks/*`
   are out of scope and remain showcase-pinned (documented as the known limitation, not swept).
3. `notebooks/00_setup_load_data.py` parses; structure check shows all `akzo_*` schemas + tables
   created via Spark from committed parquet, idempotent re-run, and a final PASS/FAIL count cell.
   `genie/` setup script either creates the 3 spaces or prints the manual fallback.
4. README has 0 em dashes (`rg -c "—" README.md` == 0) and a BYO subsection.
5. Deployed hub: Build setup shows the 7-step BYO flow with both the local and workspace skill
   installs labeled; each guide shows section-tagged skill chips + placeholders + the Lakebase
   write-back prereq.
6. `/codex review` of the diff: gate PASS.

Deployment is a **release** step, not a correctness gate — for these content-only hub edits,
local typecheck/build + the smoke checks above suffice; `databricks apps deploy` happens when
shipping, not to prove the change is correct.

## Risks

- **Placeholder vs runnable tension.** Attendees can't copy-run a `<your-catalog>` command. Mitigate
  with a one-line "replace the angle-bracket values" note + keep one showcase example visible.
- **Loader perms (under-specified before codex).** The loader needs `CAN_USE` on the warehouse,
  `USE CATALOG`, schema create/own, `CREATE VOLUME` + volume write, and table create/replace in
  each `akzo_*` schema. "Point at a catalog you own" is necessary but not sufficient — list the
  full grant set in the setup copy. Many attendee workspaces will fail the DDL otherwise.
- **Lakebase write-back plane (biggest gap).** Data load creates only UC tables/volumes. Every
  "stage it" step writes to Lakebase (`akzo` schema), hardcoded to `graphrag-spike` in
  `starters/finance/starter.py:192` and assumed pre-staged in `notebooks/05`. Without a Lakebase
  provisioning step (U-flow step 3) or an organizer-provided instance, BYO write-back fails.
- **Showcase-pinned starters/genie/notebooks.** Running a `starters/*` verbatim in a BYO
  workspace needs catalog + model-endpoint + Lakebase substitution that this plan does NOT do.
  Stated as a known limitation in the UI; a full BYO-starters pass is a separate follow-up.
- **Skill-name drift.** ai-dev-kit skill dirs could be renamed upstream; chips deep-link to
  `main`, so a rename 404s. Acceptable for a workshop; note it.
