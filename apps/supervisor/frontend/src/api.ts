// Typed API client for the supervisor-agent FastAPI backend.

export interface RoutingLeg {
  domain: string;
  reason: string;
}

export interface DomainLeg {
  domain: string;
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
  row_count: number;
  error: string | null;
}

export interface AskResult {
  session_id: number;
  session_uuid: string;
  question: string;
  persona: string;
  persona_scope: string;
  routing: RoutingLeg[];
  legs: DomainLeg[];
  answer: string;
  recommended_action: string;
}

export interface FeedbackResult {
  feedback_id: number;
  created_at: string;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  ask: (question: string, persona: string) =>
    post<AskResult>("/api/ask", { question, persona }),
  feedback: (session_uuid: string, rating: number, note?: string) =>
    post<FeedbackResult>("/api/feedback", { session_uuid, rating, note }),
};
