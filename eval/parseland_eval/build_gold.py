"""Build gold-standard.json from gold-standard.csv.

The CSV has an embedded-JSON Authors column; csv.DictReader handles it fine.
Row 101 is an empty trailing row from Google Sheets export — dropped.
The Authors JSON is re-emitted as a real list so downstream loaders don't
need to json.loads a string inside a string.
"""
from __future__ import annotations

import csv
import json
import sys

from parseland_eval.paths import GOLD_CSV, GOLD_JSON


KEEP_COLUMNS = (
    "No", "DOI", "Link", "Authors", "Abstract", "PDF URL",
    "Status", "Notes", "Has Bot Check", "Resolves To PDF",
    "broken_doi", "no english",
)


def _parse_authors(raw: str) -> object:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def build() -> list[dict]:
    with GOLD_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: list[dict] = []
        for row in reader:
            no_raw = (row.get("No") or "").strip()
            if not no_raw:
                continue
            out = {k: (row.get(k) or "").strip() for k in KEEP_COLUMNS if k != "Authors"}
            out["Authors"] = _parse_authors(row.get("Authors") or "")
            rows.append(out)
    return rows


def main() -> int:
    rows = build()
    GOLD_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} rows to {GOLD_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
