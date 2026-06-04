#!/usr/bin/env python3
"""Fill mismatches/whole-goldie-cache/ for the 10K Goldie via Taxicab + R2.

Reads merged-FINAL.csv, identifies rows with missing HTML, resolves each DOI
to a harvest UUID via Taxicab, reads HTML from R2 (Cloudflare), and writes
to the local cache keyed by SHA1(lowercase DOI).

Mirrors the proven flow from scripts/field_inprocess_diff.py but operates on
the corpus level rather than per-publisher fixtures.

Skips:
- already-cached rows (unless --force)
- rows whose DOI is empty
- rows where publisher classifies to 'unknown' (skipped by default — pass
  --include-unknown to attempt anyway)

Usage:
    python scripts/retrieval_fill.py \\
        --corpus /Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv \\
        --cache-dir mismatches/whole-goldie-cache \\
        --concurrency 16 \\
        --limit 100               # smoke run; omit to process the full corpus
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
_PARSELAND_EVAL_PATH = os.environ.get(
    "PARSELAND_EVAL_PATH",
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval",
)
sys.path.insert(0, _PARSELAND_EVAL_PATH)

from scripts.lib.publisher_index import classify_row, _load_registrant_cache  # noqa: E402
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

DEFAULT_CACHE_DIR = REPO_ROOT / "mismatches" / "whole-goldie-cache"
TAXICAB_TIMEOUT_S = 15
R2_TIMEOUT_S = 20


# Thread-local boto3 client (boto3 clients are NOT thread-safe by default).
_local = threading.local()


def _doi_hash(doi: str) -> str:
    return hashlib.sha1(doi.lower().encode()).hexdigest()


def _cache_path(doi: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_doi_hash(doi)}.html"


def _get_r2_client():
    if not hasattr(_local, "s3"):
        import boto3
        from dotenv import load_dotenv
        load_dotenv(str(REPO_ROOT / ".env"), override=True)
        account_id = os.environ["R2_ACCOUNT_ID"]
        _local.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
    return _local.s3


@dataclass
class FetchOutcome:
    doi: str
    publisher: str
    status: str          # ok | missing_uuid | r2_404 | r2_error | taxicab_error | exception | cached
    size: int = 0
    error: str | None = None
    duration_ms: int = 0


def fetch_one(doi: str, publisher: str, cache_dir: Path,
              *, force: bool = False) -> FetchOutcome:
    if not doi:
        return FetchOutcome(doi="", publisher=publisher, status="exception",
                            error="empty doi")
    p = _cache_path(doi, cache_dir)
    if p.exists() and not force:
        return FetchOutcome(doi=doi, publisher=publisher, status="cached",
                            size=p.stat().st_size)
    t0 = time.time()
    # 1. Taxicab — resolve harvest UUID
    try:
        from parseland_eval.api import resolve_harvest_uuid  # type: ignore
        uuid, call = resolve_harvest_uuid(doi)
    except Exception as exc:
        return FetchOutcome(doi=doi, publisher=publisher, status="taxicab_error",
                            error=f"{type(exc).__name__}: {exc}",
                            duration_ms=int((time.time() - t0) * 1000))
    if not uuid:
        return FetchOutcome(doi=doi, publisher=publisher, status="missing_uuid",
                            duration_ms=int((time.time() - t0) * 1000))
    # 2. R2 — fetch HTML by UUID
    try:
        from parseland_lib.s3 import get_landing_page_from_r2  # type: ignore
        from parseland_lib.exceptions import S3FileNotFoundError  # type: ignore
        s3 = _get_r2_client()
        html = get_landing_page_from_r2(uuid, s3)
        if html is None:
            # PDF-only record (no HTML)
            return FetchOutcome(doi=doi, publisher=publisher, status="r2_404",
                                error="harvest is PDF-only",
                                duration_ms=int((time.time() - t0) * 1000))
    except S3FileNotFoundError:
        return FetchOutcome(doi=doi, publisher=publisher, status="r2_404",
                            error="no R2 object for uuid",
                            duration_ms=int((time.time() - t0) * 1000))
    except Exception as exc:
        return FetchOutcome(doi=doi, publisher=publisher, status="r2_error",
                            error=f"{type(exc).__name__}: {exc}",
                            duration_ms=int((time.time() - t0) * 1000))
    # 3. Write to disk
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(html, bytes):
            p.write_bytes(html)
        else:
            p.write_text(str(html), encoding="utf-8", errors="replace")
        return FetchOutcome(doi=doi, publisher=publisher, status="ok",
                            size=p.stat().st_size,
                            duration_ms=int((time.time() - t0) * 1000))
    except Exception as exc:
        return FetchOutcome(doi=doi, publisher=publisher, status="exception",
                            error=f"{type(exc).__name__}: {exc}",
                            duration_ms=int((time.time() - t0) * 1000))


def iter_rows(corpus_path: Path, limit: int | None,
              publishers: set[str] | None,
              include_unknown: bool,
              reg_cache: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = (row.get("DOI") or "").strip()
            if not doi:
                continue
            pub = classify_row(row, allow_network=False, _cache=reg_cache)
            if pub == "unknown" and not include_unknown:
                continue
            if publishers is not None and pub not in publishers:
                continue
            rows.append((doi, pub))
            if limit and len(rows) >= limit:
                break
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--limit", type=int)
    p.add_argument("--publishers", type=str,
                   help="Comma-separated publisher_ids to include.")
    p.add_argument("--include-unknown", action="store_true",
                   help="Attempt fetch for rows where publisher classification "
                        "fails (off by default).")
    p.add_argument("--force", action="store_true",
                   help="Re-fetch even if cached.")
    p.add_argument("--run-id", type=str)
    p.add_argument("--report-every", type=int, default=200,
                   help="Emit a ledger progress event every N completions.")
    args = p.parse_args()

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 2

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    reg_cache = _load_registrant_cache()
    publishers = set(args.publishers.split(",")) if args.publishers else None
    rows = iter_rows(args.corpus, args.limit, publishers,
                     args.include_unknown, reg_cache)

    run_id = args.run_id or new_run_id()
    emit(run_id=run_id, action="fill.start", agent_name="retrieval_fill",
         progress_total=len(rows),
         notes=f"corpus={args.corpus.name} concurrency={args.concurrency} "
               f"target_rows={len(rows)}")

    state_counts: dict[str, int] = {}
    per_publisher_state: dict[str, dict[str, int]] = {}
    t0 = time.time()
    completed = 0
    bytes_written = 0

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = {pool.submit(fetch_one, doi, pub, args.cache_dir,
                            force=args.force): (doi, pub) for doi, pub in rows}
        for fut in as_completed(futs):
            outcome = fut.result()
            state_counts[outcome.status] = state_counts.get(outcome.status, 0) + 1
            d = per_publisher_state.setdefault(outcome.publisher, {})
            d[outcome.status] = d.get(outcome.status, 0) + 1
            if outcome.status == "ok":
                bytes_written += outcome.size
            completed += 1
            if completed % args.report_every == 0:
                emit(run_id=run_id, action="fill.progress",
                     agent_name="retrieval_fill",
                     progress_current=completed, progress_total=len(rows),
                     notes=json.dumps(state_counts))

    duration_ms = int((time.time() - t0) * 1000)
    summary = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_path": str(args.corpus),
        "cache_dir": str(args.cache_dir),
        "target_rows": len(rows),
        "completed_rows": completed,
        "duration_ms": duration_ms,
        "throughput_rows_per_sec": round(completed / max(duration_ms / 1000.0, 1.0), 2),
        "bytes_written": bytes_written,
        "state_counts": state_counts,
        "per_publisher_state": per_publisher_state,
    }

    summary_path = REPO_ROOT / "mismatches" / "retrieval-fill-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    emit(run_id=run_id, action="fill.complete", agent_name="retrieval_fill",
         progress_current=completed, progress_total=len(rows),
         duration_ms=duration_ms,
         artifact_path=str(summary_path),
         notes=f"states={state_counts} bytes_written={bytes_written}")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
