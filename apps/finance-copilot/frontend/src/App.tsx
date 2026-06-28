import { useEffect, useMemo, useState } from "react";
import {
  api,
  AskResult,
  Bridge,
  SavedRow,
  Trace,
  VarianceResult,
} from "./api";
import { ActionsPanel } from "./ActionsPanel";
import { ActBody } from "./actions";

// Map a margin-variance result to a default governed action. If price was the
// dominant drag on margin, the recovery move is a price_change (price-recovery);
// otherwise nudge the plan with a forecast_override.
function defaultActionFor(v: VarianceResult): ActBody {
  const d = v.bridge.drivers;
  const priceDrag = d.price.delta_pp;
  const region = v.region;
  if (priceDrag <= d.volume.delta_pp && priceDrag < 0) {
    return {
      action_type: "price_change",
      subject: `Price recovery — ${v.product_line} ${region} (${v.from_period}→${v.to_period})`,
      region,
      level: 2,
      payload: {
        account: `${v.product_line} ${region}`,
        product_line: v.product_line,
        region,
        // Price-recovery move, not a discount: keep discount_pct at 0 so the
        // guardrail's discount cap reads "in policy" while we restore price.
        discount_pct: 0,
        price_recovery_pp: Math.abs(priceDrag),
        summary: v.recommended_action,
        task: v.recommended_action,
      },
    };
  }
  return {
    action_type: "forecast_override",
    subject: `Forecast override — ${v.product_line} ${region} (${v.from_period}→${v.to_period})`,
    region,
    level: 2,
    payload: {
      product_line: v.product_line,
      region,
      message: v.recommended_action,
      summary: v.recommended_action,
      total_delta_pp: v.bridge.total_delta_pp,
    },
  };
}

const PRODUCT_LINES = ["Decorative Paints", "Performance Coatings"];
const REGIONS = ["EMEA", "Americas", "APAC", "China"];
const PERIODS = ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"];

const SAMPLE_Q = "Why did Paints EMEA gross margin drop in Q2 2026?";

const pp = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}pp`;
const pct = (n: number) => `${n.toFixed(1)}%`;

const DRIVER_LABEL: Record<string, string> = {
  price: "Price",
  volume: "Volume",
  fx: "FX",
  cost: "Cost (raw material)",
};

function TracePanel({ traces }: { traces: Trace[] }) {
  const [open, setOpen] = useState(false);
  if (traces.length === 0) return null;
  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} How this works — generated SQL, certified metric view &amp;
        source tables
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

// Waterfall-style bridge: starting margin %, four driver steps, ending margin %.
function Waterfall({ bridge }: { bridge: Bridge }) {
  const order: (keyof Bridge["drivers"])[] = ["price", "cost", "fx", "volume"];
  const steps = [
    { label: bridge.from_margin_pct.toFixed(1) + "%", kind: "start", value: bridge.from_margin_pct },
    ...order.map((k) => ({
      label: DRIVER_LABEL[k],
      kind: "driver" as const,
      value: bridge.drivers[k].delta_pp,
    })),
    { label: bridge.to_margin_pct.toFixed(1) + "%", kind: "end", value: bridge.to_margin_pct },
  ];

  // Track the running cumulative margin so each driver bar floats at the right height.
  const maxMargin = Math.max(bridge.from_margin_pct, bridge.to_margin_pct, 1);
  const H = 200;
  const scale = (v: number) => (v / maxMargin) * (H - 40);

  let running = bridge.from_margin_pct;
  const positioned = steps.map((s) => {
    if (s.kind === "start" || s.kind === "end") {
      const top = H - scale(s.value);
      return { ...s, top, height: scale(s.value), floatLabel: pct(s.value) };
    }
    const before = running;
    running += s.value;
    const lo = Math.min(before, running);
    const hi = Math.max(before, running);
    return {
      ...s,
      top: H - scale(hi),
      height: Math.max(scale(hi) - scale(lo), 2),
      floatLabel: pp(s.value),
    };
  });

  return (
    <div className="waterfall">
      <div className="bars" style={{ height: H }}>
        {positioned.map((s, i) => (
          <div key={i} className="bar-col">
            <div className="bar-float" style={{ top: Math.max(s.top - 18, 0) }}>
              {s.floatLabel}
            </div>
            <div
              className={`bar bar-${s.kind} ${
                s.kind === "driver" && s.value < 0 ? "bar-neg" : "bar-pos"
              }`}
              style={{ top: s.top, height: s.height }}
            />
            <div className="bar-label">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VarianceView({ result }: { result: VarianceResult }) {
  const { bridge } = result;
  const order: (keyof Bridge["drivers"])[] = ["price", "cost", "fx", "volume"];
  return (
    <>
      <div className="headline">
        {result.product_line} · {result.region}: gross margin{" "}
        <strong>{pct(bridge.from_margin_pct)}</strong> ({result.from_period}) →{" "}
        <strong>{pct(bridge.to_margin_pct)}</strong> ({result.to_period}) ={" "}
        <strong className={bridge.total_delta_pp < 0 ? "neg" : "pos"}>
          {pp(bridge.total_delta_pp)}
        </strong>
      </div>

      <Waterfall bridge={bridge} />

      <table className="bridge-table">
        <thead>
          <tr>
            <th>Driver</th>
            <th>Margin impact</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {order.map((k) => (
            <tr key={k}>
              <td>{DRIVER_LABEL[k]}</td>
              <td className={bridge.drivers[k].delta_pp < 0 ? "neg" : "pos"}>
                {pp(bridge.drivers[k].delta_pp)}
              </td>
              <td className="detail">{bridge.drivers[k].detail}</td>
            </tr>
          ))}
          <tr className="total-row">
            <td>Total</td>
            <td className={bridge.total_delta_pp < 0 ? "neg" : "pos"}>
              {pp(bridge.total_delta_pp)}
            </td>
            <td className="detail">sum of the four legs = observed margin-% change</td>
          </tr>
        </tbody>
      </table>

      {result.narrative && (
        <div className="narrative">
          <h3>Variance narrative</h3>
          <p>{result.narrative}</p>
        </div>
      )}
      {result.recommended_action && (
        <div className="action">
          <h3>Recommended action</h3>
          <p>{result.recommended_action}</p>
        </div>
      )}
    </>
  );
}

export default function App() {
  const [mode, setMode] = useState<"variance" | "ask">("variance");

  // variance form
  const [productLine, setProductLine] = useState("Decorative Paints");
  const [region, setRegion] = useState("EMEA");
  const [fromPeriod, setFromPeriod] = useState("2026-Q1");
  const [toPeriod, setToPeriod] = useState("2026-Q2");
  const [variance, setVariance] = useState<VarianceResult | null>(null);

  // ask form
  const [question, setQuestion] = useState(SAMPLE_Q);
  const [askResult, setAskResult] = useState<AskResult | null>(null);

  const [saved, setSaved] = useState<SavedRow[]>([]);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const traces: Trace[] = useMemo(
    () => [variance?.trace, askResult?.trace].filter(Boolean) as Trace[],
    [variance, askResult]
  );

  async function loadSaved() {
    try {
      setSaved(await api.saved());
    } catch {
      /* ignore on initial load */
    }
  }
  useEffect(() => {
    loadSaved();
  }, []);

  function run<T>(label: string, fn: () => Promise<T>, onOk: (v: T) => void) {
    setBusy(label);
    setError(null);
    setSavedMsg(null);
    fn()
      .then(onOk)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  }

  function onVariance() {
    setVariance(null);
    run(
      "variance",
      () =>
        api.variance({
          product_line: productLine,
          region,
          from_period: fromPeriod,
          to_period: toPeriod,
        }),
      setVariance
    );
  }

  function onAsk() {
    setAskResult(null);
    run("ask", () => api.ask(question), setAskResult);
  }

  function onSaveVariance() {
    if (!variance) return;
    const title = `${variance.product_line} · ${variance.region} · ${variance.from_period}→${variance.to_period}`;
    run(
      "save",
      () =>
        api.save({
          kind: "variance",
          title,
          summary: `${variance.bridge.from_margin_pct}% → ${variance.bridge.to_margin_pct}% (${pp(
            variance.bridge.total_delta_pp
          )}). ${variance.recommended_action}`,
          payload: variance,
          product_line: variance.product_line,
          region: variance.region,
          from_period: variance.from_period,
          to_period: variance.to_period,
        }),
      (r) => {
        setSavedMsg(`Saved analysis #${r.analysis_id} to Lakebase.`);
        loadSaved();
      }
    );
  }

  function onSaveAsk() {
    if (!askResult) return;
    run(
      "save",
      () =>
        api.save({
          kind: "ask",
          title: question.slice(0, 80),
          summary: askResult.answer.slice(0, 280),
          payload: askResult,
          question,
        }),
      (r) => {
        setSavedMsg(`Saved analysis #${r.analysis_id} to Lakebase.`);
        loadSaved();
      }
    );
  }

  return (
    <div className="app">
      <header>
        <h1>Finance Controlling Copilot</h1>
        <p className="sub">
          AkzoNobel coatings · gross-margin variance decomposition (price / volume / FX / cost) ·
          governed Unity Catalog data + certified metric view · Lakebase write-back
        </p>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      <div className="grid">
        <main>
          <div className="tabs">
            <button
              className={mode === "variance" ? "tab active" : "tab"}
              onClick={() => setMode("variance")}
            >
              Variance analysis
            </button>
            <button
              className={mode === "ask" ? "tab active" : "tab"}
              onClick={() => setMode("ask")}
            >
              Ask a question
            </button>
          </div>

          {mode === "variance" && (
            <section className="card">
              <h2>Run a variance analysis</h2>
              <div className="controls">
                <label>
                  Product line
                  <select value={productLine} onChange={(e) => setProductLine(e.target.value)}>
                    {PRODUCT_LINES.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Region
                  <select value={region} onChange={(e) => setRegion(e.target.value)}>
                    {REGIONS.map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </label>
                <label>
                  From
                  <select value={fromPeriod} onChange={(e) => setFromPeriod(e.target.value)}>
                    {PERIODS.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </label>
                <label>
                  To
                  <select value={toPeriod} onChange={(e) => setToPeriod(e.target.value)}>
                    {PERIODS.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </label>
              </div>
              <button className="primary" onClick={onVariance} disabled={busy === "variance"}>
                {busy === "variance" ? "Decomposing…" : "Decompose margin variance"}
              </button>
            </section>
          )}

          {mode === "ask" && (
            <section className="card">
              <h2>Ask the finance copilot</h2>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={3}
              />
              <button className="primary" onClick={onAsk} disabled={busy === "ask"}>
                {busy === "ask" ? "Thinking…" : "Ask (text2SQL → reasoning)"}
              </button>
            </section>
          )}

          {mode === "variance" && variance && (
            <section className="card">
              <h2>Margin bridge</h2>
              <VarianceView result={variance} />
              <button className="secondary" onClick={onSaveVariance} disabled={busy === "save"}>
                {busy === "save" ? "Saving…" : "Save analysis → Lakebase"}
              </button>
            </section>
          )}

          {mode === "variance" && variance && (
            <ActionsPanel
              defaultAction={defaultActionFor(variance)}
              title="Act on this variance"
              hint="Turn the recovery recommendation into a governed action — staged for approval, then executed (mock) into the connected systems."
            />
          )}

          {mode === "ask" && askResult && (
            <section className="card">
              <h2>Answer</h2>
              <p className="answer">{askResult.answer}</p>
              {askResult.rows.length > 0 && (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {askResult.columns.map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {askResult.rows.slice(0, 12).map((r, i) => (
                        <tr key={i}>
                          {askResult.columns.map((c) => (
                            <td key={c}>{String(r[c] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <button className="secondary" onClick={onSaveAsk} disabled={busy === "save"}>
                {busy === "save" ? "Saving…" : "Save analysis → Lakebase"}
              </button>
            </section>
          )}

          {savedMsg && <div className="card success">✓ {savedMsg}</div>}

          <TracePanel traces={traces} />
        </main>

        <aside className="card queue">
          <h2>Saved analyses</h2>
          {saved.length === 0 && <p className="muted">No saved analyses yet.</p>}
          {saved.map((s) => (
            <div key={s.analysis_id} className="qrow">
              <div className="qrow-head">
                <span className={`badge badge-${s.kind === "variance" ? "write" : "ask"}`}>
                  {s.kind}
                </span>{" "}
                <strong>#{s.analysis_id}</strong> {s.title}
              </div>
              {s.summary && <div className="qrow-rationale">{s.summary}</div>}
              <div className="qrow-body">
                {s.created_by} · {s.created_at?.slice(0, 19).replace("T", " ")}
              </div>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
