import { useCallback, useEffect, useState } from "react";
import type { Action, ActionDetail, Ladder, Status } from "./api";
import { api } from "./api";
import { STATUS_META } from "./format";
import { LadderMeter } from "./components/LadderMeter";
import { ActionTable } from "./components/ActionTable";
import { DetailPanel } from "./components/DetailPanel";

const STATUS_FILTERS = Object.keys(STATUS_META) as Status[];

export default function App() {
  const [ladder, setLadder] = useState<Ladder | null>(null);
  const [actions, setActions] = useState<Action[] | null>(null);
  const [identity, setIdentity] = useState<string>("");
  const [approver, setApprover] = useState<string>("");

  const [statusFilter, setStatusFilter] = useState<Status | "">("");
  const [levelFilter, setLevelFilter] = useState<number | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ActionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [lad, list] = await Promise.all([
        api.ladder(),
        api.actions({
          status: statusFilter || undefined,
          level: levelFilter ?? undefined,
        }),
      ]);
      setLadder(lad);
      setActions(list.actions);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, levelFilter]);

  // Load identity once (seeds the approver field).
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setIdentity(h.identity);
        setApprover((a) => a || h.identity);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    refresh();
  }, [refresh]);

  // Load detail when selection changes.
  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    api
      .action(selectedId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // After an act, refresh the queue + ladder and keep the panel in sync.
  const onChanged = useCallback(
    (d: ActionDetail) => {
      setDetail(d);
      refresh();
    },
    [refresh]
  );

  const filtersActive = statusFilter !== "" || levelFilter != null;

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Action Center</h1>
          <p className="sub">Every agent action — recommended, staged, executed, autonomous — governed and audited on one plane.</p>
        </div>
        {identity && (
          <div className="identity-chip" title="Workspace identity">
            <span className="identity-dot" />
            {identity}
          </div>
        )}
      </header>

      {error && <div className="error banner">{error}</div>}

      <section className="ladder-section">
        <LadderMeter ladder={ladder} activeLevel={levelFilter} onPick={setLevelFilter} />
      </section>

      <div className={`layout${selectedId != null ? " with-detail" : ""}`}>
        <main>
          <div className="queue-bar">
            <div className="queue-title">
              <h2>Action queue</h2>
              {actions && <span className="count-pill">{actions.length}</span>}
            </div>
            <div className="filters">
              <label className="field">
                <span>Status</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as Status | "")}
                >
                  <option value="">All</option>
                  {STATUS_FILTERS.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Level</span>
                <select
                  value={levelFilter ?? ""}
                  onChange={(e) =>
                    setLevelFilter(e.target.value === "" ? null : Number(e.target.value))
                  }
                >
                  <option value="">All</option>
                  {[1, 2, 3, 4].map((l) => (
                    <option key={l} value={l}>
                      L{l}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field approver-field">
                <span>Acting as</span>
                <input
                  value={approver}
                  onChange={(e) => setApprover(e.target.value)}
                  placeholder="approver@akzonobel.com"
                />
              </label>
            </div>
          </div>

          {loading ? (
            <div className="state-card">
              <span className="spinner" /> Loading actions…
            </div>
          ) : actions && actions.length > 0 ? (
            <div className="table-wrap">
              <ActionTable actions={actions} selectedId={selectedId} onSelect={setSelectedId} />
            </div>
          ) : (
            <div className="state-card empty">
              <p className="empty-title">
                {filtersActive ? "No actions match these filters" : "No actions yet"}
              </p>
              <p className="muted">
                {filtersActive
                  ? "Clear the status/level filters to see the full queue."
                  : "Agents will stage actions here as they recommend, approve, and execute."}
              </p>
              {filtersActive && (
                <button
                  className="ghost"
                  onClick={() => {
                    setStatusFilter("");
                    setLevelFilter(null);
                  }}
                >
                  Clear filters
                </button>
              )}
            </div>
          )}
        </main>

        {selectedId != null && (
          <div className="detail-wrap">
            {detailLoading && !detail ? (
              <aside className="detail">
                <div className="state-card">
                  <span className="spinner" /> Loading detail…
                </div>
              </aside>
            ) : detail ? (
              <DetailPanel
                detail={detail}
                approver={approver}
                onClose={() => setSelectedId(null)}
                onChanged={onChanged}
              />
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
