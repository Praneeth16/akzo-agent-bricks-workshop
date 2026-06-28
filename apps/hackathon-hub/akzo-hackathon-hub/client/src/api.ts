/** Typed client for the /api/hack/* Lakebase-backed hackathon API. */

export interface TeamMember {
  name: string;
  email?: string;
  role?: string;
}
export interface Team {
  id: number;
  team_name: string;
  track: string;
  contact_email: string | null;
  created_at: string;
  members: TeamMember[];
  submission_count: number | string;
}
export interface Submission {
  id: number;
  team_id: number;
  team_name: string;
  track: string;
  title: string;
  summary: string | null;
  artifact_url: string | null;
  artifact_kind: string;
  status: string;
  submitted_at: string;
}
export interface RubricCriterion {
  criterion: string;
  weight: number | string;
  max_score: number;
  description: string | null;
}
export interface Score {
  id: number;
  submission_id: number;
  judge_email: string;
  criterion: string;
  score: number;
  comment: string | null;
}
export interface LeaderboardRow {
  id: number;
  title: string;
  track: string;
  team_name: string;
  expert_score: number | string;
  judge_count: number | string;
  votes: number | string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(err.error ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const json = (await res.json().catch(() => ({}))) as { error?: string };
  if (!res.ok) throw new Error(json.error ?? `${res.status} ${res.statusText}`);
  return json as T;
}

export const api = {
  teams: () => getJSON<{ teams: Team[] }>('/api/hack/teams').then((r) => r.teams),
  createTeam: (body: {
    team_name: string;
    track: string;
    contact_email?: string;
    members: TeamMember[];
  }) => postJSON<{ id: number }>('/api/hack/teams', body),
  submissions: () => getJSON<{ submissions: Submission[] }>('/api/hack/submissions').then((r) => r.submissions),
  createSubmission: (body: {
    team_id: number;
    track: string;
    title: string;
    summary?: string;
    artifact_url?: string;
    artifact_kind?: string;
  }) => postJSON<{ id: number }>('/api/hack/submissions', body),
  rubric: () => getJSON<{ rubric: RubricCriterion[] }>('/api/hack/rubric').then((r) => r.rubric),
  scores: (submissionId: number) =>
    getJSON<{ scores: Score[] }>(`/api/hack/scores?submission_id=${submissionId}`).then((r) => r.scores),
  score: (body: { submission_id: number; criterion: string; score: number; comment?: string }) =>
    postJSON<{ ok: true }>('/api/hack/scores', body),
  vote: (submissionId: number) => postJSON<{ ok: true }>('/api/hack/votes', { submission_id: submissionId }),
  leaderboard: () =>
    getJSON<{ leaderboard: LeaderboardRow[] }>('/api/hack/leaderboard').then((r) => r.leaderboard),
};
