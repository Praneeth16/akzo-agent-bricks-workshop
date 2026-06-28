import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
  Skeleton,
} from '@databricks/appkit-ui/react';
import { useAnalyticsQuery } from '@databricks/appkit-ui/react';
import { ExternalLink, TrendingDown, Truck, AlertTriangle } from 'lucide-react';
import { Page, PageHeader, Section, EmptyState, ErrorText } from '../components/kit';
import { APPS } from '../content';

/**
 * "Try it live" — genuinely live surfaces on this workspace. The three panels run
 * AppKit analytics queries over the akzo_* Unity Catalog tables through the SQL
 * warehouse (dogfooding the analytics plugin); the cards deep-link to the three
 * deployed live-agent apps. Native Genie spaces are the documented upgrade: create
 * the spaces, add the genie() plugin, and swap these panels for <GenieChat alias />.
 */

function QueryPanel<T extends Record<string, unknown>>({
  queryKey,
  columns,
  empty,
}: {
  queryKey: string;
  columns: { key: keyof T; label: string }[];
  empty: string;
}) {
  // These queries take no parameters; the generated types expect undefined.
  const { data, loading, error } = useAnalyticsQuery(queryKey as never, undefined) as {
    data: T[] | null;
    loading: boolean;
    error: string | null;
  };

  if (loading) return <Skeleton className="h-40 w-full" />;
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!data?.length) return <EmptyState>{empty}</EmptyState>;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((c) => (
            <TableHead key={String(c.key)}>{c.label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.slice(0, 8).map((row, i) => (
          <TableRow key={i}>
            {columns.map((c) => (
              <TableCell key={String(c.key)} className="text-sm">
                {String(row[c.key] ?? '')}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const PANELS = [
  {
    icon: TrendingDown,
    title: 'Paints EMEA gross margin',
    note: 'Decorative Paints × EMEA, monthly — watch the Q2 erosion.',
    queryKey: 'margin_trend',
    columns: [
      { key: 'month', label: 'Month' },
      { key: 'margin_pct', label: 'Margin %' },
    ],
    empty: 'No margin rows.',
  },
  {
    icon: Truck,
    title: 'Rotterdam OTIF',
    note: 'On-time-in-full % by month for the Rotterdam-NL plant.',
    queryKey: 'otif_trend',
    columns: [
      { key: 'month', label: 'Month' },
      { key: 'otif_pct', label: 'OTIF %' },
    ],
    empty: 'No OTIF rows.',
  },
  {
    icon: AlertTriangle,
    title: 'At-risk EMEA accounts',
    note: 'Top churn scores in the latest month.',
    queryKey: 'churn_top',
    columns: [
      { key: 'account_name', label: 'Account' },
      { key: 'churn_score', label: 'Churn' },
      { key: 'nps', label: 'NPS' },
    ],
    empty: 'No churn rows.',
  },
] as const;

export default function LivePage() {
  const liveApps = APPS.filter((a) => a.url);

  return (
    <Page>
      <PageHeader
        eyebrow="Live"
        title="Try it live"
        subtitle="Live data and live agents on this very workspace. The panels below run AppKit analytics queries over the governed akzo_* Unity Catalog tables through the SQL warehouse — the same data the hackathon tracks investigate."
      />

      <Section title="Live workspace data" description="Queried live via the AppKit analytics plugin — this app is dogfooding the stack.">
        <div className="grid gap-4 lg:grid-cols-3">
          {PANELS.map((p) => (
            <Card key={p.queryKey} className="flex flex-col">
              <CardHeader className="pb-2">
                <p.icon className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">{p.title}</CardTitle>
                <p className="text-xs text-muted-foreground">{p.note}</p>
              </CardHeader>
              <CardContent>
                <QueryPanel queryKey={p.queryKey} columns={p.columns as never} empty={p.empty} />
              </CardContent>
            </Card>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Upgrade path: create the three Akzo Genie spaces, add the genie() plugin, and swap these panels
          for a conversational <code>&lt;GenieChat /&gt;</code> — the same move the workshop teaches.
        </p>
      </Section>

      <Section title="Live agent apps" description="The deployed agents — each opens in a new tab.">
        <div className="grid gap-4 md:grid-cols-3">
          {liveApps.map((app) => (
            <a key={app.name} href={app.url!} target="_blank" rel="noreferrer" className="group block">
              <Card className="flex h-full flex-col transition-colors group-hover:border-primary/50">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">{app.name}</CardTitle>
                    <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col">
                  <p className="text-sm text-muted-foreground">{app.blurb}</p>
                </CardContent>
              </Card>
            </a>
          ))}
        </div>
      </Section>
    </Page>
  );
}
