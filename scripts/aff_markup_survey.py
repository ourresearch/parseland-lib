"""Survey: of the 434 'parser_affs_no_match' rows (avg_soft_f1==0, pairs>0),
how many pages have `<dl class="affiliation">` blocks vs only
`__PRELOADED_STATE__` JSON affs vs neither?

Cross-references with the 244 perfect-match rows for control.

Reads HTML from R2 using harvest_uuids in iter2-after.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

ITER2 = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-iter2-after.json")
OUT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts-out/aff_markup_survey.json")

SAMPLE_PER_BUCKET = 60  # ~60 of each bucket — keeps it under 2 minutes


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


def classify_markup(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    n_dl = len(soup.find_all("dl", class_="affiliation"))
    has_ag = bool(soup.find("div", class_="author-group"))
    has_legacy_li = bool(soup.find_all("li", class_="author"))
    has_preloaded = "__PRELOADED_STATE__" in html
    return {
        "dl_aff_count": n_dl,
        "has_author_group": has_ag,
        "has_legacy_li_author": has_legacy_li,
        "has_preloaded_state": has_preloaded,
    }


def main():
    import random
    iter2 = json.loads(ITER2.read_text())
    rng = random.Random(20260521)

    buckets = {"zero": [], "perfect": [], "partial": []}
    for r in iter2["scored_rows"]:
        aff = r["score"]["affiliations"]
        ps = aff.get("pairs_scored", 0)
        sf1 = aff.get("avg_soft_f1", 0.0)
        if ps > 0 and sf1 == 0.0:
            buckets["zero"].append((r["doi"], r["harvest_uuid"]))
        elif ps > 0 and sf1 == 1.0:
            buckets["perfect"].append((r["doi"], r["harvest_uuid"]))
        elif ps > 0 and 0 < sf1 < 1:
            buckets["partial"].append((r["doi"], r["harvest_uuid"]))

    sampled = {k: rng.sample(v, min(SAMPLE_PER_BUCKET, len(v))) for k, v in buckets.items()}

    s3 = _make_r2_client()
    results = {k: [] for k in sampled}
    summary = {}

    for bucket, items in sampled.items():
        print(f"\n--- bucket: {bucket} (n={len(items)}) ---")
        dl_yes = 0
        dl_no = 0
        ag_yes = 0
        for doi, uuid in items:
            try:
                html = get_landing_page_from_r2(uuid, s3)
            except Exception as e:  # noqa: BLE001
                print(f"  R2 ERR {doi}: {e}")
                continue
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="ignore")
            if not html:
                continue
            cls = classify_markup(html)
            cls["doi"] = doi
            results[bucket].append(cls)
            if cls["dl_aff_count"] > 0:
                dl_yes += 1
            else:
                dl_no += 1
            if cls["has_author_group"]:
                ag_yes += 1
        n = len(results[bucket])
        summary[bucket] = {
            "n_sampled": n,
            "pages_with_dl_affiliation": dl_yes,
            "pages_without_dl_affiliation": dl_no,
            "pages_with_author_group_div": ag_yes,
        }
        print(json.dumps(summary[bucket], indent=2))

    artifact = {"summary": summary, "rows": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
