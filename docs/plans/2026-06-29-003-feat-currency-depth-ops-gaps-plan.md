---
title: Currency, platform-depth & workshop-ops gaps (from a deep source scan)
date: 2026-06-29
status: planned
author: ce-plan + 4-agent source scan + codex review
related:
  - docs/plans/2026-06-29-001-feat-hub-guides-dabs-notebooks-plan.md
  - docs/plans/2026-06-29-002-feat-byo-workspace-setup-skills-plan.md
---

# Currency, depth & ops gaps

A deep scan of all sources (latest Databricks docs, the ai-dev-kit repo, our own docs/notebooks/
hub, and workshop-design best practices) surfaced gaps the two existing plans don't cover. This
is the triage backlog. Each item: source, action, target. Tiered by urgency.

> Caveat (verify live): a few items trace to DAIS-2026 announcement blogs, not GA doc pages
> (Unity AI Gateway rename, Agent Memory Service, Genie Ontology). Confirm per-feature status
> before building on them. Foundation-model names + preview flags must be re-verified the morning
> of the event.

## Codex review corrections (applied — web-verified)

A web-verified codex pass corrected these before they could reach attendee copy:
- **REFUTED:** "DAB omits 09a/09b" — false; root `databricks.yml` already runs both. Only the 3
  NEW product notebooks need adding to `NOTEBOOKS[]` + the DAB. (T0.6 fixed.)
- **CORRECTED:** Vector Search reranker is `RerankerConfig(reranker_model="databricks-reranker")`
  and `query_type="hybrid"` (lowercase) — not `databricks_reranker` / `"HYBRID"`. (T1.7 fixed.)
- **VERIFIED (2026-06-29):** `ai_prep_search` IS available — official doc
  https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_prep_search .
  Re-promoted to attendee material. (T1.7.)
- **CORRECTED:** MAS limit — "up to 30 agents/tools selectable in the UI, but keep a single
  supervisor under ~20; for the workshop use exactly the 3 domain tools." (T1.1 fixed.)
- **DOWNGRADED:** foundation-model "panic" overstated — `ai_query` docs still list
  `databricks-claude-opus-4-7` + `databricks-gpt-5-5`; our pins are not broken. Keep morning-of
  verification; drop the bump-urgency. (T0.8 downgraded.)
- **VERIFY-ON-LAB:** the "skills fire only in Genie Code Agent mode at `.assistant/skills/`" claim
  came from the `install_genie_code_skills.py` notebook itself (which writes to
  `/Workspace/Users/<you>/.assistant/skills/`), but codex could not confirm the Agent-mode
  requirement from the public Agent Skills docs (those show `databricks aitools install` →
  `~/.databricks/ai-tools` for the LOCAL agent — a different install). Two installs, two paths:
  keep the distinction, but mark the Genie-Code-side mechanic "verify on the actual lab workspace"
  rather than asserting it. Also the repo command `databricks experimental aitools install` is
  stale — current is `databricks aitools install`. (T0.1 updated.)
- **Critical missed gap (codex):** the "prebuilt tracing" promise is overstated *everywhere*, not
  just the Layer-6 blurb — nb 06 sets up no MLflow tracing/autolog. Either add real tracing (T1.6)
  or remove the claim from all copy. Treat as Tier 0 correctness.

## Tier 0 — correctness / will break live (do before the event)

These are version-drift and setup-blocker items. If unfixed, attendees hit silent failures.

- **T0.1 Workspace Genie Code skills install (VERIFY-ON-LAB).** The `install_genie_code_skills.py`
  notebook writes per-user to `/Workspace/Users/<you>/.assistant/skills/`; the "skills fire only
  in Agent mode" requirement is plausible but UNVERIFIED from public docs — confirm on the actual
  lab workspace before teaching it as a hard step. Separately, the repo command `databricks
  experimental aitools install` is stale → current is `databricks aitools install` (local agent,
  installs to `~/.databricks/ai-tools`). Keep the two-install distinction (workspace notebook vs
  local CLI). Each attendee installs under their own identity. → BuildSetup: fix the command, show
  how to verify skills appear, mark the Agent-mode requirement as lab-verified. (plan 002 U3)
- **T0.2 Lakebase rebuilt to Autoscaling Projects (2026-03-12).** New instances are *projects*
  (branches, scale-to-zero); our `notebooks/05`, `09a`, and `apps/*/lakebase.ts` use the legacy
  `instance`/`generate_database_credential(instance_names=...)` API. A BYO attendee provisioning
  today gets a project and our snippets + UI terminology mismatch. → Verify the credential SDK call
  against the projects API; update the Lakebase provisioning step (plan 002 flow step 5) + nb 05
  schema cell. Source: docs/oltp/projects/connect-overview.
- **T0.3 Serverless budget + UC + Model Serving are hard prereqs for ALL Agent Bricks.** Nothing
  works without a serverless usage policy with nonzero budget. #1 Day-1 blocker. → Day-0 admin
  prereq check (see T1.10). Source: docs agent-bricks/knowledge-assistant.
- **T0.4 GitHub outbound required for the skills installer.** Notebook hits api.github.com /
  raw.githubusercontent.com; Free Edition + locked labs may block it → silent failure. → Pre-test
  outbound GitHub from the actual Vocareum/FE workspace; stage a fallback skills bundle. (plan 002 U3)
- **T0.5 OBO + AI Gateway are account-console-gated → not on Free Edition.** The Supervisor+OBO and
  AI-Gateway parts are Vocareum-only. → Document FE fallback scope; route the advanced spine to
  full-platform labs. (Cross-ref the locked decision: Vocareum full-platform, FE fallback.)
- **T0.6 Repo inconsistencies (internal scan, verified):**
  - Layer-6 hub blurb overclaims "Tracing + ... MemAlign" vs eval-first nb 06 (`content.ts:139`). Fix copy.
  - "10 notebooks" everywhere vs 12 actual `.py` (09a/09b omitted from `NOTEBOOKS[]`) + 3 new
    product notebooks = 15. Reconcile copy repo-wide; add 09a/09b + the 3 new ones to `NOTEBOOKS[]`.
    NOTE: the DAB already runs 09a/09b (codex refuted the "DAB omits" claim) — only the 3 NEW
    product notebooks need adding to the DAB job.
  - `00` collision: plan 002 `00_setup_load_data` vs new `00_agent_bricks_product_map`. Renumber
    (setup outside the numbered layer sequence; product map = lesson 0).
  - nb 08 labeled "Extra" in hub but Layer 8 elsewhere, and doc-intelligence has no `DAY1_AGENDA`
    slot though Quote depends on it. Reconcile + add agenda item.
  - Governance track guide points at a Genie space on `akzo_gateway` with no `genie/*` config.
    Add `genie/gateway_space.md` or drop the Genie assumption from that guide.
  - app `CLAUDE.md` + hub `SETUP_STEPS`/`SKILLS` still teach `aitools install` as the skills path
    (contradicts plan 002's central fix). Add app `CLAUDE.md` to plan 002's file list.
  - `compound-engineering` href is bare `https://github.com/` (`content.ts:411`). Fix (plan 002 U5).
  - `starters/*/eval.yaml` are byte-identical dupes of `eval/*.yaml` — pick one canonical source.
- **T0.7 Terminology + name drift:** "Mosaic AI Gateway" → **Unity AI Gateway**; "Mosaic AI Vector
  Search" → **AI Search** (URLs now `/ai-search/`); never write `ai_parse` (it is `ai_parse_document`).
  Sweep copy + notebooks.
- **T0.8 (downgraded) Re-verify foundation-model names morning-of.** Codex confirmed `ai_query`
  docs still list `databricks-claude-opus-4-7` + `databricks-gpt-5-5`, so our pins are NOT broken —
  no bump needed. Keep exact pinned strings and a morning-of verification step in the runbook
  (catalog does churn; some models retire in 2026). Source: docs FM APIs supported-models.

## Tier 1 — high value (fold into the current iteration)

Curriculum currency + platform depth + the workshop-ops on-ramp.

- **T1.1 Native MAS (04a) should cover UC-governed managed MCP.** MAS is GA, orchestrates Genie
  spaces + Knowledge Assistants + UC functions + managed MCP (Google Drive/Jira/Slack/GitHub),
  OBO on every fetch; SDK/API management is Beta (UI is GA). Limit (codex-corrected): up to 30
  agents/tools selectable in the UI, but keep a single supervisor under ~20 — for the workshop use
  exactly the 3 domain tools. Managed-MCP depth is optional/Resources unless time allows. Source:
  docs agent-bricks/multi-agent-supervisor.
- **T1.2 Genie-as-a-tool gotcha:** the managed MCP Genie URL is *stateless*; use the GA Genie
  Conversation API for multi-turn. Space Management APIs are GA for CI/CD. Note in 04a. Source:
  docs mcp/managed-mcp + genie/conversation-api.
- **T1.3 Information Extraction (08a) is Public Preview + region-limited (128k cap).** May not
  appear in the lab region. Verify region; flag Preview. Source: docs agent-bricks/info-extraction.
- **T1.4 Genie space setup checklist (new hub guide):** ≤5 tables to start (hard cap 30, pre-join
  with views), UC column descriptions + synonyms are the accuracy lever, prefer SQL expressions /
  example queries, register trusted assets, benchmark verified questions. Determines whether an
  attendee's first Genie space works. Source: docs genie/best-practices + trusted-assets.
- **T1.5 Eval notebook → MLflow 3 GenAI.** `mlflow.genai.evaluate(predict_fn=, scorers=[Correctness(),
  Safety(), Guidelines()])` + `make_judge()` + review apps replace MLflow-2 `mlflow.evaluate()`.
  Requires `mlflow[databricks]>=3.1`. Pull in the `agent-evaluation` mlflow skill. (nb 06 already
  has a guarded genai path — promote it.) Source: docs mlflow3/genai/eval-monitor.
- **T1.6 MLflow Tracing (new short notebook or extend 06).** `mlflow.<lib>.autolog()` + `@mlflow.trace`
  capture inputs/outputs/latency/tokens/retrieved-docs/tool-calls — the unit scorers run against.
  This also makes the Layer-6 "tracing" claim true instead of just fixing the copy. Source:
  mlflow.org/genai/tracing.
- **T1.7 Doc-intel (nb 08) extensions (optional/Resources unless time):** AI Search built-in
  reranker `RerankerConfig(reranker_model="databricks-reranker")` (~10% lift) + `query_type="hybrid"`
  (lowercase, RRF) — highest-ROI retrieval knobs for jargon/part-number data; trivial param changes.
  Confirm reranker GA before relying on it. **`ai_prep_search` VERIFIED available** (2026-06-29):
  docs.databricks.com/aws/en/sql/language-manual/functions/ai_prep_search — OK for attendee material.
  Source: docs ai-search/retrieval-quality.
- **T1.8 `ai_query` GA with `responseFormat` structured output + `modelParameters` + `failOnError`.**
  Structured output replaces brittle prompt-parsing in extraction. Needs DBR 15.4 LTS+. Extend nb 08.
  Source: docs sql ai_query.
- **T1.9 AI Gateway (nb 07) extensions (all Beta — mark):** Guardrails (PII redact/block, safety,
  jailbreak, custom; block/sanitize on input/output); usage system table `system.ai_gateway.usage`
  + built-in cost dashboard; fallbacks/failover on 429/5xx (external models, backups at 0% traffic).
  Source: docs ai-gateway/guardrails + usage-tracking + configure-endpoints.
- **T1.10 Day-0 green-light gate (workshop ops).** Add a `ready` status to Register/Teams, a T-48h
  cutoff, a named rover to chase every red. The pre-read has a smoke test but no enforcement; the
  slowest ~20% silently fail hour 1. Source: hackathon.guide.
- **T1.11 Attendee troubleshooting page (new hub page).** Common errors + fixes (auth, Genie
  throttle, OBO access-denied, npm-proxy 404, missing SP grant, Agent-mode-not-on, GitHub-blocked
  installer). Seed from the gotchas already documented for facilitators. Scales the rover ratio.
- **T1.12 First-win checkpoint in the Day-1 agenda.** A collective early success ("everyone has the
  Finance Genie answering one query by 10:30"). Novices need their *own* first green run early.
  Source: hackathon.guide. (Pairs with the prior codex "Start here" finding.)
- **T1.13 Judging mechanics in the facilitator playbook.** 15-min calibration on sample submissions,
  conflict-of-interest recusal, top-3 stack-rank normalization, ≥3 judges/team, hard demo time-box.
  Add a recuse action + per-team judge count to the Judge page. Source: MLH judging guide.
- **T1.14 OBO in Databricks Apps (Public Preview).** Apps can act as the logged-in user via the
  `x-forwarded-access-token` header (scopes sql/genie/files/serving); admin-enable + app restart;
  scopes set in UI, not DABs. The whole Day-1 per-user-governance thesis; the hub honestly uses
  app-SP + `X-Forwarded-Email`. Add a BuildSetup + nb-02 callout; confirm enabled on the lab.
  Source: docs databricks-apps/auth.
- **T1.15 App resources (declarative authorization).** Declare warehouse / serving endpoint / secret
  / UC volume/table/function / Genie space / **Lakebase database** as app resources; Databricks
  injects `DATABRICKS_CLIENT_ID/SECRET` and you grant the SP least-privilege per resource. Supersedes
  our documented "SP rotates → manually re-grant" toil. Add to hub README + BuildSetup. Source: docs
  databricks-apps/resources.
- **T1.16 `bundle deploy` ≠ `bundle run` for apps — make it loud.** `bundle deploy` creates +
  uploads but does not start the app; you must `bundle run <app>`. #1 first-timer footgun; only in
  the hub README, not root README Quickstart. Add the two-step + a BuildSetup warning. Source: docs
  bundles/apps-tutorial.

## Tier 2 — for-later / nice-to-have (Resources tier + optional)

Feeds the "After the hackathon: production AI platform" Resources group (the locked decision) and
optional appendices. None required to ship anything during the event.

- **T2.1 Custom / BYO / OSS Model Serving** — log→UC register→endpoint; Provisioned Throughput FM
  APIs (GA) for fine-tuned models; External Models via Unity AI Gateway. **GPU_LARGE + Custom-LLM
  serving are Beta — a trap for a 2-day event; steer to FM APIs / PT.** Resources pointer + optional
  read-only markdown appendix. Source: docs model-serving/custom-models.
- **T2.2 MLflow Prompt Registry + UC model aliases (Champion/Challenger).** Versioned UC-backed
  prompts (`load_prompt("prompts:/name@alias")`); aliases replace deprecated Stages. Resources.
- **T2.3 MLflow production monitoring (Beta) with online scorers.** Schedule built-in judges on live
  traces; gotcha: custom code `@scorer` is offline-only. Resources pointer; flag Beta.
- **T2.4 Genie Agent Mode (Preview) + Inspect (Beta) latest features** — multi-step reasoning with
  streaming traces, parallel queries, auto SQL verification. Resources "latest features" pointer.
- **T2.5 Qwen3-Embedding-0.6B is the recommended embedding default** (32k context, Matryoshka). We
  already use `qwen3-embed` — confirm it's the default in nb 08; keep GTE/BGE as fallback. Mark Preview.
- **T2.6 App observability (OTel) + multi-instance scaling.** 2026 Apps emit OTel traces/logs/metrics
  to UC tables; horizontal scaling with session affinity. One line in the guide ship step.
- **T2.7 Pin AppKit version.** AppKit is v0 (0.41.x), pre-1.0; minor releases can break. Pin exact
  `@databricks/appkit*` in the hub `package.json` + note in README.
- **T2.8 Team matchmaking + skill-mix** ("needs a team" flag on Teams page; pair beginners+advanced).
- **T2.9 Code of Conduct + reporting path + tiered awards** (CoC checkbox at Register; enumerate the
  "Named awards" the plan already gestures at: best first-time team, most creative, etc.).
- **T2.10 Free Edition quota brick risk.** Exceeding FE daily/monthly quota halts the *whole*
  workspace; FMAPI has ITPM/OTPM burst limits a full room can trip. Keep heavy work on Vocareum;
  warn in the FE-fallback note.

## Routing into existing plans

- Tier 0 + most of Tier 1 setup/curriculum items → **fold into plan 002** (BYO setup, Genie Code
  Agent mode, Lakebase projects, repo fixes) and the **curriculum addendum** (00/04a/08a, eval→MLflow 3,
  nb 07/08 extensions, Genie checklist).
- Workshop-ops items (T1.10–T1.13) + deploy items (T1.14–T1.16) → a **facilitator runbook + hub
  Troubleshooting/Day-0 page** (new artifacts; smallest standalone unit set).
- Tier 2 → the **"After the hackathon" Resources group** + optional read-only appendices.

## Verification

- Every cited feature re-checked against a GA/Preview doc page (not a blog) before it lands in
  attendee-facing copy; Preview/Beta items labeled in the UI.
- Foundation-model names + region/preview availability re-verified on the event-workspace the
  morning of Day 1 (runbook step).
- Notebook count reconciled repo-wide; DAB job lists every notebook; no `00` collision.
- `/codex review` of this plan: accuracy + scope + dedupe gate PASS.
