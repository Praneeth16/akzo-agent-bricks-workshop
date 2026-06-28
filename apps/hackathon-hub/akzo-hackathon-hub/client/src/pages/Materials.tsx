import { FileText, ExternalLink } from 'lucide-react';
import { Page, PageHeader, Section } from '../components/kit';
import { MATERIALS, REPO_BASE } from '../content';

export default function MaterialsPage() {
  return (
    <Page>
      <PageHeader
        eyebrow="Materials"
        title="Workshop materials"
        subtitle="The planning and demo documents behind the event — open them straight from the repo."
      />
      <Section>
        <div className="grid gap-3 sm:grid-cols-2">
          {MATERIALS.map((d) => (
            <a
              key={d.file}
              href={`${REPO_BASE}/${d.file}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/50"
            >
              <FileText className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <span className="flex-1">
                <span className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                  {d.title}
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{d.blurb}</span>
                <span className="mt-1 block font-mono text-[11px] text-muted-foreground/70">{d.file}</span>
              </span>
            </a>
          ))}
        </div>
      </Section>
    </Page>
  );
}
