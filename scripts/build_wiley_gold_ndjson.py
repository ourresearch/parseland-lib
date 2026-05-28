"""Convert Wiley rows of merged-FINAL.csv into NDJSON.

Mirrors build_springer_gold_ndjson.py exactly, but selects rows whose DOI
starts with a Wiley/Blackwell registrant prefix. The parser's own host
check (Wiley parser fires on onlinelibrary.wiley.com canonicals) handles
any stragglers whose Link resolves elsewhere.

Prefixes included:
    10.1002 — Wiley primary registrant
    10.1111 — legacy Blackwell, merged into Wiley in 2007

Excluded by design (low row count, weaker Wiley signal):
    10.1046, 10.1034 — older Blackwell prefixes (~14 rows combined)

Source:    parseland-eval/eval/data/merged-FINAL.csv  (read-only)
Sink:      parseland-lib/tests/fixtures/wiley-gold.ndjson

Per-row output shape matches the Springer/Elsevier gold NDJSONs so the
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
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/wiley-gold.ndjson"
)

WILEY_DOI_PREFIXES = ("10.1002", "10.1111")


_NULL_TOKENS = {"", "n/a", "na", "-", "none", "null"}

# Wiley publishes two URL forms for the same article PDF:
#   /doi/pdf/<doi>          → HTML viewer page with PDF embedded
#   /doi/pdfdirect/<doi>    → raw PDF bytes (what downstream consumers want)
# The parseland-lib parser deliberately rewrites the page's `citation_pdf_url`
# (which Wiley emits as the viewer form) to the direct-download form because
# downstream Unpaywall harvesters need raw bytes. Gold annotators wrote down
# what their browser showed when they clicked "PDF" — the viewer URL. To make
# the derived NDJSON match what the parser emits, canonicalize at build time.
# The source CSV (merged-FINAL.csv) is left as raw human annotation.
_VIEWER_PREFIX = "onlinelibrary.wiley.com/doi/pdf/"
_DIRECT_PREFIX = "onlinelibrary.wiley.com/doi/pdfdirect/"


def _clean(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if value.lower() in _NULL_TOKENS:
        return None
    return value


def _canonicalize_pdf_url(pdf: str | None) -> str | None:
    """Rewrite Wiley viewer URLs to the direct-download form. Idempotent —
    URLs already in pdfdirect form or epdf form pass through unchanged."""
    if not pdf:
        return pdf
    if _VIEWER_PREFIX in pdf and _DIRECT_PREFIX not in pdf:
        return pdf.replace(_VIEWER_PREFIX, _DIRECT_PREFIX, 1)
    return pdf


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
        "pdf_url": _canonicalize_pdf_url(_clean(row.get("PDF URL"))),
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
    skipped_not_wiley = 0
    per_prefix: dict[str, int] = {p: 0 for p in WILEY_DOI_PREFIXES}
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = (row.get("DOI") or "").strip().lower()
            matched = next((p for p in WILEY_DOI_PREFIXES if doi.startswith(p)), None)
            if matched is None:
                skipped_not_wiley += 1
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
        f"wrote {len(rows)} Wiley rows to {OUTPUT_PATH} "
        f"({per_prefix_str}; skipped: {skipped_no_number} missing-No, "
        f"{skipped_not_wiley} non-Wiley)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
