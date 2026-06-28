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
}

export const TRACKS: Track[] = [
  {
    key: 'finance',
    name: 'Finance variance copilot',
    domain: 'Finance',
    goal: 'Governed text2SQL over akzo_finance → four-way variance decomposition (price/volume/FX/cost) + a recommended action.',
    shipTarget: 'Working notebook + live MLflow trace + a forecast_overrides row written to Lakebase.',
    goldenQuestion: 'What happened to Paints EMEA gross margin in Q2 vs Q1?',
    starterPath: 'starters/finance',
    evalPath: 'eval/finance.yaml',
  },
  {
    key: 'scm',
    name: 'SCM OTIF rescue',
    domain: 'Supply chain',
    goal: 'OTIF / inventory / service-level agent → root-cause (stockouts, lead-time drift) → expedite / reroute / reorder.',
    shipTarget: 'Root-cause answer + a scm_interventions row staged for approval.',
    goldenQuestion: 'Why did Rotterdam→EMEA-DACH OTIF drop to 88.9% in May?',
    starterPath: 'starters/scm',
    evalPath: 'eval/scm.yaml',
  },
  {
    key: 'commercial',
    name: 'Commercial churn defender',
    domain: 'Commercial',
    goal: 'Account / pipeline / churn agent → at-risk accounts + signals → next-best-action (outreach / discount / review).',
    shipTarget: 'At-risk list + a commercial_actions row for approval.',
    goldenQuestion: 'Which EMEA accounts are at churn risk and why?',
    starterPath: 'starters/commercial',
    evalPath: 'eval/commercial.yaml',
  },
  {
    key: 'supervisor',
    name: 'Cross-domain supervisor',
    domain: 'Multi-agent',
    goal: 'Multi-Agent Supervisor routing cross-domain questions to Finance / SCM / Commercial Genie spaces → fused answer under OBO.',
    shipTarget: 'One question answered across all three domains with a per-user trace.',
    goldenQuestion: 'Paints EMEA margin dropped 8% — is it price, supply, or demand?',
    starterPath: 'starters/supervisor',
    evalPath: 'eval/supervisor.yaml',
  },
  {
    key: 'governance',
    name: 'AI Gateway governance',
    domain: 'Platform',
    goal: 'Govern LLM calls — model choice, rate limits, spend caps, payload logging — with OBO identity checks.',
    shipTarget: 'A policy that caps spend + a payload_logs audit query.',
    goldenQuestion: 'Which LLM calls exceeded the cost cap this week?',
    starterPath: 'starters/governance',
    evalPath: 'eval/governance.yaml',
  },
  {
    key: 'forecast',
    name: 'Forecast override planner',
    domain: 'Finance',
    goal: 'Paints EMEA forecast override agent: explain deltas → propose override → Lakebase write with the synced-table pattern.',
    shipTarget: 'A forecast_overrides row written + approved.',
    goldenQuestion: 'Should we override the Paints EMEA forecast given the OTIF miss?',
    starterPath: 'starters/forecast',
    evalPath: 'eval/forecast.yaml',
  },
  {
    key: 'quote',
    name: 'Quote-to-cash agent',
    domain: 'Commercial',
    goal: 'Densest end-to-end: parse RFQ → Genie pricing → draft quote → Lakebase write → approval queue → execute (email + CRM + mock PO).',
    shipTarget: 'A quote drafted, approved, and "executed" against the mock systems.',
    goldenQuestion: 'Quote 5,000 units of DEC-1008 at a 10% discount — is it within policy?',
    starterPath: 'starters/quote',
    evalPath: 'eval/quote.yaml',
  },
  {
    key: 'action',
    name: 'Agents that act (L1→L4)',
    domain: 'Action',
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
