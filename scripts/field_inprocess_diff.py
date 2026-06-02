"""Generalized in-process diff: <Publisher>.parse() vs human-goldie gold.

Collapses elsevier_inprocess_diff.py, ieee_inprocess_diff.py,
springer_inprocess_diff.py, and wiley_inprocess_diff.py — which were ~95%
identical — into a single CLI dispatching on ``--publisher``. Per row:

  1. Resolve the latest harvest UUID via Taxicab (publisher-aware host filter).
  2. Read HTML from R2.
  3. Wrap in BeautifulSoup.
  4. Call ``<Publisher>(soup).parse()`` directly.
  5. Score against gold using parseland-eval's per-field scorers.
  6. Aggregate.

The ``--field`` flag is informational: the script always runs all 5 scorers
because the multi-agent workflow needs full per-field deltas to enforce the
opus-judge no-regression rule. It highlights the target field in stdout
and reports it in the artifact's ``target_field`` key.

Usage:

    python scripts/field_inprocess_diff.py \\
        --publisher elsevier \\
        --field corresponding \\
        --gold tests/fixtures/elsevier-gold.ndjson \\
        --out  tests/fixtures/elsevier-iter4-after.json

Adding a new publisher: register an entry in ``PUBLISHER_REGISTRY``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

# parseland-eval and parseland-lib on the path. Read-only imports.
#
# The parseland-lib path resolves to THIS file's repo root so the script picks
# up worktree-local parser code when invoked from inside a git worktree. The
# previous hardcoded absolute path silently loaded main's parsers regardless
# of the cwd, breaking the multi-agent regression-sentinel's worktree
# isolation: a sentinel applying a patch in its worktree was still importing
# main's parser code and reporting the unpatched results.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT_FROM_FILE = _THIS_FILE.parent.parent  # scripts/ -> repo root
sys.path.insert(0, str(_REPO_ROOT_FROM_FILE))
# parseland-eval lives outside the repo. Allow override via env var; fall back
# to the conventional sibling path.
_PARSELAND_EVAL_PATH = os.environ.get(
    "PARSELAND_EVAL_PATH",
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval",
)
sys.path.insert(0, _PARSELAND_EVAL_PATH)

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
from parseland_lib.s3 import get_landing_page_from_r2  # noqa: E402

REPO_ROOT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib")
FIXTURES = REPO_ROOT / "tests" / "fixtures"

VALID_FIELDS = ("authors", "affiliations", "abstract", "pdf_url", "corresponding")


@dataclass(frozen=True)
class PublisherSpec:
    """Per-publisher configuration for the generalized diff harness."""

    name: str
    parser_import: str  # "parseland_lib.publisher.parsers.elsevier_bv:ElsevierBV"
    default_gold: Path
    default_artifact: Path
    # Hostnames or URL substrings that mark binary-stub / non-article records.
    # The Taxicab UUID resolver prefers article landing pages over these.
    asset_hosts: tuple[str, ...]
    # Match style: 'endswith' compares against the hostname; 'in_url' substring-
    # matches against the full lowercased resolved_url. IEEE needs 'in_url'
    # because its asset CDN lives on the same host as articles.
    asset_match: str = "endswith"


PUBLISHER_REGISTRY: dict[str, PublisherSpec] = {
    "elsevier": PublisherSpec(
        name="elsevier",
        parser_import="parseland_lib.publisher.parsers.elsevier_bv:ElsevierBV",
        default_gold=FIXTURES / "elsevier-gold.ndjson",
        default_artifact=FIXTURES / "elsevier-iter-after.json",
        asset_hosts=(
            "pdf.sciencedirectassets.com",
            "ars.els-cdn.com",
            "linkinghub.elsevier.com",
        ),
    ),
    "springer": PublisherSpec(
        name="springer",
        parser_import="parseland_lib.publisher.parsers.springer:Springer",
        default_gold=FIXTURES / "springer-gold.ndjson",
        default_artifact=FIXTURES / "springer-iter-after.json",
        asset_hosts=("doi.org", "linkinghub.elsevier.com"),
    ),
    "wiley": PublisherSpec(
        name="wiley",
        parser_import="parseland_lib.publisher.parsers.wiley:Wiley",
        default_gold=FIXTURES / "wiley-gold.ndjson",
        default_artifact=FIXTURES / "wiley-iter-after.json",
        asset_hosts=("doi.org", "linkinghub.elsevier.com"),
    ),
    "ieee": PublisherSpec(
        name="ieee",
        parser_import="parseland_lib.publisher.parsers.ieee:IEEE",
        default_gold=FIXTURES / "ieee-10k-gold.ndjson",
        default_artifact=FIXTURES / "ieee-iter-after.json",
        asset_hosts=("ieeexplore.ieee.org/ielx", "ieeexplore.ieee.org/iel"),
        asset_match="in_url",
    ),
    "taylor": PublisherSpec(
        name="taylor",
        parser_import="parseland_lib.publisher.parsers.taylor:Taylor",
        default_gold=FIXTURES / "taylor-gold.ndjson",
        default_artifact=FIXTURES / "taylor-iter-after.json",
        asset_hosts=("doi.org",),
    ),
    "oup": PublisherSpec(
        name="oup",
        parser_import="parseland_lib.publisher.parsers.oxford:Oxford",
        default_gold=FIXTURES / "oup-gold.ndjson",
        default_artifact=FIXTURES / "oup-iter-after.json",
        asset_hosts=("doi.org",),
    ),
    "sage": PublisherSpec(
        name="sage",
        parser_import="parseland_lib.publisher.parsers.sage:Sage",
        default_gold=FIXTURES / "sage-gold.ndjson",
        default_artifact=FIXTURES / "sage-iter-after.json",
        asset_hosts=("doi.org",),
    ),
    "wolters_kluwer": PublisherSpec(
        name="wolters_kluwer",
        parser_import="parseland_lib.publisher.parsers.lippincott:Lippincott",
        default_gold=FIXTURES / "wolters-kluwer-gold.ndjson",
        default_artifact=FIXTURES / "wolters-kluwer-iter-after.json",
        # LWW serves landing + PDF from the same host (journals.lww.com), so
        # 'endswith' would wrongly drop the article landing too. Use 'in_url'
        # and mark only the PDF-download stub paths as assets; doi.org marks
        # un-followed redirect stubs.
        asset_hosts=("doi.org", "downloadpdf.aspx", "oaks.journals"),
        asset_match="in_url",
    ),
}


def _load_parser_class(import_spec: str):
    """Resolve a 'module.path:ClassName' string to the class object."""
    module_path, class_name = import_spec.split(":")
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def resolve_latest_harvest_uuid(doi: str, spec: PublisherSpec) -> str | None:
    """Return the best harvest UUID for ``doi`` for in-process parsing.

    Taxicab's html[] can contain multiple records per DOI — the article landing
    page AND any redirect targets the harvester followed (asset CDNs whose
    stored "html" is just a binary stub). Prefer article-landing records over
    asset records, with most-recent-by-created_date as the tiebreaker.
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

    def _host(rec: dict) -> str:
        return (urlparse(rec.get("resolved_url") or "").hostname or "").lower()

    def _is_asset(rec: dict) -> bool:
        if spec.asset_match == "in_url":
            url = (rec.get("resolved_url") or "").lower()
            return any(h in url for h in spec.asset_hosts)
        host = _host(rec)
        return bool(host) and any(host.endswith(h) for h in spec.asset_hosts)

    article_records = [r for r in records if _host(r) and not _is_asset(r)]
    if article_records:
        best = max(article_records, key=lambda h: h.get("created_date") or "")
        return best.get("id")

    latest = max(records, key=lambda h: h.get("created_date") or "")
    return latest.get("id")


def _make_r2_client():
    load_dotenv(str(REPO_ROOT / ".env"), override=True)
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def parse_in_process(html: str, parser_cls, skip_non_dispatched: bool = True) -> dict:
    """Run ``<parser_cls>(soup).parse()`` directly. No HTTP, no dispatcher.

    When ``skip_non_dispatched`` is True (default), rows where the parser's own
    ``is_publisher_specific_parser()`` returns False are reported as
    ``_dispatch_skipped`` and excluded from scoring aggregates. This eliminates
    cross-publisher routing noise: an Elsevier-prefixed DOI that actually lives
    on Oxford Academic's Atypon portal will be skipped instead of being
    force-scored as a zero. Production never reaches the wrong parser for these
    rows — production routes via ``is_publisher_specific_parser`` — so scoring
    them is a measurement artifact, not a real parser failure.

    Returns the same shape parseland's HTTP path returns. PDF / license /
    version come from ``parse_publisher_fulltext_location`` to mirror the
    production ``parse_page`` pipeline; without that call the in-process eval
    would report zero PDFs for parsers that don't surface ``urls`` directly.
    """
    soup = BeautifulSoup(html, "lxml")
    parser = parser_cls(soup)

    if skip_non_dispatched:
        try:
            dispatched = bool(parser.is_publisher_specific_parser())
        except Exception:  # noqa: BLE001
            # Some parsers raise on unusual HTML; treat as not-dispatched.
            dispatched = False
        if not dispatched:
            return {
                "_authors_found": False,
                "_dispatch_skipped": True,
                "authors": [],
                "urls": [],
                "license": None,
                "version": None,
                "abstract": None,
            }

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
    """Normalize gold authors via parseland-eval's coercion helper."""
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
    """Apply the five parseland-eval scorers to a single parsed/gold pair."""
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


def fmt_score_line(
    doi: str,
    has_bot_check: bool,
    score: dict,
    elapsed: float,
    authors_found: bool,
    target_field: str,
) -> str:
    """One-line summary for stdout. Highlights the target field with [brackets]."""
    bot = "(BOT-CHECK)" if has_bot_check else "          "
    a = score["authors"].get("f1_soft")
    af = score["affiliations"].get("avg_soft_f1")
    ab = score["abstract"]
    pdf = score["pdf_url"]
    cf = score["corresponding"].get("f1")
    found_mark = "✓" if authors_found else "✗"
    a_str = f"{a:.2f}" if a is not None else "  - "
    af_str = f"{af:.2f}" if af is not None else "  - "
    ab_str = "1.00 (✓)" if ab.get("match_at_threshold") else f"{ab.get('fuzzy_ratio', 0):.2f} (✗)"
    pdf_str = "✓" if pdf.get("strict_match") else "✗"
    cf_str = f"{cf:.2f}" if cf is not None else "  - "

    def hl(label: str, value: str) -> str:
        return f"[{label} {value}]" if target_field == label.lower() or (
            target_field == "pdf_url" and label == "pdf"
        ) else f"{label} {value}"

    return (
        f"  found={found_mark}  {doi:<40} {bot}  "
        f"{hl('auth', a_str)}  {hl('aff', af_str)}  {hl('abs', ab_str)}  "
        f"{hl('pdf', pdf_str)}  {hl('corresp', cf_str)}  ({elapsed:.1f}s)"
    )


def aggregate_scored(scored: list[dict]) -> dict:
    """Reduce per-row scores into the artifact's aggregate block."""
    n = len(scored)
    eligible_a = [r for r in scored if r["score"]["authors"].get("gold_total", 0) > 0]
    eligible_aff = [r for r in scored if r["score"]["affiliations"].get("pairs_scored", 0) > 0]
    abs_matched = sum(1 for r in scored if r["score"]["abstract"].get("match_at_threshold"))
    pdf_eligible = [r for r in scored if r["score"]["pdf_url"].get("strict_match") is not None]
    pdf_matched = sum(1 for r in pdf_eligible if r["score"]["pdf_url"].get("strict_match"))

    a_mean = (
        sum(r["score"]["authors"]["f1_soft"] for r in eligible_a) / len(eligible_a)
        if eligible_a
        else None
    )
    aff_mean = (
        sum(r["score"]["affiliations"]["avg_soft_f1"] for r in eligible_aff) / len(eligible_aff)
        if eligible_aff
        else None
    )

    tp = sum(r["score"]["corresponding"].get("tp", 0) for r in scored)
    fp = sum(r["score"]["corresponding"].get("fp", 0) for r in scored)
    fn = sum(r["score"]["corresponding"].get("fn", 0) for r in scored)
    prec = tp / (tp + fp) if (tp + fp) > 0 else None
    rec = tp / (tp + fn) if (tp + fn) > 0 else None
    corresp_f1 = (
        2 * prec * rec / (prec + rec) if prec is not None and rec is not None and (prec + rec) > 0 else None
    )

    n_authors_found = sum(1 for r in scored if r.get("authors_found"))

    return {
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
    }


def run_diff(
    spec: PublisherSpec,
    gold_path: Path,
    artifact_path: Path,
    target_field: str,
    skip_non_dispatched: bool = True,
) -> dict:
    """End-to-end: load gold, resolve UUIDs, parse, score, aggregate, write artifact.

    ``skip_non_dispatched`` controls whether rows that the parser's own
    ``is_publisher_specific_parser()`` rejects are counted in the aggregate. See
    ``parse_in_process`` for the rationale.
    """
    if not gold_path.exists():
        print(f"ERROR: {gold_path} not found", file=sys.stderr)
        sys.exit(1)

    rows = []
    with gold_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    print(f"loaded {len(rows)} {spec.name} gold rows from {gold_path.name}\n")

    parser_cls = _load_parser_class(spec.parser_import)
    s3 = _make_r2_client()
    scored: list[dict] = []
    failed: list[dict] = []
    dispatch_skipped: list[dict] = []

    from parseland_lib.audit.progress import ProgressLogger  # noqa: E402

    job_id = f"inprocess-diff-{artifact_path.stem}"
    use_progress = os.environ.get("PARSELAND_NO_PROGRESS") != "1"
    progress = (
        ProgressLogger(
            job_id=job_id,
            total=len(rows),
            label=f"{spec.name} inprocess diff → {artifact_path.name}",
        )
        if use_progress
        else None
    )
    p = progress.__enter__() if progress is not None else None

    for row in rows:
        doi = row.get("doi", "")
        gold = row.get("annotation") or {}
        has_bot_check = bool(row.get("has_bot_check"))
        t0 = time.time()

        try:
            uuid = resolve_latest_harvest_uuid(doi, spec)
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

        parsed = parse_in_process(html, parser_cls, skip_non_dispatched=skip_non_dispatched)

        if parsed.get("_dispatch_skipped"):
            elapsed = time.time() - t0
            dispatch_skipped.append(
                {
                    "doi": doi,
                    "harvest_uuid": uuid,
                    "publisher_domain": row.get("publisher_domain"),
                    "elapsed_seconds": round(elapsed, 2),
                }
            )
            print(
                f"  skip  {doi:<40}  (not dispatched to {spec.name}; "
                f"is_publisher_specific_parser=False)  ({elapsed:.1f}s)"
            )
            if p is not None:
                p.row(doi=doi, action="dispatch_skipped", elapsed=elapsed)
                p.heartbeat()
            continue

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
        print(fmt_score_line(doi, has_bot_check, score, elapsed, parsed.get("_authors_found"), target_field))
        if p is not None:
            p.row(
                doi=doi,
                action="scored",
                elapsed=elapsed,
                extra={
                    "f1_soft": score["authors"].get("f1_soft"),
                    "aff_f1": score["affiliations"].get("avg_soft_f1"),
                },
            )
            p.heartbeat()

    agg = aggregate_scored(scored)

    if failed:
        print(f"\n=== Failures ({len(failed)}) ===")
        for f in failed:
            print(f"    {f['doi']}  stage={f['stage']}  err={f['error']}")
    else:
        print("\nfailed: 0")

    n = agg["n_rows"]
    print(f"\n========== TL;DR AGGREGATE (n={n}, publisher={spec.name}, target_field={target_field}) ==========")
    print(f"  {spec.name}.authors_found(): {agg['n_authors_found']}/{n} rows")
    a_mean = agg["authors_mean_f1_soft"]
    aff_mean = agg["affiliations_mean_soft_f1"]
    if a_mean is not None:
        print(f"  Authors      mean F1_soft: {a_mean:.3f}  ({agg['authors_eligible_count']}/{n} eligible)")
    if aff_mean is not None:
        print(f"  Affiliations mean F1_soft: {aff_mean:.3f}  ({agg['affiliations_pairs_scored_rows']}/{n} rows had matched pairs)")
    if n:
        print(f"  Abstract     match@0.74:   {agg['abstract_match_at_074']}/{n} rows ({100*agg['abstract_match_at_074']/n:.1f}%)")
    if agg["pdf_eligible_count"]:
        print(f"  PDF URL      strict match: {agg['pdf_strict_match']}/{agg['pdf_eligible_count']} gold-truthed rows")
    corresp = agg["corresponding"]
    if corresp["micro_f1"] is not None:
        print(
            f"  Corresp      micro F1:     {corresp['micro_f1']:.3f}  "
            f"(P {corresp['precision']:.3f} / R {corresp['recall']:.3f}, "
            f"tp/fp/fn = {corresp['tp']}/{corresp['fp']}/{corresp['fn']})"
        )
    print(f"  failed: {len(failed)} / {n + len(failed) + len(dispatch_skipped)} input rows")
    if dispatch_skipped:
        print(
            f"  dispatch-skipped: {len(dispatch_skipped)} rows "
            f"(parser self-rejected — cross-publisher routing artifact)"
        )
    print("=" * 47)

    method_suffix = (
        " (skip_non_dispatched=on)" if skip_non_dispatched else " (skip_non_dispatched=off)"
    )
    artifact = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "publisher": spec.name,
        "target_field": target_field,
        "source_ndjson": str(gold_path),
        "measurement_method": (
            f"in-process {spec.name}.parse() — no HTTP, no dispatcher" + method_suffix
        ),
        "scorer_source": "parseland-eval/eval/parseland_eval/score/*.py",
        "skip_non_dispatched": skip_non_dispatched,
        "aggregate": agg,
        "scored_rows": scored,
        "failed_rows": failed,
        "dispatch_skipped_rows": dispatch_skipped,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, default=str))
    print(f"\n  artifact: {artifact_path}")

    if p is not None:
        p.done(
            summary={
                "artifact": str(artifact_path),
                "publisher": spec.name,
                "n_rows": n,
                "authors_mean_f1_soft": round(a_mean, 4) if a_mean is not None else None,
                "affiliations_mean_soft_f1": round(aff_mean, 4) if aff_mean is not None else None,
                "abstract_match_at_074": agg["abstract_match_at_074"],
                "pdf_strict_match": agg["pdf_strict_match"],
                "corresp_micro_f1": round(corresp["micro_f1"], 4) if corresp["micro_f1"] is not None else None,
                "failed": len(failed),
            }
        )
        progress.__exit__(None, None, None)

    return artifact


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Generalized in-process parser diff against gold NDJSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--publisher",
        required=True,
        choices=sorted(PUBLISHER_REGISTRY.keys()),
        help="Publisher key — selects parser class and default paths.",
    )
    ap.add_argument(
        "--field",
        default="authors",
        choices=VALID_FIELDS,
        help="Target field for this diff. Informational only — all 5 scorers always run.",
    )
    ap.add_argument(
        "--gold",
        type=Path,
        default=None,
        help="Path to gold NDJSON. Defaults to per-publisher fixture.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Path to write the artifact JSON. Defaults to per-publisher fixture.",
    )
    ap.add_argument(
        "--include-non-dispatched",
        action="store_true",
        help=(
            "Score every gold row, even when the parser's is_publisher_specific_parser() "
            "returns False. Off by default — set to reproduce the old noisy aggregate."
        ),
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    spec = PUBLISHER_REGISTRY[args.publisher]
    gold_path = args.gold or spec.default_gold
    artifact_path = args.out or spec.default_artifact
    run_diff(
        spec,
        gold_path,
        artifact_path,
        args.field,
        skip_non_dispatched=not args.include_non_dispatched,
    )


if __name__ == "__main__":
    main()
