/**
 * Static workshop inventory that drives the launcher pages. Sourced from
 * WORKSHOP_MATERIALS.md / BUILD_PLAN.md / AGENTS_THAT_ACT_PLAN.md. The hackathon
 * *state* (teams, submissions, scores) is live in Lakebase via /api/hack/*; this
 * module is the read-only catalogue of what was already built.
 */

export const REPO_BASE =
  'https://github.com/Praneeth16/akzo-agent-bricks-workshop/blob/main';

export interface Track {
  key: string;
  name: string;
  domain: string;
  goal: string;
  shipTarget: string;
  goldenQuestion: string;
  starterPath: string;
  evalPath: string;
  role?: string; // workshop role from the deck (flagship / teaching / showcase / adjacent)
  deckNo?: string; // use-case number in the AkzoNobel deck
}

// Use-case names + roles + numbers reconciled to the source deck
// "Agentbricks - Databricks x AkzoNobel" (5 priority + 2 adjacent). The `action`
// track is a bonus beyond the deck's seven (the deck folds acting into Quote + L5).
export const TRACKS: Track[] = [
  {
    key: 'finance',
    name: 'Finance controlling copilot',
    domain: 'Finance',
    role: 'Teaching thread + live showcase',
    deckNo: '01',
    goal: 'Governed text2SQL over akzo_finance → four-way variance decomposition (price/volume/FX/cost) + a recommended action.',
    shipTarget: 'Working notebook + live MLflow trace + a forecast_overrides row written to Lakebase.',
    goldenQuestion: 'What happened to Paints EMEA gross margin in Q2 vs Q1?',
    starterPath: 'starters/finance',
    evalPath: 'eval/finance.yaml',
  },
  {
    key: 'scm',
    name: 'SCM control tower copilot',
    domain: 'Supply chain',
    role: 'Priority use case',
    deckNo: '02',
    goal: 'OTIF / inventory / service-level agent → root-cause (stockouts, lead-time drift) → expedite / reroute / reorder.',
    shipTarget: 'Root-cause answer + a scm_interventions row staged for approval.',
    goldenQuestion: 'Why did Rotterdam→EMEA-DACH OTIF drop to 88.9% in May?',
    starterPath: 'starters/scm',
    evalPath: 'eval/scm.yaml',
  },
  {
    key: 'commercial',
    name: 'Commercial action assistant',
    domain: 'Commercial',
    role: 'Priority use case',
    deckNo: '05',
    goal: 'Account / pipeline / churn agent → at-risk accounts + signals → next-best-action (outreach / discount / review).',
    shipTarget: 'At-risk list + a commercial_actions row for approval.',
    goldenQuestion: 'Which EMEA accounts are at churn risk and why?',
    starterPath: 'starters/commercial',
    evalPath: 'eval/commercial.yaml',
  },
  {
    key: 'supervisor',
    name: 'Multi-domain supervisor',
    domain: 'Multi-agent',
    role: 'Flagship + the whole-game demo',
    deckNo: '03',
    goal: 'Multi-Agent Supervisor routing cross-domain questions to Finance / SCM / Commercial Genie spaces → fused answer under OBO.',
    shipTarget: 'One question answered across all three domains with a per-user trace.',
    goldenQuestion: 'Paints EMEA margin dropped 8% — is it price, supply, or demand?',
    starterPath: 'starters/supervisor',
    evalPath: 'eval/supervisor.yaml',
  },
  {
    key: 'governance',
    name: 'AI governance & policy agent',
    domain: 'Platform',
    role: 'Priority use case',
    deckNo: '04',
    goal: 'Govern LLM calls — model choice, rate limits, spend caps, payload logging — with OBO identity checks.',
    shipTarget: 'A policy that caps spend + a payload_logs audit query.',
    goldenQuestion: 'Which LLM calls exceeded the cost cap this week?',
    starterPath: 'starters/governance',
    evalPath: 'eval/governance.yaml',
  },
  {
    key: 'forecast',
    name: 'Forecast planner copilot (MMF)',
    domain: 'Finance',
    role: 'Adjacent track',
    deckNo: '06',
    goal: 'Paints EMEA forecast override agent: explain deltas → propose override → Lakebase write with the synced-table pattern.',
    shipTarget: 'A forecast_overrides row written + approved.',
    goldenQuestion: 'Should we override the Paints EMEA forecast given the OTIF miss?',
    starterPath: 'starters/forecast',
    evalPath: 'eval/forecast.yaml',
  },
  {
    key: 'quote',
    name: 'Pricing & quote agent',
    domain: 'Commercial',
    role: 'Showcase · the agent acts',
    deckNo: '18',
    goal: 'Document Intelligence reads the RFQ → Genie pricing → draft quote → Lakebase write behind an approval gate → execute (email + CRM + mock PO).',
    shipTarget: 'A quote drafted, approved, and "executed" against the mock systems.',
    goldenQuestion: 'Quote 5,000 units of DEC-1008 at a 10% discount — is it within policy?',
    starterPath: 'starters/quote',
    evalPath: 'eval/quote.yaml',
  },
  {
    key: 'action',
    name: 'Agents that act (L1→L4)',
    domain: 'Action',
    role: "Bonus track (beyond the deck's seven)",
    deckNo: '—',
    goal: 'The Action Maturity Ladder: propose → evaluate guardrails → approve → execute to an external system via a governed UC HTTP connection.',
    shipTarget: 'An action executed end-to-end with an external_ref + audit lineage, plus a breach→escalate path.',
    goldenQuestion: 'Expedite the DEC-1000 reorder as an L3 action — does it pass guardrails?',
    starterPath: 'starters/action',
    evalPath: 'eval/action.yaml',
  },
];

export interface Notebook {
  file: string;
  title: string;
  layer: string;
  blurb: string;
}

export const NOTEBOOKS: Notebook[] = [
  { file: 'notebooks/01_domain_agent_finance.py', title: 'The domain agent: Finance over governed data', layer: 'Layer 1', blurb: 'Genie + UC metric views + text2SQL on akzo_finance.' },
  { file: 'notebooks/02_per_user_truth_uc_obo.py', title: 'Per-user truth: Unity Catalog RLS/ABAC + OBO', layer: 'Layer 2', blurb: 'Same question, different rows: controller vs planner.' },
  { file: 'notebooks/03_scm_commercial_legs.py', title: 'More domain legs: SCM + Commercial', layer: 'Layer 3', blurb: 'OTIF, service levels, churn signals as new agents.' },
  { file: 'notebooks/04_supervisor_agent.py', title: 'The supervisor itself', layer: 'Layer 4', blurb: 'Multi-Agent Supervisor routing across three Genie spaces.' },
  { file: 'notebooks/05_lakebase_memory_action.py', title: 'Memory + action (Lakebase)', layer: 'Layer 5', blurb: 'Write-back + approval patterns — the agent acts.' },
  { file: 'notebooks/06_mlflow_eval_judge.py', title: 'Trust: MLflow eval + an LLM judge', layer: 'Layer 6', blurb: 'Tracing + golden-question evals + MemAlign.' },
  { file: 'notebooks/07_ai_gateway_govern.py', title: 'Govern at scale: AI Gateway', layer: 'Layer 7', blurb: 'Routes, spend caps, rate limits, payload logs.' },
  { file: 'notebooks/08_doc_intelligence_qwen.py', title: 'Document intelligence with the latest AI functions', layer: 'Extra', blurb: 'ai_parse_document → ai_extract → auto-chunk → Qwen embed → Vector Search → RAG.' },
  { file: 'notebooks/09_agents_that_act.py', title: 'Agents that act — the maturity ladder (L1→L4)', layer: 'Action', blurb: 'Propose → guardrail → approve → execute → lineage.' },
  { file: 'notebooks/10_autonomous_closed_loop.py', title: 'Autonomous closed loop', layer: 'Action', blurb: 'Detect → act → verify → escalate, idempotent.' },
];

export interface DeployedApp {
  name: string;
  url: string | null;
  blurb: string;
  status: string;
}

export const APPS: DeployedApp[] = [
  { name: 'akzo-supervisor', url: 'https://akzo-supervisor-7474654904882204.aws.databricksapps.com', status: 'ACTIVE', blurb: 'Cross-domain routing (Finance/SCM/Commercial) + fused answer + per-user (OBO) trace.' },
  { name: 'akzo-finance-copilot', url: 'https://akzo-finance-copilot-7474654904882204.aws.databricksapps.com', status: 'ACTIVE', blurb: 'Variance decomposition (price/volume/FX/cost bridge) + recommended action.' },
  { name: 'akzo-quote-agent', url: 'https://akzo-quote-agent-7474654904882204.aws.databricksapps.com', status: 'ACTIVE', blurb: 'read→reason→act→write→approve: parse RFQ → price → Lakebase quote → approval queue.' },
  { name: 'akzo-action-center', url: null, status: 'ACTIVE', blurb: "The exec's single screen: cross-agent action queue, maturity ladder, guardrail verdicts, approve/execute." },
  { name: 'akzo-mock-systems', url: null, status: 'ACTIVE', blurb: 'Governed external target (email/teams/crm/erp/sharepoint/ticket) for agent actions; logs receipts.' },
];

export interface AgendaLayer {
  layer: string;
  title: string;
  blurb: string;
}

export const DAY1_AGENDA: AgendaLayer[] = [
  { layer: 'Layer 1', title: 'The domain agent', blurb: 'A Finance agent over governed data — the whole game, end to end.' },
  { layer: 'Layer 2', title: 'Per-user truth (OBO)', blurb: 'Unity Catalog RLS/ABAC so each user sees only their rows.' },
  { layer: 'Layer 3', title: 'More domain legs', blurb: 'Add SCM and Commercial agents.' },
  { layer: 'Layer 4', title: 'The supervisor', blurb: 'Route cross-domain questions and fuse the answer.' },
  { layer: 'Layer 5', title: 'Memory + action', blurb: 'Lakebase write-back with approval — the agent acts.' },
  { layer: 'Layer 6', title: 'Trust', blurb: 'MLflow evaluation and an LLM judge over golden questions.' },
  { layer: 'Layer 7', title: 'Govern at scale', blurb: 'AI Gateway: spend caps, rate limits, payload logging.' },
];

export interface ResourceLink {
  label: string;
  href: string;
  blurb: string;
}

export const RESOURCES: ResourceLink[] = [
  { label: 'Agent Bricks', href: 'https://www.databricks.com/product/artificial-intelligence/agent-bricks', blurb: 'Genie, Multi-Agent Supervisor, Knowledge Assistant.' },
  { label: 'Databricks AppKit', href: 'https://developers.databricks.com/docs/appkit/v0/', blurb: 'The SDK this very app is built on — dogfooding the stack.' },
  { label: 'Lakebase', href: 'https://www.databricks.com/product/lakebase', blurb: 'Managed Postgres backing the hackathon state you see here.' },
  { label: 'Databricks Apps', href: 'https://www.databricks.com/product/databricks-apps', blurb: 'How every app in this workshop is hosted.' },
];

export interface DocLink {
  title: string;
  file: string;
  blurb: string;
}

export const MATERIALS: DocLink[] = [
  { title: 'Workshop materials index', file: 'WORKSHOP_MATERIALS.md', blurb: 'The master index of everything built.' },
  { title: 'Workshop plan', file: 'AKZONOBEL_WORKSHOP_PLAN.md', blurb: 'Strategy, scope, and the focus-5 use cases.' },
  { title: 'Agenda', file: 'WORKSHOP_AGENDA.md', blurb: 'Day-1 and Day-2 run of show.' },
  { title: 'Demo plan', file: 'AKZONOBEL_DEMO_PLAN.md', blurb: 'The numbered demo narratives.' },
  { title: 'Vibe-coding session', file: 'VIBE_CODING_SESSION.md', blurb: 'Genie Code mechanics + the build loop.' },
  { title: 'Agents that act', file: 'AGENTS_THAT_ACT_PLAN.md', blurb: 'The Action Maturity Ladder, architecture, and guards.' },
];

export const TRACK_KEYS = TRACKS.map((t) => t.key);

// ---------------------------------------------------------------------------
// Per-track build guides. The spine is Genie Code: Genie's side-pane agent mode
// where you prompt in natural language and it writes the SQL / analysis for you.
// Each guide turns a track into a build-by-prompting recipe.
// ---------------------------------------------------------------------------
export interface TrackGuide {
  key: string;
  schema: string;
  whatItIs: string;
  whyItMatters: string;
  prerequisites: string[];
  genieCodeSteps: { title: string; prompt?: string; note?: string }[];
  shipTarget: string;
  evalNote: string;
  notebook: string;
}

const CAT = 'serverless_lakebase_praneeth_catalog';

export const GUIDES: TrackGuide[] = [
  {
    key: 'finance',
    schema: `${CAT}.akzo_finance`,
    whatItIs: 'A controlling copilot that explains a margin move by decomposing it into price, volume, FX, and cost.',
    whyItMatters: 'Finance teams spend hours reconciling a margin delta by hand. A governed agent does it in one question and stages the recommended action.',
    prerequisites: ['Access to the akzo_finance schema', 'A Genie space (or Genie Code) pointed at akzo_finance', 'SQL warehouse 4d39ac2e32b72a3a'],
    genieCodeSteps: [
      { title: 'Open Genie Code on the finance schema', note: 'In the workspace, open a Genie space scoped to akzo_finance (or the Genie side-pane in a notebook). This is where you prompt instead of writing SQL.' },
      { title: 'Ground the agent in the data', prompt: 'Describe the tables in akzo_finance and how margin_actuals, margin_budget, products, fx_rates and cost_drivers join. What grain is each at?' },
      { title: 'Reproduce the headline number', prompt: 'For Decorative Paints in EMEA, what was gross margin % by quarter in 2026? Show Q1 vs Q2 and the delta in percentage points.' },
      { title: 'Decompose the delta', prompt: 'Decompose the Q2-vs-Q1 Paints EMEA gross-margin change into price, volume, FX, and cost effects. Return one row per effect with its pp contribution.' },
      { title: 'Recommend an action', prompt: 'Given the decomposition, propose one concrete pricing or hedging action with an estimated margin recovery, in two sentences.' },
      { title: 'Stage it for approval', note: 'Wire the recommendation to a forecast_overrides row in Lakebase with status=pending (see starters/finance and notebook 05). The agent proposes; a human approves.' },
    ],
    shipTarget: 'A working notebook + a live MLflow trace + a forecast_overrides row written to Lakebase.',
    evalNote: 'Run eval/finance.yaml golden questions through the MLflow judge.',
    notebook: 'notebooks/01_domain_agent_finance.py',
  },
  {
    key: 'scm',
    schema: `${CAT}.akzo_scm`,
    whatItIs: 'An OTIF rescue agent that root-causes a service drop and proposes an expedite, reroute, or reorder.',
    whyItMatters: 'A missed OTIF cascades into lost margin and churn. Finding the lane and SKU behind it fast is the whole game.',
    prerequisites: ['Access to akzo_scm', 'Genie Code on akzo_scm', 'SQL warehouse'],
    genieCodeSteps: [
      { title: 'Open Genie Code on the SCM schema', note: 'Scope a Genie space to akzo_scm.' },
      { title: 'Ground in the data', prompt: 'Describe akzo_scm: otif, inventory, lanes, service_levels. What is the grain and how do they relate?' },
      { title: 'Find the drop', prompt: 'Which plant and month had the largest OTIF decline in 2026? Show OTIF % by month for the Rotterdam-NL plant.' },
      { title: 'Root-cause it', prompt: 'For Rotterdam-NL in the worst month, which SKUs and lanes drove the OTIF miss? Bring in lead-time drift and stockouts from inventory.' },
      { title: 'Propose an intervention', prompt: 'Recommend one intervention (expedite, reroute, or reorder) for the top offending SKU, with the trade-off in one sentence.' },
      { title: 'Stage it', note: 'Write a scm_interventions row to Lakebase with status=pending for approval (starters/scm).' },
    ],
    shipTarget: 'A root-cause answer + a scm_interventions row staged for approval.',
    evalNote: 'eval/scm.yaml golden questions via the judge.',
    notebook: 'notebooks/03_scm_commercial_legs.py',
  },
  {
    key: 'commercial',
    schema: `${CAT}.akzo_commercial`,
    whatItIs: 'A churn-defender that finds at-risk accounts and proposes the next best action.',
    whyItMatters: 'Catching a churn signal before renewal is worth far more than a post-mortem.',
    prerequisites: ['Access to akzo_commercial', 'Genie Code on akzo_commercial'],
    genieCodeSteps: [
      { title: 'Open Genie Code on the commercial schema' },
      { title: 'Ground in the data', prompt: 'Describe akzo_commercial: accounts, pipeline, sales_actuals, churn_signals. How do they join on account_id?' },
      { title: 'Find at-risk accounts', prompt: 'Which EMEA accounts have a churn_score above 0.7 in the latest month? Show name, score, complaint_count, and NPS.' },
      { title: 'Explain the risk', prompt: 'For the top at-risk account, what signals explain the score? Look at order recency, complaints, and NPS trend.' },
      { title: 'Next best action', prompt: 'Recommend one next-best-action (outreach, discount, or account review) for each at-risk account, one line each.' },
      { title: 'Stage it', note: 'Write a commercial_actions row to Lakebase for approval (starters/commercial).' },
    ],
    shipTarget: 'An at-risk list + a commercial_actions row for approval.',
    evalNote: 'eval/commercial.yaml via the judge.',
    notebook: 'notebooks/03_scm_commercial_legs.py',
  },
  {
    key: 'supervisor',
    schema: `${CAT} (all three domains)`,
    whatItIs: 'A Multi-Agent Supervisor that routes a cross-domain question to Finance / SCM / Commercial and fuses the answer under OBO.',
    whyItMatters: 'Real questions cross domains. The supervisor is the pattern that makes a fleet of domain agents feel like one assistant.',
    prerequisites: ['The three domain agents or Genie spaces exist', 'On-behalf-of (OBO) configured'],
    genieCodeSteps: [
      { title: 'Build the three legs first', note: 'Do the finance, scm, and commercial guides first; the supervisor routes to them.' },
      { title: 'Frame the routing prompt', prompt: 'Paints EMEA margin dropped about 8 points. Is it price, supply, or demand? Decide which domain(s) to consult and why.' },
      { title: 'Fan out and fuse', prompt: 'Consult the finance, scm, and commercial agents as needed and return one fused answer that ties margin, OTIF, and churn together.' },
      { title: 'Show the per-user scope', note: 'Run the same question as a controller vs a planner identity; OBO returns different rows (notebook 02).' },
    ],
    shipTarget: 'One question answered across all three domains with a per-user trace.',
    evalNote: 'eval/supervisor.yaml via the judge.',
    notebook: 'notebooks/04_supervisor_agent.py',
  },
  {
    key: 'governance',
    schema: `${CAT}.akzo_gateway`,
    whatItIs: 'An AI Gateway governance agent: model choice, rate limits, spend caps, and payload logging with OBO identity checks.',
    whyItMatters: 'Governance is what lets agents run in production without a blank cheque or a data-leak.',
    prerequisites: ['AI Gateway enabled', 'akzo_gateway.payload_logs available'],
    genieCodeSteps: [
      { title: 'Open Genie Code on akzo_gateway' },
      { title: 'Audit spend', prompt: 'From payload_logs, which LLM calls exceeded the per-request cost cap this week? Group by endpoint and user.' },
      { title: 'Set a policy', note: 'Define a spend cap + rate limit on a gateway route (notebook 07); show a blocked call.' },
      { title: 'Prove OBO', prompt: 'Show that the same query returns only the rows the calling identity is entitled to.' },
    ],
    shipTarget: 'A policy that caps spend + a payload_logs audit query.',
    evalNote: 'eval/governance.yaml via the judge.',
    notebook: 'notebooks/07_ai_gateway_govern.py',
  },
  {
    key: 'forecast',
    schema: `${CAT}.akzo_finance`,
    whatItIs: 'A forecast-override planner: explain a delta, propose an override, write it back with the synced-table pattern.',
    whyItMatters: 'Forecasts that nobody can adjust with rationale get ignored. This makes overrides explainable and governed.',
    prerequisites: ['akzo_finance access', 'Lakebase forecast_overrides table'],
    genieCodeSteps: [
      { title: 'Open Genie Code on akzo_finance' },
      { title: 'Explain the delta', prompt: 'For Paints EMEA, how does the latest forecast compare to actuals and budget? Explain the biggest delta.' },
      { title: 'Propose the override', prompt: 'Given the OTIF miss feeding into demand, propose a forecast override value for next month with a one-sentence rationale.' },
      { title: 'Write it back', note: 'Persist a forecast_overrides row to Lakebase and approve it (starters/forecast, notebook 05).' },
    ],
    shipTarget: 'A forecast_overrides row written + approved.',
    evalNote: 'eval/forecast.yaml via the judge.',
    notebook: 'notebooks/05_lakebase_memory_action.py',
  },
  {
    key: 'quote',
    schema: `${CAT}.akzo_finance + akzo.quotes (Lakebase)`,
    whatItIs: 'The densest end-to-end loop: parse an RFQ, price it via Genie, draft a quote, write to Lakebase, queue for approval, execute.',
    whyItMatters: 'It is the full read, reason, act, write, approve loop on one screen, the clearest demo of agents that act.',
    prerequisites: ['akzo_finance pricing data', 'Lakebase quotes table', 'Mock systems app for execute'],
    genieCodeSteps: [
      { title: 'Parse the RFQ', note: 'Use ai_extract / ai_parse_document on a sample RFQ to pull SKU, quantity, requested discount (notebook 08).' },
      { title: 'Price it', prompt: 'For DEC-1008, what is the list price and standard cost? At a 10% discount on 5,000 units, what is the margin %?' },
      { title: 'Check policy', prompt: 'Is a 10% discount within policy for this product line? If not, what is the maximum allowed?' },
      { title: 'Draft + stage', note: 'Write a quotes row to Lakebase with status=pending.' },
      { title: 'Approve + execute', note: 'On approval, execute against the mock systems (email + CRM + mock PO) and log the receipt.' },
    ],
    shipTarget: 'A quote drafted, approved, and executed against the mock systems.',
    evalNote: 'eval/quote.yaml via the judge.',
    notebook: 'notebooks/08_doc_intelligence_qwen.py',
  },
  {
    key: 'action',
    schema: `akzo.actions (Lakebase) + UC HTTP connection`,
    whatItIs: 'The Action Maturity Ladder: propose, evaluate guardrails, approve, execute to an external system via a governed UC HTTP connection.',
    whyItMatters: 'This is the answer to "can agents take action?" with governance: identity, policy, approval, and audit lineage.',
    prerequisites: ['akzo.actions / action_policies tables', 'UC HTTP connection akzo_external_systems', 'Mock systems app'],
    genieCodeSteps: [
      { title: 'Understand the ladder', note: 'Read notebook 09: L1 recommend, L2 stage+approve, L3 execute externally, L4 autonomous.' },
      { title: 'Propose an action', prompt: 'Propose an L3 action to expedite the DEC-1000 reorder. What payload and target system does it need?' },
      { title: 'Evaluate guardrails', prompt: 'Check the action against action_policies: discount cap, spend cap, allowed regions. Does it pass or should it escalate?' },
      { title: 'Execute + audit', note: 'On approval, execute via the akzo_external_systems UC HTTP connection; capture external_ref + lineage (notebook 09b/10).' },
      { title: 'Try the breach path', note: 'Submit an over-cap action and watch it escalate instead of executing.' },
    ],
    shipTarget: 'An action executed end-to-end with an external_ref + audit lineage, plus a breach to escalate path.',
    evalNote: 'eval/action.yaml via the judge.',
    notebook: 'notebooks/09_agents_that_act.py',
  },
];

// ---------------------------------------------------------------------------
// Build setup: the Databricks ai-dev-kit + skills, plus open-source skills.
// ---------------------------------------------------------------------------
export interface SetupStep {
  title: string;
  body: string;
  command?: string;
}

export const SETUP_STEPS: SetupStep[] = [
  {
    title: '1. Install + configure the Databricks CLI',
    body: 'Authenticate the CLI to this workspace once. Everything below (skills, bundles, apps) runs through it.',
    command: 'databricks auth login --host https://fevm-serverless-lakebase-praneeth.cloud.databricks.com --profile fe-vm-lakebase-praneeth',
  },
  {
    title: '2. Install the AI dev kit (Agent Skills) into your coding agent',
    body: 'The ai-dev-kit installs Databricks Agent Skills into your coding assistant (Claude Code, Cursor, etc.) so it knows how to drive the CLI, explore data, and scaffold apps. Run once per machine.',
    command: 'databricks experimental aitools install',
  },
  {
    title: '3. Browse + manage the installed skills',
    body: 'List the skills the dev kit installed and what each does. These teach your agent the Databricks-native patterns used across this workshop.',
    command: 'databricks experimental aitools skills',
  },
  {
    title: '4. Point your agent at the workspace',
    body: 'Open this repo in your coding agent with the fe-vm-lakebase-praneeth profile active. Ask it to explore the akzo_* schemas; the skills make it Databricks-aware.',
  },
  {
    title: '5. Build by prompting with Genie Code',
    body: 'For each hackathon track, open the per-track Guide and follow the Genie Code steps. Genie Code is the side-pane agent that writes the SQL/analysis from your natural-language prompt, so you build by describing what you want.',
  },
];

export interface SkillRef {
  name: string;
  what: string;
  href: string;
}

export const SKILLS: SkillRef[] = [
  { name: 'Databricks ai-dev-kit (Agent Skills)', what: 'Databricks-native skills for your coding agent: CLI, auth, data exploration, app dev. Install with `databricks experimental aitools install`.', href: 'https://developers.databricks.com/docs/tools/ai-tools/agent-skills' },
  { name: 'Databricks Docs MCP Server', what: 'Give your agent live access to Databricks docs while it builds.', href: 'https://developers.databricks.com/docs/tools/ai-tools/docs-mcp-server' },
  { name: 'AppKit Agent Skills', what: 'Scaffold and evolve Databricks Apps (like this hub) with an AI assistant.', href: 'https://developers.databricks.com/docs/appkit/v0/development/ai-assisted-development' },
  { name: 'gstack', what: 'Open-source skill suite: browse, qa, review, ship, plan-and-design loops for agentic dev.', href: 'https://garryslist.org' },
  { name: 'compound-engineering', what: 'Open-source ce-plan / ce-work / ce-review skills for plan-then-build workflows.', href: 'https://github.com/' },
];

// ---------------------------------------------------------------------------
// Demos: the narrated showcases shipped in the repo.
// ---------------------------------------------------------------------------
export interface DemoRef {
  title: string;
  blurb: string;
  stack: string;
  doc: string;
}

export const DEMOS: DemoRef[] = [
  { title: 'Agents that act (L1 to L4)', blurb: 'The Action Maturity Ladder walked end to end: recommend a margin-recovery action, stage it, approve, execute to email + mock PO, verify, and escalate on a guardrail breach.', stack: 'Agent Bricks + Lakebase + guardrails + UC HTTP connection + AI Gateway', doc: 'demo/agents_that_act.md' },
  { title: 'Cross-domain supervisor', blurb: 'A single question (margin down 8pp: price, supply, or demand?) routed across Finance, SCM, and Commercial and fused into one answer under OBO.', stack: 'Multi-Agent Supervisor + Genie + Unity Catalog OBO', doc: 'AKZONOBEL_DEMO_PLAN.md' },
  { title: 'Quote-to-cash', blurb: 'Parse an RFQ, price via Genie, draft a quote, write to Lakebase, approve, and execute against mock systems.', stack: 'ai_extract + Genie + Lakebase + approval + mock systems', doc: 'AKZONOBEL_DEMO_PLAN.md' },
  { title: 'Document intelligence', blurb: 'SDS and supplier contracts parsed with ai_parse_document, extracted with ai_extract, auto-chunked, embedded with Qwen, searched over Vector Search, and answered with RAG.', stack: 'ai_parse_document + ai_extract + Qwen embeddings + Vector Search', doc: 'AKZONOBEL_DEMO_PLAN.md' },
];

// ---------------------------------------------------------------------------
// Curated resources, grouped by topic (enriched Resources tab).
// ---------------------------------------------------------------------------
export interface ResourceGroup {
  group: string;
  links: { label: string; href: string; blurb: string }[];
}

export const RESOURCE_GROUPS: ResourceGroup[] = [
  {
    group: 'Agent Bricks & agents',
    links: [
      { label: 'Agent Bricks', href: 'https://www.databricks.com/product/artificial-intelligence/agent-bricks', blurb: 'Genie, Multi-Agent Supervisor, Knowledge Assistant.' },
      { label: 'AI/BI Genie', href: 'https://docs.databricks.com/aws/en/genie/', blurb: 'Natural-language analytics; Genie Code is the side-pane agent you build with.' },
    ],
  },
  {
    group: 'Build the app',
    links: [
      { label: 'Databricks AppKit', href: 'https://developers.databricks.com/docs/appkit/v0/', blurb: 'The SDK this hub is built on. Genie/Lakebase/analytics plugins.' },
      { label: 'Databricks Apps', href: 'https://www.databricks.com/product/databricks-apps', blurb: 'How every app in this workshop is hosted.' },
      { label: 'Asset Bundles (DABs)', href: 'https://docs.databricks.com/aws/en/dev-tools/bundles/', blurb: 'Deploy notebooks, jobs, and apps from one databricks.yml.' },
    ],
  },
  {
    group: 'Data, governance & trust',
    links: [
      { label: 'Lakebase', href: 'https://www.databricks.com/product/lakebase', blurb: 'Managed Postgres backing the hackathon state.' },
      { label: 'AI Gateway', href: 'https://docs.databricks.com/aws/en/ai-gateway/', blurb: 'Spend caps, rate limits, payload logging for LLM calls.' },
      { label: 'MLflow LLM evaluation', href: 'https://docs.databricks.com/aws/en/mlflow/llm-evaluate', blurb: 'Judge agents against golden questions.' },
      { label: 'Vector Search', href: 'https://docs.databricks.com/aws/en/generative-ai/vector-search', blurb: 'Index + search embeddings for RAG.' },
      { label: 'AI functions (ai_*)', href: 'https://docs.databricks.com/aws/en/large-language-models/ai-functions', blurb: 'ai_parse_document, ai_extract, ai_classify, ai_query in SQL.' },
    ],
  },
  {
    group: 'AI dev kit & skills',
    links: [
      { label: 'Agent Skills (ai-dev-kit)', href: 'https://developers.databricks.com/docs/tools/ai-tools/agent-skills', blurb: 'Install with `databricks experimental aitools install`.' },
      { label: 'Docs MCP Server', href: 'https://developers.databricks.com/docs/tools/ai-tools/docs-mcp-server', blurb: 'Live Databricks docs for your coding agent.' },
    ],
  },
  {
    group: 'Hands-on & pre-reads (from the workshop deck)',
    links: [
      { label: 'Agent Bricks product tour', href: 'https://www.databricks.com/product/artificial-intelligence/agent-bricks', blurb: 'Knowledge Assistant, Supervisor Agent, Custom Agents.' },
      { label: 'Databricks templates', href: 'https://developers.databricks.com/templates', blurb: 'Starting points for agentic apps.' },
      { label: 'Databricks Free Edition', href: 'https://www.databricks.com/learn/free-edition', blurb: 'Practice on a personal workspace.' },
      { label: 'Intelligent Document Processing', href: 'https://docs.databricks.com/aws/en/large-language-models/ai-functions', blurb: 'ai_parse_document + ai_extract for the Pricing & quote agent.' },
      { label: 'Agent tracing & evaluation (MLflow)', href: 'https://docs.databricks.com/aws/en/mlflow/llm-evaluate', blurb: 'Improve agent quality with golden questions.' },
    ],
  },
];

export const GUIDE_KEYS = GUIDES.map((g) => g.key);
