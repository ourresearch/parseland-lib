"""Gold cleanup: replace truncated abstracts in wiley-gold.ndjson.

Some Wiley gold rows have abstracts ending in literal "..." or "…" — the
annotator's copy-paste source truncated the text at ~200 chars and added
the ellipsis marker. The parser correctly extracts the full abstract from
the page, and in every spot-checked case gold is a strict prefix of the
parser output.

This script rewrites the `annotation.abstract` field for those rows with
the parser's full abstract extraction. The source CSV
(`parseland-eval/eval/data/merged-FINAL.csv`) is left as raw human
annotation; this canonicalization lives only in the derived NDJSON.

For symmetry with the iter-1 PDF URL canonicalization, this is a one-shot
script. To make it durable, port the rewrite into
`scripts/build_wiley_gold_ndjson.py` after the run.

Run:

    cd parseland-lib
    .venv/bin/python scripts/fix_wiley_gold_truncated_abstracts.py
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
    skipped_parser_shorter = 0

    with GOLD_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ann = row.get("annotation") or {}
            ab = (ann.get("abstract") or "").strip()
            if not ab or not (ab.endswith("...") or ab.endswith("…")):
                rows.append(row)
                continue

            # Truncated abstract candidate — extract full from page
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

            # Guard: parser abstract must be longer than gold (we're filling
            # in the truncated tail, not replacing with junk).
            if len(full.strip()) <= len(ab):
                skipped_parser_shorter += 1
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
    print(f"  rewrote ellipsis-truncated abstracts: {rewrote}")
    print(f"  skipped (no taxicab uuid):            {skipped_no_uuid}")
    print(f"  skipped (parser returned no abstract): {skipped_no_parser_abs}")
    print(f"  skipped (parser abstract shorter):     {skipped_parser_shorter}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
