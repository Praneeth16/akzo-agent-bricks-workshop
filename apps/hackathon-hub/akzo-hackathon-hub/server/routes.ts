/**
 * Hackathon REST API, mounted on the AppKit Express app under /api/hack/*.
 * Thin layer over Lakebase (server/lakebase.ts). The acting identity always
 * comes from the Databricks Apps forwarded-identity headers (never the request
 * body), falling back to the SDK identity locally.
 */
import type { Application, Request, Response } from 'express';
import { query, execute, currentUser } from './lakebase.js';

async function endUser(req: Request): Promise<string> {
  const hdr =
    req.header('X-Forwarded-Email') ||
    req.header('X-Forwarded-Preferred-Username') ||
    req.header('X-Forwarded-User');
  if (hdr) return hdr;
  try {
    return await currentUser();
  } catch {
    return 'anonymous@local';
  }
}

const ARTIFACT_KINDS = new Set(['notebook', 'app', 'genie', 'agent', 'dashboard', 'other']);

export function registerHackRoutes(app: Application): void {
  app.get('/api/hack/health', async (_req: Request, res: Response) => {
    try {
      await query('SELECT 1');
      res.json({ status: 'ok', identity: await endUser(_req) });
    } catch (e) {
      res.status(500).json({ status: 'error', message: String(e) });
    }
  });

  app.get('/api/hack/teams', async (_req: Request, res: Response) => {
    try {
      const teams = await query(
        `SELECT t.id, t.team_name, t.track, t.contact_email, t.created_at,
                COALESCE(m.members, '[]'::json) AS members,
                COALESCE(sub.cnt, 0) AS submission_count
         FROM hack_teams t
         LEFT JOIN (
           SELECT team_id, json_agg(json_build_object('name', name, 'email', email, 'role', role)) AS members
           FROM hack_members GROUP BY team_id
         ) m ON m.team_id = t.id
         LEFT JOIN (SELECT team_id, count(*) AS cnt FROM hack_submissions GROUP BY team_id) sub ON sub.team_id = t.id
         ORDER BY t.created_at DESC, t.id DESC`
      );
      res.json({ teams });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.post('/api/hack/teams', async (req: Request, res: Response) => {
    const { team_name, track, contact_email, members } = (req.body ?? {}) as {
      team_name?: string;
      track?: string;
      contact_email?: string;
      members?: Array<{ name?: string; email?: string }>;
    };
    if (!team_name || !track) {
      res.status(400).json({ error: 'team_name and track are required' });
      return;
    }
    try {
      const team = await execute<{ id: number }>(
        `INSERT INTO hack_teams (team_name, track, contact_email) VALUES ($1, $2, $3)
         ON CONFLICT (team_name) DO NOTHING RETURNING id`,
        [team_name, track, contact_email ?? (await endUser(req))]
      );
      if (!team) {
        res.status(409).json({ error: `team "${team_name}" already exists` });
        return;
      }
      const list = Array.isArray(members) ? members : [];
      for (let i = 0; i < list.length; i++) {
        if (!list[i]?.name) continue;
        await execute(
          `INSERT INTO hack_members (team_id, name, email, role) VALUES ($1, $2, $3, $4)`,
          [team.id, list[i].name, list[i].email ?? null, i === 0 ? 'Lead' : 'Member']
        );
      }
      await execute(`INSERT INTO hack_registrations (team_id, email) VALUES ($1, $2)`, [
        team.id,
        await endUser(req),
      ]).catch(() => null); // registrations table is optional/audit-only
      res.status(201).json({ id: team.id });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.get('/api/hack/submissions', async (_req: Request, res: Response) => {
    try {
      const submissions = await query(
        `SELECT s.id, s.team_id, t.team_name, s.track, s.title, s.summary,
                s.artifact_url, s.artifact_kind, s.status, s.submitted_at
         FROM hack_submissions s JOIN hack_teams t ON t.id = s.team_id
         ORDER BY s.submitted_at DESC, s.id DESC`
      );
      res.json({ submissions });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.post('/api/hack/submissions', async (req: Request, res: Response) => {
    const { team_id, track, title, summary, artifact_url, artifact_kind } = (req.body ?? {}) as {
      team_id?: number;
      track?: string;
      title?: string;
      summary?: string;
      artifact_url?: string;
      artifact_kind?: string;
    };
    if (!team_id || !title || !track) {
      res.status(400).json({ error: 'team_id, track and title are required' });
      return;
    }
    const kind = artifact_kind && ARTIFACT_KINDS.has(artifact_kind) ? artifact_kind : 'notebook';
    try {
      const row = await execute<{ id: number }>(
        `INSERT INTO hack_submissions (team_id, track, title, summary, artifact_url, artifact_kind)
         VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
        [team_id, track, title, summary ?? null, artifact_url ?? null, kind]
      );
      res.status(201).json({ id: row?.id });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.get('/api/hack/rubric', async (_req: Request, res: Response) => {
    try {
      const rubric = await query(
        `SELECT criterion, weight, max_score, description FROM hack_rubric ORDER BY sort_order, id`
      );
      res.json({ rubric });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.get('/api/hack/scores', async (req: Request, res: Response) => {
    const submissionId = Number(req.query.submission_id);
    try {
      const scores = submissionId
        ? await query(`SELECT * FROM hack_scores WHERE submission_id = $1 ORDER BY criterion`, [submissionId])
        : await query(`SELECT * FROM hack_scores ORDER BY submission_id, criterion`);
      res.json({ scores });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.post('/api/hack/scores', async (req: Request, res: Response) => {
    const { submission_id, criterion, score, comment } = (req.body ?? {}) as {
      submission_id?: number;
      criterion?: string;
      score?: number;
      comment?: string;
    };
    if (!submission_id || !criterion || score == null) {
      res.status(400).json({ error: 'submission_id, criterion and score are required' });
      return;
    }
    const judge = await endUser(req);
    try {
      // Separation of duties: a judge may not score their own team's submission.
      const own = await query<{ n: string }>(
        `SELECT count(*)::text AS n
         FROM hack_submissions s JOIN hack_members m ON m.team_id = s.team_id
         WHERE s.id = $1 AND lower(m.email) = lower($2)`,
        [submission_id, judge]
      );
      if (Number(own[0]?.n ?? '0') > 0) {
        res.status(403).json({ error: 'you cannot score a submission from your own team' });
        return;
      }
      await execute(
        `INSERT INTO hack_scores (submission_id, judge_email, criterion, score, comment)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (submission_id, judge_email, criterion)
         DO UPDATE SET score = EXCLUDED.score, comment = EXCLUDED.comment, scored_at = now()`,
        [submission_id, judge, criterion, score, comment ?? null]
      );
      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.post('/api/hack/votes', async (req: Request, res: Response) => {
    const { submission_id } = (req.body ?? {}) as { submission_id?: number };
    if (!submission_id) {
      res.status(400).json({ error: 'submission_id is required' });
      return;
    }
    const voter = await endUser(req);
    try {
      await execute(
        `INSERT INTO hack_votes (submission_id, voter_email) VALUES ($1, $2)
         ON CONFLICT (submission_id, voter_email) DO NOTHING`,
        [submission_id, voter]
      );
      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });

  app.get('/api/hack/leaderboard', async (_req: Request, res: Response) => {
    try {
      const leaderboard = await query(
        `SELECT s.id, s.title, s.track, t.team_name,
                COALESCE(e.expert_score, 0) AS expert_score,
                COALESCE(e.judges, 0) AS judge_count,
                COALESCE(v.votes, 0) AS votes
         FROM hack_submissions s
         JOIN hack_teams t ON t.id = s.team_id
         LEFT JOIN (
           SELECT sc.submission_id,
                  ROUND(100.0 * SUM(sc.score * r.weight) / NULLIF(SUM(r.max_score * r.weight), 0), 1) AS expert_score,
                  COUNT(DISTINCT sc.judge_email) AS judges
           FROM hack_scores sc JOIN hack_rubric r ON r.criterion = sc.criterion
           GROUP BY sc.submission_id
         ) e ON e.submission_id = s.id
         LEFT JOIN (SELECT submission_id, COUNT(*) AS votes FROM hack_votes GROUP BY submission_id) v
           ON v.submission_id = s.id
         ORDER BY expert_score DESC, votes DESC, s.id`
      );
      res.json({ leaderboard });
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });
}
