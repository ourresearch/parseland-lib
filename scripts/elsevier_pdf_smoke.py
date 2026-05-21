"""Quick smoke: run the patched parse_in_process on 5 of the missing-PDF DOIs
and verify it now produces pdf_urls. No scoring, just a yes/no per DOI.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

# Re-use the patched function
from scripts.elsevier_inprocess_diff import parse_in_process  # noqa: E402

ITER2 = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-iter2-after.json")

DOIS = [
    "10.1016/s0140-6736(00)44689-1",
    "10.1016/j.pain.2012.11.015",
    "10.1016/j.cell.2012.09.023",
    "10.1016/j.isci.2025.111875",
    "10.1016/j.jaci.2011.03.034",
]


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


def main():
    iter2 = json.loads(ITER2.read_text())
    uuids = {r["doi"]: r["harvest_uuid"] for r in iter2["scored_rows"]}
    s3 = _make_r2_client()
    for doi in DOIS:
        uuid = uuids.get(doi)
        try:
            html = get_landing_page_from_r2(uuid, s3)
        except Exception as e:  # noqa: BLE001
            print(f"  {doi}  R2 ERR: {e}")
            continue
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="ignore")
        out = parse_in_process(html)
        urls = out.get("urls") or []
        pdf = next((u["url"] for u in urls if u.get("content_type") == "pdf"), None)
        ft_err = out.get("_fulltext_error")
        if pdf:
            print(f"  PDF  {doi}\n        -> {pdf}")
        elif ft_err:
            print(f"  ERR  {doi}  {ft_err}")
        else:
            print(f"  MISS {doi}  (no pdf_url)")


if __name__ == "__main__":
    main()
