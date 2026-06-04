#!/usr/bin/env python3
"""Retrieval coverage audit for the 10K Goldie corpus.

Walks merged-FINAL.csv and classifies each row's retrieval state into:
- cached_ok          : HTML in cache, size >= MIN_SIZE_BYTES, no bot-check
- cached_tiny        : HTML in cache, size < MIN_SIZE_BYTES (likely stub/redirect)
- cached_bot_check   : HTML in cache, bot-check / login / captcha pattern in first 8KB
- cached_router_only : HTML in cache, content is a router page (matches ROUTER_PATTERNS)
- missing            : no HTML cached
- unknown_publisher  : publisher classifies to 'unknown'; retrieval is moot for ranking

Also runs the publisher classification to slice everything per-publisher.

Outputs:
- mismatches/retrieval-audit-<timestamp>.json   (full per-row state)
- mismatches/retrieval-audit-summary.json       (rollup; idempotent name)
- ledger events (Pathfinder role: audit.start, audit.row, audit.complete)

Usage:
    python scripts/retrieval_audit.py \\
        --corpus /Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv \\
        --cache-dir mismatches/whole-goldie-cache \\
        --extra-cache /Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/html-cache
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.publisher_index import classify_row, _load_registrant_cache  # noqa: E402
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

# Minimum HTML size to be treated as a real landing page (4 KB is a useful
# floor; doi.org redirect pages and Apache 302 stubs are typically < 1 KB).
MIN_SIZE_BYTES = 4 * 1024

# Patterns that indicate a bot-check, login, or captcha page. Scanned in the
# first 8 KB so we don't decode multi-MB HTML.
BOT_CHECK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"are you a robot",
        r"please verify",
        r"unusual traffic",
        r"cloudflare",
        r"cf-challenge",
        r"recaptcha",
        r"\bg-recaptcha\b",
        r"\bhcaptcha\b",
        r"captcha",
        r"this site uses cookies",  # weaker; some publishers wrap real content
        r"<title[^>]*>just a moment",
        r"<title[^>]*>checking your browser",
        r"access denied",
        r"<title[^>]*>login",
        r"<title[^>]*>sign in",
        r"please log in",
    )
]

# Router-only markers — pages that are clearly DOI router stubs without
# article content.
ROUTER_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"<title[^>]*>doi\.org",
        r"<title[^>]*>301 moved",
        r"<title[^>]*>302 found",
        r"<meta\s+http-equiv=[\"']?refresh[\"']?\s+content=[\"']?\d",  # meta-refresh redirect
    )
]


def _doi_hash(doi: str) -> str:
    return hashlib.sha1(doi.lower().encode()).hexdigest()


def _candidate_paths(doi: str, cache_dirs: list[Path]) -> list[Path]:
    h = _doi_hash(doi)
    return [d / f"{h}.html" for d in cache_dirs]


def _read_head(path: Path, max_bytes: int = 8 * 1024) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(max_bytes)
    except Exception:
        return b""


def classify_retrieval_state(
    doi: str, cache_dirs: list[Path]
) -> tuple[str, dict]:
    """Return (state_label, details) for one DOI."""
    for p in _candidate_paths(doi, cache_dirs):
        if not p.exists():
            continue
        try:
            size = p.stat().st_size
        except Exception:
            continue
        head = _read_head(p)
        # Decode best-effort for pattern matching
        try:
            text = head.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        for pat in BOT_CHECK_PATTERNS:
            if pat.search(text):
                return "cached_bot_check", {
                    "path": str(p), "size": size, "matched": pat.pattern,
                }
        for pat in ROUTER_PATTERNS:
            if pat.search(text):
                return "cached_router_only", {
                    "path": str(p), "size": size, "matched": pat.pattern,
                }
        if size < MIN_SIZE_BYTES:
            return "cached_tiny", {"path": str(p), "size": size}
        return "cached_ok", {"path": str(p), "size": size}
    return "missing", {}


def audit(
    corpus_path: Path,
    cache_dirs: list[Path],
    *,
    run_id: str | None = None,
    out_dir: Path = REPO_ROOT / "mismatches",
) -> dict:
    run_id = run_id or new_run_id()
    t_start = time.time()
    reg_cache = _load_registrant_cache()
    out_dir.mkdir(parents=True, exist_ok=True)

    emit(run_id=run_id, action="audit.start", agent_name="retrieval_audit",
         notes=f"corpus={corpus_path.name} cache_dirs={[str(d) for d in cache_dirs]}")

    per_state: dict[str, int] = defaultdict(int)
    per_publisher: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_publisher_rowcount: dict[str, int] = defaultdict(int)
    rows_out: list[dict] = []
    total = 0
    progress_every = 1000

    with open(corpus_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            doi = (row.get("DOI") or "").strip()
            pub = classify_row(row, allow_network=False, _cache=reg_cache)
            per_publisher_rowcount[pub] += 1
            if pub == "unknown":
                state = "unknown_publisher"
                details: dict = {}
            else:
                state, details = classify_retrieval_state(doi, cache_dirs)
            per_state[state] += 1
            per_publisher[pub][state] += 1
            rows_out.append({
                "doi": doi,
                "publisher": pub,
                "state": state,
                **({"path": details.get("path")} if details.get("path") else {}),
                **({"size": details.get("size")} if details.get("size") else {}),
            })
            if total % progress_every == 0:
                emit(run_id=run_id, action="audit.progress",
                     agent_name="retrieval_audit",
                     progress_current=total, progress_total=10000)

    duration_ms = int((time.time() - t_start) * 1000)
    summary = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_path": str(corpus_path),
        "cache_dirs": [str(d) for d in cache_dirs],
        "total_rows": total,
        "per_state": dict(per_state),
        "per_publisher": {
            pub: {"rows": per_publisher_rowcount[pub], **dict(per_publisher[pub])}
            for pub in sorted(per_publisher_rowcount, key=lambda p: -per_publisher_rowcount[p])
        },
        "duration_ms": duration_ms,
        "coverage_pct": round(
            100.0 * per_state.get("cached_ok", 0) / max(total, 1), 2
        ),
    }

    # Full per-row state — written under a timestamp so we can compare audits.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    full_path = out_dir / f"retrieval-audit-{ts}.ndjson"
    with open(full_path, "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary_path = out_dir / "retrieval-audit-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    emit(run_id=run_id, action="audit.complete", agent_name="retrieval_audit",
         progress_current=total, progress_total=total,
         duration_ms=duration_ms, artifact_path=str(summary_path),
         notes=(f"coverage_pct={summary['coverage_pct']} "
                f"per_state={dict(per_state)}"))

    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--cache-dir", type=Path, action="append",
                   default=None,
                   help="Cache dir to check (repeatable; default: "
                        "mismatches/whole-goldie-cache + parseland-eval/eval/html-cache).")
    p.add_argument("--out-dir", type=Path,
                   default=REPO_ROOT / "mismatches")
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    if args.cache_dir is None:
        cache_dirs = [
            REPO_ROOT / "mismatches" / "whole-goldie-cache",
            Path("/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/html-cache"),
        ]
    else:
        cache_dirs = args.cache_dir

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 2

    summary = audit(args.corpus, cache_dirs,
                    run_id=args.run_id, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
