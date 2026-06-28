import { useState } from "react";
import { api, AskResult, DomainLeg } from "./api";
import { ActionsPanel } from "./ActionsPanel";
import { ActBody } from "./actions";

// Map the supervisor's fused recommendation to a default governed action.
// If SCM was consulted, the next-best-action is a supply reroute; otherwise a
// CRM follow-up task captures the recommendation against the account.
function defaultActionFor(result: AskResult): ActBody {
  const domains = result.routing.map((r) => r.domain);
  // The flagship story is EMEA Paints; the seeded action_policies scope these
  // action types to EMEA, so default the action's region there.
  const region = "EMEA";
  const subject = (result.recommended_action || "Act on the supervisor recommendation").slice(0, 160);
  if (domains.includes("SCM")) {
    return {
      action_type: "scm_reroute",
      subject,
      region,
      level: 2,
      payload: {
        summary: result.recommended_action,
        message: result.recommended_action,
        task: result.recommended_action,
        account: "EMEA Paints supply",
        question: result.question,
      },
    };
  }
  return {
    action_type: "crm_task",
    subject,
    region,
    level: 2,
    payload: {
      task: result.recommended_action,
      summary: result.recommended_action,
      account: "EMEA Paints",
      question: result.question,
    },
  };
}

const FLAGSHIP =
  "Paints EMEA gross margin dropped ~8% in Q2 — is it price, volume, or a supply/service issue, and what should I do?";

const SAMPLES = [
  FLAGSHIP,
  "Connect the dots: is the EMEA churn risk related to the margin and service problems we are seeing?",
  "Give me one EMEA Paints situation report covering financial impact, supply status, and customer risk.",
  "Which domains did you consult to answer the EMEA margin question, and what did each contribute?",
];

const PERSONAS = [
  { id: "controller", label: "Group Controller" },
  { id: "emea_planner", label: "EMEA Supply Planner" },
  { id: "rep", label: "Account Rep" },
];

const DOMAIN_COLORS: Record<string, string> = {
  FINANCE: "badge-finance",
  SCM: "badge-scm",
  COMMERCIAL: "badge-commercial",
};

function LegResult({ leg }: { leg: DomainLeg }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="leg">
      <div className="leg-head">
        <span className={`badge ${DOMAIN_COLORS[leg.domain] ?? ""}`}>{leg.domain}</span>
        <span className="leg-meta">
          {leg.error ? <span className="leg-err">error: {leg.error}</span> : `${leg.row_count} rows`}
        </span>
        <button className="leg-toggle" onClick={() => setOpen((o) => !o)}>
          {open ? "▾ hide SQL + rows" : "▸ show SQL + rows"}
        </button>
      </div>
      {open && (
        <div className="leg-body">
          {leg.sql && <pre className="sql">{leg.sql}</pre>}
          {leg.rows.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {leg.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leg.rows.map((r, i) => (
                    <tr key={i}>
                      {leg.columns.map((c) => (
                        <td key={c}>{String(r[c] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState(FLAGSHIP);
  const [persona, setPersona] = useState("controller");
  const [result, setResult] = useState<AskResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<string | null>(null);
  const [note, setNote] = useState("");

  function onAsk() {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setFeedbackSent(null);
    api
      .ask(question, persona)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }

  function onFeedback(rating: number) {
    if (!result) return;
    api
      .feedback(result.session_uuid, rating, note || undefined)
      .then(() => setFeedbackSent(rating > 0 ? "👍 Thanks — recorded." : "👎 Thanks — recorded."))
      .catch((e) => setError(e.message));
  }

  return (
    <div className="app">
      <header>
        <h1>Multi-domain Supervisor Agent</h1>
        <p className="sub">
          AkzoNobel · one chat, routed across Finance / SCM / Commercial Genie spaces · governed per
          user (OBO) · fused into one answer with a visible routing trace
        </p>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      <section className="card">
        <div className="ask-controls">
          <label className="persona">
            Persona
            <select value={persona} onChange={(e) => setPersona(e.target.value)}>
              {PERSONAS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <span className="persona-hint">
            Persona sets the governed data scope — OBO enforces it at each Genie call (reads).
          </span>
        </div>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="Ask a cross-domain question…"
        />
        <div className="samples">
          {SAMPLES.map((s, i) => (
            <button key={i} className="chip" onClick={() => setQuestion(s)}>
              {i === 0 ? "★ Flagship" : `Example ${i + 1}`}
            </button>
          ))}
        </div>
        <button className="primary" onClick={onAsk} disabled={busy}>
          {busy ? "Routing → calling legs → fusing…" : "Ask the Supervisor"}
        </button>
      </section>

      {result && (
        <>
          {/* (a) ROUTING DECISION — the visible trace */}
          <section className="card">
            <h2>Routing decision</h2>
            <p className="scope">{result.persona_scope}</p>
            <div className="routing">
              {result.routing.map((r) => (
                <div key={r.domain} className="route">
                  <span className={`badge ${DOMAIN_COLORS[r.domain] ?? ""}`}>{r.domain}</span>
                  <span className="route-reason">{r.reason}</span>
                </div>
              ))}
            </div>
          </section>

          {/* (b) PER-DOMAIN RESULTS */}
          <section className="card">
            <h2>Domain legs</h2>
            {result.legs.map((leg) => (
              <LegResult key={leg.domain} leg={leg} />
            ))}
          </section>

          {/* (c) FUSED ANSWER + RECOMMENDED ACTION */}
          <section className="card answer-card">
            <h2>Fused answer</h2>
            <p className="answer">{result.answer}</p>
            {result.recommended_action && (
              <div className="action">
                <span className="action-label">Recommended action</span>
                <p>{result.recommended_action}</p>
              </div>
            )}

            {/* (e) FEEDBACK */}
            <div className="feedback">
              {feedbackSent ? (
                <span className="feedback-done">{feedbackSent}</span>
              ) : (
                <>
                  <input
                    className="note"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Optional note…"
                  />
                  <button className="thumb up" onClick={() => onFeedback(1)}>
                    👍
                  </button>
                  <button className="thumb down" onClick={() => onFeedback(-1)}>
                    👎
                  </button>
                </>
              )}
            </div>
            <p className="muted session">
              session #{result.session_id} · logged to Lakebase akzo.agent_sessions
            </p>
          </section>

          {/* (d) ACTIONS — turn the recommendation into a governed action */}
          <ActionsPanel
            defaultAction={defaultActionFor(result)}
            title="Act on this"
            hint="Stage the recommended next-best-action through the governed Action Plane — approve, then execute into the connected systems."
          />
        </>
      )}
    </div>
  );
}
