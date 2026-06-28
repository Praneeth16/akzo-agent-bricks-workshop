import type { Status } from "../api";
import { statusColor, statusLabel } from "../format";

// Pill with a status-coloured dot + label. The one canonical way a status appears.
export function StatusBadge({ status }: { status: Status }) {
  const color = statusColor(status);
  return (
    <span className="status-badge" style={{ color }}>
      <span className="status-dot" style={{ background: color }} />
      {statusLabel(status)}
    </span>
  );
}
