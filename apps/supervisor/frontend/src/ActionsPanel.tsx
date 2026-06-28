// Shared Actions panel — the "this agent can ACT" surface.
//
// Copied verbatim into each app's frontend/src/ so the panel is consistent across
// supervisor / finance-copilot / quote-agent (per DESIGN_BRIEF). It drives the full
// Act → Approve → Execute → Confirm loop against the governed Action Plane:
//   1. the parent wires a sensible default action (ActBody) from its domain output;
//   2. "Stage action" proposes it (POST /api/act) → shows the staged action + GuardrailChips;
//   3. a 2-step Approve → Execute affordance (guardrail verdict shown before execute);
//   4. on execute, the resulting external_ref + Confirm state + event Timeline.
//
// Styling uses the shared `.ap-*` classes added to each app's styles.css.

import { useState } from "react";
import {
  Action,
  ActBody,
  ActResult,
  actionsApi,
  Guardrail,
  ActionEvent,
} from "./actions";

const STATUS_LABEL: Record<string, string> = {
  proposed: "Proposed",
  approved: "Approved",
  executing: "Executing",
  executed: "Executed",
  rejected: "Rejected",
  failed: "Failed",
  escalated: "Escalated",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`ap-badge ap-status-${status}`}>
      <span className="ap-dot" />
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function GuardrailChips({ guardrail }: { guardrail: Guardrail }) {
  const checks = guardrail.checks.filter((c) => c.applicable);
  if (checks.length === 0) return null;
  return (
    <div className="ap-chips">
      {checks.map((c) => (
        <span
          key={c.rule}
          className={`ap-chip ${c.passed ? "ap-chip-ok" : "ap-chip-bad"}`}
          title={c.detail}
        >
          {c.passed ? "✓" : "✕"} {c.detail}
        </span>
      ))}
    </div>
  );
}

function Timeline({ events }: { events: ActionEvent[] }) {
  if (!events || events.length === 0) return null;
  return (
    <ol className="ap-timeline">
      {events.map((e) => (
        <li key={e.id} className={`ap-tl-item ap-tl-${e.event}`}>
          <span className="ap-tl-dot" />
          <div className="ap-tl-body">
            <div className="ap-tl-head">
              <span className="ap-tl-event">{e.event}</span>
              <span className="ap-tl-actor">{e.actor}</span>
            </div>
            <div className="ap-tl-ts">
              {String(e.ts).slice(0, 19).replace("T", " ")}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

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
  title = "Actions",
  hint,
}: {
  defaultAction: ActBody | null;
  title?: string;
  hint?: string;
}) {
  const [staged, setStaged] = useState<ActResult | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const current = action ?? staged?.action ?? null;
  const guardrail = staged?.guardrail ?? null;
  const status = current?.status;

  function reset() {
    setStaged(null);
    setAction(null);
    setError(null);
  }

  function onStage() {
    if (!defaultAction) return;
    setBusy("stage");
    setError(null);
    actionsApi
      .act(defaultAction)
      .then((r) => {
        setStaged(r);
        setAction(r.action);
      })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  }

  function onApprove() {
    if (!current) return;
    setBusy("approve");
    setError(null);
    actionsApi
      .approve(current.id)
      .then((r) => setAction(r.action))
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  }

  function onExecute() {
    if (!current) return;
    setBusy("execute");
    setError(null);
    actionsApi
      .execute(current.id)
      .then((r) => setAction(r.action))
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  }

  return (
    <section className="card ap-panel">
      <div className="ap-panel-head">
        <h2>{title}</h2>
        {current && <StatusBadge status={current.status} />}
      </div>

      {error && <div className="ap-error">⚠ {error}</div>}

      {!current && (
        <div className="ap-empty">
          {defaultAction ? (
            <>
              <p className="ap-empty-text">
                {hint ??
                  "Turn this answer into a governed action — staged for approval, then executed into the connected systems."}
              </p>
              <div className="ap-stage-preview">
                <span className="ap-type">
                  {ACTION_TYPE_LABEL[defaultAction.action_type] ??
                    defaultAction.action_type}
                </span>
                <span className="ap-subject">{defaultAction.subject}</span>
              </div>
              <button
                className="ap-btn ap-btn-primary"
                onClick={onStage}
                disabled={busy === "stage"}
              >
                {busy === "stage" ? "Staging…" : "Stage action"}
              </button>
            </>
          ) : (
            <p className="ap-empty-text">
              No action yet — run the agent above, then stage the recommended
              action here.
            </p>
          )}
        </div>
      )}

      {current && (
        <div className="ap-detail">
          <div className="ap-detail-row">
            <span className="ap-type">
              {ACTION_TYPE_LABEL[current.action_type] ?? current.action_type}
            </span>
            <span className="ap-id">#{current.id}</span>
            <span className="ap-region">{current.region || "—"}</span>
          </div>
          <p className="ap-subject-lg">{current.subject}</p>

          {guardrail && (
            <div className="ap-guardrails">
              <div className="ap-guardrails-head">
                Guardrails{" "}
                <span
                  className={
                    guardrail.passed ? "ap-verdict-ok" : "ap-verdict-bad"
                  }
                >
                  {guardrail.passed ? "all pass" : "breach"}
                </span>
              </div>
              <GuardrailChips guardrail={guardrail} />
            </div>
          )}

          {/* 2-step Approve → Execute affordance */}
          <div className="ap-actions">
            {status === "proposed" && (
              <button
                className="ap-btn ap-btn-primary"
                onClick={onApprove}
                disabled={busy === "approve"}
              >
                {busy === "approve" ? "Approving…" : "Approve →"}
              </button>
            )}
            {status === "approved" && (
              <button
                className="ap-btn ap-btn-primary"
                onClick={onExecute}
                disabled={busy === "execute"}
              >
                {busy === "execute" ? "Executing…" : "Execute"}
              </button>
            )}
            {status === "escalated" && (
              <span className="ap-note ap-note-warn">
                Escalated to a human gate — guardrail breach blocked auto-execute.
              </span>
            )}
            {(status === "executed" || status === "failed" || status === "rejected") && (
              <button className="ap-btn ap-btn-ghost" onClick={reset}>
                Stage another
              </button>
            )}
          </div>

          {/* Confirm / external effect */}
          {status === "executed" && current.external_ref && (
            <div className="ap-confirm">
              <span className="ap-confirm-tick">✓</span>
              Executed — external ref{" "}
              <code className="ap-ref">{current.external_ref}</code>
            </div>
          )}
          {status === "failed" && (
            <div className="ap-confirm ap-confirm-fail">
              Execution failed — see the timeline below.
            </div>
          )}

          {/* Audit lineage */}
          {current.events && current.events.length > 0 && (
            <div className="ap-lineage">
              <div className="ap-lineage-head">Audit lineage</div>
              <Timeline events={current.events} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
