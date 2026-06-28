import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, Button } from '@databricks/appkit-ui/react';
import { ArrowLeft, Check, Copy, ExternalLink, FlaskConical, BookText, FileCode } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { Page, PageHeader, Section, TrackBadge, EmptyState } from '../components/kit';
import { TRACKS, GUIDES, REPO_BASE } from '../content';

function CopyablePrompt({ prompt }: { prompt: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    void navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="relative mt-2">
      <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-muted p-3 pr-20 font-mono text-sm text-foreground">
        <code>{prompt}</code>
      </pre>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="absolute right-2 top-2 h-7 gap-1 px-2 text-xs"
        onClick={copy}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? 'Copied' : 'Copy'}
      </Button>
    </div>
  );
}

export default function GuidePage() {
  const { track: trackKey } = useParams();
  const track = TRACKS.find((t) => t.key === trackKey);
  const guide = GUIDES.find((g) => g.key === trackKey);

  if (!track || !guide) {
    return (
      <Page>
        <PageHeader title="Guide not found" subtitle="That track does not have a build guide." />
        <EmptyState>
          We could not find a guide for that track.{' '}
          <Link className="font-medium text-primary hover:underline" to="/challenges">
            Back to challenges
          </Link>
          .
        </EmptyState>
      </Page>
    );
  }

  const eyebrowParts = [track.role, track.deckNo ? `deck #${track.deckNo}` : null].filter(Boolean);
  const eyebrow = eyebrowParts.join(' · ') || undefined;

  return (
    <Page className="max-w-4xl">
      <Link
        to="/challenges"
        className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to challenges
      </Link>

      <div className="mb-2 flex items-center gap-3">
        <TrackBadge domain={track.domain} />
      </div>

      <PageHeader eyebrow={eyebrow} title={track.name} subtitle={guide.whatItIs} />

      <Section title="Why it matters">
        <Card className="rounded-xl">
          <CardContent className="space-y-3 py-5">
            <p className="text-sm text-foreground">{guide.whyItMatters}</p>
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">Schema:</span>{' '}
              <span className="font-mono">{guide.schema}</span>
            </p>
          </CardContent>
        </Card>
      </Section>

      <Section title="Prerequisites">
        <Card className="rounded-xl">
          <CardContent className="py-5">
            <ul className="space-y-2.5">
              {guide.prerequisites.map((p) => (
                <li key={p} className="flex items-start gap-2.5 text-sm text-foreground">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </Section>

      <Section
        title="Build it with Genie Code"
        description="Genie Code is the side-pane agent that writes the SQL and analysis from your natural-language prompt. Work through these steps in order."
      >
        <ol className="space-y-4">
          {guide.genieCodeSteps.map((step, i) => (
            <li key={step.title}>
              <Card className="rounded-xl">
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground">{step.title}</p>
                      {step.note && <p className="mt-1 text-sm text-muted-foreground">{step.note}</p>}
                      {step.prompt && <CopyablePrompt prompt={step.prompt} />}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Ship target & evaluation">
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="rounded-xl">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Ship target</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{guide.shipTarget}</p>
            </CardContent>
          </Card>
          <Card className="rounded-xl">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Evaluation</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{guide.evalNote}</p>
            </CardContent>
          </Card>
        </div>
      </Section>

      <Section>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="secondary" size="sm" className="gap-1.5">
            <a href={`${REPO_BASE}/${track.starterPath}`} target="_blank" rel="noreferrer">
              <FlaskConical className="h-4 w-4" /> Starter
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </a>
          </Button>
          <Button asChild variant="secondary" size="sm" className="gap-1.5">
            <a href={`${REPO_BASE}/${track.evalPath}`} target="_blank" rel="noreferrer">
              <BookText className="h-4 w-4" /> Eval set
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </a>
          </Button>
          <Button asChild variant="secondary" size="sm" className="gap-1.5">
            <a href={`${REPO_BASE}/${guide.notebook}`} target="_blank" rel="noreferrer">
              <FileCode className="h-4 w-4" /> Reference notebook
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </a>
          </Button>
        </div>
      </Section>
    </Page>
  );
}
