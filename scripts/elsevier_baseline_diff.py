"""Baseline diff: parseland vs human-goldie on the 13 Elsevier gold rows.

Skill-spec v2: uses the parseland-eval scorers directly (score_authors,
score_affiliations, score_abstract, score_pdf_url, score_corresponding)
rather than reinventing matching in this script. These scorers handle
the things my v1 naive scorer got wrong:

- Author name-component swap (Last, First vs First Last) — name-keyed bipartite
- Affiliation comparison after canonicalization (strip emails/urls, drop filler)
- Abstract Levenshtein with a tuned 0.74 binary threshold
- PDF URL canonicalization (host normalization, query stripping, etc.)

The script reads ``parseland-lib/tests/fixtures/elsevier-gold.ndjson`` (already
emits the 13 Elsevier rows from human-goldie.csv in a shape parallel to OpenAlex
NDJSON shards). For each row: resolves DOI to harvest UUID via Taxicab, pulls
HTML from R2, POSTs to local parseland with namespace=doi + resolved_url,
runs the five scorers, and aggregates.

Bot-check rows (Has Bot Check == true in gold) are NOT skipped here. Whether
the Zyte re-fetch has been triggered is a separate concern (Step 2 of plan
#202). If the cached R2 HTML is still a captcha page, the row scores zero
across the board — that surfaces the gap rather than hiding it.

Run:

    cd parseland-lib
    .venv/bin/python scripts/elsevier_baseline_diff.py
    # writes:
    #   tests/fixtures/elsevier-baseline-diff.json  (per-row + aggregate)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Make parseland-eval and parseland-lib importable. Read-only use only.
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval")
sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib")

import boto3  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from parseland_eval.api import resolve_harvest_uuid, TAXICAB_BASE  # noqa: E402
from parseland_eval.gold import _coerce_author  # noqa: E402  # private but authoritative


def resolve_latest_harvest_uuid(doi: str) -> str | None:
    """Return the most-recently-created harvest UUID for ``doi``, not html[0].

    parseland_eval.api.resolve_harvest_uuid takes the first record in Taxicab's
    html[] array, but that array is not sorted by recency. When a row has had
    a fresh Zyte re-fetch via Taxicab POST, the new clean UUID lands in the
    array but won't necessarily be index 0. Picking the max by created_date
    gives us the harvest we actually want.
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
    # Sort by created_date string (ISO 8601 sorts lexicographically). Pick most recent.
    latest = max(records, key=lambda h: h.get("created_date") or "")
    return latest.get("id")
from parseland_eval.score.abstract import score_abstract  # noqa: E402
from parseland_eval.score.affiliations import score_affiliations  # noqa: E402
from parseland_eval.score.authors import score_authors, score_corresponding  # noqa: E402
from parseland_eval.score.pdf_url import score_pdf_url  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

NDJSON_PATH = Path(
    "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/elsevier-gold.ndjson"
)
ARTIFACT_PATH = NDJSON_PATH.parent / "elsevier-baseline-diff.json"
LOCAL_PARSELAND = os.environ.get("LOCAL_PARSELAND_URL", "http://localhost:8080")


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


def post_parseland(html: str, resolved_url: str | None) -> dict | None:
    """POST raw HTML to local parseland with publisher-parser path enabled."""
    try:
        resp = requests.post(
            f"{LOCAL_PARSELAND}/parseland",
            json={"html": html, "namespace": "doi", "resolved_url": resolved_url},
            timeout=30,
        )
        if resp.status_code != 200:
            return {"_error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{type(e).__name__}: {e}"}


def _gold_authors_for_scoring(annotation: dict) -> list:
    """Gold authors in human-goldie are dicts with `rasses` as a string.

    The score_affiliations function expects `affiliations` as a tuple-of-strings,
    not a raw string — iterating a string yields characters, which would score
    0.0 against any real affiliation list. The parseland-eval gold loader has
    a `_coerce_author` helper that normalizes raw author dicts into typed
    `GoldAuthor` objects (with `affiliations` as a tuple), and that's the
    shape the scorers expect.
    """
    raw_authors = annotation.get("authors") or []
    return [_coerce_author(a) for a in raw_authors if isinstance(a, dict)]


def _row_publisher_domain(annotation: dict) -> str:
    link = annotation.get("link") or annotation.get("resolved_links") or ""
    try:
        from urllib.parse import urlparse
        host = urlparse(link).netloc.lower()
        return host.removeprefix("www.")
    except Exception:  # noqa: BLE001
        return ""


def _score_one_row(annotation: dict, parsed: dict) -> dict:
    """Return per-field result dicts. Uses parseland-eval scorers."""
    gold_authors = _gold_authors_for_scoring(annotation)
    parsed_authors = parsed.get("authors") or []

    # Authors — bipartite match on (last, first-initial), with token_set_ratio fallback
    auth_r = score_authors(gold_authors, parsed_authors)

    # Affiliations — per matched pair
    aff_results = []
    for match in auth_r.matched:
        ga = gold_authors[match.gold_index] if match.gold_index < len(gold_authors) else None
        pa = parsed_authors[match.parsed_index] if match.parsed_index < len(parsed_authors) else None
        if ga is not None:
            aff_results.append(score_affiliations(ga, pa))

    # Aggregate affiliations as average F1 over matched pairs.
    aff_strict_f1 = (
        sum(r.strict_f1 for r in aff_results) / len(aff_results)
        if aff_results
        else 0.0
    )
    aff_soft_f1 = (
        sum(r.soft_f1 for r in aff_results) / len(aff_results)
        if aff_results
        else 0.0
    )
    aff_fuzzy_f1 = (
        sum(r.fuzzy_f1 for r in aff_results) / len(aff_results)
        if aff_results
        else 0.0
    )

    # Abstract — Levenshtein + 0.74 binary threshold
    abs_r = score_abstract(annotation.get("abstract"), parsed.get("abstract"))

    # PDF URL — canonicalized exact match
    pdf_r = score_pdf_url(annotation.get("pdf_url"), parsed)

    # Corresponding author flag — on matched pairs only
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


def main() -> int:
    s3 = _make_r2_client()
    rows = [json.loads(line) for line in NDJSON_PATH.read_text().splitlines() if line.strip()]
    print(f"loaded {len(rows)} Elsevier gold rows from {NDJSON_PATH.name}\n")

    per_row: list[dict] = []
    failed: list[dict] = []

    for row in rows:
        ann = row["annotation"]
        doi = row["doi"]
        bot_check_note = " (BOT-CHECK)" if ann.get("has_bot_check") else ""

        t0 = time.time()
        uuid = resolve_latest_harvest_uuid(doi)
        if not uuid:
            print(f"  FAIL  {doi:<42}{bot_check_note}  no harvest UUID")
            failed.append({"doi": doi, "stage": "taxicab", "reason": "no harvest"})
            continue

        try:
            html = get_landing_page_from_r2(uuid, s3)
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL  {doi:<42}{bot_check_note}  R2: {type(e).__name__}")
            failed.append({"doi": doi, "stage": "r2", "reason": f"{type(e).__name__}: {e}"})
            continue

        if not html:
            print(f"  FAIL  {doi:<42}{bot_check_note}  R2 returned empty HTML")
            failed.append({"doi": doi, "stage": "r2", "reason": "empty html"})
            continue

        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")

        parsed = post_parseland(html, ann.get("link"))
        if not parsed or "_error" in parsed:
            err = parsed.get("_error") if parsed else "no response"
            print(f"  FAIL  {doi:<42}{bot_check_note}  parseland: {err}")
            failed.append({"doi": doi, "stage": "parseland", "reason": err})
            continue

        score = _score_one_row(ann, parsed)
        elapsed = time.time() - t0
        per_row.append({
            "doi": doi,
            "harvest_uuid": uuid,
            "has_bot_check": bool(ann.get("has_bot_check")),
            "resolves_to_pdf": bool(ann.get("resolves_to_pdf")),
            "publisher_domain": _row_publisher_domain(ann),
            "elapsed_seconds": round(elapsed, 2),
            "score": score,
        })
        print(
            f"  OK    {doi:<42}{bot_check_note}  "
            f"auth F1 {score['authors']['f1_soft']:.2f}  "
            f"aff F1 {score['affiliations']['avg_soft_f1']:.2f}  "
            f"abs {score['abstract']['fuzzy_ratio']:.2f} "
            f"({'✓' if score['abstract']['match_at_threshold'] else '✗'})  "
            f"pdf {'✓' if score['pdf_url']['strict_match'] else '✗'}  "
            f"({elapsed:.1f}s)"
        )

    # ---------- aggregate ----------
    print()
    print("=== Aggregate (n={}) ===".format(len(per_row)))

    if per_row:
        # Macro averages across rows where the field was applicable.
        scored_rows = [r["score"] for r in per_row]

        def _macro_mean(field: str, key: str) -> float:
            vals = [s[field][key] for s in scored_rows]
            return sum(vals) / len(vals) if vals else 0.0

        # Authors — average soft F1 over rows where there was at least 1 gold or parsed author
        auth_eligible = [s for s in scored_rows if s["authors"]["gold_total"] + s["authors"]["parsed_total"] > 0]
        auth_f1_soft_mean = (
            sum(s["authors"]["f1_soft"] for s in auth_eligible) / len(auth_eligible)
            if auth_eligible
            else 0.0
        )

        # Affiliations — average soft F1 over rows where at least one pair was scored
        aff_eligible = [s for s in scored_rows if s["affiliations"]["pairs_scored"] > 0]
        aff_f1_soft_mean = (
            sum(s["affiliations"]["avg_soft_f1"] for s in aff_eligible) / len(aff_eligible)
            if aff_eligible
            else 0.0
        )

        # Abstract — match rate at the 0.74 threshold, over rows where gold abstract is present
        abs_eligible = [s for s in scored_rows if s["abstract"]["fuzzy_ratio"] > 0 or s["abstract"]["match_at_threshold"]]
        abs_match_count = sum(1 for s in scored_rows if s["abstract"]["match_at_threshold"])

        # PDF URL — strict match rate over rows where gold PDF is present (expected_present)
        pdf_eligible = [s for s in scored_rows if s["pdf_url"]["expected_present"]]
        pdf_match_count = sum(1 for s in pdf_eligible if s["pdf_url"]["strict_match"])

        # Corresponding author — micro P/R/F1
        corresp_tp = sum(s["corresponding"]["tp"] for s in scored_rows)
        corresp_fp = sum(s["corresponding"]["fp"] for s in scored_rows)
        corresp_fn = sum(s["corresponding"]["fn"] for s in scored_rows)
        corresp_p = corresp_tp / (corresp_tp + corresp_fp) if (corresp_tp + corresp_fp) else 0.0
        corresp_r = corresp_tp / (corresp_tp + corresp_fn) if (corresp_tp + corresp_fn) else 0.0
        corresp_f1 = (2 * corresp_p * corresp_r / (corresp_p + corresp_r)) if (corresp_p + corresp_r) else 0.0

        print(f"  Authors      mean F1_soft: {auth_f1_soft_mean:.3f}  ({len(auth_eligible)}/{len(scored_rows)} eligible)")
        print(f"  Affiliations mean F1_soft: {aff_f1_soft_mean:.3f}  ({len(aff_eligible)}/{len(scored_rows)} rows had matched pairs)")
        print(f"  Abstract     match@0.74:   {abs_match_count}/{len(scored_rows)} rows ({abs_match_count/len(scored_rows):.1%})")
        print(f"  PDF URL      strict match: {pdf_match_count}/{len(pdf_eligible)} gold-truthed rows")
        print(f"  Corresp      micro F1:     {corresp_f1:.3f}  (P {corresp_p:.3f} / R {corresp_r:.3f}, tp/fp/fn = {corresp_tp}/{corresp_fp}/{corresp_fn})")

    print(f"\n  failed: {len(failed)}")
    for f in failed:
        print(f"    - {f['doi']}  ({f['stage']}: {f['reason']})")

    # ---------- write artifact ----------
    artifact = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_ndjson": str(NDJSON_PATH),
        "parseland_endpoint": LOCAL_PARSELAND,
        "scorer_source": "parseland-eval/eval/parseland_eval/score/*.py",
        "scored_rows": per_row,
        "failed_rows": failed,
    }
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"\n  artifact: {ARTIFACT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
