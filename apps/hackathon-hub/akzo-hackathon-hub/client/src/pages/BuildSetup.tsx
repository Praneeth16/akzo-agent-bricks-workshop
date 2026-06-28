import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, Button } from '@databricks/appkit-ui/react';
import { Check, Copy, ExternalLink } from 'lucide-react';
import { Page, PageHeader, Section } from '../components/kit';
import { SETUP_STEPS, SKILLS } from '../content';

function CopyableCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    void navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex items-start gap-2 rounded-lg bg-muted p-3">
      <code className="flex-1 break-all font-mono text-xs text-foreground">{command}</code>
      <Button variant="ghost" size="sm" className="h-7 shrink-0 px-2" onClick={copy}>
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        <span className="ml-1 text-xs">{copied ? 'Copied' : 'Copy'}</span>
      </Button>
    </div>
  );
}

export default function BuildSetupPage() {
  return (
    <Page>
      <PageHeader
        eyebrow="Build setup"
        title="Set up your AI dev kit"
        subtitle="Make your coding agent Databricks-aware so you can build by prompting. Install the dev kit, point your agent at the workspace, then describe what you want and let Genie Code write the SQL and analysis."
      />

      <Section
        title="Setup steps"
        description="Run these once per machine, in order. Each step makes your agent a little more native to this workspace."
      >
        <div className="grid gap-4">
          {SETUP_STEPS.map((step, i) => (
            <Card key={step.title}>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                    {i + 1}
                  </span>
                  <CardTitle className="text-base">{step.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">{step.body}</p>
                {step.command && <CopyableCommand command={step.command} />}
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section
        title="Skills & tools"
        description="The skill packs that teach your agent the Databricks-native patterns used across this workshop."
      >
        <div className="grid gap-4 md:grid-cols-2">
          {SKILLS.map((skill) => (
            <a
              key={skill.name}
              href={skill.href}
              target="_blank"
              rel="noreferrer"
              className="group block"
            >
              <Card className="h-full transition-colors hover:bg-muted/50">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base">{skill.name}</CardTitle>
                    <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground group-hover:text-primary" />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{skill.what}</p>
                </CardContent>
              </Card>
            </a>
          ))}
        </div>
      </Section>

      <p className="text-sm text-muted-foreground">
        Once set up, open any track's guide and build with Genie Code.
      </p>
    </Page>
  );
}
