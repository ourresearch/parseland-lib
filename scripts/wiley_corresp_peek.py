"""Pull HTML for a handful of Wiley corresp FP/FN rows and print the
loa-authors fragment plus the parser's per-author corresp decision.

Argv: DOI [DOI ...]
"""
from __future__ import annotations
import sys, os, json
from pathlib import Path
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3, requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from parseland_eval.api import TAXICAB_BASE
from parseland_lib.publisher.parsers.wiley import Wiley
from parseland_lib.s3 import get_landing_page_from_r2


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
    r = requests.get(f"{TAXICAB_BASE}/taxicab/doi/{doi}", timeout=30)
    if r.status_code != 200:
        return None
    recs = r.json().get("html") or []
    if not recs:
        return None
    return max(recs, key=lambda h: h.get("created_date") or "").get("id")


def peek(doi: str, s3) -> None:
    uuid = resolve_uuid(doi)
    if not uuid:
        print(f"\n##### {doi}  — no taxicab record")
        return
    html = get_landing_page_from_r2(uuid, s3)
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    parser = Wiley(soup)
    print(f"\n##### {doi}  uuid={uuid}")
    print(f"  is_publisher_specific: {parser.is_publisher_specific_parser()}")
    print(f"  authors_found:         {bool(parser.authors_found())}")

    author_soup = soup.find("div", class_="loa-authors")
    if not author_soup:
        print("  (no .loa-authors div)")
        return
    authors = author_soup.findAll("span", class_="accordion__closed")
    print(f"  n authors in loa: {len(authors)}")
    for i, a in enumerate(authors):
        name_el = a.a
        name = name_el.text.strip() if name_el else "??"
        author_type = a.find("p", class_="author-type")
        at_text = (author_type.text.strip() if author_type else "")
        mailto = a.select_one('a[href*=mailto]')
        ps = a.findAll("p", class_=None)
        print(f"  [{i}] {name!r}")
        print(f"      author-type     : {at_text!r}")
        print(f"      mailto present  : {bool(mailto)}  href={(mailto.get('href') if mailto else '')!r}")
        print(f"      n p.class=None  : {len(ps)}")
        for j, p in enumerate(ps[:4]):
            txt = p.text.strip().replace("\n", " ")
            print(f"        p[{j}]: {txt[:200]!r}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: wiley_corresp_peek.py DOI [DOI ...]")
        return 1
    s3 = _make_r2_client()
    for doi in sys.argv[1:]:
        peek(doi, s3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
