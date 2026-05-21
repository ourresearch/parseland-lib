"""Iter 3 affiliation metric audit: side-by-side gold vs parsed strings.

Loads iter2-after.json, selects DOIs from the parser_affs_no_match bucket
(avg_soft_f1 == 0 AND pairs_scored > 0), fetches HTML from R2 using the
harvest_uuid already in the artifact, re-runs ElsevierBV.parse(), and prints
the gold rasses string next to the parsed affiliation strings for each
matched author pair.

Output goes to scripts-out/elsevier_aff_audit.txt for inclusion in LEARNING.md.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.gold import _coerce_author  # noqa: E402
from parseland_eval.score.affiliations import _clean, _drop_filler  # noqa: E402
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

ITER2 = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-iter2-after.json")
GOLD = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-gold.ndjson")
OUT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts-out/elsevier_aff_audit.txt")

N_SAMPLE_PER_BUCKET = 10
SEED = 20260521


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


def parse_in_process(html: str) -> list[dict]:
    """Run ElsevierBV directly and return [{name, affiliations: [str,...]}]."""
    soup = BeautifulSoup(html, "lxml")
    parser = ElsevierBV(soup)
    try:
        raw = parser.parse()
    except Exception as e:  # noqa: BLE001
        return [{"_parse_error": f"{type(e).__name__}: {e}"}]
    out = []
    for a in (raw.get("authors") or []):
        name = getattr(a, "name", None)
        affs = list(getattr(a, "affiliations", None) or [])
        out.append({"name": name, "affiliations": affs})
    return out


def load_gold_by_doi() -> dict[str, dict]:
    by_doi = {}
    with GOLD.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            by_doi[row["doi"]] = row
    return by_doi


def pick_samples(iter2: dict) -> dict[str, list[str]]:
    """Three buckets, N each: parser_affs_no_match, parser_authors_no_affs, partial."""
    buckets = {"parser_affs_no_match": [], "parser_authors_no_affs": [], "partial": []}
    for r in iter2["scored_rows"]:
        aff = r["score"]["affiliations"]
        ps = aff.get("pairs_scored", 0)
        sf1 = aff.get("avg_soft_f1", 0.0)
        pn = r.get("parsed_n_authors", 0)
        if ps == 0 and pn > 0:
            buckets["parser_authors_no_affs"].append(r["doi"])
        elif ps > 0 and sf1 == 0.0:
            buckets["parser_affs_no_match"].append(r["doi"])
        elif ps > 0 and 0.0 < sf1 < 1.0:
            buckets["partial"].append(r["doi"])
    rng = random.Random(SEED)
    return {k: rng.sample(v, min(N_SAMPLE_PER_BUCKET, len(v))) for k, v in buckets.items()}


def main():
    iter2 = json.loads(ITER2.read_text())
    uuids = {r["doi"]: r["harvest_uuid"] for r in iter2["scored_rows"]}
    gold = load_gold_by_doi()
    samples = pick_samples(iter2)

    s3 = _make_r2_client()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = []

    def emit(s=""):
        lines.append(s)
        print(s)

    for bucket, dois in samples.items():
        emit(f"\n{'=' * 78}")
        emit(f"BUCKET: {bucket}  (sampled {len(dois)})")
        emit("=" * 78)
        for doi in dois:
            uuid = uuids.get(doi)
            try:
                html = get_landing_page_from_r2(uuid, s3)
            except Exception as e:  # noqa: BLE001
                emit(f"\n--- {doi} (uuid={uuid})")
                emit(f"  R2 ERROR: {e}")
                continue
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="ignore")
            if not html:
                emit(f"\n--- {doi} (uuid={uuid})")
                emit("  empty HTML")
                continue

            parsed_authors = parse_in_process(html)
            gold_authors = []
            for a in (gold.get(doi) or {}).get("annotation", {}).get("authors") or []:
                if isinstance(a, dict):
                    try:
                        ca = _coerce_author(a)
                    except Exception:
                        continue
                    if ca is not None:
                        gold_authors.append(ca)

            emit(f"\n--- {doi}")
            emit(f"    gold authors: {len(gold_authors)}, parsed authors: {len(parsed_authors)}")
            def _attr(o, k, default=None):
                if o is None:
                    return default
                if isinstance(o, dict):
                    return o.get(k, default)
                return getattr(o, k, default)

            n = max(len(gold_authors), len(parsed_authors))
            for i in range(min(n, 4)):
                g = gold_authors[i] if i < len(gold_authors) else None
                p = parsed_authors[i] if i < len(parsed_authors) else None
                gname = _attr(g, "name", "—") or "—"
                pname = _attr(p, "name", "—") or "—"
                graff = list(_attr(g, "affiliations") or [])
                paff = list(_attr(p, "affiliations") or [])
                emit(f"    [{i}] gold='{gname}'  parsed='{pname}'")
                for j, x in enumerate(graff):
                    emit(f"          GOLD raff[{j}]:   {x}")
                for j, x in enumerate(paff):
                    emit(f"          PARSED aff[{j}]: {x}")
                # Also show the canonicalized form the scorer compares.
                for j, x in enumerate(graff):
                    emit(f"          GOLD soft[{j}]:   {_clean(x)}")
                for j, x in enumerate(paff):
                    emit(f"          PARSED soft[{j}]: {_clean(x)}")
                # Fuzzy: drop filler, lower threshold.
                for j, x in enumerate(graff):
                    emit(f"          GOLD fuzz[{j}]:   {_drop_filler(_clean(x))}")
                for j, x in enumerate(paff):
                    emit(f"          PARSED fuzz[{j}]: {_drop_filler(_clean(x))}")

    OUT.write_text("\n".join(lines))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
