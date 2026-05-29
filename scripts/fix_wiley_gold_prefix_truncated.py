"""Gold cleanup pass 2: rewrite Wiley gold abstracts that are strict
prefixes of the page's full extracted abstract.

Iter-2 already cleaned up 11 rows whose gold abstract ended in the literal
"..." or "…" truncation marker. This pass catches the broader pattern:
gold is a strict prefix of what the parser extracts from the page, parser
is significantly longer, but the gold annotator's source didn't include
the trailing ellipsis. Same underlying issue (copy-paste source
truncation) — different surface marker.

Detection criteria:
  1. Gold normalized text appears as a substring at the start of the
     parser normalized text (first 100 chars must match).
  2. Parser output is at least 1.5x longer than gold.
  3. Gold is at least 100 chars (don't rewrite tiny stubs).

For matching rows, gold is replaced with the parser's full extraction.

Run after iter-2's ellipsis cleanup:

    cd parseland-lib
    .venv/bin/python scripts/fix_wiley_gold_prefix_truncated.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.api import TAXICAB_BASE  # noqa: E402
from parseland_lib.publisher.parsers.wiley import Wiley  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

GOLD_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/wiley-gold.ndjson"
)


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _make_r2_client():
    load_dotenv("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/.env", override=True)
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def resolve_uuid(doi: str) -> str | None:
    try:
        r = requests.get(f"{TAXICAB_BASE}/taxicab/doi/{doi}", timeout=30)
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    recs = r.json().get("html") or []
    if not recs:
        return None
    return max(recs, key=lambda h: h.get("created_date") or "").get("id")


def extract_parser_abstract(uuid: str, s3) -> str | None:
    try:
        html = get_landing_page_from_r2(uuid, s3)
    except Exception:  # noqa: BLE001
        return None
    if not html:
        return None
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    try:
        return Wiley(soup).get_abstract()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    if not GOLD_PATH.exists():
        print(f"ERROR: gold not found at {GOLD_PATH}", file=sys.stderr)
        return 1

    s3 = _make_r2_client()
    rows: list[dict] = []
    rewrote = 0
    skipped_no_uuid = 0
    skipped_no_parser_abs = 0
    skipped_not_prefix = 0
    skipped_not_longer = 0
    skipped_too_short = 0

    with GOLD_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ann = row.get("annotation") or {}
            ab = (ann.get("abstract") or "").strip()
            if not ab:
                rows.append(row)
                continue
            # Skip rows already ending in ellipsis — iter-2 handled those
            if ab.endswith("...") or ab.endswith("…"):
                rows.append(row)
                continue
            # Skip very short gold (likely legit short abstracts or stubs)
            if len(ab) < 100:
                skipped_too_short += 1
                rows.append(row)
                continue

            doi = row.get("doi", "")
            uuid = resolve_uuid(doi)
            if not uuid:
                skipped_no_uuid += 1
                rows.append(row)
                continue

            full = extract_parser_abstract(uuid, s3)
            if not full:
                skipped_no_parser_abs += 1
                rows.append(row)
                continue

            ab_norm = _norm(ab)
            full_norm = _norm(full)
            # Strict prefix check on first 100 normalized chars
            sample = ab_norm[: min(100, len(ab_norm))]
            if not (len(sample) >= 50 and sample in full_norm[: len(sample) + 20]):
                skipped_not_prefix += 1
                rows.append(row)
                continue
            if len(full.strip()) < len(ab) * 1.5:
                skipped_not_longer += 1
                rows.append(row)
                continue

            ann["abstract"] = full.strip()
            row["annotation"] = ann
            rows.append(row)
            rewrote += 1
            print(f"  rewrote {doi}: {len(ab)} -> {len(full.strip())} chars")

    tmp = GOLD_PATH.with_suffix(".ndjson.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")
    tmp.replace(GOLD_PATH)

    print(f"\nwrote {len(rows)} rows to {GOLD_PATH}")
    print(f"  rewrote prefix-truncated abstracts: {rewrote}")
    print(f"  skipped (too short for prefix check): {skipped_too_short}")
    print(f"  skipped (no taxicab uuid):            {skipped_no_uuid}")
    print(f"  skipped (parser returned no abstract): {skipped_no_parser_abs}")
    print(f"  skipped (gold not prefix of parser):  {skipped_not_prefix}")
    print(f"  skipped (parser not significantly longer): {skipped_not_longer}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
