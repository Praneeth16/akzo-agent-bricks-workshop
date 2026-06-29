/** Action-plane presentational components, per apps/DESIGN_BRIEF.md:
 *  StatusBadge, LadderMeter, GuardrailChips, Timeline. AkzoNobel dark theme. */
import { Check, X } from "lucide-react";
import type { ActionEvent, Guardrail } from "@/actions";
import { cn } from "@/lib/utils";

const STATUS: Record<string, { label: string; color: string }> = {
  proposed: { label: "Proposed", color: "var(--status-proposed)" },
  approved: { label: "Approved", color: "var(--status-approved)" },
  executing: { label: "Executing", color: "var(--status-executing)" },
  executed: { label: "Executed", color: "var(--status-executed)" },
  rejected: { label: "Rejected", color: "var(--status-rejected)" },
  failed: { label: "Failed", color: "var(--status-failed)" },
  escalated: { label: "Escalated", color: "var(--status-escalated)" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, color: "var(--status-proposed)" };
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold"
      style={{ color: s.color, borderColor: s.color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.color }} />
      {s.label}
    </span>
  );
}

// --- Action Maturity Ladder ------------------------------------------------
const LADDER = [
  { level: 1, label: "Recommend", desc: "Agent advises" },
  { level: 2, label: "Stage & approve", desc: "Human gate" },
  { level: 3, label: "Execute", desc: "Acts into systems" },
  { level: 4, label: "Autonomous", desc: "Policy-governed" },
];

export function LadderMeter({ current }: { current: number | null }) {
  return (
    <div className="grid grid-cols-4 gap-2">
      {LADDER.map((step) => {
        const active = current === step.level;
        const reached = current != null && step.level <= current;
        return (
          <div
            key={step.level}
            className={cn(
              "rounded-lg border px-3 py-2.5 transition-colors",
              active
                ? "border-primary bg-primary/10"
                : reached
                  ? "border-border bg-secondary"
                  : "border-border/60 bg-transparent opacity-60"
            )}
          >
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold",
                  active
                    ? "bg-primary text-primary-foreground"
                    : reached
                      ? "bg-muted text-foreground"
                      : "bg-secondary text-muted-foreground"
                )}
              >
                {step.level}
              </span>
              <span
                className={cn(
                  "text-xs font-semibold",
                  active ? "text-primary" : "text-foreground"
                )}
              >
                {step.label}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">{step.desc}</div>
          </div>
        );
      })}
    </div>
  );
}

// --- Guardrail chips --------------------------------------------------------
export function GuardrailChips({ guardrail }: { guardrail: Guardrail }) {
  const checks = guardrail.checks.filter((c) => c.applicable);
  if (checks.length === 0) {
    return <p className="text-xs text-muted-foreground">No guardrail policies apply to this action.</p>;
  }
  return (
    <div className="flex flex-col gap-1.5">
      {checks.map((c) => (
        <span
          key={c.rule}
          title={c.detail}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs leading-snug",
            c.passed
              ? "border-[var(--status-executed)]/40 bg-[var(--status-executed)]/10 text-[var(--status-executed)]"
              : "border-destructive/40 bg-destructive/10 text-destructive"
          )}
        >
          {c.passed ? <Check className="h-3.5 w-3.5 shrink-0" /> : <X className="h-3.5 w-3.5 shrink-0" />}
          {c.detail}
        </span>
      ))}
    </div>
  );
}

// --- Audit timeline ---------------------------------------------------------
const EVENT_COLOR: Record<string, string> = {
  proposed: "var(--status-proposed)",
  approved: "var(--status-approved)",
  executing: "var(--status-executing)",
  executed: "var(--status-executed)",
  rejected: "var(--status-rejected)",
  failed: "var(--status-failed)",
  escalated: "var(--status-escalated)",
};

export function Timeline({ events }: { events: ActionEvent[] }) {
  if (!events || events.length === 0) return null;
  return (
    <ol className="relative ml-1">
      {events.map((e, i) => {
        const color = EVENT_COLOR[e.event] ?? "var(--status-proposed)";
        const last = i === events.length - 1;
        return (
          <li key={e.id} className="relative flex gap-3 pb-4 last:pb-0">
            {!last && (
              <span className="absolute left-[4px] top-3 bottom-0 w-px bg-border" aria-hidden />
            )}
            <span
              className="z-10 mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: color }}
            />
            <div className="flex flex-col gap-0.5">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-semibold capitalize text-foreground">{e.event}</span>
                <span className="text-xs text-muted-foreground">{e.actor}</span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {String(e.ts).slice(0, 19).replace("T", " ")}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
