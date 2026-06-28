import { Card, CardContent, CardHeader, CardTitle } from '@databricks/appkit-ui/react';
import { ExternalLink } from 'lucide-react';
import { Page, PageHeader, Section } from '../components/kit';
import { RESOURCE_GROUPS } from '../content';

const WORKSPACE = [
  ['Catalog', 'serverless_lakebase_praneeth_catalog'],
  ['Schemas', 'akzo_finance · akzo_scm · akzo_commercial · akzo_docs · akzo_ops · akzo_gateway'],
  ['Genie spaces', 'Akzo Finance · Akzo SCM · Akzo Commercial'],
  ['Lakebase', 'graphrag-spike / databricks_postgres / akzo'],
  ['Vector Search', 'akzo_workshop_vs → akzo_docs.chunks_idx (Qwen embeddings)'],
  ['Models', 'databricks-claude-opus-4-7 · databricks-gpt-5-5 · databricks-qwen3-embedding-0-6b'],
];

export default function ResourcesPage() {
  return (
    <Page>
      <PageHeader
        eyebrow="Resources"
        title="Resources"
        subtitle="The platform pieces this workshop is built on, and the shared workspace every team uses."
      />

      {RESOURCE_GROUPS.map((g) => (
        <Section key={g.group} title={g.group}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {g.links.map((r) => (
              <a key={r.href} href={r.href} target="_blank" rel="noreferrer" className="block">
                <Card className="h-full transition-colors hover:border-primary/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-1.5 text-base">
                      {r.label}
                      <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{r.blurb}</p>
                  </CardContent>
                </Card>
              </a>
            ))}
          </div>
        </Section>
      ))}

      <Section title="Shared workspace">
        <div className="overflow-hidden rounded-xl border border-border">
          {WORKSPACE.map(([k, v], i) => (
            <div
              key={k}
              className={`flex flex-col gap-0.5 px-4 py-3 sm:flex-row sm:gap-4 ${
                i !== WORKSPACE.length - 1 ? 'border-b border-border' : ''
              }`}
            >
              <span className="w-40 shrink-0 text-sm font-semibold text-foreground">{k}</span>
              <span className="font-mono text-xs text-muted-foreground">{v}</span>
            </div>
          ))}
        </div>
      </Section>
    </Page>
  );
}
