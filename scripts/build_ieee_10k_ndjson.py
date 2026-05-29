"""Convert the IEEE rows of merged-FINAL.csv into NDJSON.

Mirror of ``build_elsevier_10k_ndjson.py`` for the IEEE publisher slice. The
source CSV (parseland-eval/eval/data/merged-FINAL.csv, 10,000 rows) is the
union of the 10K eval set and the human-goldie hand-annotations. We filter to
DOI prefix ``10.1109`` (IEEE registrant) and emit one NDJSON row per article.

The output shape parallels the elsevier-10k-gold.ndjson shard so the same
downstream diff tooling (``ieee_inprocess_diff.py``) scores it identically.

Source:    parseland-eval/eval/data/merged-FINAL.csv  (read-only)
Filter:    rows whose DOI starts with "10.1109"
Sink:      parseland-lib/tests/fixtures/ieee-10k-gold.ndjson
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CSV_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv"
)
OUTPUT_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/ieee-10k-gold.ndjson"
)

IEEE_PREFIX = "10.1109"


_NULL_TOKENS = {"", "n/a", "na", "-", "none", "null"}


def _clean(raw: str | None) -> str | None:
    """Normalize spreadsheet null tokens to None; otherwise return stripped value."""
    if raw is None:
        return None
    value = raw.strip()
    if value.lower() in _NULL_TOKENS:
        return None
    return value


def _to_bool(raw: str) -> bool:
    """Spreadsheet booleans land as 'TRUE'/'FALSE'/'' strings; normalize."""
    value = (raw or "").strip().lower()
    return value in {"true", "1", "yes", "y"}


def _parse_authors(raw: str) -> list[dict] | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return parsed
    return None


def _row_to_ndjson(row: dict) -> dict:
    doi = (row.get("DOI") or "").strip()
    annotation = {
        "no": int((row.get("No") or "0").strip() or 0),
        "link": _clean(row.get("Link")),
        "resolved_links": _clean(row.get("resolved_links")),
        "authors": _parse_authors(row.get("Authors") or ""),
        "abstract": _clean(row.get("Abstract")),
        "pdf_url": _clean(row.get("PDF URL")),
        "status": _clean(row.get("Status")),
        "notes": _clean(row.get("Notes")),
        "has_bot_check": _to_bool(row.get("Has Bot Check") or ""),
        "resolves_to_pdf": _to_bool(row.get("Resolves To PDF") or ""),
        "broken_doi": _to_bool(row.get("broken_doi") or ""),
        "no_english": _to_bool(row.get("no english") or ""),
    }
    return {
        "doi": doi,
        "source": "human-goldie",
        "captured_at": None,
        "annotation": annotation,
    }


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: source CSV not found at {CSV_PATH}", file=sys.stderr)
        return 1
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ieee_rows: list[dict] = []
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = (row.get("DOI") or "").strip().lower()
            if not doi.startswith(IEEE_PREFIX):
                continue
            if not (row.get("No") or "").strip():
                continue
            ieee_rows.append(_row_to_ndjson(row))

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in ieee_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    print(f"wrote {len(ieee_rows)} IEEE rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
