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

// Judging rubric, reconciled to the source deck's five weighted criteria
// (Business value 30%, Technical execution 25%, Platform depth 20%,
// Innovation 15%, Demo quality 10%). Weights are the percentages as relative
// values; the leaderboard normalizes them.
const RUBRIC: Array<[string, number, number, string, number]> = [
  ['Business value / measurable ROI', 3.0, 5, 'Ties to a stated AkzoNobel priority; measurable ROI. (30%)', 1],
  ['Technical execution', 2.5, 5, 'Works end to end: a deployed app or endpoint plus a live trace. (25%)', 2],
  ['Platform depth, used with intent', 2.0, 5, 'Not feature-bingo: governance, routing, and eval design used deliberately. (20%)', 3],
  ['Innovation', 1.5, 5, 'Agents that act, plus external tool-calling. (15%)', 4],
  ['Demo quality', 1.0, 5, 'A five-minute narrative plus executable evidence. (10%)', 5],
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

  // Rubric is canonical config (reconciled to the deck): upsert the canonical
  // rows and prune any criterion no longer in the set, so the live rubric always
  // matches. Safe because hack_scores.criterion has no FK to hack_rubric.
  for (const [criterion, weight, max, desc, order] of RUBRIC) {
    await query(
      `INSERT INTO hack_rubric (criterion, weight, max_score, description, sort_order)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (criterion)
       DO UPDATE SET weight = EXCLUDED.weight, max_score = EXCLUDED.max_score,
                     description = EXCLUDED.description, sort_order = EXCLUDED.sort_order`,
      [criterion, weight, max, desc, order]
    );
  }
  await query(
    `DELETE FROM hack_rubric WHERE criterion <> ALL($1::text[])`,
    [RUBRIC.map((r) => r[0])]
  );

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
