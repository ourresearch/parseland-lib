import type { Overall } from "../lib/schema";
import { pct } from "../lib/format";
import { DeltaBadge } from "./DeltaBadge";

interface Props {
  current: Overall;
  previous: Overall | null;
}

export function Scorecard({ current, previous }: Props) {
  const stats = [
    {
      kicker: "Authors · F1 (soft)",
      value: pct(current.authors_f1_soft),
      strict: pct(current.authors_f1_strict),
      rows: current.authors_scored_rows,
      delta: {
        current: current.authors_f1_soft,
        previous: previous?.authors_f1_soft ?? null,
      },
      subtitle: `Strict: ${pct(current.authors_f1_strict)}  ·  ${current.authors_scored_rows} scored`,
    },
    {
      kicker: "Affiliations · F1 (fuzzy)",
      value: pct(current.affiliations_f1_fuzzy),
      strict: pct(current.affiliations_f1_strict),
      rows: current.rows,
      delta: {
        current: current.affiliations_f1_fuzzy,
        previous: previous?.affiliations_f1_fuzzy ?? null,
      },
      subtitle: `Soft: ${pct(current.affiliations_f1_soft)}  ·  Strict: ${pct(current.affiliations_f1_strict)}`,
    },
    {
      kicker: "Abstract · Levenshtein",
      value: pct(current.abstract_ratio_fuzzy),
      strict: pct(current.abstract_strict_match_rate),
      rows: current.rows,
      delta: {
        current: current.abstract_ratio_fuzzy,
        previous: previous?.abstract_ratio_fuzzy ?? null,
      },
      subtitle: `Present: ${pct(current.abstract_present_rate)}  ·  Exact: ${pct(current.abstract_strict_match_rate)}`,
    },
    {
      kicker: "PDF URL · accuracy",
      value: pct(current.pdf_url_accuracy),
      strict: pct(current.pdf_url_divergence_rate),
      rows: current.rows,
      delta: {
        current: current.pdf_url_accuracy,
        previous: previous?.pdf_url_accuracy ?? null,
      },
      subtitle: `Divergent: ${pct(current.pdf_url_divergence_rate)}  ·  Errors: ${current.errors}`,
    },
  ];

  return (
    <section aria-label="Top-line scorecard" className="scorecard">
      {stats.map((s) => (
        <div key={s.kicker} className="stat">
          <div className="kicker">{s.kicker}</div>
          <div className="value">
            {s.value.replace("%", "")}
            <span className="unit">%</span>
          </div>
          <div className="detail">
            <DeltaBadge current={s.delta.current} previous={s.delta.previous} />
            <span>{s.subtitle}</span>
          </div>
        </div>
      ))}
    </section>
  );
}
