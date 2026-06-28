import type { GuardrailVerdict } from "../api";
import { formatRuleNumber, humanize } from "../format";

// Pass/breach checks as small chips — governance made tangible. The
// `requires_approval` rule is informational (no pass/fail), shown as neutral.
const RULE_LABELS: Record<string, string> = {
  action_type_allowed: "Action type allowed",
  max_discount_pct: "Discount cap",
  max_spend_eur: "Spend cap",
  allowed_regions: "Region in scope",
  requires_approval: "Approval policy",
};

export function GuardrailChips({ verdict }: { verdict: GuardrailVerdict }) {
  return (
    <div className="guardrails">
      <div className="guardrails-head">
        <span
          className={`verdict ${verdict.passed ? "pass" : "breach"}`}
        >
          {verdict.passed ? "All checks pass" : `${verdict.breaches.length} breach${verdict.breaches.length === 1 ? "" : "es"}`}
        </span>
      </div>
      <div className="chip-row">
        {verdict.checks.map((c) => {
          const informational = c.rule === "requires_approval";
          const cls = informational ? "info" : c.applicable ? (c.passed ? "ok" : "bad") : "muted";
          const label = RULE_LABELS[c.rule] ?? humanize(c.rule);
          return (
            <span className={`chip ${cls}`} key={c.rule} title={c.detail}>
              <span className="chip-mark" aria-hidden>
                {informational ? "•" : c.applicable ? (c.passed ? "✓" : "✕") : "–"}
              </span>
              <span className="chip-label">{label}</span>
              {c.applicable && c.limit != null && !informational && (
                <span className="chip-limit">
                  {formatRuleNumber(c.rule, c.value)} / {formatRuleNumber(c.rule, c.limit)}
                </span>
              )}
            </span>
          );
        })}
      </div>
      {!verdict.passed && (
        <ul className="breach-list">
          {verdict.breaches.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
