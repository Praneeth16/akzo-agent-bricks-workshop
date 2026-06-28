import { useEffect, useMemo, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Button,
  Input,
  Label,
  Separator,
  Skeleton,
  Alert,
} from '@databricks/appkit-ui/react';
import { Gavel, ThumbsUp, Save } from 'lucide-react';
import { Page, PageHeader, Section, TrackBadge, EmptyState, ErrorText } from '../components/kit';
import { api } from '../api';
import type { Submission, RubricCriterion, Score } from '../api';
import { cn } from '../lib/utils';

interface CriterionState {
  score: string;
  comment: string;
}

export default function JudgePage() {
  const [submissions, setSubmissions] = useState<Submission[] | null>(null);
  const [subsError, setSubsError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [rubric, setRubric] = useState<RubricCriterion[] | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, CriterionState>>({});

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState<string | null>(null);

  const [voting, setVoting] = useState(false);
  const [voteError, setVoteError] = useState<string | null>(null);
  const [voteOk, setVoteOk] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .submissions()
      .then((s) => active && setSubmissions(s))
      .catch((e) => active && setSubsError(e instanceof Error ? e.message : String(e)));
    return () => {
      active = false;
    };
  }, []);

  const selected = useMemo(
    () => submissions?.find((s) => s.id === selectedId) ?? null,
    [submissions, selectedId]
  );

  useEffect(() => {
    if (selectedId == null) return;
    let active = true;
    setPanelLoading(true);
    setPanelError(null);
    setSaveError(null);
    setSaveOk(null);
    setVoteError(null);
    setVoteOk(null);
    Promise.all([api.rubric(), api.scores(selectedId)])
      .then(([rub, scores]) => {
        if (!active) return;
        setRubric(rub);
        const existing = new Map<string, Score>(scores.map((sc) => [sc.criterion, sc]));
        const next: Record<string, CriterionState> = {};
        for (const c of rub) {
          const prev = existing.get(c.criterion);
          next[c.criterion] = {
            score: prev ? String(prev.score) : '',
            comment: prev?.comment ?? '',
          };
        }
        setForm(next);
      })
      .catch((e) => active && setPanelError(e instanceof Error ? e.message : String(e)))
      .finally(() => active && setPanelLoading(false));
    return () => {
      active = false;
    };
  }, [selectedId]);

  function updateField(criterion: string, patch: Partial<CriterionState>) {
    setForm((f) => ({ ...f, [criterion]: { ...f[criterion], ...patch } }));
  }

  async function handleSave() {
    if (selectedId == null || !rubric) return;
    setSaving(true);
    setSaveError(null);
    setSaveOk(null);
    try {
      let saved = 0;
      for (const c of rubric) {
        const state = form[c.criterion];
        if (!state || state.score === '') continue;
        await api.score({
          submission_id: selectedId,
          criterion: c.criterion,
          score: Number(state.score),
          comment: state.comment || undefined,
        });
        saved += 1;
      }
      setSaveOk(saved === 0 ? 'Enter at least one score to save.' : `Saved ${saved} score${saved === 1 ? '' : 's'}.`);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleVote() {
    if (selectedId == null) return;
    setVoting(true);
    setVoteError(null);
    setVoteOk(null);
    try {
      await api.vote(selectedId);
      setVoteOk('Your People’s Choice vote was recorded.');
    } catch (e) {
      setVoteError(e instanceof Error ? e.message : String(e));
    } finally {
      setVoting(false);
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Judging"
        title="Judge submissions"
        subtitle="Score against the rubric and cast your People’s Choice vote. Pick a submission on the left, then rate each criterion. Judges cannot score their own team."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_1fr]">
        {/* Submission list */}
        <Section title="Submissions" className="mb-0">
          {subsError && <ErrorText>{subsError}</ErrorText>}
          {!subsError && submissions == null && (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))}
            </div>
          )}
          {!subsError && submissions != null && submissions.length === 0 && (
            <EmptyState>No submissions yet. Once teams submit, they will appear here for scoring.</EmptyState>
          )}
          {!subsError && submissions != null && submissions.length > 0 && (
            <div className="space-y-3">
              {submissions.map((s) => {
                const active = s.id === selectedId;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSelectedId(s.id)}
                    className={cn(
                      'w-full rounded-xl border px-4 py-3 text-left transition-colors',
                      active
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-card hover:bg-muted/50'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-semibold text-foreground">{s.title}</span>
                      <TrackBadge domain={s.track} />
                    </div>
                    <span className="mt-1 block text-xs text-muted-foreground">{s.team_name}</span>
                  </button>
                );
              })}
            </div>
          )}
        </Section>

        {/* Scoring panel */}
        <Section title="Scorecard" className="mb-0">
          {selected == null && (
            <EmptyState>Select a submission to begin scoring.</EmptyState>
          )}

          {selected != null && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">{selected.title}</CardTitle>
                    <CardDescription>{selected.team_name}</CardDescription>
                  </div>
                  <TrackBadge domain={selected.track} />
                </div>
                {selected.summary && (
                  <p className="mt-2 text-sm text-muted-foreground">{selected.summary}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-5">
                {panelError && <ErrorText>{panelError}</ErrorText>}

                {panelLoading && (
                  <div className="space-y-4">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                  </div>
                )}

                {!panelLoading && !panelError && rubric != null && rubric.length === 0 && (
                  <EmptyState>No rubric criteria are configured yet.</EmptyState>
                )}

                {!panelLoading && !panelError && rubric != null && rubric.length > 0 && (
                  <>
                    <div className="space-y-5">
                      {rubric.map((c) => {
                        const state = form[c.criterion] ?? { score: '', comment: '' };
                        return (
                          <div key={c.criterion} className="rounded-lg border border-border p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="text-sm font-semibold text-foreground">{c.criterion}</div>
                                {c.description && (
                                  <p className="mt-0.5 text-xs text-muted-foreground">{c.description}</p>
                                )}
                              </div>
                              <span className="shrink-0 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                                weight {c.weight}
                              </span>
                            </div>
                            <div className="mt-3 grid gap-3 sm:grid-cols-[7rem_1fr]">
                              <div>
                                <Label htmlFor={`score-${c.criterion}`} className="text-xs text-muted-foreground">
                                  Score (0–{c.max_score})
                                </Label>
                                <Input
                                  id={`score-${c.criterion}`}
                                  type="number"
                                  min={0}
                                  max={c.max_score}
                                  value={state.score}
                                  onChange={(e) => updateField(c.criterion, { score: e.target.value })}
                                  className="mt-1"
                                />
                              </div>
                              <div>
                                <Label htmlFor={`comment-${c.criterion}`} className="text-xs text-muted-foreground">
                                  Comment
                                </Label>
                                <Input
                                  id={`comment-${c.criterion}`}
                                  value={state.comment}
                                  onChange={(e) => updateField(c.criterion, { comment: e.target.value })}
                                  placeholder="Optional note"
                                  className="mt-1"
                                />
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {saveError && <ErrorText>{saveError}</ErrorText>}
                    {saveOk && (
                      <Alert>
                        {saveOk}
                      </Alert>
                    )}

                    <div className="flex flex-wrap items-center gap-3">
                      <Button onClick={handleSave} disabled={saving}>
                        <Save className="mr-2 h-4 w-4" />
                        {saving ? 'Saving…' : 'Save scores'}
                      </Button>
                    </div>

                    <Separator />

                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                        <Gavel className="h-4 w-4 text-primary" /> People’s Choice
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Cast a single peer vote for the submission you would most want to see win.
                      </p>
                      {voteError && <ErrorText>{voteError}</ErrorText>}
                      {voteOk && <Alert>{voteOk}</Alert>}
                      <Button variant="outline" onClick={handleVote} disabled={voting}>
                        <ThumbsUp className="mr-2 h-4 w-4" />
                        {voting ? 'Voting…' : 'Vote — People’s Choice'}
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </Section>
      </div>
    </Page>
  );
}
