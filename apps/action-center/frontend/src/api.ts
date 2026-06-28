// Typed API client for the Action Center FastAPI backend.

export type Status =
  | "proposed"
  | "approved"
  | "executing"
  | "executed"
  | "rejected"
  | "failed"
  | "escalated";

export interface ActionEvent {
  id: number;
  action_id: number;
  ts: string;
  event: string;
  actor: string;
  detail: Record<string, unknown> | null;
}

export interface Action {
  id: number;
  agent: string;
  action_type: string;
  subject: string;
  payload: Record<string, unknown> | null;
  status: Status;
  level: number;
  region: string;
  requested_by: string | null;
  approved_by: string | null;
  created_at: string;
  decided_at: string | null;
  executed_at: string | null;
  result: Record<string, unknown> | null;
  external_ref: string | null;
  events?: ActionEvent[];
}

export interface GuardrailCheck {
  rule: string;
  applicable: boolean;
  passed: boolean;
  limit: unknown;
  value: unknown;
  detail: string;
}

export interface GuardrailVerdict {
  passed: boolean;
  breaches: string[];
  checks: GuardrailCheck[];
}

export interface ActionDetail {
  action: Action;
  guardrails: GuardrailVerdict;
}

export interface LadderLevel {
  level: number;
  total: number;
  by_status: Partial<Record<Status, number>>;
}

export interface Ladder {
  levels: LadderLevel[];
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface ActionFilters {
  status?: string;
  level?: number;
  agent?: string;
}

export const api = {
  ladder: () => get<Ladder>("/api/ladder"),
  health: () => get<{ status: string; identity: string }>("/api/health"),
  actions: (f: ActionFilters = {}) => {
    const q = new URLSearchParams();
    if (f.status) q.set("status", f.status);
    if (f.level != null) q.set("level", String(f.level));
    if (f.agent) q.set("agent", f.agent);
    const qs = q.toString();
    return get<{ actions: Action[] }>(`/api/actions${qs ? `?${qs}` : ""}`);
  },
  action: (id: number) => get<ActionDetail>(`/api/actions/${id}`),
  approve: (id: number, approver: string) =>
    post<ActionDetail>(`/api/actions/${id}/approve`, { approver }),
  reject: (id: number, approver: string, reason: string) =>
    post<ActionDetail>(`/api/actions/${id}/reject`, { approver, reason }),
  execute: (id: number) => post<ActionDetail>(`/api/actions/${id}/execute`),
};
