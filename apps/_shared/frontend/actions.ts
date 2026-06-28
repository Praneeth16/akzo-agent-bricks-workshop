// Typed client for the shared Action Plane API (/api/act, /api/actions, approve, execute).
// Copied verbatim into each app's frontend/src/ so all three apps share one
// Act → Approve → Execute → Confirm contract against the same governed plane.

export interface GuardrailCheck {
  rule: string;
  applicable: boolean;
  passed: boolean;
  limit: unknown;
  value: unknown;
  detail: string;
}

export interface Guardrail {
  passed: boolean;
  breaches: string[];
  checks: GuardrailCheck[];
}

export interface ActionEvent {
  id: number;
  action_id: number;
  ts: string;
  event: string;
  actor: string;
  detail: unknown;
}

export interface Action {
  id: number;
  agent: string;
  action_type: string;
  subject: string;
  payload: Record<string, unknown> | string | null;
  status: string;
  level: number;
  region: string;
  requested_by: string;
  approved_by: string | null;
  created_at: string;
  decided_at: string | null;
  executed_at: string | null;
  result: Record<string, unknown> | string | null;
  external_ref: string | null;
  events?: ActionEvent[];
}

export interface ActResult {
  action: Action;
  guardrail: Guardrail;
}

async function jpost<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface ActBody {
  action_type: string;
  subject: string;
  payload: Record<string, unknown>;
  region: string;
  level?: number;
}

export const actionsApi = {
  act: (body: ActBody) => jpost<ActResult>("/api/act", body),
  list: async (status?: string): Promise<Action[]> => {
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await fetch(`/api/actions${q}`);
    if (!res.ok) throw new Error("Failed to load actions");
    return (await res.json()).actions;
  },
  get: async (id: number): Promise<ActResult> => {
    const res = await fetch(`/api/actions/${id}`);
    if (!res.ok) throw new Error("Failed to load action");
    return res.json();
  },
  approve: (id: number, approver?: string) =>
    jpost<{ action: Action }>(`/api/actions/${id}/approve`, { approver }),
  execute: (id: number) => jpost<{ action: Action }>(`/api/actions/${id}/execute`),
};
