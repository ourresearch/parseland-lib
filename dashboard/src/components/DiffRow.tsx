import type { RowPayload } from "../lib/schema";
import { pct, shortDoi, truncate } from "../lib/format";

interface Props {
  row: RowPayload;
}

function authorNames(authors: Array<{ name?: string }>): string {
  return authors
    .map((a) => (typeof a === "object" && a ? (a as { name?: string }).name ?? "" : ""))
    .filter(Boolean)
    .join(" · ");
}

export function DiffRow({ row }: Props) {
  const goldAuthors = authorNames(row.gold.authors as Array<{ name?: string }>);
  const parsedAuthors = authorNames(row.parsed.authors as Array<{ name?: string }>);
  const goldAbstract = row.gold.abstract ?? "";
  const parsedAbstract = row.parsed.abstract ?? "";

  const aScore = row.score.authors;
  const absScore = row.score.abstract;
  const pdfScore = row.score.pdf_url;

  return (
    <div className="diff-row">
      <div className="no">{row.no}</div>
      <div className="doi">
        <span className="publisher">{row.publisher_domain || "—"}</span>
        <span title={row.doi}>{shortDoi(row.doi)}</span>
        <div className="tags">
          {row.gold.has_bot_check && <span className="tag bot">bot</span>}
          {row.gold.status && <span className="tag ok">gold ok</span>}
          {row.gold.failure_modes.slice(0, 2).map((m) => (
            <span key={m} className="tag">
              {m.replace(/_/g, " ")}
            </span>
          ))}
          {row.error && <span className="tag bot">err</span>}
        </div>
      </div>
      <div className="col">
        <span className="col-head">Expected · authors / abstract</span>
        <span className={`content ${goldAuthors ? "" : "empty"}`}>
          {goldAuthors || "no authors in gold"}
        </span>
        <span className={`content ${goldAbstract ? "" : "empty"}`}>
          {truncate(goldAbstract, 260) || "no abstract"}
        </span>
      </div>
      <div className="col">
        <span className="col-head">Parsed · authors / abstract</span>
        <span className={`content ${parsedAuthors ? "" : "empty"}`}>
          {parsedAuthors || "parser returned no authors"}
        </span>
        <span className={`content ${parsedAbstract ? "" : "empty"}`}>
          {truncate(parsedAbstract, 260) || "parser returned no abstract"}
        </span>
      </div>
      <div className="scores">
        {aScore ? (
          <span className={aScore.f1_soft >= 0.9 ? "good" : aScore.f1_soft > 0 ? "" : "bad"}>
            authors {pct(aScore.f1_soft)}
          </span>
        ) : (
          <span className="faint">authors skip</span>
        )}
        <span
          className={
            absScore.fuzzy_ratio >= 0.85
              ? "good"
              : absScore.fuzzy_ratio > 0
              ? ""
              : "bad"
          }
        >
          abstract {pct(absScore.fuzzy_ratio)}
        </span>
        <span className={pdfScore.strict_match ? "good" : pdfScore.expected_present ? "bad" : ""}>
          pdf {pdfScore.strict_match ? "✓" : pdfScore.expected_present ? "✗" : "—"}
        </span>
      </div>
    </div>
  );
}
