"""In-process Elsevier diff: ElsevierBV.parse() vs human-goldie.

PLAN.md Step 2 of oxjob #203 (parseland-elsevier-iter2). Companion to
``elsevier_baseline_diff.py``, which routes through HTTP POST + the dispatcher
and therefore mixes "publisher parser behavior" with "dispatcher fallback to
generic parser" in its scores.

This script isolates ``ElsevierBV.parse()`` so the iter 2 parser delta is
unambiguous. For each gold row:

  1. Resolve the latest harvest UUID via Taxicab (same logic as baseline).
  2. Read HTML from R2 (no HTTP to local parseland).
  3. Wrap in BeautifulSoup.
  4. Call ``ElsevierBV(soup).parse()`` directly.
  5. Score against gold using parseland-eval's scorers.
  6. Aggregate.

Output artifact format mirrors ``elsevier-baseline-diff.json`` so the iter 2
before/after pair is structurally diffable.

Run:

    cd parseland-lib
    .venv/bin/python scripts/elsevier_inprocess_diff.py
    # writes:
    #   tests/fixtures/elsevier-iter2-before.json
    # or whatever ITER2_ARTIFACT env var points to (used for after-snapshot
    # by passing ITER2_ARTIFACT=tests/fixtures/elsevier-iter2-after.json)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# parseland-eval and parseland-lib on the path. Read-only imports.
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.api import TAXICAB_BASE  # noqa: E402
from parseland_eval.gold import _coerce_author  # noqa: E402
from parseland_eval.score.abstract import score_abstract  # noqa: E402
from parseland_eval.score.affiliations import score_affiliations  # noqa: E402
from parseland_eval.score.authors import score_authors, score_corresponding  # noqa: E402
from parseland_eval.score.pdf_url import score_pdf_url  # noqa: E402
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

GOLD_NDJSON = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-gold.ndjson"
)
ARTIFACT = Path(
    os.environ.get(
        "ITER2_ARTIFACT",
        "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-iter2-before.json",
    )
)


def resolve_latest_harvest_uuid(doi: str) -> str | None:
    """Return the most-recently-created harvest UUID for ``doi``.

    Mirrors the helper in ``elsevier_baseline_diff.py``. Taxicab's html[] array
    is not sorted by recency; the bot-check Zyte re-fetch UUID lives in the
    array but is not always index 0. Pick the max by created_date.
    """
    try:
        resp = requests.get(f"{TAXICAB_BASE}/taxicab/doi/{doi}", timeout=30)
    except Exception:  # noqa: BLE001
        return None
    if resp.status_code != 200:
        return None
    body = resp.json()
    records = body.get("html") or []
    if not records:
        return None
    latest = max(records, key=lambda h: h.get("created_date") or "")
    return latest.get("id")


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


def parse_in_process(html: str) -> dict:
    """Run ElsevierBV.parse() directly on the HTML. No HTTP, no dispatcher.

    Returns the same shape parseland's HTTP path returns, normalized through
    the same author/affiliation/url/abstract envelope, so the scorers consume
    it identically. If ``authors_found()`` is False, we still call parse() and
    record what it returns (almost certainly empty) — that's the iter 2
    before-snapshot we want to measure against.
    """
    soup = BeautifulSoup(html, "lxml")
    parser = ElsevierBV(soup)
    authors_found = bool(parser.authors_found())
    try:
        raw = parser.parse()
    except Exception as e:  # noqa: BLE001
        return {
            "_authors_found": authors_found,
            "_parse_error": f"{type(e).__name__}: {e}",
            "authors": [],
            "urls": [],
            "license": None,
            "version": None,
            "abstract": None,
        }

    # parse() returns {"authors": [AuthorAffiliations...], "abstract": "..."}.
    # Normalize into parseland's HTTP response shape so the scorers consume it
    # identically to the baseline diff artifact.
    authors = []
    for a in raw.get("authors", []) or []:
        name = getattr(a, "name", None) or (a.get("name") if isinstance(a, dict) else None)
        affs = getattr(a, "affiliations", None) or (
            a.get("affiliations") if isinstance(a, dict) else []
        )
        is_corresponding = getattr(a, "is_corresponding", None)
        if is_corresponding is None and isinstance(a, dict):
            is_corresponding = a.get("is_corresponding")
        authors.append(
            {
                "name": name,
                "affiliations": [{"name": x} for x in (affs or [])],
                "is_corresponding": is_corresponding,
            }
        )

    return {
        "_authors_found": authors_found,
        "authors": authors,
        "urls": [],  # ElsevierBV.parse() doesn't populate fulltext_location
        "license": None,
        "version": None,
        "abstract": raw.get("abstract"),
    }


def _gold_authors_for_scoring(annotation: dict) -> list:
    """Normalize gold authors via parseland-eval's coercion helper.

    Same logic as baseline diff. Gold author records in human-goldie use a
    `rasses` field (string) where the scorers expect `affiliations` as a tuple
    of strings. parseland-eval's gold loader does this normalization, but the
    NDJSON shard skips the loader path — we apply the same coercion here.
    """
    out = []
    for a in annotation.get("authors") or []:
        # _coerce_author handles the rasses→affiliations rename + tuple coercion.
        coerced = _coerce_author(a)
        if coerced is not None:
            out.append(coerced)
    return out


def score_row(parsed: dict, gold: dict) -> dict:
    """Apply the five parseland-eval scorers to a single parsed/gold pair.

    Mirrors the call signatures used in elsevier_baseline_diff.py so the two
    artifact JSONs are structurally identical and diffable.
    """
    gold_authors = _gold_authors_for_scoring(gold)
    parsed_authors = parsed.get("authors") or []

    # Authors — bipartite match
    auth_r = score_authors(gold_authors, parsed_authors)

    # Affiliations — per matched pair, averaged
    aff_results = []
    for match in auth_r.matched:
        ga = gold_authors[match.gold_index] if match.gold_index < len(gold_authors) else None
        pa = parsed_authors[match.parsed_index] if match.parsed_index < len(parsed_authors) else None
        if ga is not None:
            aff_results.append(score_affiliations(ga, pa))
    aff_strict_f1 = sum(r.strict_f1 for r in aff_results) / len(aff_results) if aff_results else 0.0
    aff_soft_f1 = sum(r.soft_f1 for r in aff_results) / len(aff_results) if aff_results else 0.0
    aff_fuzzy_f1 = sum(r.fuzzy_f1 for r in aff_results) / len(aff_results) if aff_results else 0.0

    # Abstract
    abs_r = score_abstract(gold.get("abstract"), parsed.get("abstract"))

    # PDF URL
    pdf_r = score_pdf_url(gold.get("pdf_url"), parsed)

    # Corresponding author — needs matched pairs from author scoring
    corresp_r = score_corresponding(gold_authors, parsed_authors, auth_r.matched)

    return {
        "authors": {
            "matched": len(auth_r.matched),
            "gold_total": len(gold_authors),
            "parsed_total": len(parsed_authors),
            "precision": round(auth_r.precision, 3),
            "recall": round(auth_r.recall, 3),
            "f1": round(auth_r.f1, 3),
            "precision_soft": round(auth_r.precision_soft, 3),
            "recall_soft": round(auth_r.recall_soft, 3),
            "f1_soft": round(auth_r.f1_soft, 3),
        },
        "affiliations": {
            "pairs_scored": len(aff_results),
            "avg_strict_f1": round(aff_strict_f1, 3),
            "avg_soft_f1": round(aff_soft_f1, 3),
            "avg_fuzzy_f1": round(aff_fuzzy_f1, 3),
        },
        "abstract": {
            "fuzzy_ratio": round(abs_r.fuzzy_ratio, 3),
            "soft_ratio": round(abs_r.soft_ratio, 3),
            "length_ratio": round(abs_r.length_ratio, 3),
            "match_at_threshold": abs_r.match_at_threshold,
            "present": abs_r.present,
        },
        "pdf_url": {
            "strict_match": pdf_r.strict_match,
            "present": pdf_r.present,
            "expected_present": pdf_r.expected_present,
            "divergent": pdf_r.divergent,
        },
        "corresponding": {
            "tp": corresp_r.tp,
            "fp": corresp_r.fp,
            "fn": corresp_r.fn,
            "precision": round(corresp_r.precision, 3),
            "recall": round(corresp_r.recall, 3),
            "f1": round(corresp_r.f1, 3),
            "gold_total_ca": corresp_r.gold_total_ca,
            "parsed_total_ca": corresp_r.parsed_total_ca,
        },
    }


def fmt_score_line(doi: str, has_bot_check: bool, score: dict, elapsed: float,
                    authors_found: bool) -> str:
    """One-line summary for stdout, mirroring the baseline diff format."""
    bot = "(BOT-CHECK)" if has_bot_check else "          "
    a = score["authors"].get("f1_soft")
    af = score["affiliations"].get("avg_soft_f1")
    ab = score["abstract"]
    pdf = score["pdf_url"]
    found_mark = "✓" if authors_found else "✗"
    a_str = f"{a:.2f}" if a is not None else "  - "
    af_str = f"{af:.2f}" if af is not None else "  - "
    ab_str = "1.00 (✓)" if ab.get("match_at_threshold") else f"{ab.get('fuzzy_ratio', 0):.2f} (✗)"
    pdf_str = "✓" if pdf.get("strict_match") else "✗"
    return (
        f"  found={found_mark}  {doi:<40} {bot}  "
        f"auth F1 {a_str}  aff F1 {af_str}  abs {ab_str}  pdf {pdf_str}  "
        f"({elapsed:.1f}s)"
    )


def main():
    if not GOLD_NDJSON.exists():
        print(f"ERROR: {GOLD_NDJSON} not found")
        sys.exit(1)

    rows = []
    with GOLD_NDJSON.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    print(f"loaded {len(rows)} Elsevier gold rows from {GOLD_NDJSON.name}\n")

    s3 = _make_r2_client()
    scored = []
    failed = []

    for row in rows:
        doi = row.get("doi", "")
        gold = row.get("annotation") or {}
        has_bot_check = bool(row.get("has_bot_check"))
        t0 = time.time()

        try:
            uuid = resolve_latest_harvest_uuid(doi)
        except Exception as e:  # noqa: BLE001
            failed.append({"doi": doi, "stage": "resolve_uuid", "error": str(e)})
            print(f"  FAIL  {doi}  resolve_uuid: {e}")
            continue

        if not uuid:
            failed.append({"doi": doi, "stage": "resolve_uuid", "error": "no UUID"})
            print(f"  FAIL  {doi}  no UUID")
            continue

        try:
            html = get_landing_page_from_r2(uuid, s3)
        except Exception as e:  # noqa: BLE001
            failed.append({"doi": doi, "stage": "r2_read", "error": str(e), "uuid": uuid})
            print(f"  FAIL  {doi}  r2: {e}")
            continue

        if not html:
            failed.append({"doi": doi, "stage": "r2_read", "error": "empty", "uuid": uuid})
            print(f"  FAIL  {doi}  empty HTML")
            continue

        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="ignore")

        parsed = parse_in_process(html)
        score = score_row(parsed, gold)
        elapsed = time.time() - t0

        scored.append(
            {
                "doi": doi,
                "harvest_uuid": uuid,
                "has_bot_check": has_bot_check,
                "publisher_domain": row.get("publisher_domain"),
                "authors_found": parsed.get("_authors_found"),
                "elapsed_seconds": round(elapsed, 2),
                "parsed_n_authors": len(parsed.get("authors") or []),
                "score": score,
            }
        )
        print(fmt_score_line(doi, has_bot_check, score, elapsed, parsed.get("_authors_found")))

    # Aggregate
    n = len(scored)
    eligible_a = [r for r in scored if r["score"]["authors"].get("gold_total", 0) > 0]
    eligible_aff = [r for r in scored if r["score"]["affiliations"].get("pairs_scored", 0) > 0]
    abs_matched = sum(1 for r in scored if r["score"]["abstract"].get("match_at_threshold"))
    pdf_eligible = [r for r in scored if r["score"]["pdf_url"].get("strict_match") is not None]
    pdf_matched = sum(1 for r in pdf_eligible if r["score"]["pdf_url"].get("strict_match"))

    if eligible_a:
        a_mean = sum(r["score"]["authors"]["f1_soft"] for r in eligible_a) / len(eligible_a)
    else:
        a_mean = None
    if eligible_aff:
        aff_mean = sum(r["score"]["affiliations"]["avg_soft_f1"] for r in eligible_aff) / len(
            eligible_aff
        )
    else:
        aff_mean = None

    # Corresponding micro F1 across rows
    tp = sum(r["score"]["corresponding"].get("tp", 0) for r in scored)
    fp = sum(r["score"]["corresponding"].get("fp", 0) for r in scored)
    fn = sum(r["score"]["corresponding"].get("fn", 0) for r in scored)
    if tp + fp > 0:
        prec = tp / (tp + fp)
    else:
        prec = None
    if tp + fn > 0:
        rec = tp / (tp + fn)
    else:
        rec = None
    if prec is not None and rec is not None and (prec + rec) > 0:
        corresp_f1 = 2 * prec * rec / (prec + rec)
    else:
        corresp_f1 = None

    n_authors_found = sum(1 for r in scored if r.get("authors_found"))

    print(f"\n=== Aggregate (n={n}) ===")
    print(f"  ElsevierBV.authors_found(): {n_authors_found}/{n} rows")
    if a_mean is not None:
        print(f"  Authors      mean F1_soft: {a_mean:.3f}  ({len(eligible_a)}/{n} eligible)")
    else:
        print(f"  Authors      mean F1_soft: n/a (0 eligible rows)")
    if aff_mean is not None:
        print(f"  Affiliations mean F1_soft: {aff_mean:.3f}  ({len(eligible_aff)}/{n} rows had matched pairs)")
    else:
        print(f"  Affiliations mean F1_soft: n/a (0 rows had matched pairs)")
    print(f"  Abstract     match@0.74:   {abs_matched}/{n} rows ({100*abs_matched/n:.1f}%)" if n else "  Abstract: n/a")
    if pdf_eligible:
        print(f"  PDF URL      strict match: {pdf_matched}/{len(pdf_eligible)} gold-truthed rows")
    if corresp_f1 is not None:
        print(f"  Corresp      micro F1:     {corresp_f1:.3f}  (P {prec:.3f} / R {rec:.3f}, tp/fp/fn = {tp}/{fp}/{fn})")
    else:
        print(f"  Corresp      micro F1:     n/a (tp/fp/fn = {tp}/{fp}/{fn})")

    print(f"\n  failed: {len(failed)}")
    if failed:
        for f in failed:
            print(f"    {f['doi']}  stage={f['stage']}  err={f['error']}")

    artifact = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_ndjson": str(GOLD_NDJSON),
        "measurement_method": "in-process ElsevierBV.parse() — no HTTP, no dispatcher",
        "scorer_source": "parseland-eval/eval/parseland_eval/score/*.py",
        "aggregate": {
            "n_rows": n,
            "n_authors_found": n_authors_found,
            "authors_mean_f1_soft": a_mean,
            "authors_eligible_count": len(eligible_a),
            "affiliations_mean_soft_f1": aff_mean,
            "affiliations_pairs_scored_rows": len(eligible_aff),
            "abstract_match_at_074": abs_matched,
            "pdf_strict_match": pdf_matched,
            "pdf_eligible_count": len(pdf_eligible),
            "corresponding": {
                "micro_f1": corresp_f1,
                "precision": prec,
                "recall": rec,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            },
        },
        "scored_rows": scored,
        "failed_rows": failed,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, indent=2, default=str))
    print(f"\n  artifact: {ARTIFACT}")


if __name__ == "__main__":
    main()
