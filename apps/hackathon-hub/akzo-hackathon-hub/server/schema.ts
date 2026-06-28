/**
 * Hackathon state schema — additive `hack_*` tables in the existing Lakebase
 * `akzo` schema (search_path is pinned there). DDL is idempotent (IF NOT EXISTS)
 * so it is safe to run on every boot; seeding uses ON CONFLICT DO NOTHING so a
 * populated demo survives restarts without duplicating rows.
 */
import { query } from './lakebase.js';

const DDL = [
  `CREATE TABLE IF NOT EXISTS hack_teams (
     id            SERIAL PRIMARY KEY,
     team_name     TEXT NOT NULL UNIQUE,
     track         TEXT NOT NULL,
     contact_email TEXT,
     created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
   )`,
  `CREATE TABLE IF NOT EXISTS hack_members (
     id      SERIAL PRIMARY KEY,
     team_id INTEGER NOT NULL REFERENCES hack_teams(id) ON DELETE CASCADE,
     name    TEXT NOT NULL,
     email   TEXT,
     role    TEXT
   )`,
  `CREATE TABLE IF NOT EXISTS hack_registrations (
     id            SERIAL PRIMARY KEY,
     team_id       INTEGER REFERENCES hack_teams(id) ON DELETE CASCADE,
     email         TEXT NOT NULL,
     registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
   )`,
  `CREATE TABLE IF NOT EXISTS hack_submissions (
     id           SERIAL PRIMARY KEY,
     team_id      INTEGER NOT NULL REFERENCES hack_teams(id) ON DELETE CASCADE,
     track        TEXT NOT NULL,
     title        TEXT NOT NULL,
     summary      TEXT,
     artifact_url TEXT,
     artifact_kind TEXT NOT NULL DEFAULT 'notebook',
     status       TEXT NOT NULL DEFAULT 'submitted',
     submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
   )`,
  `CREATE TABLE IF NOT EXISTS hack_rubric (
     id          SERIAL PRIMARY KEY,
     criterion   TEXT NOT NULL UNIQUE,
     weight      NUMERIC NOT NULL DEFAULT 1,
     max_score   INTEGER NOT NULL DEFAULT 5,
     description TEXT,
     sort_order  INTEGER NOT NULL DEFAULT 0
   )`,
  `CREATE TABLE IF NOT EXISTS hack_scores (
     id            SERIAL PRIMARY KEY,
     submission_id INTEGER NOT NULL REFERENCES hack_submissions(id) ON DELETE CASCADE,
     judge_email   TEXT NOT NULL,
     criterion     TEXT NOT NULL,
     score         INTEGER NOT NULL,
     comment       TEXT,
     scored_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
     UNIQUE (submission_id, judge_email, criterion)
   )`,
  `CREATE TABLE IF NOT EXISTS hack_votes (
     id            SERIAL PRIMARY KEY,
     submission_id INTEGER NOT NULL REFERENCES hack_submissions(id) ON DELETE CASCADE,
     voter_email   TEXT NOT NULL,
     voted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
     UNIQUE (submission_id, voter_email)
   )`,
];

// Databricks Expert Choice rubric (the reference app judges "on the rubric").
const RUBRIC: Array<[string, number, number, string, number]> = [
  ['Business impact', 1.5, 5, 'Does it move a real AkzoNobel metric (margin, OTIF, churn, cycle time)?', 1],
  ['Technical execution', 1.0, 5, 'Does it actually work end-to-end on Databricks? Working code over slides.', 2],
  ['Use of Agent Bricks & platform', 1.25, 5, 'Genie, Supervisor, Lakebase, AI Gateway, governed actions used well.', 3],
  ['Governance & trust', 1.0, 5, 'OBO / guardrails / approval / lineage where actions are taken.', 4],
  ['Demo quality & story', 1.0, 5, 'Clear narrative, live demo, crisp framing of the win.', 5],
];

const TEAMS: Array<[string, string, string, string[]]> = [
  ['Margin Menders', 'finance', 'lena.fischer@akzonobel.com', ['Lena Fischer', 'Tomas Novak']],
  ['Lane Rangers', 'scm', 'ravi.menon@akzonobel.com', ['Ravi Menon', 'Sofie Jansen']],
  ['Churn Busters', 'commercial', 'marco.rossi@akzonobel.com', ['Marco Rossi', 'Ada Kowalski']],
  ['The Supervisors', 'supervisor', 'yuki.tanaka@akzonobel.com', ['Yuki Tanaka', 'Pieter de Vries']],
];

const SUBMISSIONS: Array<[string, string, string, string, string]> = [
  [
    'Margin Menders',
    'finance',
    'Paints EMEA margin-recovery copilot',
    'Decomposes the Q2 −8.9pp margin drop into price/volume/FX/cost and stages a hedged price-recovery action for approval.',
    'apps/finance-copilot',
  ],
  [
    'Lane Rangers',
    'scm',
    'Rotterdam OTIF rescue agent',
    'Roots the OTIF drop to lead-time drift + DEC-1000/1004 stockouts and proposes an expedite/reroute within policy.',
    'notebooks/03_scm_commercial_legs.py',
  ],
];

export async function ensureSchema(): Promise<void> {
  for (const stmt of DDL) await query(stmt);

  for (const [criterion, weight, max, desc, order] of RUBRIC) {
    await query(
      `INSERT INTO hack_rubric (criterion, weight, max_score, description, sort_order)
       VALUES ($1, $2, $3, $4, $5) ON CONFLICT (criterion) DO NOTHING`,
      [criterion, weight, max, desc, order]
    );
  }

  for (const [name, track, email, members] of TEAMS) {
    const team = await query<{ id: number }>(
      `INSERT INTO hack_teams (team_name, track, contact_email) VALUES ($1, $2, $3)
       ON CONFLICT (team_name) DO NOTHING RETURNING id`,
      [name, track, email]
    );
    const teamId =
      team[0]?.id ??
      (await query<{ id: number }>(`SELECT id FROM hack_teams WHERE team_name = $1`, [name]))[0]?.id;
    if (!teamId) continue;
    const existing = await query<{ n: string }>(
      `SELECT count(*)::text AS n FROM hack_members WHERE team_id = $1`,
      [teamId]
    );
    if (Number(existing[0]?.n ?? '0') === 0) {
      for (let i = 0; i < members.length; i++) {
        await query(
          `INSERT INTO hack_members (team_id, name, email, role) VALUES ($1, $2, $3, $4)`,
          [teamId, members[i], email, i === 0 ? 'Lead' : 'Member']
        );
      }
    }
  }

  for (const [teamName, track, title, summary, url] of SUBMISSIONS) {
    const t = await query<{ id: number }>(`SELECT id FROM hack_teams WHERE team_name = $1`, [teamName]);
    const teamId = t[0]?.id;
    if (!teamId) continue;
    const dup = await query<{ id: number }>(
      `SELECT id FROM hack_submissions WHERE team_id = $1 AND title = $2`,
      [teamId, title]
    );
    if (dup.length === 0) {
      await query(
        `INSERT INTO hack_submissions (team_id, track, title, summary, artifact_url, artifact_kind)
         VALUES ($1, $2, $3, $4, $5, 'app')`,
        [teamId, track, title, summary, url]
      );
    }
  }
}
