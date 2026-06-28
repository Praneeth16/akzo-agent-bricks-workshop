// Typed API client for the finance-copilot FastAPI backend.

export interface Trace {
  step: string;
  data_source: string;
  sql: string[];
}

export interface AskResult {
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  answer: string;
  trace: Trace;
}

export interface PeriodMetrics {
  period: string;
  units: number;
  revenue_eur: number;
  cogs_eur: number;
  gross_margin_eur: number;
  gross_margin_pct: number;
  price_per_unit_eur: number;
  cogs_per_unit_eur: number;
  raw_mat_per_unit_eur: number;
  freight_per_unit_eur: number;
  energy_per_unit_eur: number;
  overhead_per_unit_eur: number;
  usd_rate_to_eur: number;
}

export interface Driver {
  delta_pp: number;
  detail: string;
}

export interface Bridge {
  from_margin_pct: number;
  to_margin_pct: number;
  total_delta_pp: number;
  drivers: {
    price: Driver;
    volume: Driver;
    fx: Driver;
    cost: Driver;
  };
}

export interface VarianceResult {
  product_line: string;
  region: string;
  from_period: string;
  to_period: string;
  periods: Record<string, PeriodMetrics>;
  bridge: Bridge;
  narrative: string;
  recommended_action: string;
  trace: Trace;
}

export interface SaveResult {
  analysis_id: number;
  created_at: string;
  trace: Trace;
}

export interface SavedRow {
  analysis_id: number;
  kind: string;
  title: string;
  product_line: string | null;
  region: string | null;
  from_period: string | null;
  to_period: string | null;
  question: string | null;
  summary: string | null;
  created_by: string;
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
  ask: (question: string) => post<AskResult>("/api/ask", { question }),
  variance: (body: {
    product_line: string;
    region: string;
    from_period: string;
    to_period: string;
  }) => post<VarianceResult>("/api/variance", body),
  save: (body: {
    kind: string;
    title: string;
    summary: string;
    payload: unknown;
    product_line?: string;
    region?: string;
    from_period?: string;
    to_period?: string;
    question?: string;
  }) => post<SaveResult>("/api/save", body),
  saved: async (): Promise<SavedRow[]> => {
    const res = await fetch("/api/saved");
    if (!res.ok) throw new Error("Failed to load saved analyses");
    return (await res.json()).analyses;
  },
};
