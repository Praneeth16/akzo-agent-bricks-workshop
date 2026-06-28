import { useState } from "react";
import type { Action } from "../api";
import { formatTs, humanize } from "../format";
import { StatusBadge } from "./StatusBadge";

type SortKey = "id" | "status" | "agent" | "action_type" | "level" | "region" | "created_at";

const COLUMNS: { key: SortKey; label: string; className?: string }[] = [
  { key: "status", label: "Status" },
  { key: "agent", label: "Agent" },
  { key: "action_type", label: "Type" },
  { key: "level", label: "Level", className: "num" },
  { key: "region", label: "Region" },
  { key: "created_at", label: "Created", className: "num" },
];

// Dense queue table: sortable headers, hover highlight, sticky header, status badge
// column. Subject gets its own full-width primary cell per row.
export function ActionTable({
  actions,
  selectedId,
  onSelect,
}: {
  actions: Action[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({
    key: "created_at",
    dir: -1,
  });

  const sorted = [...actions].sort((a, b) => {
    const av = a[sort.key];
    const bv = b[sort.key];
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return -1 * sort.dir;
    if (av > bv) return 1 * sort.dir;
    return 0;
  });

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: 1 }));

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th className="th-subject">Action</th>
          {COLUMNS.map((c) => (
            <th
              key={c.key}
              className={`sortable ${c.className ?? ""}`}
              onClick={() => toggleSort(c.key)}
            >
              {c.label}
              <span className="sort-caret">
                {sort.key === c.key ? (sort.dir === 1 ? "▲" : "▼") : ""}
              </span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((a) => (
          <tr
            key={a.id}
            className={a.id === selectedId ? "selected" : ""}
            onClick={() => onSelect(a.id)}
          >
            <td className="td-subject">
              <span className="subject-text">{a.subject}</span>
              <span className="subject-id">#{a.id}</span>
            </td>
            <td>
              <StatusBadge status={a.status} />
            </td>
            <td>{humanize(a.agent)}</td>
            <td className="td-type">{humanize(a.action_type)}</td>
            <td className="num">
              <span className="level-pill">L{a.level}</span>
            </td>
            <td>{a.region}</td>
            <td className="num td-ts">{formatTs(a.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
