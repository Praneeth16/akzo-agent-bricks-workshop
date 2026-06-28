import { useEffect, useState } from "react";
import type { ActionDetail } from "../api";
import { api } from "../api";
import { formatTs, humanize } from "../format";
import { StatusBadge } from "./StatusBadge";
import { GuardrailChips } from "./GuardrailChips";
import { Timeline } from "./Timeline";

type Pending = null | "approve" | "reject" | "execute";

// The detail drawer: identity, guardrail verdict, the external effect, the full
// audit timeline, and the act controls with a 2-step confirm.
export function DetailPanel({
  detail,
  approver,
  onClose,
  onChanged,
}: {
  detail: ActionDetail;
  approver: string;
  onClose: () => void;
  onChanged: (d: ActionDetail) => void;
}) {
  const { action, guardrails } = detail;
  const [confirm, setConfirm] = useState<Pending>(null);
  const [busy, setBusy] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  // Reset transient act state when the selected action changes.
  useEffect(() => {
    setConfirm(null);
    setBusy(null);
    setError(null);
    setRejectReason("");
  }, [action.id]);

  const canApprove = action.status === "proposed" || action.status === "escalated";
  const canReject =
    action.status === "proposed" || action.status === "approved" || action.status === "escalated";
  const canExecute = action.status === "approved";
  const noApprover = !approver.trim();

  async function run(kind: Exclude<Pending, null>) {
    setBusy(kind);
    setError(null);
    try {
      let res: ActionDetail;
      if (kind === "approve") res = await api.approve(action.id, approver);
      else if (kind === "reject") res = await api.reject(action.id, approver, rejectReason);
      else res = await api.execute(action.id);
      onChanged(res);
      setConfirm(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const connectors = extractConnectors(action.result);

  return (
    <aside className="detail">
      <div className="detail-head">
        <div>
          <div className="detail-eyebrow">
            <span className="level-pill">L{action.level}</span>
            <StatusBadge status={action.status} />
          </div>
          <h2 className="detail-title">{action.subject}</h2>
        </div>
        <button className="ghost icon-btn" onClick={onClose} title="Close" aria-label="Close detail">
          ✕
        </button>
      </div>

      <dl className="detail-fields">
        <div>
          <dt>Action</dt>
          <dd>#{action.id}</dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{humanize(action.agent)}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{humanize(action.action_type)}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{action.region}</dd>
        </div>
        <div>
          <dt>Requested by</dt>
          <dd>{action.requested_by ?? "—"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatTs(action.created_at)}</dd>
        </div>
      </dl>

      <section className="detail-section">
        <h3>Guardrails</h3>
        <GuardrailChips verdict={guardrails} />
      </section>

      {connectors.length > 0 && (
        <section className="detail-section">
          <h3>External effect</h3>
          <ul className="effect-list">
            {connectors.map((c, i) => (
              <li key={i}>
                <span className="effect-system">{humanize(c.system)}</span>
                <span className="effect-ref">{c.ref}</span>
                {c.via && <span className="effect-via">via {c.via}</span>}
              </li>
            ))}
          </ul>
          {action.external_ref && (
            <p className="effect-primary">
              External ref <code>{action.external_ref}</code>
            </p>
          )}
        </section>
      )}

      <section className="detail-section">
        <h3>Audit lineage</h3>
        <Timeline events={action.events ?? []} />
      </section>

      {action.payload && Object.keys(action.payload).length > 0 && (
        <details className="detail-section payload">
          <summary>Action payload</summary>
          <pre className="code">{JSON.stringify(action.payload, null, 2)}</pre>
        </details>
      )}

      {(canApprove || canReject || canExecute) && (
        <div className="act-bar">
          {error && <div className="error">{error}</div>}
          {noApprover && (canApprove || canReject) && (
            <p className="hint">Set an approver identity above to act.</p>
          )}

          {confirm === "execute" && (
            <div className="confirm">
              <p className="confirm-q">
                {guardrails.passed
                  ? "Guardrails pass. Execute this action into the connected systems?"
                  : "Guardrails breach — executing will escalate instead of acting. Continue?"}
              </p>
              <div className="confirm-row">
                <button className="primary" disabled={busy === "execute"} onClick={() => run("execute")}>
                  {busy === "execute" ? "Executing…" : "Confirm execute"}
                </button>
                <button className="ghost" disabled={busy === "execute"} onClick={() => setConfirm(null)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {confirm === "approve" && (
            <div className="confirm">
              <p className="confirm-q">Approve as {approver}?</p>
              <div className="confirm-row">
                <button className="primary" disabled={busy === "approve"} onClick={() => run("approve")}>
                  {busy === "approve" ? "Approving…" : "Confirm approve"}
                </button>
                <button className="ghost" disabled={busy === "approve"} onClick={() => setConfirm(null)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {confirm === "reject" && (
            <div className="confirm">
              <p className="confirm-q">Reject as {approver}. Reason is recorded in the audit trail.</p>
              <input
                className="reason-input"
                placeholder="Reason for rejection"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                autoFocus
              />
              <div className="confirm-row">
                <button
                  className="danger"
                  disabled={busy === "reject" || !rejectReason.trim()}
                  onClick={() => run("reject")}
                >
                  {busy === "reject" ? "Rejecting…" : "Confirm reject"}
                </button>
                <button className="ghost" disabled={busy === "reject"} onClick={() => setConfirm(null)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {confirm === null && (
            <div className="act-row">
              {canExecute && (
                <button className="primary" disabled={noApprover && false} onClick={() => setConfirm("execute")}>
                  Execute
                </button>
              )}
              {canApprove && (
                <button className="primary" disabled={noApprover} onClick={() => setConfirm("approve")}>
                  Approve
                </button>
              )}
              {canReject && (
                <button className="danger" disabled={noApprover} onClick={() => setConfirm("reject")}>
                  Reject
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

interface ConnectorEffect {
  system: string;
  ref: string;
  via?: string;
}

// Pull the connector receipts out of the executor result shape:
// result.connectors = [{system, ref_id, via, ...}].
function extractConnectors(result: Record<string, unknown> | null): ConnectorEffect[] {
  if (!result || typeof result !== "object") return [];
  const list = (result as Record<string, unknown>).connectors;
  if (!Array.isArray(list)) return [];
  const out: ConnectorEffect[] = [];
  for (const c of list) {
    if (!c || typeof c !== "object") continue;
    const rec = c as Record<string, unknown>;
    out.push({
      system: String(rec.system ?? "system"),
      ref: String(rec.ref_id ?? rec.external_ref ?? "—"),
      via: rec.via ? String(rec.via) : undefined,
    });
  }
  return out;
}
