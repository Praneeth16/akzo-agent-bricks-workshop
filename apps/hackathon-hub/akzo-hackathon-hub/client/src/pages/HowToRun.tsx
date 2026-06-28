import { Card, CardContent, CardHeader, CardTitle } from '@databricks/appkit-ui/react';
import { Page, PageHeader, Section } from '../components/kit';

const RHYTHM = [
  { step: 'See', body: 'Run a prebuilt agent and watch it work end to end — the whole game, before any theory.' },
  { step: 'Tweak', body: 'Change one instruction, metric, or example and re-run. Watch the change ripple through.' },
  { step: 'Return', body: 'Step back to the supervisor and see how the leg you touched changed the fused answer.' },
];

const SPRINTS = [
  { name: 'Sprint 1 — Tweak', body: 'Fork a starter, change the instruction or a certified metric, and re-run the golden questions.' },
  { name: 'Sprint 2 — Swap', body: 'Swap the recommended action (e.g. expedite → reroute) and wire it to a Lakebase write + approval.' },
  { name: 'Sprint 3 — Extend', body: 'Add a new domain leg, a guardrail, or a governed external action. Demo it live.' },
];

export default function HowToRunPage() {
  return (
    <Page>
      <PageHeader
        eyebrow="Facilitator playbook"
        title="How to run it"
        subtitle="The pedagogy is fast.ai's: show the whole game first, then peel back layers. Hands-on follows a See → Tweak → Return rhythm so nobody starts from a blank cell."
      />

      <Section title="The hands-on rhythm">
        <div className="grid gap-4 sm:grid-cols-3">
          {RHYTHM.map((r, i) => (
            <Card key={r.step}>
              <CardHeader className="pb-2">
                <div className="text-xs font-semibold text-primary">Step {i + 1}</div>
                <CardTitle className="text-base">{r.step}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{r.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section title="Day 2 — three sprints to ship">
        <div className="space-y-3">
          {SPRINTS.map((s) => (
            <div key={s.name} className="rounded-xl border border-border bg-card p-4">
              <div className="text-sm font-semibold text-foreground">{s.name}</div>
              <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Awards & judging">
        <div className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
          Two prizes. <span className="font-medium text-foreground">Databricks Expert Choice</span> is judged
          against the rubric (Judge tab); <span className="font-medium text-foreground">People&apos;s Choice</span>{' '}
          is a peer vote. Both update the Leaderboard live. Judges may not score their own team&apos;s
          submission — the app enforces it.
        </div>
      </Section>
    </Page>
  );
}
