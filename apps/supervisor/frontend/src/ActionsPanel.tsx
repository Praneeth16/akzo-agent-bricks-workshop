// The "this agent can ACT" surface — first-class in the supervisor demo.
//
// Drives the full Act → Approve → Execute → Confirm loop against the governed
// Action Plane, with the signature exec visuals from apps/DESIGN_BRIEF.md:
//   - LadderMeter (L1 Recommend → L4 Autonomous) tracking the action's level;
//   - "Stage action" proposes it (POST /api/act) → GuardrailChips verdict;
//   - a 2-step Approve → Execute affordance (verdict shown before execute);
//   - StatusBadge transitioning proposed → approved → executing → executed
//     (or escalated on a guardrail breach);
//   - the action_events Timeline (audit lineage) + the external_ref on success.

import { useState } from "react";
import { Button, Card, CardContent, CardHeader } from "@databricks/appkit-ui/react";
import { ArrowRight, CheckCircle2, ExternalLink, ShieldAlert } from "lucide-react";
import { Action, ActBody, ActResult, actionsApi, Guardrail } from "@/actions";
import { GuardrailChips, LadderMeter, StatusBadge, Timeline } from "@/components/action-ui";
import { SectionTitle } from "@/components/kit";

const ACTION_TYPE_LABEL: Record<string, string> = {
  crm_task: "CRM task",
  scm_reroute: "SCM reroute",
  scm_reorder: "SCM reorder",
  price_change: "Price change",
  forecast_override: "Forecast override",
  quote_send: "Quote send",
  escalation: "Escalation",
};

export function ActionsPanel({
  defaultAction,
  hint,
}: {
  defaultAction: ActBody | null;
  hint?: string;
}) {
  const [staged, setStaged] = useState<ActResult | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const current = action ?? staged?.action ?? null;
  const guardrail: Guardrail | null = staged?.guardrail ?? null;
  const status = current?.status;
  const level = current?.level ?? defaultAction?.level ?? 2;

  function reset() {
    setStaged(null);
    setAction(null);
    setError(null);
  }

  function run(kind: "stage" | "approve" | "execute") {
    setBusy(kind);
    setError(null);
    const p =
      kind === "stage"
        ? actionsApi.act(defaultAction!).then((r) => {
            setStaged(r);
            setAction(r.action);
          })
        : kind === "approve"
          ? actionsApi.approve(current!.id).then((r) => setAction(r.action))
          : actionsApi.execute(current!.id).then((r) => setAction(r.action));
    p.catch((e) => setError(e.message)).finally(() => setBusy(null));
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <SectionTitle>Governed action</SectionTitle>
        {current && <StatusBadge status={current.status} />}
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted-foreground">
            Action Maturity Ladder
          </span>
          <LadderMeter current={current ? level : null} />
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {!current && (
          <div className="flex flex-col gap-3">
            <p className="text-sm leading-relaxed text-muted-foreground">
              {hint ??
                "Turn this recommendation into a governed action — staged for approval, then executed into the connected systems."}
            </p>
            {defaultAction ? (
              <>
                <div className="flex flex-col gap-1 rounded-lg border border-border bg-secondary px-3 py-2.5">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                    {ACTION_TYPE_LABEL[defaultAction.action_type] ?? defaultAction.action_type}
                  </span>
                  <span className="text-sm text-foreground">{defaultAction.subject}</span>
                </div>
                <div>
                  <Button onClick={() => run("stage")} disabled={busy === "stage"}>
                    {busy === "stage" ? "Staging…" : "Stage action"}
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                No action yet — ask the supervisor above, then stage the recommended action here.
              </p>
            )}
          </div>
        )}

        {current && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                  {ACTION_TYPE_LABEL[current.action_type] ?? current.action_type}
                </span>
                <span className="text-xs text-muted-foreground">#{current.id}</span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {current.region || "—"} · L{current.level}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-foreground">{current.subject}</p>
            </div>

            {guardrail && (
              <div className="rounded-lg border border-border bg-secondary p-3">
                <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                  Guardrails
                  <span
                    className="font-bold"
                    style={{
                      color: guardrail.passed
                        ? "var(--status-executed)"
                        : "var(--status-rejected)",
                    }}
                  >
                    {guardrail.passed ? "all pass" : "breach"}
                  </span>
                </div>
                <GuardrailChips guardrail={guardrail} />
              </div>
            )}

            {/* 2-step Approve → Execute affordance */}
            <div className="flex flex-wrap items-center gap-3">
              {status === "proposed" && (
                <Button onClick={() => run("approve")} disabled={busy === "approve"}>
                  {busy === "approve" ? "Approving…" : "Approve"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              )}
              {status === "approved" && (
                <Button onClick={() => run("execute")} disabled={busy === "execute"}>
                  {busy === "execute" ? "Executing…" : "Execute"}
                </Button>
              )}
              {status === "escalated" && (
                <span className="inline-flex items-center gap-2 text-sm" style={{ color: "var(--status-escalated)" }}>
                  <ShieldAlert className="h-4 w-4" />
                  Escalated to a human gate — a guardrail breach blocked auto-execute.
                </span>
              )}
              {(status === "executed" || status === "failed" || status === "rejected") && (
                <Button variant="outline" onClick={reset}>
                  Stage another
                </Button>
              )}
            </div>

            {/* Confirm / external effect */}
            {status === "executed" && current.external_ref && (
              <div
                className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2.5 text-sm"
                style={{
                  color: "var(--status-executed)",
                  borderColor: "color-mix(in oklab, var(--status-executed) 40%, transparent)",
                  background: "color-mix(in oklab, var(--status-executed) 10%, transparent)",
                }}
              >
                <CheckCircle2 className="h-4 w-4" />
                Executed — external ref
                <code className="inline-flex items-center gap-1 rounded border border-border bg-[var(--akzo-input-bg)] px-1.5 py-0.5 font-mono text-xs text-[var(--akzo-link)]">
                  <ExternalLink className="h-3 w-3" />
                  {current.external_ref}
                </code>
              </div>
            )}
            {status === "failed" && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
                Execution failed — see the timeline below.
              </div>
            )}

            {/* Audit lineage */}
            {current.events && current.events.length > 0 && (
              <div>
                <div className="mb-2 text-xs text-muted-foreground">Audit lineage</div>
                <Timeline events={current.events} />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
