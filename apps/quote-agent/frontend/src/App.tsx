import { useEffect, useState } from "react";
import {
  api,
  Approval,
  Dispatched,
  Draft,
  ParseResult,
  PriceResult,
  QuoteResult,
  Trace,
} from "./api";
import { Action, actionsApi } from "./actions";

const SAMPLE_RFQ =
  "Need a quote for 5,000 L of exterior weatherproof decorative paint for our EMEA distribution, net 30";

const eur = (n: number) =>
  new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(n);

const STATUS_LABEL: Record<string, string> = {
  proposed: "Proposed", approved: "Approved", executing: "Executing",
  executed: "Executed", rejected: "Rejected", failed: "Failed", escalated: "Escalated",
};

function ApStatusBadge({ status }: { status: string }) {
  return (
    <span className={`ap-badge ap-status-${status}`}>
      <span className="ap-dot" />
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

// The quote-agent's Actions surface: approving a quote ALSO stages + executes a
// governed quote_send action (email customer + CRM task) through the Action
// Plane, so the quote really goes out. This panel shows those dispatched actions
// with their status + external ref — Act → Approve → Execute → Confirm, audited.
function QuotesSentPanel({
  actions,
  lastDispatch,
}: {
  actions: Action[];
  lastDispatch: Dispatched | null;
}) {
  const sends = actions.filter((a) => a.action_type === "quote_send");
  return (
    <section className="card ap-panel">
      <div className="ap-panel-head">
        <h2>Quotes sent (Action Plane)</h2>
      </div>
      <p className="ap-empty-text">
        Approving a quote stages + executes a governed <strong>quote_send</strong>{" "}
        action — the customer email goes out and a CRM follow-up task is created,
        every send carrying an auditable external ref.
      </p>
      {lastDispatch && !lastDispatch.error && lastDispatch.external_ref && (
        <div className="ap-confirm">
          <span className="ap-confirm-tick">✓</span>
          Quote sent — action #{lastDispatch.action_id}, external ref{" "}
          <code className="ap-ref">{lastDispatch.external_ref}</code>
        </div>
      )}
      {lastDispatch?.error && (
        <div className="ap-confirm ap-confirm-fail">Dispatch issue: {lastDispatch.error}</div>
      )}
      {lastDispatch && lastDispatch.guardrail && !lastDispatch.guardrail.passed && (
        <div className="ap-confirm ap-confirm-fail">
          Guardrail breach — escalated instead of sending:{" "}
          {lastDispatch.guardrail.breaches.join("; ")}
        </div>
      )}
      {sends.length === 0 ? (
        <p className="muted">No quotes sent yet — approve a quote to send it.</p>
      ) : (
        <div className="ap-detail">
          {sends.slice(0, 8).map((a) => (
            <div key={a.id} className="ap-detail-row" style={{ gap: 10 }}>
              <ApStatusBadge status={a.status} />
              <span className="ap-id">#{a.id}</span>
              <span className="ap-subject" style={{ flex: 1 }}>{a.subject}</span>
              {a.external_ref && <code className="ap-ref">{a.external_ref}</code>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function TracePanel({ traces }: { traces: Trace[] }) {
  const [open, setOpen] = useState(false);
  if (traces.length === 0) return null;
  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} How this works — generated SQL, data sources &amp; the Lakebase write
      </button>
      {open && (
        <div className="trace-body">
          {traces.map((t, i) => (
            <div key={i} className="trace-step">
              <div className="trace-step-head">
                <span className={`badge badge-${t.step}`}>{t.step}</span>
                <span className="trace-source">{t.data_source}</span>
              </div>
              {t.sql.map((s, j) => (
                <pre key={j} className="sql">
                  {s}
                </pre>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [rfq, setRfq] = useState(SAMPLE_RFQ);
  const [parsed, setParsed] = useState<ParseResult | null>(null);
  const [priced, setPriced] = useState<PriceResult | null>(null);
  const [discount, setDiscount] = useState(10);
  const [qty, setQty] = useState<number>(5000);
  const [account, setAccount] = useState("ACME-EMEA");
  const [quoteResult, setQuoteResult] = useState<QuoteResult | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [approver, setApprover] = useState("controller@akzo.example");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sentActions, setSentActions] = useState<Action[]>([]);
  const [lastDispatch, setLastDispatch] = useState<Dispatched | null>(null);

  async function loadSentActions() {
    try {
      setSentActions(await actionsApi.list());
    } catch {
      /* ignore on initial load */
    }
  }

  const traces: Trace[] = [
    parsed?.trace,
    priced?.trace,
    quoteResult?.trace,
  ].filter(Boolean) as Trace[];

  async function loadApprovals() {
    try {
      setApprovals(await api.approvals());
    } catch (e) {
      /* ignore on initial load */
    }
  }

  useEffect(() => {
    loadApprovals();
    loadSentActions();
  }, []);

  function run<T>(label: string, fn: () => Promise<T>, onOk: (v: T) => void) {
    setBusy(label);
    setError(null);
    fn()
      .then(onOk)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  }

  function onParse() {
    setPriced(null);
    setQuoteResult(null);
    run("parse", () => api.parse(rfq), (p) => {
      setParsed(p);
      if (p.fields.quantity_litres) setQty(p.fields.quantity_litres);
      if (p.fields.customer) setAccount(p.fields.customer);
    });
  }

  function onPrice() {
    if (!parsed?.matched) return;
    run(
      "price",
      () => api.price(parsed.matched!.sku, parsed.matched!.region),
      setPriced
    );
  }

  function onQuote() {
    if (!priced) return;
    run(
      "quote",
      () =>
        api.quote({
          account_id: account,
          sku: priced.sku,
          region: priced.region,
          quantity_units: qty,
          list_price_eur: priced.list_price_eur,
          standard_cost_eur: priced.standard_cost_eur,
          discount_pct: discount,
        }),
      (q) => {
        setQuoteResult(q);
        loadApprovals();
      }
    );
  }

  function onDecide(id: number, decision: "approved" | "rejected") {
    setLastDispatch(null);
    run(
      "decide",
      () => api.decide(id, decision, approver),
      (r) => {
        // On approval the quote actually goes out: the backend stages + executes
        // a governed quote_send action (email + CRM task). Surface its result.
        if (r.dispatched) setLastDispatch(r.dispatched);
        loadApprovals();
        loadSentActions();
      }
    );
  }

  // Live client-side preview of the draft as the discount slider moves.
  const preview: Draft | null = priced
    ? (() => {
        const net = +(priced.list_price_eur * (1 - discount / 100)).toFixed(2);
        const unitMargin = +(net - priced.standard_cost_eur).toFixed(2);
        const marginPct = net ? +((unitMargin / net) * 100).toFixed(1) : 0;
        return {
          quantity_units: qty,
          list_price_eur: priced.list_price_eur,
          discount_pct: discount,
          net_unit_price_eur: net,
          extended_price_eur: +(net * qty).toFixed(2),
          standard_cost_eur: priced.standard_cost_eur,
          total_cost_eur: +(priced.standard_cost_eur * qty).toFixed(2),
          unit_margin_eur: unitMargin,
          margin_pct: marginPct,
          total_margin_eur: +(unitMargin * qty).toFixed(2),
          guardrail_flags: [
            ...(discount > 15 ? [`Discount ${discount}% exceeds the 15% policy limit.`] : []),
            ...(marginPct < 25 ? [`Post-discount margin ${marginPct}% is below the 25% floor.`] : []),
          ],
          requires_escalation: discount > 15 || marginPct < 25,
        };
      })()
    : null;

  return (
    <div className="app">
      <header>
        <h1>Pricing &amp; Quote Agent</h1>
        <p className="sub">
          AkzoNobel coatings · read → reason → act → write → approve · governed Unity Catalog data +
          Lakebase write-back
        </p>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      <div className="grid">
        <main>
          {/* STEP 1 — RFQ */}
          <section className="card">
            <h2>1 · Inbound RFQ</h2>
            <textarea value={rfq} onChange={(e) => setRfq(e.target.value)} rows={4} />
            <button className="primary" onClick={onParse} disabled={busy === "parse"}>
              {busy === "parse" ? "Parsing…" : "Parse RFQ (ai_extract)"}
            </button>
          </section>

          {/* STEP 2 — Parsed fields */}
          {parsed && (
            <section className="card">
              <h2>2 · Parsed fields</h2>
              <dl className="fields">
                <div><dt>Customer</dt><dd>{parsed.fields.customer ?? "—"}</dd></div>
                <div><dt>Product (text)</dt><dd>{parsed.fields.product ?? "—"}</dd></div>
                <div><dt>Region</dt><dd>{parsed.fields.region ?? "—"}</dd></div>
                <div><dt>Quantity</dt><dd>{parsed.fields.quantity_litres ?? "—"} L</dd></div>
                <div><dt>Terms</dt><dd>{parsed.fields.requested_terms ?? "—"}</dd></div>
              </dl>
              {parsed.matched ? (
                <div className="matched">
                  Matched to SKU <strong>{parsed.matched.sku}</strong> —{" "}
                  {parsed.matched.product_name} ({parsed.matched.product_line},{" "}
                  {parsed.matched.region})
                  <button className="primary" onClick={onPrice} disabled={busy === "price"}>
                    {busy === "price" ? "Pricing…" : "Look up pricing"}
                  </button>
                </div>
              ) : (
                <div className="warn">No SKU matched — refine the RFQ product text.</div>
              )}
            </section>
          )}

          {/* STEP 3 — Pricing basis */}
          {priced && (
            <section className="card">
              <h2>3 · Pricing basis</h2>
              <dl className="fields">
                <div><dt>List price</dt><dd>{eur(priced.list_price_eur)}</dd></div>
                <div><dt>Standard cost</dt><dd>{eur(priced.standard_cost_eur)}</dd></div>
                <div><dt>Unit margin</dt><dd>{eur(priced.unit_margin_eur)} ({priced.unit_margin_pct}%)</dd></div>
                {priced.recent_realized && (
                  <>
                    <div><dt>Recent realized price</dt><dd>{priced.recent_realized.realized_price_eur != null ? eur(priced.recent_realized.realized_price_eur) : "—"}</dd></div>
                    <div><dt>Recent realized margin</dt><dd>{priced.recent_realized.realized_margin_pct ?? "—"}% ({priced.recent_realized.month?.slice(0, 7)})</dd></div>
                  </>
                )}
              </dl>
            </section>
          )}

          {/* STEP 4 — Draft */}
          {priced && preview && (
            <section className="card">
              <h2>4 · Draft quote</h2>
              <div className="controls">
                <label>
                  Quantity (units)
                  <input type="number" value={qty} onChange={(e) => setQty(+e.target.value)} />
                </label>
                <label>
                  Account
                  <input value={account} onChange={(e) => setAccount(e.target.value)} />
                </label>
                <label>
                  Discount: <strong>{discount}%</strong>
                  <input
                    type="range"
                    min={0}
                    max={30}
                    value={discount}
                    onChange={(e) => setDiscount(+e.target.value)}
                  />
                </label>
              </div>
              <dl className="fields">
                <div><dt>Net unit price</dt><dd>{eur(preview.net_unit_price_eur)}</dd></div>
                <div><dt>Extended price</dt><dd>{eur(preview.extended_price_eur)}</dd></div>
                <div><dt>Margin %</dt><dd>{preview.margin_pct}%</dd></div>
                <div><dt>Total margin</dt><dd>{eur(preview.total_margin_eur)}</dd></div>
              </dl>
              {preview.guardrail_flags.length > 0 && (
                <div className="warn">
                  ⚠ Guardrail: {preview.guardrail_flags.join(" ")} — will be staged for escalation.
                </div>
              )}
              <button className="primary" onClick={onQuote} disabled={busy === "quote"}>
                {busy === "quote" ? "Writing to Lakebase…" : "Submit quote → Lakebase"}
              </button>
            </section>
          )}

          {quoteResult && (
            <section className="card success">
              ✓ Quote <strong>#{quoteResult.quote_id}</strong> written to Lakebase as{" "}
              <strong>{quoteResult.status}</strong>. See the Approval Queue →
            </section>
          )}

          <QuotesSentPanel actions={sentActions} lastDispatch={lastDispatch} />

          <TracePanel traces={traces} />
        </main>

        {/* APPROVAL QUEUE */}
        <aside className="card queue">
          <h2>Approval Queue</h2>
          <label className="approver">
            Approver
            <input value={approver} onChange={(e) => setApprover(e.target.value)} />
          </label>
          {approvals.length === 0 && <p className="muted">No pending quotes.</p>}
          {approvals.map((a) => (
            <div key={a.quote_id} className="qrow">
              <div className="qrow-head">
                <strong>#{a.quote_id}</strong> · {a.sku} · {a.region}
              </div>
              <div className="qrow-body">
                {a.account_id} · {a.quantity_units} units @ {eur(a.quoted_price_eur)} ({a.discount_pct}% off)
              </div>
              <div className="qrow-rationale">{a.rationale}</div>
              <div className="qrow-actions">
                <button className="approve" onClick={() => onDecide(a.quote_id, "approved")}>
                  Approve
                </button>
                <button className="reject" onClick={() => onDecide(a.quote_id, "rejected")}>
                  Reject
                </button>
              </div>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
