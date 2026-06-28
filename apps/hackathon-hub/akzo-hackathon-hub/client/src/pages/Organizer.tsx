import { Card, CardContent, CardHeader, CardTitle, Button } from '@databricks/appkit-ui/react';
import { ExternalLink, FileCheck, FlaskConical, AppWindow } from 'lucide-react';
import { Page, PageHeader, Section, StatusBadge } from '../components/kit';
import { APPS, REPO_BASE } from '../content';

const SMOKE_DOCS = [
  { title: 'SMOKE_RESULTS.md', file: 'deploy/SMOKE_RESULTS.md', blurb: 'App-by-app deploy verification — every app reachable and healthy.', icon: FlaskConical },
  { title: 'ACTION_SMOKE_RESULTS.md', file: 'deploy/ACTION_SMOKE_RESULTS.md', blurb: 'End-to-end action ladder (L1→L4): propose → guardrail → approve → execute.', icon: FileCheck },
];

const APP_INVENTORY = [
  ...APPS.map((a) => ({ name: a.name, note: a.blurb })),
  { name: 'akzo-hackathon-hub', note: 'this app — the organizer + participant hub for the workshop.' },
];

export default function OrganizerPage() {
  return (
    <Page>
      <PageHeader
        eyebrow="Organizer (internal)"
        title="Operate the workshop"
        subtitle="The deployed-apps gallery, deploy smoke results, and the full app inventory — everything you need to run the room."
      />

      <Section
        title="Deployed apps"
        description="The live agent apps backing the demos and tracks. Open them in a new tab or note the internal targets."
      >
        <div className="grid gap-4 md:grid-cols-2">
          {APPS.map((app) => (
            <Card key={app.name} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="font-mono text-base">{app.name}</CardTitle>
                  <StatusBadge status={app.status} />
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3">
                <p className="text-sm text-muted-foreground">{app.blurb}</p>
                <div className="mt-auto pt-1">
                  {app.url ? (
                    <Button variant="outline" size="sm" asChild>
                      <a href={app.url} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-4 w-4" /> Open app
                      </a>
                    </Button>
                  ) : (
                    <span className="text-xs italic text-muted-foreground">internal target</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section
        title="Deploy & smoke"
        description="The verification artifacts from the deploy run — confirm everything is green before the room arrives."
      >
        <div className="overflow-hidden rounded-xl border border-border">
          {SMOKE_DOCS.map((d, i) => (
            <a
              key={d.file}
              href={`${REPO_BASE}/${d.file}`}
              target="_blank"
              rel="noreferrer"
              className={`flex items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/50 ${
                i !== SMOKE_DOCS.length - 1 ? 'border-b border-border' : ''
              }`}
            >
              <d.icon className="h-5 w-5 shrink-0 text-primary" />
              <span className="flex-1">
                <span className="block text-sm font-medium text-foreground">{d.title}</span>
                <span className="block text-xs text-muted-foreground">{d.blurb}</span>
              </span>
              <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground" />
            </a>
          ))}
        </div>
      </Section>

      <Section
        title="App inventory"
        description="The five workshop apps plus this hub — six surfaces in total."
      >
        <div className="overflow-hidden rounded-xl border border-border">
          {APP_INVENTORY.map((app, i) => (
            <div
              key={app.name}
              className={`flex items-center gap-4 px-4 py-3 ${
                i !== APP_INVENTORY.length - 1 ? 'border-b border-border' : ''
              }`}
            >
              <AppWindow className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="flex-1">
                <span className="block font-mono text-sm font-medium text-foreground">{app.name}</span>
                <span className="block text-xs text-muted-foreground">{app.note}</span>
              </span>
            </div>
          ))}
        </div>
      </Section>
    </Page>
  );
}
