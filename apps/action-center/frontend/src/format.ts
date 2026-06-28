// Shared formatting + status metadata. Keep status colours/labels in ONE place so
// they read identically in the queue, the ladder, the detail panel, and the timeline.
import type { Status } from "./api";

export const STATUS_META: Record<Status, { label: string; color: string }> = {
  proposed: { label: "Proposed", color: "var(--st-proposed)" },
  approved: { label: "Approved", color: "var(--st-approved)" },
  executing: { label: "Executing", color: "var(--st-executing)" },
  executed: { label: "Executed", color: "var(--st-executed)" },
  rejected: { label: "Rejected", color: "var(--st-rejected)" },
  failed: { label: "Failed", color: "var(--st-failed)" },
  escalated: { label: "Escalated", color: "var(--st-escalated)" },
};

export const LADDER_LEVELS = [
  { level: 1, name: "Recommend", blurb: "Proposes a next-best action" },
  { level: 2, name: "Stage & approve", blurb: "Writes a governed record, human approves" },
  { level: 3, name: "Execute", blurb: "Pushes into real systems on approval" },
  { level: 4, name: "Autonomous", blurb: "Acts within policy, escalates on breach" },
];

export function statusColor(status: Status): string {
  return STATUS_META[status]?.color ?? "var(--muted)";
}

export function statusLabel(status: Status): string {
  return STATUS_META[status]?.label ?? status;
}

// Sentence-case an agent / event token like "scm-agent" → "Scm agent".
export function humanize(token: string): string {
  const s = token.replace(/[-_]/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const _dt = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatTs(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return _dt.format(d);
}

const _eur = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

export function formatEur(value: number): string {
  return _eur.format(value);
}

export function formatPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

// Render a guardrail limit/value, formatting currency vs percent vs plain by rule.
export function formatRuleNumber(rule: string, value: unknown): string {
  if (value == null) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (rule === "max_spend_eur") return formatEur(value);
    if (rule === "max_discount_pct") return formatPct(value);
    return String(value);
  }
  return String(value);
}
