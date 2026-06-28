import { useEffect, useMemo, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
  Skeleton,
} from '@databricks/appkit-ui/react';
import { Trophy, Award, Users } from 'lucide-react';
import { Page, PageHeader, Section, TrackBadge, EmptyState, ErrorText } from '../components/kit';
import { TRACKS } from '../content';
import { api } from '../api';
import type { LeaderboardRow } from '../api';
import { cn } from '../lib/utils';

const TRACK_DOMAIN: Record<string, string> = Object.fromEntries(
  TRACKS.map((t) => [t.key, t.domain])
);

const MEDAL_STYLES = [
  'bg-[oklch(0.92_0.09_85)] text-[oklch(0.45_0.12_85)]',
  'bg-[oklch(0.93_0.01_250)] text-[oklch(0.45_0.02_250)]',
  'bg-[oklch(0.92_0.06_55)] text-[oklch(0.45_0.1_55)]',
];

function RankCell({ rank }: { rank: number }) {
  if (rank <= 3) {
    return (
      <span
        className={cn(
          'inline-flex h-7 w-7 items-center justify-center rounded-full',
          MEDAL_STYLES[rank - 1]
        )}
        title={`Rank ${rank}`}
      >
        <Trophy className="h-3.5 w-3.5" />
      </span>
    );
  }
  return <span className="pl-2 text-sm font-medium text-muted-foreground">{rank}</span>;
}

function ExpertScore({ score, judges }: { score: number; judges: number }) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-semibold tabular-nums text-foreground">
        {score.toFixed(1)}
        <span className="ml-1.5 text-xs font-normal text-muted-foreground">
          · {judges} {judges === 1 ? 'judge' : 'judges'}
        </span>
      </span>
      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
}

export default function LeaderboardPage() {
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .leaderboard()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const { expertLeader, peopleLeader } = useMemo(() => {
    if (!rows || rows.length === 0) return { expertLeader: null, peopleLeader: null };
    let expertLeader = rows[0];
    let peopleLeader = rows[0];
    for (const r of rows) {
      if (Number(r.expert_score) > Number(expertLeader.expert_score)) expertLeader = r;
      if (Number(r.votes) > Number(peopleLeader.votes)) peopleLeader = r;
    }
    return { expertLeader, peopleLeader };
  }, [rows]);

  return (
    <Page>
      <PageHeader
        eyebrow="Judging"
        title="Leaderboard"
        subtitle="Live standings. Databricks Expert Choice is judged on the rubric; People's Choice is the peer vote. Sorted by expert score, then votes."
      />

      {error && (
        <Section>
          <ErrorText>Could not load the leaderboard: {error}</ErrorText>
        </Section>
      )}

      {!error && (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-2">
            {rows === null ? (
              <>
                <Skeleton className="h-28 rounded-xl" />
                <Skeleton className="h-28 rounded-xl" />
              </>
            ) : (
              <>
                <Card>
                  <CardHeader className="pb-2">
                    <Trophy className="h-5 w-5 text-primary" />
                    <CardTitle className="text-base">Expert Choice leader</CardTitle>
                    <CardDescription>Highest rubric score from the judges.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {expertLeader ? (
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-foreground">
                            {expertLeader.team_name}
                          </div>
                          <div className="text-xs text-muted-foreground">{expertLeader.title}</div>
                        </div>
                        <div className="text-lg font-bold tabular-nums text-primary">
                          {Number(expertLeader.expert_score).toFixed(1)}
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No scores yet.</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <Award className="h-5 w-5 text-primary" />
                    <CardTitle className="text-base">People's Choice leader</CardTitle>
                    <CardDescription>Most peer votes from the room.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {peopleLeader ? (
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-foreground">
                            {peopleLeader.team_name}
                          </div>
                          <div className="text-xs text-muted-foreground">{peopleLeader.title}</div>
                        </div>
                        <div className="inline-flex items-center gap-1.5 text-lg font-bold tabular-nums text-primary">
                          <Users className="h-4 w-4" />
                          {Number(peopleLeader.votes)}
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No votes yet.</p>
                    )}
                  </CardContent>
                </Card>
              </>
            )}
          </div>

          <Section title="Standings">
            {rows === null ? (
              <div className="overflow-hidden rounded-xl border border-border">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={cn(
                      'flex items-center gap-4 px-4 py-3.5',
                      i !== 4 && 'border-b border-border'
                    )}
                  >
                    <Skeleton className="h-7 w-7 rounded-full" />
                    <Skeleton className="h-4 flex-1" />
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                ))}
              </div>
            ) : rows.length === 0 ? (
              <EmptyState>
                No submissions have been scored yet. Standings appear once judges score and the room
                votes.
              </EmptyState>
            ) : (
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">Rank</TableHead>
                      <TableHead>Team</TableHead>
                      <TableHead>Submission</TableHead>
                      <TableHead>Track</TableHead>
                      <TableHead>Expert Choice</TableHead>
                      <TableHead className="text-right">People's Choice</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((r, i) => (
                      <TableRow key={r.id}>
                        <TableCell>
                          <RankCell rank={i + 1} />
                        </TableCell>
                        <TableCell className="font-medium text-foreground">{r.team_name}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{r.title}</TableCell>
                        <TableCell>
                          <TrackBadge domain={TRACK_DOMAIN[r.track] ?? r.track} />
                        </TableCell>
                        <TableCell>
                          <ExpertScore
                            score={Number(r.expert_score)}
                            judges={Number(r.judge_count)}
                          />
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="inline-flex items-center gap-1.5 text-sm font-medium tabular-nums text-foreground">
                            <Users className="h-3.5 w-3.5 text-muted-foreground" />
                            {Number(r.votes)}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </Section>
        </>
      )}
    </Page>
  );
}
