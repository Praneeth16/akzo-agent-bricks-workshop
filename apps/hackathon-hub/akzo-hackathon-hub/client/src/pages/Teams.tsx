import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Skeleton,
} from '@databricks/appkit-ui/react';
import { Mail, UserPlus, FileText } from 'lucide-react';
import { Page, PageHeader, TrackBadge, EmptyState, ErrorText } from '../components/kit';
import { TRACKS } from '../content';
import { api } from '../api';
import type { Team } from '../api';

function trackDomain(track: string): string {
  return TRACKS.find((t) => t.key === track)?.domain ?? track;
}

function TeamCard({ team }: { team: Team }) {
  const count = Number(team.submission_count) || 0;
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{team.team_name}</CardTitle>
          <TrackBadge domain={trackDomain(team.track)} />
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {team.contact_email && (
          <div className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Mail className="h-3.5 w-3.5" /> {team.contact_email}
          </div>
        )}
        {team.members.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {team.members.map((m, i) => (
              <span
                key={`${m.name}-${i}`}
                className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs text-foreground"
              >
                <span className="font-medium">{m.name}</span>
                {m.role && <span className="text-muted-foreground">· {m.role}</span>}
              </span>
            ))}
          </div>
        )}
        <div className="mt-auto inline-flex items-center gap-1.5 pt-1 text-xs text-muted-foreground">
          <FileText className="h-3.5 w-3.5" />
          <span className="font-semibold text-foreground">{count}</span>
          {count === 1 ? 'submission' : 'submissions'}
        </div>
      </CardContent>
    </Card>
  );
}

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .teams()
      .then((data) => active && setTeams(data))
      .catch((e: unknown) => active && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      active = false;
    };
  }, []);

  return (
    <Page>
      <PageHeader
        eyebrow="Participate"
        title="Teams"
        subtitle="Every team registered for the hackathon, their track, and what they have shipped so far."
        actions={
          <Button asChild>
            <Link to="/register">
              <UserPlus className="mr-2 h-4 w-4" /> Register a team
            </Link>
          </Button>
        }
      />

      {error ? (
        <ErrorText>Could not load teams: {error}</ErrorText>
      ) : teams === null ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
          ))}
        </div>
      ) : teams.length === 0 ? (
        <EmptyState>
          No teams registered yet. Be the first —{' '}
          <Link to="/register" className="font-medium text-primary hover:underline">
            register a team
          </Link>
          .
        </EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <TeamCard key={team.id} team={team} />
          ))}
        </div>
      )}
    </Page>
  );
}
