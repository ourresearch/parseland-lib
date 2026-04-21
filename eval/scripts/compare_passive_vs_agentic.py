"""Pilot diff — compare passive (Pass A) vs agentic (Pass B) extraction.

Reads the two extracted CSVs and their meta JSONs, classifies each DOI × field
as same / agentic_richer / passive_richer / both_empty / disagree, and writes
`eval/data/random-50-diff.csv` plus a printed summary.

Judgement rules per field:
- Text fields (Authors JSON, Abstract, PDF URL, Notes):
    both empty           → both_empty
    only A populated     → passive_richer
    only B populated     → agentic_richer
    both populated, same → same
    both populated, diff → disagree
- Boolean flag fields (Has Bot Check, Resolves To PDF, broken_doi, no english):
    both set, same value → same
    both set, different  → disagree
    one unset            → whichever is set is {richer}
    both unset           → both_empty
- Authors list length comparison is used as a richness tiebreaker when both are
  non-empty but textually different.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parseland_eval.paths import EVAL_DIR


PASSIVE_CSV = EVAL_DIR / "data" / "random-50-extracted.csv"
PASSIVE_META = EVAL_DIR / "data" / "random-50-extracted.meta.json"
AGENTIC_CSV = EVAL_DIR / "data" / "random-50-agentic.csv"
AGENTIC_META = EVAL_DIR / "data" / "random-50-agentic.meta.json"
OUTPUT_CSV = EVAL_DIR / "data" / "random-50-diff.csv"

TEXT_FIELDS = ["Authors", "Abstract", "PDF URL", "Notes"]
BOOL_FIELDS = ["Has Bot Check", "Resolves To PDF", "broken_doi", "no english"]
VERDICTS = ["same", "agentic_richer", "passive_richer", "both_empty", "disagree"]


def _norm_text(v: Any) -> str:
    return (v or "").strip()


def _parse_authors(raw: str) -> list[dict]:
    if not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _classify_text(a: str, b: str) -> str:
    a, b = _norm_text(a), _norm_text(b)
    if not a and not b:
        return "both_empty"
    if a and not b:
        return "passive_richer"
    if b and not a:
        return "agentic_richer"
    if a == b:
        return "same"
    return "disagree"


def _classify_authors(a_raw: str, b_raw: str) -> str:
    a, b = _parse_authors(a_raw), _parse_authors(b_raw)
    if not a and not b:
        return "both_empty"
    if a and not b:
        return "passive_richer"
    if b and not a:
        return "agentic_richer"
    # Both populated: richer = more authors OR more affiliations; else disagree/same.
    a_names = [x.get("name", "").strip() for x in a]
    b_names = [x.get("name", "").strip() for x in b]
    if a_names == b_names:
        a_affs = sum(len(x.get("affiliations") or []) for x in a)
        b_affs = sum(len(x.get("affiliations") or []) for x in b)
        if a_affs == b_affs:
            return "same"
        return "passive_richer" if a_affs > b_affs else "agentic_richer"
    if len(a_names) > len(b_names):
        return "passive_richer"
    if len(b_names) > len(a_names):
        return "agentic_richer"
    return "disagree"


def _classify_bool(a: str, b: str) -> str:
    a, b = _norm_text(a), _norm_text(b)
    if not a and not b:
        return "both_empty"
    if a and not b:
        return "passive_richer"
    if b and not a:
        return "agentic_richer"
    return "same" if a == b else "disagree"


@dataclass
class DiffRow:
    no: int
    doi: str
    field: str
    passive_value: str
    agentic_value: str
    verdict: str


def build_diff(passive: list[dict], agentic: list[dict]) -> list[DiffRow]:
    by_doi_a = {r["DOI"]: r for r in passive}
    by_doi_b = {r["DOI"]: r for r in agentic}
    all_dois = sorted(set(by_doi_a) | set(by_doi_b),
                      key=lambda d: int(by_doi_a.get(d, by_doi_b[d])["No"]))
    rows: list[DiffRow] = []
    for doi in all_dois:
        a = by_doi_a.get(doi) or {f: "" for f in TEXT_FIELDS + BOOL_FIELDS + ["No", "DOI"]}
        b = by_doi_b.get(doi) or {f: "" for f in TEXT_FIELDS + BOOL_FIELDS + ["No", "DOI"]}
        no = int(a.get("No") or b.get("No") or 0)
        for f in TEXT_FIELDS:
            if f == "Authors":
                v = _classify_authors(a.get(f, ""), b.get(f, ""))
            else:
                v = _classify_text(a.get(f, ""), b.get(f, ""))
            rows.append(DiffRow(no=no, doi=doi, field=f,
                                passive_value=_norm_text(a.get(f, ""))[:200],
                                agentic_value=_norm_text(b.get(f, ""))[:200],
                                verdict=v))
        for f in BOOL_FIELDS:
            v = _classify_bool(a.get(f, ""), b.get(f, ""))
            rows.append(DiffRow(no=no, doi=doi, field=f,
                                passive_value=_norm_text(a.get(f, "")),
                                agentic_value=_norm_text(b.get(f, "")),
                                verdict=v))
    return rows


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize(rows: list[DiffRow]) -> dict[str, dict[str, int]]:
    """Return {field: {verdict: count}}."""
    out: dict[str, Counter] = {}
    for r in rows:
        out.setdefault(r.field, Counter())[r.verdict] += 1
    return {f: dict(c) for f, c in out.items()}


def _print_summary(
    rows: list[DiffRow],
    passive_meta: dict,
    agentic_meta: dict,
) -> None:
    by_field = _summarize(rows)
    fields = TEXT_FIELDS + BOOL_FIELDS
    header = ["field"] + VERDICTS
    widths = [max(12, len(h)) for h in header]
    print(" | ".join(h.rjust(w) for h, w in zip(header, widths)))
    print("-+-".join("-" * w for w in widths))
    for f in fields:
        counts = by_field.get(f, {})
        cells = [f] + [str(counts.get(v, 0)) for v in VERDICTS]
        print(" | ".join(c.rjust(w) for c, w in zip(cells, widths)))

    pa_totals = (passive_meta.get("totals") or {})
    ag_totals = (agentic_meta.get("totals") or {})
    print()
    print(f"Pass A (passive):  rows={pa_totals.get('rows','?')}  "
          f"errors={pa_totals.get('errors','?')}  "
          f"cost=${pa_totals.get('cost_usd','?')}  "
          f"wall={pa_totals.get('wall_seconds','?')}s")
    print(f"Pass B (agentic):  rows={ag_totals.get('rows','?')}  "
          f"errors={ag_totals.get('errors','?')}  "
          f"cost=${ag_totals.get('cost_usd','?')}  "
          f"wall={ag_totals.get('wall_seconds','?')}s  "
          f"turns={ag_totals.get('total_turns','?')}  "
          f"tool_calls={ag_totals.get('tool_calls_by_name','?')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passive-csv", default=str(PASSIVE_CSV))
    ap.add_argument("--agentic-csv", default=str(AGENTIC_CSV))
    ap.add_argument("--output", default=str(OUTPUT_CSV))
    args = ap.parse_args()

    passive = _load_csv(Path(args.passive_csv))
    agentic = _load_csv(Path(args.agentic_csv))
    rows = build_diff(passive, agentic)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["no", "doi", "field",
                                               "passive_value",
                                               "agentic_value", "verdict"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r.__dict__)

    passive_meta = _load_meta(PASSIVE_META)
    agentic_meta = _load_meta(AGENTIC_META)
    _print_summary(rows, passive_meta, agentic_meta)
    print(f"\ndiff written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
