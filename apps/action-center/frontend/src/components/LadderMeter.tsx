import type { Ladder, Status } from "../api";
import { LADDER_LEVELS, STATUS_META } from "../format";

// The signature exec visual: the Action Maturity Ladder L1→L4 as four steps with
// live counts. The level filter highlights the active step.
export function LadderMeter({
  ladder,
  activeLevel,
  onPick,
}: {
  ladder: Ladder | null;
  activeLevel: number | null;
  onPick: (level: number | null) => void;
}) {
  const byLevel = new Map<number, Ladder["levels"][number]>();
  ladder?.levels.forEach((l) => byLevel.set(l.level, l));

  return (
    <div className="ladder" role="group" aria-label="Action maturity ladder">
      {LADDER_LEVELS.map((meta, i) => {
        const data = byLevel.get(meta.level);
        const total = data?.total ?? 0;
        const active = activeLevel === meta.level;
        // Order the status breakdown by the canonical status order.
        const statuses = (Object.keys(STATUS_META) as Status[]).filter(
          (s) => (data?.by_status?.[s] ?? 0) > 0
        );
        return (
          <div className="ladder-step-wrap" key={meta.level}>
            <button
              type="button"
              className={`ladder-step${active ? " active" : ""}${total === 0 ? " empty" : ""}`}
              onClick={() => onPick(active ? null : meta.level)}
              aria-pressed={active}
              title={
                active
                  ? "Clear level filter"
                  : `Filter queue to level ${meta.level}`
              }
            >
              <div className="ladder-step-head">
                <span className="ladder-num">L{meta.level}</span>
                <span className="ladder-count">{total}</span>
              </div>
              <div className="ladder-name">{meta.name}</div>
              <div className="ladder-blurb">{meta.blurb}</div>
              <div className="ladder-bar">
                {statuses.map((s) => {
                  const c = data!.by_status[s] ?? 0;
                  return (
                    <span
                      key={s}
                      className="ladder-seg"
                      style={{
                        flexGrow: c,
                        background: STATUS_META[s].color,
                      }}
                      title={`${STATUS_META[s].label}: ${c}`}
                    />
                  );
                })}
                {total === 0 && <span className="ladder-seg empty" />}
              </div>
            </button>
            {i < LADDER_LEVELS.length - 1 && <span className="ladder-arrow" aria-hidden>→</span>}
          </div>
        );
      })}
    </div>
  );
}
