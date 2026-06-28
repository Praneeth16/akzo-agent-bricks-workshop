import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Button,
  Input,
  Label,
  Textarea,
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
  Skeleton,
  Alert,
} from '@databricks/appkit-ui/react';
import { Send, Trophy, Gavel, ArrowRight } from 'lucide-react';
import { Page, PageHeader, EmptyState, ErrorText } from '../components/kit';
import { TRACKS, TRACK_KEYS } from '../content';
import { api } from '../api';
import type { Team } from '../api';

const ARTIFACT_KINDS = ['notebook', 'app', 'genie', 'agent', 'dashboard', 'other'];

const trackLabel = (key: string) => TRACKS.find((t) => t.key === key)?.name ?? key;

export default function SubmitPage() {
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [teamId, setTeamId] = useState('');
  const [track, setTrack] = useState('');
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [artifactUrl, setArtifactUrl] = useState('');
  const [artifactKind, setArtifactKind] = useState('notebook');

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ id: number } | null>(null);

  useEffect(() => {
    let active = true;
    api
      .teams()
      .then((t) => active && setTeams(t))
      .catch((e: Error) => active && setLoadError(e.message));
    return () => {
      active = false;
    };
  }, []);

  const canSubmit = useMemo(
    () => teamId !== '' && track !== '' && title.trim() !== '' && !submitting,
    [teamId, track, title, submitting]
  );

  function chooseTeam(id: string) {
    setTeamId(id);
    const team = teams?.find((t) => String(t.id) === id);
    if (team) setTrack(team.track);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const res = await api.createSubmission({
        team_id: Number(teamId),
        track,
        title: title.trim(),
        summary: summary.trim() || undefined,
        artifact_url: artifactUrl.trim() || undefined,
        artifact_kind: artifactKind,
      });
      setCreated(res);
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Participate"
        title="Submit your project"
        subtitle="Register your build for judging and the People's Choice vote. Pick your team, point us at the artifact, and ship."
      />

      {loadError ? (
        <ErrorText>Failed to load teams: {loadError}</ErrorText>
      ) : teams === null ? (
        <Card className="max-w-xl">
          <CardHeader>
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-64" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-9 w-32" />
          </CardContent>
        </Card>
      ) : teams.length === 0 ? (
        <EmptyState>
          No teams have registered yet. <Link to="/register" className="font-medium text-primary hover:underline">Register a team</Link> first, then come back to submit.
        </EmptyState>
      ) : created ? (
        <Card className="max-w-xl">
          <CardHeader>
            <CardTitle className="text-base">Submission received</CardTitle>
            <CardDescription>
              Your project for {trackLabel(track)} is in. Judges score it on the rubric and peers can vote.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <Send className="h-4 w-4" />
              <span>Submission #{created.id} — "{title.trim()}" was created.</span>
            </Alert>
            <div className="flex flex-wrap gap-3">
              <Button asChild>
                <Link to="/judge">
                  <Gavel className="mr-2 h-4 w-4" /> Go to judging
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link to="/leaderboard">
                  <Trophy className="mr-2 h-4 w-4" /> View leaderboard
                </Link>
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setCreated(null);
                  setTitle('');
                  setSummary('');
                  setArtifactUrl('');
                  setArtifactKind('notebook');
                }}
              >
                Submit another <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="max-w-xl">
          <CardHeader>
            <CardTitle className="text-base">Project submission</CardTitle>
            <CardDescription>All fields except the title are optional.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-5" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="team">Team</Label>
                <Select value={teamId} onValueChange={chooseTeam}>
                  <SelectTrigger id="team">
                    <SelectValue placeholder="Select your team" />
                  </SelectTrigger>
                  <SelectContent>
                    {teams.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.team_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="track">Track</Label>
                <Select value={track} onValueChange={setTrack}>
                  <SelectTrigger id="track">
                    <SelectValue placeholder="Select a track" />
                  </SelectTrigger>
                  <SelectContent>
                    {TRACK_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        {trackLabel(key)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Finance variance copilot — Q2 EMEA"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="summary">Summary</Label>
                <Textarea
                  id="summary"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="What you built, what it does, and the golden question it answers."
                  rows={4}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="artifact_url">Artifact URL</Label>
                <Input
                  id="artifact_url"
                  type="url"
                  value={artifactUrl}
                  onChange={(e) => setArtifactUrl(e.target.value)}
                  placeholder="Link to the notebook, app, dashboard, or Genie space"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="artifact_kind">Artifact kind</Label>
                <Select value={artifactKind} onValueChange={setArtifactKind}>
                  <SelectTrigger id="artifact_kind">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ARTIFACT_KINDS.map((k) => (
                      <SelectItem key={k} value={k}>
                        {k}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {submitError && <ErrorText>{submitError}</ErrorText>}

              <Button type="submit" disabled={!canSubmit}>
                <Send className="mr-2 h-4 w-4" />
                {submitting ? 'Submitting…' : 'Submit project'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </Page>
  );
}
