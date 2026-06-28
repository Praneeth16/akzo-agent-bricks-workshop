import { Card, CardContent, CardHeader, CardTitle } from '@databricks/appkit-ui/react';
import { ExternalLink, MonitorPlay } from 'lucide-react';
import { Page, PageHeader, Section } from '../components/kit';
import { DEMOS, REPO_BASE } from '../content';

export default function DemosPage() {
  return (
    <Page className="max-w-5xl">
      <PageHeader
        eyebrow="Demos"
        title="Reference demos"
        subtitle="The narrated showcases shipped in the repo. Each one walks an end-to-end agent story you can open, read, and run."
      />

      <Section title="Showcases">
        <div className="grid gap-4 md:grid-cols-2">
          {DEMOS.map((demo) => (
            <Card key={demo.title} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <MonitorPlay className="h-4 w-4" />
                  </span>
                  <CardTitle className="text-base">{demo.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3">
                <p className="text-sm text-muted-foreground">{demo.blurb}</p>
                <div className="text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground">Stack:</span> {demo.stack}
                </div>
                <div className="mt-auto pt-1 text-xs">
                  <a
                    className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                    href={`${REPO_BASE}/${demo.doc}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink className="h-3.5 w-3.5" /> Open the script
                  </a>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>
    </Page>
  );
}
