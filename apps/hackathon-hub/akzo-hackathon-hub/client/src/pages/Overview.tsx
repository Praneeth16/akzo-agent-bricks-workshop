import { Link } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle, Button } from '@databricks/appkit-ui/react';
import { Target, Trophy, Users, ArrowRight, Gauge } from 'lucide-react';
import { Page } from '../components/kit';
import { DAY1_AGENDA } from '../content';

function Hero() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-[oklch(0.97_0.03_183)] via-card to-card p-8">
      <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
        Hackathon-in-the-Box
      </div>
      <h1 className="mt-4 max-w-3xl text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Run an AkzoNobel Agent Bricks Hackathon
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
        Everything to run the event end to end — the challenges teams build on, the playbook to plan and
        judge it, and live agents you can try right now. Teams ship working prototypes on Databricks
        (working code over slides). This app is itself built on Databricks AppKit — you are dogfooding the
        stack.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button asChild>
          <Link to="/challenges">
            <Target className="mr-2 h-4 w-4" /> Browse challenges
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/leaderboard">
            <Trophy className="mr-2 h-4 w-4" /> Leaderboard
          </Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link to="/register">
            Register a team <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}

const FACTS = [
  {
    icon: Gauge,
    title: 'What teams deliver',
    body: 'Working notebooks, AI/BI dashboards, Genie spaces, or agent prototypes — demoed live on a shared Databricks environment.',
  },
  {
    icon: Trophy,
    title: 'Awards',
    body: "Databricks Expert Choice (judged on the rubric) and People's Choice (peer vote). Both are live on the Leaderboard.",
  },
  {
    icon: Users,
    title: 'Format',
    body: 'Cross-functional teams, 1–2 days, mentors circulating. Day 1 builds the whole game layer by layer; Day 2 forks a track.',
  },
];

export default function OverviewPage() {
  return (
    <Page>
      <Hero />

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {FACTS.map((f) => (
          <Card key={f.title}>
            <CardHeader className="pb-2">
              <f.icon className="h-5 w-5 text-primary" />
              <CardTitle className="text-base">{f.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{f.body}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-10">
        <h2 className="mb-1 text-base font-semibold text-foreground">Day 1 — the whole game, layer by layer</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          We show a working agent first, then peel back one layer at a time. Day 2, teams fork a track.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {DAY1_AGENDA.map((l) => (
            <div key={l.layer} className="rounded-xl border border-border bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-primary">{l.layer}</div>
              <div className="mt-1 text-sm font-semibold text-foreground">{l.title}</div>
              <p className="mt-1 text-sm text-muted-foreground">{l.blurb}</p>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <Button variant="outline" asChild>
            <Link to="/how-to-run">
              <BookHint /> Read the facilitator playbook
            </Link>
          </Button>
        </div>
      </div>
    </Page>
  );
}

function BookHint() {
  return <ArrowRight className="mr-2 h-4 w-4" />;
}
