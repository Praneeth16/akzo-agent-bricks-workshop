// Typed API client for the quote-agent FastAPI backend.

export interface Matched {
  sku: string;
  product_name: string;
  product_line: string;
  region: string;
  currency: string;
  list_price_eur: number;
  standard_cost_eur: number;
}

export interface Trace {
  step: string;
  data_source: string;
  sql: string[];
}

export interface ParseResult {
  fields: {
    customer: string | null;
    product: string | null;
    region: string | null;
    quantity_litres: number | null;
    requested_terms: string | null;
  };
  matched: Matched | null;
  trace: Trace;
}

export interface PriceResult {
  sku: string;
  product_name: string;
  region: string;
  currency: string;
  list_price_eur: number;
  standard_cost_eur: number;
  unit_margin_eur: number;
  unit_margin_pct: number;
  recent_realized: {
    month: string | null;
    realized_price_eur: number | null;
    realized_margin_pct: number | null;
  } | null;
  trace: Trace;
}

export interface Draft {
  quantity_units: number;
  list_price_eur: number;
  discount_pct: number;
  net_unit_price_eur: number;
  extended_price_eur: number;
  standard_cost_eur: number;
  total_cost_eur: number;
  unit_margin_eur: number;
  margin_pct: number;
  total_margin_eur: number;
  guardrail_flags: string[];
  requires_escalation: boolean;
}

export interface QuoteResult {
  draft: Draft;
  quote_id: number;
  status: string;
  created_at: string;
  trace: Trace;
}

export interface Approval {
  quote_id: number;
  account_id: string;
  sku: string;
  region: string;
  quantity_units: number;
  list_price_eur: number;
  quoted_price_eur: number;
  discount_pct: number;
  rationale: string;
  status: string;
  created_by: string;
  created_at: string;
  decision: string | null;
  approver: string | null;
  comment: string | null;
  decided_at: string | null;
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
  parse: (rfq_text: string) => post<ParseResult>("/api/parse", { rfq_text }),
  price: (sku: string, region?: string) => post<PriceResult>("/api/price", { sku, region }),
  quote: (body: {
    account_id: string;
    sku: string;
    region?: string;
    quantity_units: number;
    list_price_eur: number;
    standard_cost_eur: number;
    discount_pct: number;
  }) => post<QuoteResult>("/api/quote", body),
  approvals: async (): Promise<Approval[]> => {
    const res = await fetch("/api/approvals?status=pending");
    if (!res.ok) throw new Error("Failed to load approvals");
    return (await res.json()).quotes;
  },
  decide: (quote_id: number, decision: "approved" | "rejected", approver: string, comment?: string) =>
    post<DecideResult>(`/api/approvals/${quote_id}`, {
      decision,
      approver,
      comment,
    }),
};

// The quote-agent's approve flow ALSO stages + executes a governed quote_send
// action (email the customer + CRM task) through the Action Plane, so the quote
// really goes out. `dispatched` carries that action's id + external_ref.
export interface Dispatched {
  action_id?: number;
  status?: string;
  external_ref?: string | null;
  guardrail?: { passed: boolean; breaches: string[] };
  result?: unknown;
  error?: string;
}

export interface DecideResult {
  quote_id: number;
  status: string;
  approver: string;
  dispatched: Dispatched | null;
}
