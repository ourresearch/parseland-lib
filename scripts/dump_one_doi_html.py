"""Dump a single DOI's HTML from R2 (via harvest_uuid in iter2-after.json)
plus the relevant slices (author-group, dl.affiliation blocks, and the
__PRELOADED_STATE__ JSON) for offline inspection. Usage:

    .venv/bin/python scripts/dump_one_doi_html.py 10.1016/j.mtener.2023.101453
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

ITER2 = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-iter2-after.json")
OUT_DIR = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts-out/doi-dumps")


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
    doi = sys.argv[1] if len(sys.argv) > 1 else "10.1016/j.mtener.2023.101453"
    iter2 = json.loads(ITER2.read_text())
    uuids = {r["doi"]: r["harvest_uuid"] for r in iter2["scored_rows"]}
    uuid = uuids.get(doi)
    if not uuid:
        print(f"no uuid for {doi}")
        sys.exit(1)

    s3 = _make_r2_client()
    html = get_landing_page_from_r2(uuid, s3)
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = doi.replace("/", "_")
    full = OUT_DIR / f"{slug}.html"
    full.write_text(html)
    print(f"wrote {full}  ({len(html):,} chars)")

    soup = BeautifulSoup(html, "lxml")

    # author-group block
    ag = soup.find("div", class_="author-group")
    print("\n=== <div class='author-group'> ===")
    if ag:
        ag_str = str(ag)
        print(f"len: {len(ag_str)}  (saving first 8K to ag.html)")
        (OUT_DIR / f"{slug}_author-group.html").write_text(ag_str)
        print(ag_str[:4000])
    else:
        print("NOT FOUND")

    # dl.affiliation blocks
    print("\n=== <dl class='affiliation'> blocks ===")
    dls = soup.find_all("dl", class_="affiliation")
    print(f"count: {len(dls)}")
    for i, dl in enumerate(dls[:15]):
        dt = dl.find("dt")
        dd = dl.find("dd")
        label = dt.get_text(strip=True) if dt else "<no dt>"
        text = dd.get_text(" ", strip=True) if dd else "<no dd>"
        print(f"  [{i}] dt='{label}'  dd='{text[:120]}'")

    # __PRELOADED_STATE__
    print("\n=== __PRELOADED_STATE__ ===")
    found = False
    for script in soup.find_all("script"):
        text = script.string or script.text or ""
        if "__PRELOADED_STATE__" not in text:
            continue
        m = re.search(r"__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?\s*$", text, re.DOTALL)
        if not m:
            print("  found __PRELOADED_STATE__ marker but regex didn't match")
            continue
        try:
            data = json.loads(m.group(1))
        except Exception as e:
            print(f"  json parse error: {e}")
            continue
        found = True
        authors_node = data.get("authors") or {}
        print(f"  authors keys: {list(authors_node.keys())[:10]}")
        if "affiliations" in authors_node:
            print(f"  authors.affiliations keys: {list(authors_node['affiliations'].keys())[:10]}")
            for k, v in list(authors_node["affiliations"].items())[:5]:
                # get textfn
                tfn = None
                for c in v.get("$$") or []:
                    if isinstance(c, dict) and c.get("#name") == "textfn":
                        tfn = c.get("_")
                        break
                print(f"    {k}: textfn={tfn!r}")
        # authors.content surnames + cross-refs
        content = authors_node.get("content") or []
        for i, grp in enumerate(content[:1]):
            for entry in (grp.get("$$") or [])[:6]:
                if entry.get("#name") != "author":
                    continue
                surname = None
                refids = []
                for child in entry.get("$$") or []:
                    if child.get("#name") == "surname":
                        surname = child.get("_")
                    elif child.get("#name") == "cross-ref":
                        refids.append((child.get("$") or {}).get("refid"))
                print(f"  author: {surname!r}  refids={refids}")
        # dump first ~30K of decoded __PRELOADED_STATE__ for offline reference
        (OUT_DIR / f"{slug}_preloaded.json").write_text(json.dumps(data, indent=2)[:120000])
        break
    if not found:
        print("  not found in any <script>")


if __name__ == "__main__":
    main()
