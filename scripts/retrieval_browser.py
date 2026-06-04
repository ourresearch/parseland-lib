#!/usr/bin/env python3
"""Browser-rendered retrieval fallback for rows where R2 had no good HTML.

Targets rows whose retrieval-audit state is one of:
- missing
- missing_uuid           (Taxicab has no harvest record)
- r2_404                 (R2 has no object for the UUID)
- cached_bot_check       (HTML cached but contains captcha / login wall)
- cached_router_only     (HTML cached but is a DOI router stub)
- cached_tiny            (HTML cached but is < 4KB; usually a stub)

Strategy:
1. Prefer Browserbase if BROWSERBASE_API_KEY + BROWSERBASE_PROJECT_ID are set.
   Browserbase handles fingerprint, residential IPs, and captcha-aware sessions.
2. Fall back to local Playwright (headless Chromium) when no Browserbase
   credentials. Slower, less stealthy, but free and offline-runnable.

Boundary (per the user's directive):
  Browserbase is for retrieval/evidence only. It is NOT gold truth, NOT the
  scorer, and NOT the parser improvement mechanism.

Outputs:
- Writes rendered HTML to mismatches/whole-goldie-cache/<sha1>.html
- Writes mismatches/retrieval-browser-summary.json
- Emits ledger events under Pathfinder role (retrieval is part of preparation)

Usage:
    python scripts/retrieval_browser.py \\
        --audit mismatches/retrieval-audit-summary.json \\
        --rows mismatches/retrieval-audit-<ts>.ndjson \\
        --states missing,missing_uuid,r2_404,cached_bot_check,cached_router_only,cached_tiny \\
        --limit 50 --concurrency 2
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

DEFAULT_CACHE_DIR = REPO_ROOT / "mismatches" / "whole-goldie-cache"
DEFAULT_WAIT_S = 20      # max wait for page to render
PAGE_TIMEOUT_S = 30      # overall navigation timeout


def _doi_hash(doi: str) -> str:
    return hashlib.sha1(doi.lower().encode()).hexdigest()


def _cache_path(doi: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_doi_hash(doi)}.html"


def _doi_url(doi: str) -> str:
    return f"https://doi.org/{doi.strip()}"


@dataclass
class BrowserOutcome:
    doi: str
    state_before: str
    status: str         # ok | timeout | nav_error | bot_check_blocked | exception | skipped
    size: int = 0
    backend: str = ""   # browserbase | playwright_local
    duration_ms: int = 0
    error: str | None = None


def _have_browserbase_creds() -> bool:
    return bool(os.environ.get("BROWSERBASE_API_KEY")
                and os.environ.get("BROWSERBASE_PROJECT_ID"))


def _retrieve_via_browserbase(url: str) -> tuple[str, int, str | None]:
    """Returns (html, status, error)."""
    from browserbase import Browserbase
    from playwright.sync_api import sync_playwright

    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(session.connect_url)
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(PAGE_TIMEOUT_S * 1000)
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=DEFAULT_WAIT_S * 1000)
            except Exception as exc:
                # Even on timeout we may have a usable DOM
                html = ""
                try:
                    html = page.content()
                except Exception:
                    pass
                if html and len(html) > 8 * 1024:
                    return html, "ok", None
                return "", "nav_error", f"{type(exc).__name__}: {exc}"
            html = page.content()
            return html, "ok", None
    finally:
        try:
            session.stop()
        except Exception:
            pass


def _retrieve_via_playwright_local(url: str) -> tuple[str, int, str | None]:
    """Returns (html, status, error)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.set_default_timeout(PAGE_TIMEOUT_S * 1000)
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=DEFAULT_WAIT_S * 1000)
            except Exception as exc:
                html = ""
                try:
                    html = page.content()
                except Exception:
                    pass
                if html and len(html) > 8 * 1024:
                    return html, "ok", None
                return "", "nav_error", f"{type(exc).__name__}: {exc}"
            html = page.content()
            return html, "ok", None
        finally:
            browser.close()


def retrieve_one(doi: str, state_before: str, cache_dir: Path,
                 *, prefer_browserbase: bool = True) -> BrowserOutcome:
    url = _doi_url(doi)
    t0 = time.time()
    backend = ""
    try:
        if prefer_browserbase and _have_browserbase_creds():
            backend = "browserbase"
            html, status, err = _retrieve_via_browserbase(url)
        else:
            backend = "playwright_local"
            html, status, err = _retrieve_via_playwright_local(url)
    except Exception as exc:
        return BrowserOutcome(
            doi=doi, state_before=state_before, status="exception",
            backend=backend, error=f"{type(exc).__name__}: {exc}",
            duration_ms=int((time.time() - t0) * 1000),
        )
    if status != "ok" or not html or len(html) < 4 * 1024:
        return BrowserOutcome(
            doi=doi, state_before=state_before,
            status=status if status != "ok" else "too_small",
            backend=backend, error=err,
            duration_ms=int((time.time() - t0) * 1000),
        )
    # Light bot-check sanity — if it's still a captcha wall, mark blocked.
    head = html[:8 * 1024].lower()
    if "recaptcha" in head or "cf-challenge" in head or "just a moment" in head:
        return BrowserOutcome(
            doi=doi, state_before=state_before, status="bot_check_blocked",
            backend=backend, size=len(html),
            duration_ms=int((time.time() - t0) * 1000),
        )
    p = _cache_path(doi, cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8", errors="replace")
    return BrowserOutcome(
        doi=doi, state_before=state_before, status="ok",
        backend=backend, size=len(html),
        duration_ms=int((time.time() - t0) * 1000),
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rows", type=Path, required=True,
                   help="NDJSON from retrieval_audit (per-row state).")
    p.add_argument("--states", type=str,
                   default="missing,missing_uuid,r2_404,cached_bot_check,"
                           "cached_router_only,cached_tiny",
                   help="Comma-separated states to target.")
    p.add_argument("--publishers", type=str,
                   help="Only retrieve rows whose publisher is in this set.")
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    p.add_argument("--concurrency", type=int, default=2,
                   help="Default 2; browser rendering is heavy. Browserbase "
                        "can sustain higher concurrency than local Playwright.")
    p.add_argument("--limit", type=int)
    p.add_argument("--no-browserbase", action="store_true",
                   help="Force local Playwright even if BROWSERBASE_* set.")
    p.add_argument("--run-id", type=str)
    p.add_argument("--report-every", type=int, default=20)
    args = p.parse_args()

    targeted_states = set(args.states.split(","))
    publishers = set(args.publishers.split(",")) if args.publishers else None

    if not args.rows.exists():
        print(f"ERROR: rows file not found: {args.rows}", file=sys.stderr)
        return 2

    target: list[tuple[str, str]] = []
    with open(args.rows, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("state") not in targeted_states:
                continue
            if publishers is not None and r.get("publisher") not in publishers:
                continue
            target.append((r["doi"], r["state"]))
            if args.limit and len(target) >= args.limit:
                break

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or new_run_id()
    prefer_bb = not args.no_browserbase
    bb_ok = _have_browserbase_creds() and prefer_bb
    emit(run_id=run_id, action="retrieval_browser.start",
         agent_name="retrieval_browser",
         progress_total=len(target),
         notes=f"backend={'browserbase' if bb_ok else 'playwright_local'} "
               f"states={sorted(targeted_states)}")

    state_after: dict[str, int] = {}
    completed = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = {pool.submit(retrieve_one, doi, st, args.cache_dir,
                            prefer_browserbase=prefer_bb): (doi, st)
                for doi, st in target}
        for fut in as_completed(futs):
            o = fut.result()
            state_after[o.status] = state_after.get(o.status, 0) + 1
            completed += 1
            if completed % args.report_every == 0:
                emit(run_id=run_id, action="retrieval_browser.progress",
                     agent_name="retrieval_browser",
                     progress_current=completed, progress_total=len(target),
                     notes=json.dumps(state_after))

    duration_ms = int((time.time() - t0) * 1000)
    summary = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "rows_file": str(args.rows),
        "targeted_states": sorted(targeted_states),
        "target_rows": len(target),
        "completed_rows": completed,
        "duration_ms": duration_ms,
        "throughput_rows_per_sec": round(
            completed / max(duration_ms / 1000.0, 1.0), 2),
        "state_after": state_after,
        "backend": "browserbase" if bb_ok else "playwright_local",
    }
    summary_path = REPO_ROOT / "mismatches" / "retrieval-browser-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    emit(run_id=run_id, action="retrieval_browser.complete",
         agent_name="retrieval_browser",
         progress_current=completed, progress_total=len(target),
         duration_ms=duration_ms,
         artifact_path=str(summary_path),
         notes=json.dumps(state_after))

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
