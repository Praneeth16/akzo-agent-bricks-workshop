import { Card, CardContent, CardHeader, CardTitle, Button } from '@databricks/appkit-ui/react';
import { ExternalLink, FlaskConical, BookText, ArrowRight } from 'lucide-react';
import { Link } from 'react-router';
import { Page, PageHeader, Section, TrackBadge } from '../components/kit';
import { TRACKS, NOTEBOOKS, REPO_BASE } from '../content';

export default function ChallengesPage() {
  return (
    <Page>
      <PageHeader
        eyebrow="Day 2"
        title="Challenges"
        subtitle="Eight forkable tracks, each pre-wired with a governed agent, a Lakebase write + approval, and an MLflow judge. Pick one and ship. The notebooks below are the Day-1 learning path that builds up to them."
      />

      <Section title="Hackathon tracks">
        <div className="grid gap-4 md:grid-cols-2">
          {TRACKS.map((t) => (
            <Card key={t.key} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col gap-1">
                    {t.deckNo && t.deckNo !== '—' && (
                      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Use case {t.deckNo}
                      </span>
                    )}
                    <CardTitle className="text-base">{t.name}</CardTitle>
                    {t.role && <span className="text-xs text-muted-foreground">{t.role}</span>}
                  </div>
                  <TrackBadge domain={t.domain} />
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3">
                <p className="text-sm text-muted-foreground">{t.goal}</p>
                <div className="rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground">Golden question:</span> {t.goldenQuestion}
                </div>
                <div className="text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground">Ship target:</span> {t.shipTarget}
                </div>
                <div className="mt-auto flex flex-wrap items-center gap-3 pt-1 text-xs">
                  <Button asChild size="sm">
                    <Link to={`/guide/${t.key}`}>
                      Open guide <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                  <a
                    className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                    href={`${REPO_BASE}/${t.starterPath}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <FlaskConical className="h-3.5 w-3.5" /> starter
                  </a>
                  <a
                    className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                    href={`${REPO_BASE}/${t.evalPath}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <BookText className="h-3.5 w-3.5" /> eval set
                  </a>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section
        title="Day-1 learning path"
        description="Seven reference notebooks — five core chapters that build the stack, plus two advanced ones (custom agents + serving). Run live in the room."
      >
        <div className="overflow-hidden rounded-xl border border-border">
          {NOTEBOOKS.map((n, i) => (
            <a
              key={n.file}
              href={`${REPO_BASE}/${n.file}`}
              target="_blank"
              rel="noreferrer"
              className={`flex items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/50 ${
                i !== NOTEBOOKS.length - 1 ? 'border-b border-border' : ''
              }`}
            >
              <span className="w-16 shrink-0 text-xs font-semibold uppercase tracking-wide text-primary">
                {n.layer}
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium text-foreground">{n.title}</span>
                <span className="block text-xs text-muted-foreground">{n.blurb}</span>
              </span>
              <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground" />
            </a>
          ))}
        </div>
      </Section>
    </Page>
  );
}
