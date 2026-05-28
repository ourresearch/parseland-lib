"""In-process Wiley diff: Wiley.parse() vs human-goldie.

Mirror of scripts/springer_inprocess_diff.py for the Wiley publisher
parser. Same envelope, same scorers, same artifact shape — only the
parser class and default fixture paths change so iter before/after
artifacts stay parallel between publishers.

Env vars:
    TAXICAB_URL          override Taxicab base (default from parseland_eval.api)
    GOLD_NDJSON          path to gold NDJSON (default: tests/fixtures/wiley-gold.ndjson)
    ITER_ARTIFACT        path to write the per-iter result (default: tests/fixtures/wiley-iter1-before.json)
    PARSELAND_NO_PROGRESS=1  disable ProgressLogger writes

Run:

    cd parseland-lib
    GOLD_NDJSON=tests/fixtures/wiley-gold.ndjson \\
      ITER_ARTIFACT=tests/fixtures/wiley-iter1-before.json \\
      .venv/bin/python scripts/wiley_inprocess_diff.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

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
from parseland_lib.legacy_parse_utils.fulltext import (  # noqa: E402
    parse_publisher_fulltext_location,
)
from parseland_lib.publisher.parsers.wiley import Wiley  # noqa: E402
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

GOLD_NDJSON = Path(
    os.environ.get(
        "GOLD_NDJSON",
        "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/wiley-gold.ndjson",
    )
)
ARTIFACT = Path(
    os.environ.get(
        "ITER_ARTIFACT",
        "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/tests/fixtures/wiley-iter1-before.json",
    )
)


def resolve_latest_harvest_uuid(doi: str) -> str | None:
    """Pick best harvest UUID for ``doi``. Prefer onlinelibrary.wiley.com
    canonical hosts over PDF asset or generic redirector URLs."""
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

    ASSET_HOSTS = (
        "doi.org",
        "linkinghub.elsevier.com",
    )

    def _host(rec: dict) -> str:
        from urllib.parse import urlparse
        return (urlparse(rec.get("resolved_url") or "").hostname or "").lower()

    article_records = [
        r for r in records
        if _host(r) and not any(_host(r).endswith(h) for h in ASSET_HOSTS)
    ]
    if article_records:
        best = max(article_records, key=lambda h: h.get("created_date") or "")
        return best.get("id")

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
    """Run Wiley.parse() directly on the HTML. No HTTP, no dispatcher.

    Normalizes the result through the same envelope ``parse_page()`` uses so
    the scorers consume it identically to the HTTP path. Any exception in
    parse() is captured into ``_parse_error`` so one bad row doesn't kill
    the eval.
    """
    soup = BeautifulSoup(html, "lxml")
    parser = Wiley(soup)
    is_publisher = bool(parser.is_publisher_specific_parser())
    authors_found = bool(parser.authors_found())
    try:
        raw = parser.parse()
    except Exception as e:  # noqa: BLE001
        return {
            "_authors_found": authors_found,
            "_is_publisher": is_publisher,
            "_parse_error": f"{type(e).__name__}: {e}",
            "authors": [],
            "urls": [],
            "license": None,
            "version": None,
            "abstract": None,
        }

    fulltext = None
    fulltext_error: str | None = None
    try:
        fulltext = parse_publisher_fulltext_location(soup, None)
    except Exception as e:  # noqa: BLE001
        fulltext_error = f"{type(e).__name__}: {e}"

    pdf_url = (fulltext or {}).get("pdf_url")
    urls: list[dict] = []
    if pdf_url:
        urls.append({"url": pdf_url, "content_type": "pdf"})

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

    out = {
        "_authors_found": authors_found,
        "_is_publisher": is_publisher,
        "authors": authors,
        "urls": urls,
        "license": (fulltext or {}).get("license"),
        "version": (fulltext or {}).get("version"),
        "abstract": raw.get("abstract"),
    }
    if fulltext_error:
        out["_fulltext_error"] = fulltext_error
    return out


def _gold_authors_for_scoring(annotation: dict) -> list:
    out = []
    for a in annotation.get("authors") or []:
        if not isinstance(a, dict):
            continue
        try:
            coerced = _coerce_author(a)
        except Exception:
            continue
        if coerced is not None:
            out.append(coerced)
    return out


def score_row(parsed: dict, gold: dict) -> dict:
    gold_authors = _gold_authors_for_scoring(gold)
    parsed_authors = parsed.get("authors") or []
    auth_r = score_authors(gold_authors, parsed_authors)
    aff_results = []
    for match in auth_r.matched:
        ga = gold_authors[match.gold_index] if match.gold_index < len(gold_authors) else None
        pa = parsed_authors[match.parsed_index] if match.parsed_index < len(parsed_authors) else None
        if ga is not None:
            aff_results.append(score_affiliations(ga, pa))
    aff_strict_f1 = sum(r.strict_f1 for r in aff_results) / len(aff_results) if aff_results else 0.0
    aff_soft_f1 = sum(r.soft_f1 for r in aff_results) / len(aff_results) if aff_results else 0.0
    aff_fuzzy_f1 = sum(r.fuzzy_f1 for r in aff_results) / len(aff_results) if aff_results else 0.0
    abs_r = score_abstract(gold.get("abstract"), parsed.get("abstract"))
    pdf_r = score_pdf_url(gold.get("pdf_url"), parsed)
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
                   authors_found: bool, is_publisher: bool) -> str:
    bot = "(BOT-CHECK)" if has_bot_check else "          "
    a = score["authors"].get("f1_soft")
    af = score["affiliations"].get("avg_soft_f1")
    ab = score["abstract"]
    pdf = score["pdf_url"]
    found_mark = "✓" if authors_found else "✗"
    pub_mark = "P" if is_publisher else "g"  # 'g' = generic fallback would fire instead
    a_str = f"{a:.2f}" if a is not None else "  - "
    af_str = f"{af:.2f}" if af is not None else "  - "
    ab_str = "1.00 (✓)" if ab.get("match_at_threshold") else f"{ab.get('fuzzy_ratio', 0):.2f} (✗)"
    pdf_str = "✓" if pdf.get("strict_match") else "✗"
    return (
        f"  {pub_mark}/{found_mark}  {doi:<35} {bot}  "
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
    print(f"loaded {len(rows)} Wiley gold rows from {GOLD_NDJSON.name}\n")

    s3 = _make_r2_client()
    scored = []
    failed = []

    from parseland_lib.audit.progress import ProgressLogger  # noqa: E402
    job_id = f"inprocess-diff-{ARTIFACT.stem}"
    use_progress = os.environ.get("PARSELAND_NO_PROGRESS") != "1"
    progress = ProgressLogger(job_id=job_id, total=len(rows),
                              label=f"Wiley inprocess diff → {ARTIFACT.name}") if use_progress else None
    p = progress.__enter__() if progress is not None else None

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
            if p is not None:
                p.error(doi, "resolve_uuid", str(e))
            continue

        if not uuid:
            failed.append({"doi": doi, "stage": "resolve_uuid", "error": "no UUID"})
            print(f"  FAIL  {doi}  no UUID")
            if p is not None:
                p.error(doi, "resolve_uuid", "no UUID")
            continue

        try:
            html = get_landing_page_from_r2(uuid, s3)
        except Exception as e:  # noqa: BLE001
            failed.append({"doi": doi, "stage": "r2_read", "error": str(e), "uuid": uuid})
            print(f"  FAIL  {doi}  r2: {e}")
            if p is not None:
                p.error(doi, "r2_read", str(e))
            continue

        if not html:
            failed.append({"doi": doi, "stage": "r2_read", "error": "empty", "uuid": uuid})
            print(f"  FAIL  {doi}  empty HTML")
            if p is not None:
                p.error(doi, "r2_read", "empty html")
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
                "is_publisher_specific": parsed.get("_is_publisher"),
                "parse_error": parsed.get("_parse_error"),
                "elapsed_seconds": round(elapsed, 2),
                "parsed_n_authors": len(parsed.get("authors") or []),
                "score": score,
            }
        )
        print(fmt_score_line(doi, has_bot_check, score, elapsed,
                             parsed.get("_authors_found"),
                             parsed.get("_is_publisher")))
        if p is not None:
            p.row(doi=doi, action="scored", elapsed=elapsed,
                  extra={"f1_soft": score["authors"].get("f1_soft"),
                         "aff_f1": score["affiliations"].get("avg_soft_f1")})
            p.heartbeat()

    n = len(scored)
    n_authors_found = sum(1 for r in scored if r.get("authors_found"))
    n_is_publisher = sum(1 for r in scored if r.get("is_publisher_specific"))
    n_parse_errors = sum(1 for r in scored if r.get("parse_error"))
    eligible_a = [r for r in scored if r["score"]["authors"].get("gold_total", 0) > 0]
    eligible_aff = [r for r in scored if r["score"]["affiliations"].get("pairs_scored", 0) > 0]
    abs_matched = sum(1 for r in scored if r["score"]["abstract"].get("match_at_threshold"))
    pdf_eligible = [r for r in scored if r["score"]["pdf_url"].get("strict_match") is not None]
    pdf_matched = sum(1 for r in pdf_eligible if r["score"]["pdf_url"].get("strict_match"))

    a_mean = (sum(r["score"]["authors"]["f1_soft"] for r in eligible_a) / len(eligible_a)) if eligible_a else None
    aff_mean = (sum(r["score"]["affiliations"]["avg_soft_f1"] for r in eligible_aff) / len(eligible_aff)) if eligible_aff else None

    tp = sum(r["score"]["corresponding"].get("tp", 0) for r in scored)
    fp = sum(r["score"]["corresponding"].get("fp", 0) for r in scored)
    fn = sum(r["score"]["corresponding"].get("fn", 0) for r in scored)
    prec = (tp / (tp + fp)) if (tp + fp) > 0 else None
    rec = (tp / (tp + fn)) if (tp + fn) > 0 else None
    corresp_f1 = (2 * prec * rec / (prec + rec)) if (prec and rec and (prec + rec) > 0) else None

    if failed:
        print(f"\n=== Failures ({len(failed)}) ===")
        for f in failed:
            print(f"    {f['doi']}  stage={f['stage']}  err={f['error']}")
    else:
        print(f"\nfailed: 0")

    print(f"\n========== TL;DR AGGREGATE (n={n}) ==========")
    print(f"  Wiley.is_publisher_specific_parser(): {n_is_publisher}/{n} rows")
    print(f"  Wiley.authors_found(): {n_authors_found}/{n} rows")
    if n_parse_errors:
        print(f"  Parser exceptions: {n_parse_errors}/{n} rows")
    if a_mean is not None:
        print(f"  Authors      mean F1_soft: {a_mean:.3f}  ({len(eligible_a)}/{n} eligible)")
    else:
        print(f"  Authors      mean F1_soft: n/a")
    if aff_mean is not None:
        print(f"  Affiliations mean F1_soft: {aff_mean:.3f}  ({len(eligible_aff)}/{n} rows had matched pairs)")
    else:
        print(f"  Affiliations mean F1_soft: n/a")
    print(f"  Abstract     match@0.74:   {abs_matched}/{n} rows ({100*abs_matched/n:.1f}%)" if n else "  Abstract: n/a")
    if pdf_eligible:
        print(f"  PDF URL      strict match: {pdf_matched}/{len(pdf_eligible)} gold-truthed rows")
    if corresp_f1 is not None:
        print(f"  Corresp      micro F1:     {corresp_f1:.3f}  (P {prec:.3f} / R {rec:.3f}, tp/fp/fn = {tp}/{fp}/{fn})")
    else:
        print(f"  Corresp      micro F1:     n/a (tp/fp/fn = {tp}/{fp}/{fn})")
    print(f"  failed: {len(failed)} / {n + len(failed)} input rows")
    print(f"=" * 47)

    artifact = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_ndjson": str(GOLD_NDJSON),
        "measurement_method": "in-process Wiley.parse() — no HTTP, no dispatcher",
        "scorer_source": "parseland-eval/eval/parseland_eval/score/*.py",
        "aggregate": {
            "n_rows": n,
            "n_authors_found": n_authors_found,
            "n_is_publisher_specific": n_is_publisher,
            "n_parse_errors": n_parse_errors,
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

    if p is not None:
        p.done(summary={
            "artifact": str(ARTIFACT),
            "n_rows": n,
            "authors_mean_f1_soft": round(a_mean, 4) if a_mean is not None else None,
            "affiliations_mean_soft_f1": round(aff_mean, 4) if aff_mean is not None else None,
            "abstract_match_at_074": abs_matched,
            "pdf_strict_match": pdf_matched,
            "corresp_micro_f1": round(corresp_f1, 4) if corresp_f1 is not None else None,
            "failed": len(failed),
        })
        progress.__exit__(None, None, None)


if __name__ == "__main__":
    main()
