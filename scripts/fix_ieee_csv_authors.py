"""IEEE gold cleanup: null the Authors column in merged-FINAL.csv for the
163 rows tagged `disjoint_names_gold_likely_wrong` by the iter-1 gold audit.

Audit verification (2026-05-29, posted to #project-parseland): a deterministic
30-row sample from the 163-row pool was re-fetched via Taxicab+R2 and
re-parsed with `IEEE(soup).parse()`. Token-overlap between parser authors
and gold authors:
  - 26/30 confirmed wrong (0% overlap)
  - 4/30 likely wrong (11-21% overlap from coincidental single-letter
    initials only)
  - 0/30 format-mismatch (none of the "wrong" rows were actually right
    just in a different format)
  - 0/30 false positives

All 163 rows are real wrong-paper cases — gold's Authors cell describes
the authors of a different paper than what the DOI resolves to. Setting
those Authors cells to `N/A` (the existing null-token convention) excludes
them from author/affs F1 averaging without losing the row's usable signal
on PDF / abstract / corresp scoring.

This script mutates the source-of-truth CSV directly per the new
"gold source-fix decision" rule for *factually wrong* gold (not just
non-canonical). Wiley iter-1's "keep CSV pristine" pattern applies to
canonicalization choices; this one is a data correction.

Run:

    cd parseland-lib
    /opt/homebrew/bin/python3.11 scripts/fix_ieee_csv_authors.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CSV_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv"
)
AUDIT_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/ieee-iter1-gold-audit.json"
)

NULL_TOKEN = "N/A"
TARGET_VERDICT = "disjoint_names_gold_likely_wrong"


def main() -> int:
    if not AUDIT_PATH.exists():
        print(f"ERROR: audit file not found at {AUDIT_PATH}", file=sys.stderr)
        return 1
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}", file=sys.stderr)
        return 1

    # Load target DOIs from the audit
    audit = json.loads(AUDIT_PATH.read_text())
    target_dois = {
        (r.get("doi") or "").strip().lower()
        for r in audit.get("rows", [])
        if r.get("verdict") == TARGET_VERDICT
    }
    target_dois.discard("")
    print(f"audit: {len(target_dois)} DOIs tagged {TARGET_VERDICT!r}")

    rows_out: list[dict] = []
    fieldnames: list[str] = []
    rewrote = 0
    target_seen: set[str] = set()
    target_skipped_already_null = 0

    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if "DOI" not in fieldnames or "Authors" not in fieldnames:
            print(
                f"ERROR: CSV missing required columns. "
                f"Got: {fieldnames!r}",
                file=sys.stderr,
            )
            return 1

        for row in reader:
            doi = (row.get("DOI") or "").strip().lower()
            if doi and doi in target_dois:
                target_seen.add(doi)
                current = (row.get("Authors") or "").strip()
                if current.lower() in {"", "n/a", "na", "-", "none", "null"}:
                    target_skipped_already_null += 1
                else:
                    row["Authors"] = NULL_TOKEN
                    rewrote += 1
            rows_out.append(row)

    missing = target_dois - target_seen
    if missing:
        print(
            f"WARNING: {len(missing)} target DOIs were not found in CSV "
            f"(audit DOI not present in merged-FINAL.csv). Showing first 5:"
        )
        for d in list(missing)[:5]:
            print(f"  {d}")

    # Atomic write
    tmp = CSV_PATH.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    tmp.replace(CSV_PATH)

    print(f"\nwrote {len(rows_out)} rows to {CSV_PATH}")
    print(f"  target DOIs in CSV:                {len(target_seen)} / {len(target_dois)}")
    print(f"  Authors column rewrote -> {NULL_TOKEN}: {rewrote}")
    print(f"  already null, no change:            {target_skipped_already_null}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
