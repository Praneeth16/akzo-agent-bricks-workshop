import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Separator,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from "@databricks/appkit-ui/react";
import {
  ChevronDown,
  GitBranch,
  Loader2,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  User,
} from "lucide-react";
import { api, AskResult, DomainLeg } from "./api";
import { ActBody } from "./actions";
import { ActionsPanel } from "./ActionsPanel";
import { DomainBadge, ErrorText, Page, PageHeader, SectionTitle } from "@/components/kit";

// Staged "thinking" indicator — the supervisor turn calls real Genie spaces (each leg ~15-30s),
// so we surface what it is doing rather than a frozen button. Steps advance on a timer (the API is
// a single call, so progress is indicative, not exact).
const THINKING_STEPS = [
  "Routing the question to the right domain Genie spaces…",
  "Consulting the Finance / SCM / Commercial Genie spaces (real Genie generates + runs governed SQL)…",
  "Reading the governed rows under your identity (OBO)…",
  "Fusing one cross-domain answer + a recommended action…",
];

function ThinkingIndicator() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, THINKING_STEPS.length - 1)), 7000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="mt-3 flex items-start gap-2.5 rounded-md border border-border bg-secondary px-3 py-2.5">
      <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
      <div className="flex flex-col gap-1">
        <span className="text-sm text-foreground">
          {THINKING_STEPS[step]}
          <span className="animate-pulse">▍</span>
        </span>
        <div className="flex gap-1">
          {THINKING_STEPS.map((_, i) => (
            <span
              key={i}
              className={`h-1 w-6 rounded-full transition-colors ${
                i <= step ? "bg-primary" : "bg-border"
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// Map the supervisor's fused recommendation to a default governed action.
// If SCM was consulted, the next-best-action is a supply reroute; otherwise a
// CRM follow-up task captures the recommendation against the account.
function defaultActionFor(result: AskResult): ActBody {
  const domains = result.routing.map((r) => r.domain);
  const region = "EMEA";
  const subject = (result.recommended_action || "Act on the supervisor recommendation").slice(0, 160);
  if (domains.includes("SCM")) {
    return {
      action_type: "scm_reroute",
      subject,
      region,
      level: 2,
      payload: {
        summary: result.recommended_action,
        message: result.recommended_action,
        task: result.recommended_action,
        account: "EMEA Paints supply",
        question: result.question,
      },
    };
  }
  return {
    action_type: "crm_task",
    subject,
    region,
    level: 2,
    payload: {
      task: result.recommended_action,
      summary: result.recommended_action,
      account: "EMEA Paints",
      question: result.question,
    },
  };
}

const FLAGSHIP =
  "Paints EMEA gross margin dropped ~8% in Q2 — is it price, volume, or a supply/service issue, and what should I do?";

const SAMPLES = [
  { label: "Flagship", q: FLAGSHIP },
  { label: "Example 2", q: "Connect the dots: is the EMEA churn risk related to the margin and service problems we are seeing?" },
  { label: "Example 3", q: "Give me one EMEA Paints situation report covering financial impact, supply status, and customer risk." },
  { label: "Example 4", q: "Which domains did you consult to answer the EMEA margin question, and what did each contribute?" },
];

const PERSONAS = [
  { id: "controller", label: "Group Controller" },
  { id: "emea_planner", label: "EMEA Supply Planner" },
  { id: "rep", label: "Account Rep" },
];

function LegResult({ leg }: { leg: DomainLeg }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border bg-secondary">
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex items-center gap-3 px-3 py-2.5">
          <DomainBadge domain={leg.domain} />
          <span className="text-xs text-muted-foreground">
            {leg.error ? (
              <span className="text-destructive">error: {leg.error}</span>
            ) : (
              `${leg.row_count} ${leg.row_count === 1 ? "row" : "rows"}`
            )}
          </span>
          <CollapsibleTrigger asChild>
            <button className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[var(--akzo-link)] hover:underline">
              <ChevronDown
                className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
              />
              {open ? "Hide SQL + rows" : "Show SQL + rows"}
            </button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent>
          <div className="border-t border-border px-3 py-3">
            {leg.sql && (
              <pre className="mb-3 overflow-x-auto rounded-md border border-border bg-[var(--akzo-input-bg)] p-3 font-mono text-xs leading-relaxed text-[oklch(0.78_0.02_260)] whitespace-pre-wrap break-words">
                {leg.sql}
              </pre>
            )}
            {leg.rows.length > 0 && (
              <div className="overflow-x-auto rounded-md border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {leg.columns.map((c) => (
                        <TableHead key={c} className="whitespace-nowrap text-xs">
                          {c}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {leg.rows.map((r, i) => (
                      <TableRow key={i}>
                        {leg.columns.map((c) => (
                          <TableCell key={c} className="whitespace-nowrap text-xs">
                            {String(r[c] ?? "")}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState(FLAGSHIP);
  const [persona, setPersona] = useState("controller");
  const [result, setResult] = useState<AskResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [identity, setIdentity] = useState<string | null>(null);

  useEffect(() => {
    api.health().then((h) => setIdentity(h.identity)).catch(() => {});
  }, []);

  function onAsk() {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setFeedbackSent(null);
    api
      .ask(question, persona)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }

  function onFeedback(rating: number) {
    if (!result) return;
    api
      .feedback(result.session_uuid, rating, note || undefined)
      .then(() => setFeedbackSent(rating > 0 ? "Thanks — recorded." : "Thanks — recorded."))
      .catch((e) => setError(e.message));
  }

  return (
    <Page>
      <PageHeader
        eyebrow="AkzoNobel · Agent Bricks"
        title="Multi-domain Supervisor Agent"
        subtitle="One chat, routed across Finance / SCM / Commercial Genie spaces · governed per user (on-behalf-of) · fused into one answer with a visible routing trace — and turned into a governed action."
        actions={
          identity && (
            <Badge variant="secondary" className="gap-1.5 font-normal">
              <User className="h-3.5 w-3.5" />
              {identity}
            </Badge>
          )
        }
      />

      <div className="flex flex-col gap-6">
        {error && <ErrorText>{error}</ErrorText>}

        {/* Ask box */}
        <Card className="border-border bg-card">
          <CardContent className="flex flex-col gap-4 pt-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex min-w-[220px] flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground">Persona</label>
                <Select value={persona} onValueChange={setPersona}>
                  <SelectTrigger className="w-[240px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PERSONAS.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="flex-1 text-xs leading-relaxed text-muted-foreground">
                Persona sets the governed data scope — OBO enforces it at each Genie call (reads).
              </p>
            </div>

            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder="Ask a cross-domain question…"
              className="resize-y"
            />

            <div className="flex flex-wrap gap-2">
              {SAMPLES.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setQuestion(s.q)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-2.5 py-1 text-xs font-medium text-[var(--akzo-link)] transition-colors hover:border-primary"
                >
                  {i === 0 && <Sparkles className="h-3 w-3" />}
                  {s.label}
                </button>
              ))}
            </div>

            <div>
              <Button onClick={onAsk} disabled={busy}>
                {busy ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Thinking…
                  </>
                ) : (
                  "Ask the Supervisor"
                )}
              </Button>
              {busy && <ThinkingIndicator />}
            </div>
          </CardContent>
        </Card>

        {result && (
          <>
            {/* Routing decision — the visible trace */}
            <Card className="border-border bg-card">
              <CardHeader className="space-y-0 pb-3">
                <div className="flex items-center gap-2">
                  <GitBranch className="h-4 w-4 text-primary" />
                  <SectionTitle>Routing decision</SectionTitle>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="rounded-md border-l-2 border-primary bg-secondary px-3 py-2 text-xs text-muted-foreground">
                  {result.persona_scope}
                </p>
                <div className="flex flex-col gap-2.5">
                  {result.routing.map((r) => (
                    <div key={r.domain} className="flex items-baseline gap-3">
                      <DomainBadge domain={r.domain} />
                      <span className="text-sm leading-relaxed text-foreground">{r.reason}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Domain legs — per-leg TracePanel */}
            <Card className="border-border bg-card">
              <CardHeader className="space-y-0 pb-3">
                <SectionTitle>Domain legs</SectionTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2.5">
                {result.legs.map((leg) => (
                  <LegResult key={leg.domain} leg={leg} />
                ))}
              </CardContent>
            </Card>

            {/* Fused answer + recommended action + feedback */}
            <Card className="border-primary/50 bg-card">
              <CardHeader className="space-y-0 pb-3">
                <SectionTitle>Fused answer</SectionTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <p className="text-[15px] leading-relaxed text-foreground whitespace-pre-wrap">
                  {result.answer}
                </p>
                {result.recommended_action && (
                  <div className="rounded-lg border-l-2 border-primary bg-primary/10 px-3.5 py-3">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                      Recommended action
                    </span>
                    <p className="mt-1 text-sm leading-relaxed text-foreground">
                      {result.recommended_action}
                    </p>
                  </div>
                )}

                <Separator />

                <div className="flex flex-wrap items-center gap-2">
                  {feedbackSent ? (
                    <span className="text-sm font-medium" style={{ color: "var(--status-executed)" }}>
                      {feedbackSent}
                    </span>
                  ) : (
                    <>
                      <input
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Optional note…"
                        className="h-9 flex-1 rounded-md border border-border bg-[var(--akzo-input-bg)] px-3 text-sm text-foreground outline-none focus:border-primary"
                      />
                      <Button variant="outline" size="icon" onClick={() => onFeedback(1)} aria-label="Thumbs up">
                        <ThumbsUp className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="icon" onClick={() => onFeedback(-1)} aria-label="Thumbs down">
                        <ThumbsDown className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  session #{result.session_id} · logged to Lakebase akzo.agent_sessions
                </p>
              </CardContent>
            </Card>

            {/* The agent ACTS — governed action plane */}
            <ActionsPanel
              defaultAction={defaultActionFor(result)}
              hint="Stage the recommended next-best-action through the governed Action Plane — guardrails are checked, then a 2-step Approve → Execute drives it into the connected systems with a full audit trail."
            />
          </>
        )}
      </div>
    </Page>
  );
}
