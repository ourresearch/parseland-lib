"""Convert the Elsevier rows of human-goldie.csv into NDJSON.

The output shape parallels the OpenAlex baseline NDJSON shards in
parseland-eval/eval/data/openalex-baseline/shards/, so the same downstream
diff tooling can score against either dataset.

Source:    parseland-eval/eval/human-goldie.csv  (read-only; lives in parseland-eval)
Filter:    rows whose DOI starts with "10.1016" (Elsevier registrant)
Sink:      parseland-lib/tests/fixtures/elsevier-gold.ndjson

Per-row output shape:

    {
      "doi": "10.1016/...",
      "source": "human-goldie",
      "captured_at": null,                       # CSV has no annotation timestamp
      "annotation": {
        "no": 7,
        "link": "https://doi.org/10.1016/...",
        "resolved_links": "https://www.cell.com/...",
        "authors": [                              # list of {name, rasses, corresponding_author}
          {"name": "...", "rasses": "...", "corresponding_author": false}
        ],
        "abstract": "...",
        "pdf_url": "...",
        "status": "ok",
        "notes": "...",
        "has_bot_check": false,
        "resolves_to_pdf": false,
        "broken_doi": false,
        "no_english": false
      }
    }

The `rasses` field name on author dicts is intentional and matches the gold.py
quirks handler in parseland-eval. Do not rename it.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CSV_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/human-goldie.csv"
)
OUTPUT_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-gold.ndjson"
)

ELSEVIER_PREFIX = "10.1016"


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

    elsevier_rows: list[dict] = []
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = (row.get("DOI") or "").strip().lower()
            if not doi.startswith(ELSEVIER_PREFIX):
                continue
            if not (row.get("No") or "").strip():
                continue
            elsevier_rows.append(_row_to_ndjson(row))

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in elsevier_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    print(f"wrote {len(elsevier_rows)} Elsevier rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
