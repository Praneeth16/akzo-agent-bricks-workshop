import type { ActionEvent, Status } from "../api";
import { formatTs, humanize, statusColor } from "../format";

// Map an event name to the status colour it represents, so the lineage dots read
// in the same colour language as the badges.
const EVENT_STATUS: Record<string, Status> = {
  proposed: "proposed",
  approved: "approved",
  executing: "executing",
  executed: "executed",
  rejected: "rejected",
  failed: "failed",
  escalated: "escalated",
  connector: "executing",
  partial_failure: "failed",
  connector_failed: "failed",
};

function eventDetail(ev: ActionEvent): string | null {
  const d = ev.detail;
  if (!d || typeof d !== "object") return null;
  const parts: string[] = [];
  const rec = d as Record<string, unknown>;
  if (rec.external_ref) parts.push(`ref ${rec.external_ref}`);
  if (rec.system) parts.push(String(rec.system));
  if (rec.via) parts.push(`via ${rec.via}`);
  if (rec.reason) parts.push(String(rec.reason));
  if (rec.error) parts.push(String(rec.error));
  return parts.length ? parts.join(" · ") : null;
}

// Vertical event lineage — the audit story, visible. Dot + event + actor + ts + detail.
export function Timeline({ events }: { events: ActionEvent[] }) {
  if (!events.length) {
    return <p className="muted">No events recorded.</p>;
  }
  return (
    <ol className="timeline">
      {events.map((ev) => {
        const color = statusColor(EVENT_STATUS[ev.event] ?? "proposed");
        const detail = eventDetail(ev);
        return (
          <li className="timeline-item" key={ev.id}>
            <span className="timeline-dot" style={{ background: color, borderColor: color }} />
            <div className="timeline-body">
              <div className="timeline-line">
                <span className="timeline-event" style={{ color }}>
                  {humanize(ev.event)}
                </span>
                <span className="timeline-ts">{formatTs(ev.ts)}</span>
              </div>
              <div className="timeline-actor">{ev.actor}</div>
              {detail && <div className="timeline-detail">{detail}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
