import type { PerFailureMode } from "../lib/schema";
import { failureColor } from "../lib/palette";
import { pct } from "../lib/format";

interface Props {
  data: PerFailureMode;
}

export function FailureModeBar({ data }: Props) {
  const entries = Object.entries(data).sort((a, b) => b[1].rows - a[1].rows);
  const total = entries.reduce((s, [, v]) => s + v.rows, 0);

  if (total === 0) return <p className="empty-state">No failure-mode data.</p>;

  return (
    <div>
      <div
        className="failure-bar"
        role="img"
        aria-label={`Failure-mode distribution across ${total} rows`}
      >
        {entries.map(([mode, stats]) => {
          const share = stats.rows / total;
          if (share === 0) return null;
          return (
            <div
              key={mode}
              style={{
                flex: `${stats.rows} 0 0`,
                background: failureColor(mode),
              }}
              title={`${mode}: ${stats.rows} rows (${pct(share)})  ·  Authors F1 ${pct(stats.authors_f1_soft)}`}
            >
              {share > 0.08 ? mode.replace("_", " ") : null}
            </div>
          );
        })}
      </div>
      <ul className="failure-legend" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {entries.map(([mode, stats]) => (
          <li key={mode}>
            <span className="swatch" style={{ background: failureColor(mode) }} />
            <span style={{ color: "var(--ink-soft)", marginRight: "0.5em" }}>
              {mode.replace(/_/g, " ")}
            </span>
            <span>
              {stats.rows}  ·  Authors {pct(stats.authors_f1_soft)}  ·  Abstract {pct(stats.abstract_ratio_fuzzy)}  ·  PDF {pct(stats.pdf_url_accuracy)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
