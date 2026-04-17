import type { PerPublisher } from "../lib/schema";
import { heatColor, heatTextColor } from "../lib/palette";
import { pct } from "../lib/format";

interface Props {
  data: PerPublisher;
  minRows?: number;
}

const FIELDS: Array<{ key: keyof PerPublisher[string]; label: string }> = [
  { key: "authors_f1_soft", label: "Authors" },
  { key: "affiliations_f1_fuzzy", label: "Affiliations" },
  { key: "abstract_ratio_fuzzy", label: "Abstract" },
  { key: "pdf_url_accuracy", label: "PDF URL" },
];

export function PublisherHeatmap({ data, minRows = 2 }: Props) {
  const rows = Object.entries(data)
    .filter(([, stats]) => stats.rows >= minRows)
    .sort((a, b) => b[1].rows - a[1].rows)
    .slice(0, 18);

  if (rows.length === 0) {
    return <p className="empty-state">No publishers with ≥ {minRows} gold-standard rows.</p>;
  }

  return (
    <div className="heatmap card">
      <table>
        <thead>
          <tr>
            <th style={{ width: "30%" }}>Publisher domain</th>
            {FIELDS.map((f) => (
              <th key={f.label} style={{ textAlign: "center" }}>
                {f.label}
              </th>
            ))}
            <th style={{ textAlign: "right", paddingRight: "var(--space-3)" }}>N</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([domain, stats]) => (
            <tr key={domain}>
              <td className="label">{domain || "—"}</td>
              {FIELDS.map((f) => {
                const v = (stats[f.key] as number) ?? 0;
                return (
                  <td
                    key={f.label}
                    className="cell"
                    style={{ background: heatColor(v), color: heatTextColor(v) }}
                    title={`${domain} · ${f.label} · ${pct(v)}`}
                  >
                    {pct(v)}
                  </td>
                );
              })}
              <td
                style={{
                  textAlign: "right",
                  fontFamily: "var(--font-mono)",
                  color: "var(--ink-muted)",
                  paddingRight: "var(--space-3)",
                  fontSize: "var(--text-micro)",
                }}
              >
                {stats.rows}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
