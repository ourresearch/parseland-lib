import { useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { RowPayload } from "../lib/schema";
import { DiffRow } from "./DiffRow";

interface Props {
  rows: RowPayload[];
}

type FieldFilter = "all" | "authors_fail" | "abstract_fail" | "pdf_fail" | "errors";

export function DiffTable({ rows }: Props) {
  const [publisher, setPublisher] = useState<string>("all");
  const [failure, setFailure] = useState<string>("all");
  const [field, setField] = useState<FieldFilter>("all");
  const [query, setQuery] = useState("");

  const publishers = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((r) => r.publisher_domain && set.add(r.publisher_domain));
    return Array.from(set).sort();
  }, [rows]);

  const failureModes = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((r) => r.gold.failure_modes.forEach((m) => set.add(m)));
    return Array.from(set).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (publisher !== "all" && r.publisher_domain !== publisher) return false;
      if (failure !== "all" && !r.gold.failure_modes.includes(failure)) return false;
      if (field === "authors_fail" && (r.score.authors?.f1_soft ?? 1) >= 0.9) return false;
      if (field === "abstract_fail" && r.score.abstract.fuzzy_ratio >= 0.85) return false;
      if (field === "pdf_fail" && !(r.score.pdf_url.expected_present && !r.score.pdf_url.strict_match)) return false;
      if (field === "errors" && !r.error) return false;
      if (q && !r.doi.toLowerCase().includes(q) && !r.publisher_domain.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [rows, publisher, failure, field, query]);

  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirt = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 180,
    overscan: 6,
  });

  return (
    <div>
      <div className="diff-controls">
        <input
          type="search"
          placeholder="Filter by DOI or publisher…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search DOI or publisher"
        />
        <select value={publisher} onChange={(e) => setPublisher(e.target.value)} aria-label="Publisher filter">
          <option value="all">All publishers ({publishers.length})</option>
          {publishers.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select value={failure} onChange={(e) => setFailure(e.target.value)} aria-label="Failure-mode filter">
          <option value="all">All failure modes</option>
          {failureModes.map((m) => (
            <option key={m} value={m}>
              {m.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select value={field} onChange={(e) => setField(e.target.value as FieldFilter)} aria-label="Field filter">
          <option value="all">All rows</option>
          <option value="authors_fail">Authors &lt; 90%</option>
          <option value="abstract_fail">Abstract &lt; 85%</option>
          <option value="pdf_fail">PDF mismatch</option>
          <option value="errors">Parser errors</option>
        </select>
        <span className="mono muted" style={{ marginLeft: "auto" }}>
          {filtered.length} / {rows.length}
        </span>
      </div>

      <div className="diff-table-wrap" ref={parentRef} style={{ maxHeight: "70vh", overflow: "auto" }}>
        <div style={{ height: `${rowVirt.getTotalSize()}px`, position: "relative" }}>
          {rowVirt.getVirtualItems().map((v) => {
            const row = filtered[v.index];
            return (
              <div
                key={v.key}
                data-index={v.index}
                ref={rowVirt.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${v.start}px)`,
                }}
              >
                <DiffRow row={row} />
              </div>
            );
          })}
        </div>
        {filtered.length === 0 && <p className="empty-state">No rows match current filters.</p>}
      </div>
    </div>
  );
}
