"""Convert Wolters Kluwer / Lippincott rows of merged-FINAL.csv into NDJSON.

Mirrors build_taylor_gold_ndjson.py. Selects rows whose DOI starts with a
Lippincott Williams & Wilkins (Wolters Kluwer Health) registrant prefix. The
Lippincott parser's own host check (fires on journals.lww.com canonicals,
#ejp-article-authors, or an ASA citation publisher) handles stragglers whose
Link resolves elsewhere.

Prefixes included (all verified host_organization_name = "Lippincott Williams
& Wilkins" on the live OpenAlex API, 2026-06-02):
    10.1097 — LWW core registrant
    10.1161 — AHA journals (Circulation family), published by LWW
    10.1212 — Neurology, published by LWW
    10.1213 — Anesthesia & Analgesia, published by LWW

Excluded by design:
    10.4103 — Medknow (Wolters Kluwer imprint, but a SEPARATE parser
              medknow.py). Baseline Medknow on its own slice; mixing it here
              would conflate two parsers under one F1.

Source:    parseland-eval/eval/data/merged-FINAL.csv  (read-only)
Sink:      parseland-lib/tests/fixtures/wolters-kluwer-gold.ndjson

Per-row output shape matches the Wiley/Springer/Taylor gold NDJSONs so the
same scoring tools consume it.
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
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/wolters-kluwer-gold.ndjson"
)

WK_DOI_PREFIXES = ("10.1097", "10.1161", "10.1212", "10.1213")

_NULL_TOKENS = {"", "n/a", "na", "-", "none", "null"}


def _clean(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if value.lower() in _NULL_TOKENS:
        return None
    return value


def _to_bool(raw: str) -> bool:
    value = (raw or "").strip().lower()
    return value in {"true", "1", "yes", "y"}


def _parse_authors(raw: str) -> list[dict] | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return None
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

    seen_dois: set[str] = set()
    rows: list[dict] = []
    skipped_no_number = 0
    skipped_not_match = 0
    per_prefix: dict[str, int] = {p: 0 for p in WK_DOI_PREFIXES}
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = (row.get("DOI") or "").strip().lower()
            matched = next(
                (p for p in WK_DOI_PREFIXES if doi.startswith(p)), None
            )
            if matched is None:
                skipped_not_match += 1
                continue
            if not (row.get("No") or "").strip():
                skipped_no_number += 1
                continue
            if doi in seen_dois:
                continue
            seen_dois.add(doi)
            rows.append(_row_to_ndjson(row))
            per_prefix[matched] += 1

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")

    per_prefix_str = ", ".join(f"{p}={n}" for p, n in per_prefix.items())
    print(
        f"wrote {len(rows)} Wolters Kluwer / Lippincott rows to {OUTPUT_PATH} "
        f"({per_prefix_str}; skipped: {skipped_no_number} missing-No, "
        f"{skipped_not_match} non-WK)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
