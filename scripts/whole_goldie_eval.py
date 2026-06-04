#!/usr/bin/env python3
"""Whole-Goldie eval adapter (component 1.B).

Scores parseland-lib against the 10,000-row merged-FINAL.csv corpus and emits
a run JSON matching the schema of eval/runs/*.json so Shield's diff logic
works unchanged.

Honest about limitations:
- Rows are skipped (and counted) when no claim is present in the column.
- Rows are skipped (and listed) when no HTML is cached.
- Records adapter version + skip stats in the run JSON.

Two modes:
- run (default): score every row that has cached HTML and a non-empty claim.
- fetch: populate the HTML cache by Taxicab UUID resolve + R2 read.
         (Use sparingly — fetches 10K rows can take hours.)

The HTML cache lives at mismatches/whole-goldie-cache/<sha1>.html keyed by
the lowercased DOI, mirroring eval/html-cache/.

Usage:
    python scripts/whole_goldie_eval.py run \\
        --corpus /Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv \\
        --out eval/runs/whole-goldie-<label>-<ts>.json \\
        --limit 100 --label smoke

    python scripts/whole_goldie_eval.py fetch \\
        --corpus /Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv \\
        --limit 100
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_PARSELAND_EVAL_PATH = os.environ.get(
    "PARSELAND_EVAL_PATH",
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval",
)
sys.path.insert(0, _PARSELAND_EVAL_PATH)

from scripts.lib.publisher_index import classify_row, _load_registrant_cache  # noqa: E402
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

ADAPTER_NAME = "whole_goldie_eval"
ADAPTER_VERSION = "0.1.0"

HTML_CACHE_DIR = REPO_ROOT / "mismatches" / "whole-goldie-cache"


def _doi_hash(doi: str) -> str:
    return hashlib.sha1(doi.lower().encode()).hexdigest()


def _cache_path(doi: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_doi_hash(doi)}.html"


def _read_cached(doi: str, cache_dir: Path) -> str | None:
    p = _cache_path(doi, cache_dir)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _parse_authors_column(raw: str) -> list[dict[str, Any]]:
    """merged-FINAL.csv Authors column: JSON string with 'rasses' or
    'affiliations' keys, 'corresponding_author' bool. Returns list of dicts
    with 'name', 'affiliations' (list[str]), 'is_corresponding' (bool|None).
    """
    if not raw or not raw.strip():
        return []
    try:
        arr = json.loads(raw)
    except Exception:
        return []
    if not isinstance(arr, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in arr:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        affs_raw = entry.get("affiliations") or entry.get("rasses") or ""
        if isinstance(affs_raw, str):
            affs = [a.strip() for a in affs_raw.split(";") if a.strip()] if affs_raw else []
        elif isinstance(affs_raw, list):
            affs = [str(a).strip() for a in affs_raw if str(a).strip()]
        else:
            affs = []
        corresp = entry.get("corresponding_author")
        if corresp is None:
            corresp = entry.get("is_corresponding")
        out.append({
            "name": name,
            "affiliations": affs,
            "is_corresponding": bool(corresp) if corresp is not None else None,
        })
    return out


@dataclass
class GoldRowLite:
    """Minimal gold-row shape compatible with the scorers."""
    no: int
    doi: str
    link: str
    authors: list[dict[str, Any]]
    abstract: str | None
    pdf_url: str | None


@dataclass
class GoldAuthorAdapter:
    """Shim matching the scorer's GoldAuthor interface."""
    name: str
    affiliations: tuple[str, ...]
    is_corresponding: bool | None


def _to_gold_authors(authors: list[dict[str, Any]]) -> tuple[GoldAuthorAdapter, ...]:
    return tuple(
        GoldAuthorAdapter(
            name=a["name"],
            affiliations=tuple(a["affiliations"]),
            is_corresponding=a["is_corresponding"],
        )
        for a in authors
    )


def _publisher_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def _iter_corpus(corpus_path: Path, limit: int | None, publishers: set[str] | None,
                 reg_cache: dict) -> list[GoldRowLite]:
    rows: list[GoldRowLite] = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader, start=1):
            if limit and len(rows) >= limit:
                break
            doi = (raw.get("DOI") or "").strip()
            if not doi:
                continue
            if publishers is not None:
                pub = classify_row(raw, allow_network=False, _cache=reg_cache)
                if pub not in publishers:
                    continue
            authors = _parse_authors_column(raw.get("Authors") or "")
            abstract = (raw.get("Abstract") or "").strip() or None
            pdf_url = (raw.get("PDF URL") or "").strip() or None
            rows.append(GoldRowLite(
                no=int(raw.get("No") or i),
                doi=doi,
                link=(raw.get("Link") or "").strip(),
                authors=authors,
                abstract=abstract,
                pdf_url=pdf_url,
            ))
    return rows


def _parse_and_score(row: GoldRowLite, cache_dir: Path) -> dict[str, Any]:
    from parseland_lib.parse import parse_page  # type: ignore[import-not-found]
    from parseland_eval.score.abstract import score_abstract
    from parseland_eval.score.affiliations import score_affiliations
    from parseland_eval.score.authors import score_authors, score_corresponding
    from parseland_eval.score.pdf_url import score_pdf_url

    html = _read_cached(row.doi, cache_dir)
    if html is None:
        return {
            "doi": row.doi,
            "error": "html-not-cached",
            "skipped_no_html": True,
            "publisher_domain": _publisher_domain(row.link),
        }

    start = time.perf_counter()
    parsed = None
    err = None
    try:
        parsed = parse_page(html, namespace="doi", resolved_url=row.link)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"
    duration_ms = (time.perf_counter() - start) * 1000.0

    gold_authors = _to_gold_authors(row.authors)
    parsed_authors = (parsed or {}).get("authors") or []
    parsed_abstract = (parsed or {}).get("abstract")

    # Scoring — be defensive about empty inputs and skipped fields.
    field_scores: dict[str, Any] = {}
    skipped_no_claim: list[str] = []

    if gold_authors:
        a_res = score_authors(gold_authors, parsed_authors)
        field_scores["authors"] = {
            "f1": a_res.f1_strict,
            "f1_soft": a_res.f1_soft,
        }
    else:
        skipped_no_claim.append("authors")

    if gold_authors:
        aff_res = score_affiliations(gold_authors, parsed_authors)
        field_scores["affiliations"] = {
            "f1": aff_res.f1_strict,
            "f1_soft": aff_res.f1_soft,
            "f1_fuzzy": aff_res.f1_fuzzy,
        }
        c_res = score_corresponding(gold_authors, parsed_authors)
        field_scores["corresponding"] = {"accuracy": c_res.accuracy}

    if row.abstract:
        ab_res = score_abstract(row.abstract, parsed_abstract)
        field_scores["abstract"] = {
            "strict_match": ab_res.strict_match,
            "soft_ratio": ab_res.soft_ratio,
            "fuzzy_ratio": ab_res.fuzzy_ratio,
            "present": ab_res.present,
        }
    else:
        skipped_no_claim.append("abstract")

    if row.pdf_url:
        pdf_res = score_pdf_url(row.pdf_url, parsed)
        field_scores["pdf_url"] = {
            "exact_match": pdf_res.exact_match,
            "accuracy": 1.0 if pdf_res.exact_match else 0.0,
        }
    else:
        skipped_no_claim.append("pdf_url")

    return {
        "no": row.no,
        "doi": row.doi,
        "link": row.link,
        "publisher_domain": _publisher_domain(row.link),
        "error": err,
        "duration_ms": duration_ms,
        "skipped_no_html": False,
        "skipped_no_claim": skipped_no_claim,
        "score": field_scores,
        "gold": {
            "n_authors": len(gold_authors),
            "abstract_len": len(row.abstract) if row.abstract else 0,
            "has_pdf_url": bool(row.pdf_url),
        },
        "parsed": {
            "n_authors": len(parsed_authors),
            "abstract_len": len((parsed or {}).get("abstract") or ""),
            "urls": (parsed or {}).get("urls") or [],
        } if parsed else None,
    }


def _aggregate(rows_out: list[dict], reg_cache: dict) -> dict[str, Any]:
    """Build summary.overall + summary.per_publisher.

    Numbers are averaged across the rows that actually had a claim for each
    field. Errors and skip counts are top-level counters.
    """
    by_pub: dict[str, list[dict]] = defaultdict(list)
    for r in rows_out:
        # Classify by DOI prefix using the row's link; this is the same scheme
        # the ranker uses so per_publisher keys align.
        # Reconstruct a minimal "row" dict for classify_row.
        pub = classify_row({"DOI": r["doi"], "Link": r.get("link", "")},
                           allow_network=False, _cache=reg_cache)
        by_pub[pub].append(r)

    def field_avg(items: list[dict], field: str, metric: str) -> tuple[float, int]:
        vals: list[float] = []
        for it in items:
            s = (it.get("score") or {}).get(field)
            if isinstance(s, dict) and metric in s:
                v = s[metric]
                if isinstance(v, (int, float)):
                    vals.append(float(v))
        if not vals:
            return (0.0, 0)
        return (sum(vals) / len(vals), len(vals))

    def summarize_group(items: list[dict]) -> dict[str, Any]:
        n = len(items)
        skipped_no_html = sum(1 for it in items if it.get("skipped_no_html"))
        # Parser-crash errors only — exclude rows where we simply had no HTML.
        errors = sum(
            1 for it in items
            if it.get("error") and not it.get("skipped_no_html")
        )
        scored = n - skipped_no_html
        a_strict, a_strict_n = field_avg(items, "authors", "f1")
        a_soft, a_soft_n = field_avg(items, "authors", "f1_soft")
        af_fuzzy, af_fuzzy_n = field_avg(items, "affiliations", "f1_fuzzy")
        af_strict, af_strict_n = field_avg(items, "affiliations", "f1")
        ab_fuzzy, ab_fuzzy_n = field_avg(items, "abstract", "fuzzy_ratio")
        ab_present = sum(
            1 for it in items
            if (it.get("score") or {}).get("abstract", {}).get("present")
        )
        pdf_acc, pdf_n = field_avg(items, "pdf_url", "accuracy")
        c_acc, c_n = field_avg(items, "corresponding", "accuracy")
        mean_dur = (
            sum(it.get("duration_ms", 0.0) for it in items) / max(scored, 1)
        )
        return {
            "rows": n,
            "scored": scored,
            "errors": errors,
            "skipped_no_html": skipped_no_html,
            "authors_f1_strict": a_strict,
            "authors_f1_soft": a_soft,
            "affiliations_f1_strict": af_strict,
            "affiliations_f1_fuzzy": af_fuzzy,
            "abstract_ratio_fuzzy": ab_fuzzy,
            "abstract_present_rate": (ab_present / max(scored, 1)) if scored else 0.0,
            "pdf_url_accuracy": pdf_acc,
            "corresponding_accuracy": c_acc,
            "duration_ms_mean": mean_dur,
            "n_authors_scored": a_soft_n,
            "n_pdf_scored": pdf_n,
            "n_corresponding_scored": c_n,
            "n_abstract_scored": ab_fuzzy_n,
        }

    overall = summarize_group(rows_out)
    per_publisher = {pub: summarize_group(items) for pub, items in sorted(by_pub.items())}
    return {"overall": overall, "per_publisher": per_publisher}


def run_eval(
    corpus_path: Path,
    *,
    out_path: Path,
    label: str,
    limit: int | None = None,
    publishers: set[str] | None = None,
    cache_dir: Path = HTML_CACHE_DIR,
    concurrency: int = 4,
    run_id: str | None = None,
) -> dict:
    run_id = run_id or new_run_id()
    t_start = time.time()
    reg_cache = _load_registrant_cache()

    emit(run_id=run_id, action="whole_goldie.start", agent_name="whole_goldie_eval",
         notes=f"corpus={corpus_path.name} label={label} limit={limit or 'all'}")

    rows = _iter_corpus(corpus_path, limit, publishers, reg_cache)
    rows_out: list[dict] = []

    if concurrency <= 1:
        for i, r in enumerate(rows):
            rows_out.append(_parse_and_score(r, cache_dir))
            if (i + 1) % 100 == 0:
                emit(run_id=run_id, action="whole_goldie.progress",
                     agent_name="whole_goldie_eval",
                     progress_current=i + 1, progress_total=len(rows))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(_parse_and_score, r, cache_dir): r for r in rows}
            done = 0
            for fut in as_completed(futures):
                rows_out.append(fut.result())
                done += 1
                if done % 100 == 0:
                    emit(run_id=run_id, action="whole_goldie.progress",
                         agent_name="whole_goldie_eval",
                         progress_current=done, progress_total=len(rows))

    summary = _aggregate(rows_out, reg_cache)
    skipped_no_html_dois = [r["doi"] for r in rows_out if r.get("skipped_no_html")]
    skipped_no_claim = defaultdict(int)
    for r in rows_out:
        for f in r.get("skipped_no_claim") or []:
            skipped_no_claim[f] += 1

    run_obj = {
        "run_id": run_id,
        "label": label,
        "adapter": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_path": str(corpus_path),
        "row_count_corpus": len(rows),
        "skipped_no_html_count": len(skipped_no_html_dois),
        "skipped_no_html_dois": skipped_no_html_dois[:100],  # cap to 100 for readability
        "skipped_no_claim": dict(skipped_no_claim),
        "summary": summary,
        "rows": rows_out,
        "duration_ms": int((time.time() - t_start) * 1000),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(run_obj, indent=2, default=str))

    emit(
        run_id=run_id,
        action="whole_goldie.complete",
        agent_name="whole_goldie_eval",
        progress_current=len(rows),
        progress_total=len(rows),
        duration_ms=run_obj["duration_ms"],
        artifact_path=str(out_path),
        kpi_after=summary["overall"]["authors_f1_soft"],
        notes=(f"scored={summary['overall']['scored']} errors={summary['overall']['errors']} "
               f"skipped_no_html={len(skipped_no_html_dois)}"),
    )
    return run_obj


def cmd_run(args: argparse.Namespace) -> int:
    out = args.out
    if out is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = REPO_ROOT / "eval" / "runs" / f"whole-goldie-{args.label}-{ts}.json"
    publishers = set(args.publishers.split(",")) if args.publishers else None
    run_obj = run_eval(
        args.corpus,
        out_path=out,
        label=args.label,
        limit=args.limit,
        publishers=publishers,
        cache_dir=args.cache_dir,
        concurrency=args.concurrency,
        run_id=args.run_id,
    )
    s = run_obj["summary"]["overall"]
    print(
        f"\n─── Whole-Goldie Eval — {run_obj['row_count_corpus']} rows "
        f"(skipped_no_html={run_obj['skipped_no_html_count']}, "
        f"errors={s['errors']}) ───\n"
        f"  Authors      F1 soft  : {s['authors_f1_soft']:.3f}   strict: {s['authors_f1_strict']:.3f}\n"
        f"  Affiliations F1 fuzzy : {s['affiliations_f1_fuzzy']:.3f}   strict: {s['affiliations_f1_strict']:.3f}\n"
        f"  Abstract     ratio    : {s['abstract_ratio_fuzzy']:.3f}   present_rate: {s['abstract_present_rate']:.3f}\n"
        f"  PDF URL      accuracy : {s['pdf_url_accuracy']:.3f}\n"
        f"  Corresponding acc    : {s['corresponding_accuracy']:.3f}\n"
        f"  Mean duration (ms)  : {s['duration_ms_mean']:.1f}\n"
        f"\n  run file: {out}"
    )
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """Populate the HTML cache by Taxicab UUID resolve + R2 read.

    Imports field_inprocess_diff's resolve+R2 helpers so we don't duplicate
    the credentials/cred-handling logic.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from field_inprocess_diff import (  # type: ignore  # noqa: E402
        resolve_latest_harvest_uuid,
        PUBLISHER_REGISTRY,
    )
    from parseland_lib.s3 import get_landing_page_from_r2  # type: ignore  # noqa: E402

    reg_cache = _load_registrant_cache()
    publishers = set(args.publishers.split(",")) if args.publishers else None
    rows = _iter_corpus(args.corpus, args.limit, publishers, reg_cache)
    cache_dir = args.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    fetched = skipped = errors = 0
    for r in rows:
        p = _cache_path(r.doi, cache_dir)
        if p.exists() and not args.force:
            skipped += 1
            continue
        pub = classify_row({"DOI": r.doi, "Link": r.link}, allow_network=False,
                           _cache=reg_cache)
        spec = PUBLISHER_REGISTRY.get(pub)
        try:
            uuid = resolve_latest_harvest_uuid(r.doi, spec) if spec else None
            if not uuid:
                # generic fallback: try the first available UUID via parseland-eval API
                from parseland_eval.api import resolve_doi_to_uuid  # type: ignore
                uuid = resolve_doi_to_uuid(r.doi)
            if not uuid:
                errors += 1
                continue
            html = get_landing_page_from_r2(uuid)
            if not html:
                errors += 1
                continue
            p.write_text(html, encoding="utf-8", errors="replace")
            fetched += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"fetch error for {r.doi}: {exc}", file=sys.stderr)

    print(f"fetch summary: fetched={fetched} skipped_cached={skipped} errors={errors} total={len(rows)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Parse cached HTML and score against the corpus")
    r.add_argument("--corpus", type=Path, required=True)
    r.add_argument("--out", type=Path)
    r.add_argument("--label", type=str, default="whole-goldie")
    r.add_argument("--limit", type=int)
    r.add_argument("--publishers", type=str, help="Comma-separated publisher_ids to include")
    r.add_argument("--cache-dir", type=Path, default=HTML_CACHE_DIR)
    r.add_argument("--concurrency", type=int, default=4)
    r.add_argument("--run-id", type=str)
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("fetch", help="Populate HTML cache from Taxicab + R2")
    f.add_argument("--corpus", type=Path, required=True)
    f.add_argument("--limit", type=int)
    f.add_argument("--publishers", type=str)
    f.add_argument("--cache-dir", type=Path, default=HTML_CACHE_DIR)
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=cmd_fetch)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
