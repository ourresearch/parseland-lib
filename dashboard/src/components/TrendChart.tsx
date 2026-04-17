import type { IndexEntry } from "../lib/schema";
import { pct } from "../lib/format";

interface Props {
  runs: IndexEntry[];
}

const METRICS = [
  { key: "authors_f1_soft", label: "Authors F1", stroke: "var(--accent)" },
  { key: "abstract_ratio_fuzzy", label: "Abstract ratio", stroke: "var(--amber)" },
  { key: "pdf_url_accuracy", label: "PDF accuracy", stroke: "var(--ok)" },
] as const;

export function TrendChart({ runs }: Props) {
  const ordered = [...runs].reverse();
  if (ordered.length < 2) {
    return (
      <p className="empty-state">
        Trend requires ≥ 2 runs. Currently {ordered.length}.
      </p>
    );
  }

  const W = 900;
  const H = 180;
  const padL = 44;
  const padR = 16;
  const padT = 16;
  const padB = 30;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const xFor = (i: number) => padL + (plotW * i) / Math.max(1, ordered.length - 1);
  const yFor = (v: number) => padT + plotH * (1 - Math.max(0, Math.min(1, v)));

  return (
    <div className="trend">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Score trend over runs">
        {/* y grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line
              x1={padL}
              x2={W - padR}
              y1={yFor(tick)}
              y2={yFor(tick)}
              stroke="var(--hairline-soft)"
              strokeWidth={1}
            />
            <text
              x={padL - 8}
              y={yFor(tick) + 4}
              textAnchor="end"
              fontSize={10}
              fill="var(--ink-faint)"
              fontFamily="var(--font-mono)"
            >
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        {/* lines */}
        {METRICS.map((metric) => {
          const pts = ordered.map((r, i) => {
            const v = (r.summary as Record<string, number | undefined>)[metric.key] ?? 0;
            return `${xFor(i)},${yFor(v)}`;
          });
          return (
            <g key={metric.key}>
              <polyline
                fill="none"
                stroke={metric.stroke}
                strokeWidth={2}
                points={pts.join(" ")}
                vectorEffect="non-scaling-stroke"
              />
              {ordered.map((r, i) => {
                const v = (r.summary as Record<string, number | undefined>)[metric.key] ?? 0;
                return (
                  <circle
                    key={i}
                    cx={xFor(i)}
                    cy={yFor(v)}
                    r={3}
                    fill="var(--paper-raised)"
                    stroke={metric.stroke}
                    strokeWidth={2}
                  >
                    <title>
                      {metric.label}: {pct(v)} · {r.label ?? r.run_id}
                    </title>
                  </circle>
                );
              })}
            </g>
          );
        })}
        {/* x labels */}
        {ordered.map((r, i) => (
          <text
            key={i}
            x={xFor(i)}
            y={H - 10}
            textAnchor="middle"
            fontSize={10}
            fill="var(--ink-faint)"
            fontFamily="var(--font-mono)"
          >
            {r.label ?? (r.run_id ?? "").slice(4, 9)}
          </text>
        ))}
      </svg>
      <div className="legend">
        {METRICS.map((m) => (
          <span key={m.key}>
            <span
              className="swatch"
              style={{
                display: "inline-block",
                width: 10,
                height: 2,
                background: m.stroke,
                marginRight: "0.5em",
                verticalAlign: "middle",
              }}
            />
            {m.label}
          </span>
        ))}
      </div>
    </div>
  );
}
