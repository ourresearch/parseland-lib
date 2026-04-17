import type { IndexEntry } from "../lib/schema";
import { formatTimestamp } from "../lib/format";

interface Props {
  runs: IndexEntry[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function RunSelector({ runs, selectedId, onSelect }: Props) {
  if (runs.length === 0) return null;
  const current = selectedId ?? runs[0].run_id ?? "";
  return (
    <label className="mono muted" style={{ display: "inline-flex", alignItems: "center", gap: "0.5em" }}>
      <span>RUN</span>
      <select
        value={current}
        onChange={(e) => onSelect(e.target.value)}
        style={{
          font: "inherit",
          fontFamily: "var(--font-mono)",
          background: "var(--paper-raised)",
          color: "var(--ink)",
          border: "1px solid var(--hairline)",
          borderRadius: "var(--radius-sm)",
          padding: "0.25em 0.5em",
        }}
      >
        {runs.map((r) => (
          <option key={r.file} value={r.run_id ?? r.file}>
            {(r.label ? `${r.label} · ` : "") + formatTimestamp(r.timestamp_utc)}
          </option>
        ))}
      </select>
    </label>
  );
}
