"""For zero-bucket affiliation rows, decide: is the GOLD string actually on
the page, or only the PARSED string? Tells us whether iter 3 should fix the
parser or fix the gold standard.

For each sampled row:
  - Load HTML from R2 (via harvest_uuid).
  - Pull all gold author 'rasses' strings.
  - Pull all parsed affiliations via in-process ElsevierBV.parse().
  - For each, check whether canonical-normalized text appears as a
    substring in the canonical-normalized HTML text.

Outputs: 4-way confusion (gold-in-page × parsed-in-page) per bucket.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.gold import _coerce_author  # noqa: E402
from parseland_eval.score.normalize import normalize_alpha  # noqa: E402
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

ITER2 = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-iter2-after.json")
GOLD = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-10k-gold.ndjson")
OUT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts-out/gold_vs_page_grounding.json")

SAMPLE_PER_BUCKET = 80


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


def _norm(s: str) -> str:
    """Normalize for substring matching: lowercase, drop emails/urls,
    collapse non-alphanumeric runs to spaces."""
    s = re.sub(r"\S+@\S+", " ", s)
    s = re.sub(r"https?://\S+", " ", s)
    return normalize_alpha(s)


def _ngram_match(needle: str, haystack: str, n: int = 12) -> bool:
    """Pick a 'distinctive' n-word slice from `needle` and look for it in
    `haystack`. Resilient to formatting differences at the head/tail of
    affiliations.

    A real match should share at least one ~12-word contiguous span.
    """
    tokens = needle.split()
    if not tokens:
        return False
    if len(tokens) <= n:
        return " ".join(tokens) in haystack
    # Try several windows; if any 12-gram from the gold is on the page, count it.
    for i in range(0, len(tokens) - n + 1):
        gram = " ".join(tokens[i : i + n])
        if gram in haystack:
            return True
    return False


def _half_match(needle: str, haystack: str) -> bool:
    """Looser check: at least half of the gold's distinct content tokens
    (>2 chars, not common stopwords) appear in haystack."""
    STOP = {"of", "the", "and", "in", "at", "for", "on", "to", "a"}
    tokens = [t for t in needle.split() if len(t) > 2 and t not in STOP]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in haystack)
    return hits >= max(3, int(0.6 * len(tokens)))


def parse_in_process(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "lxml")
    try:
        raw = ElsevierBV(soup).parse()
    except Exception:
        return []
    out = []
    for a in (raw.get("authors") or []):
        affs = list(getattr(a, "affiliations", None) or [])
        out.append(affs)
    return out


def load_gold_by_doi() -> dict[str, dict]:
    by = {}
    with GOLD.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            by[r["doi"]] = r
    return by


def main():
    iter2 = json.loads(ITER2.read_text())
    rng = random.Random(20260521)
    buckets = {"zero": [], "perfect": []}
    for r in iter2["scored_rows"]:
        aff = r["score"]["affiliations"]
        ps = aff.get("pairs_scored", 0)
        sf1 = aff.get("avg_soft_f1", 0.0)
        if ps > 0 and sf1 == 0.0:
            buckets["zero"].append((r["doi"], r["harvest_uuid"]))
        elif ps > 0 and sf1 == 1.0:
            buckets["perfect"].append((r["doi"], r["harvest_uuid"]))

    sampled = {k: rng.sample(v, min(SAMPLE_PER_BUCKET, len(v))) for k, v in buckets.items()}

    gold_by_doi = load_gold_by_doi()
    s3 = _make_r2_client()
    out = {k: [] for k in sampled}
    summary = {}

    for bucket, items in sampled.items():
        print(f"\n--- {bucket} (n={len(items)}) ---")
        counts = {
            "rows": 0,
            "gold_strings_total": 0,
            "gold_in_page_strict": 0,
            "gold_in_page_loose": 0,
            "parsed_strings_total": 0,
            "parsed_in_page_strict": 0,
            "parsed_in_page_loose": 0,
            # per-row: any gold aff in page? any parsed aff in page?
            "rows_any_gold_in_page": 0,
            "rows_any_parsed_in_page": 0,
            "rows_no_gold_yes_parsed": 0,  # gold disagrees with page, parser agrees
            "rows_yes_gold_no_parsed": 0,  # parser disagrees with page, gold agrees
            "rows_both": 0,
            "rows_neither": 0,
        }

        for doi, uuid in items:
            try:
                html = get_landing_page_from_r2(uuid, s3)
            except Exception:
                continue
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="ignore")
            if not html:
                continue

            # Extract page text once and normalize
            page_text_norm = _norm(BeautifulSoup(html, "lxml").get_text(" "))
            # Also keep raw HTML normalized, since some affs are in JSON not text
            html_norm = _norm(html)
            page_combined = page_text_norm + " ||| " + html_norm

            # Gold authors & rasses
            gold_authors = []
            for a in (gold_by_doi.get(doi) or {}).get("annotation", {}).get("authors") or []:
                if isinstance(a, dict):
                    try:
                        ca = _coerce_author(a)
                    except Exception:
                        continue
                    if ca is not None:
                        gold_authors.append(ca)
            gold_affs = []
            for ga in gold_authors:
                for x in (getattr(ga, "affiliations", None) or []):
                    if isinstance(x, str) and x.strip():
                        gold_affs.append(x)

            # Parsed authors & affs
            parsed_authors_affs = parse_in_process(html)
            parsed_affs = [x for affs in parsed_authors_affs for x in affs]

            any_gold_on_page = False
            for g in gold_affs:
                gn = _norm(g)
                counts["gold_strings_total"] += 1
                if _ngram_match(gn, page_combined, n=10):
                    counts["gold_in_page_strict"] += 1
                    any_gold_on_page = True
                if _half_match(gn, page_combined):
                    counts["gold_in_page_loose"] += 1

            any_parsed_on_page = False
            for p in parsed_affs:
                pn = _norm(p)
                counts["parsed_strings_total"] += 1
                if _ngram_match(pn, page_combined, n=10):
                    counts["parsed_in_page_strict"] += 1
                    any_parsed_on_page = True
                if _half_match(pn, page_combined):
                    counts["parsed_in_page_loose"] += 1

            counts["rows"] += 1
            if any_gold_on_page:
                counts["rows_any_gold_in_page"] += 1
            if any_parsed_on_page:
                counts["rows_any_parsed_in_page"] += 1
            if any_gold_on_page and any_parsed_on_page:
                counts["rows_both"] += 1
            elif any_parsed_on_page and not any_gold_on_page:
                counts["rows_no_gold_yes_parsed"] += 1
            elif any_gold_on_page and not any_parsed_on_page:
                counts["rows_yes_gold_no_parsed"] += 1
            else:
                counts["rows_neither"] += 1
            out[bucket].append({
                "doi": doi,
                "gold_n": len(gold_affs),
                "parsed_n": len(parsed_affs),
                "any_gold_on_page": any_gold_on_page,
                "any_parsed_on_page": any_parsed_on_page,
            })

        summary[bucket] = counts
        print(json.dumps(counts, indent=2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "rows": out}, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
