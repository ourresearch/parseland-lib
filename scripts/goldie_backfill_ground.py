#!/usr/bin/env python3
"""Browserbase-ground Goldie-backfilled candidates.

This script does not approve labels and does not mutate merged-FINAL.csv. It
only attaches rendered-page evidence to candidate rows so a Referee/gold-auditor
can approve or reject them into a separate derived ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

DEFAULT_CANDIDATES = REPO_ROOT / "mismatches" / "goldie-backfilled-candidates.ndjson"
DEFAULT_OUT = REPO_ROOT / "mismatches" / "goldie-backfilled-grounded.ndjson"
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "mismatches" / "goldie-backfilled-evidence"


@dataclass
class GroundingResult:
    doi: str
    field: str
    status: str
    final_url: str | None = None
    browserbase_session: str | None = None
    screenshot_path: str | None = None
    html_excerpt: str | None = None
    selector: str | None = None
    confidence: str = "needs_referee"
    error: str | None = None


def have_browserbase_creds() -> bool:
    return bool(os.environ.get("BROWSERBASE_API_KEY") and os.environ.get("BROWSERBASE_PROJECT_ID"))


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi.strip()}"


def candidate_needles(candidate: dict) -> list[str]:
    payload = candidate.get("parseland_candidate")
    if isinstance(payload, str):
        payload = {"value": payload}
    if not isinstance(payload, dict):
        return []
    needles: list[str] = []
    field = candidate.get("field")
    if field == "pdf_url":
        url = payload.get("pdf_url")
        if isinstance(url, str) and url:
            needles.append(url)
    elif field == "abstract":
        abstract = payload.get("abstract")
        if isinstance(abstract, str) and abstract:
            needles.append(abstract[:160])
    elif field in {"authors", "corresponding"}:
        authors = payload.get("authors") or []
        if isinstance(authors, list):
            for author in authors[:4]:
                if isinstance(author, dict):
                    name = author.get("name")
                    if isinstance(name, str) and name.strip():
                        needles.append(name.strip())
    elif field == "affiliations":
        affs = payload.get("affiliations") or []
        if isinstance(affs, list):
            needles.extend(str(a).strip() for a in affs[:4] if str(a).strip())
    return needles


def excerpt_for(html: str, needles: list[str]) -> tuple[str | None, str | None]:
    lower = html.lower()
    for needle in needles:
        needle = needle.strip()
        if not needle:
            continue
        pos = lower.find(needle.lower())
        if pos >= 0:
            start = max(0, pos - 240)
            end = min(len(html), pos + len(needle) + 240)
            return html[start:end].replace("\n", " ").strip(), "text-match"
    return html[:800].replace("\n", " ").strip() if html else None, "page-head"


def load_candidates(path: Path, fields: set[str] | None, limit: int | None) -> list[dict]:
    candidates: list[dict] = []
    if not path.exists():
        return candidates
    seen: set[tuple[str, str]] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            field = str(row.get("field") or "")
            status = str(row.get("status") or "")
            key = (str(row.get("doi") or ""), field)
            if not key[0] or not field or key in seen:
                continue
            if fields is not None and field not in fields:
                continue
            if status not in {"pending", "pending_browserbase", "blocked_no_browserbase_credentials"}:
                continue
            seen.add(key)
            candidates.append(row)
            if limit and len(candidates) >= limit:
                break
    return candidates


def ground_one(candidate: dict, evidence_dir: Path) -> GroundingResult:
    from browserbase import Browserbase
    from playwright.sync_api import sync_playwright

    doi = str(candidate.get("doi") or "")
    field = str(candidate.get("field") or "")
    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])
    session_id = getattr(session, "id", None)
    t0 = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(session.connect_url)
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(45000)
            page.goto(doi_url(doi), wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            html = page.content()
            final_url = page.url
            evidence_dir.mkdir(parents=True, exist_ok=True)
            stem = hashlib.sha1(f"{doi}|{field}".encode()).hexdigest()[:12]
            screenshot_path = evidence_dir / f"{stem}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            excerpt, selector = excerpt_for(html, candidate_needles(candidate))
            confidence = "grounded_needs_referee" if excerpt else "weak_needs_referee"
            return GroundingResult(
                doi=doi,
                field=field,
                status="grounded_needs_referee",
                final_url=final_url,
                browserbase_session=str(session_id) if session_id else None,
                screenshot_path=str(screenshot_path),
                html_excerpt=excerpt,
                selector=selector,
                confidence=confidence,
            )
    except Exception as exc:  # noqa: BLE001
        return GroundingResult(
            doi=doi,
            field=field,
            status="grounding_failed",
            browserbase_session=str(session_id) if session_id else None,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        try:
            session.stop()
        except Exception:
            pass
        _ = t0


def write_result(out: Path, candidate: dict, result: GroundingResult) -> None:
    row: dict[str, Any] = {
        **candidate,
        "browserbase_url": result.final_url,
        "browserbase_session": result.browserbase_session,
        "screenshot_path": result.screenshot_path,
        "evidence_excerpt": result.html_excerpt,
        "dom_selector": result.selector,
        "grounding_confidence": result.confidence,
        "status": result.status,
        "grounding_error": result.error,
        "grounded_at": datetime.now(timezone.utc).isoformat(),
        "approving_agent": None,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    p.add_argument("--fields", type=str, default=None)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    run_id = args.run_id or new_run_id()
    fields = set(args.fields.split(",")) if args.fields else None
    candidates = load_candidates(args.candidates, fields, args.limit)
    emit(
        run_id=run_id,
        action="goldie_backfill_ground.start",
        agent_name="gold-auditor",
        progress_total=len(candidates),
        artifact_path=str(args.out),
        notes=f"fields={sorted(fields) if fields else 'all'} limit={args.limit}",
    )

    if args.dry_run:
        payload = {
            "status": "dry_run",
            "candidate_count": len(candidates),
            "browserbase_credentials": have_browserbase_creds(),
            "concurrency": args.concurrency,
            "sample": candidates[:3],
        }
        emit(
            run_id=run_id,
            action="goldie_backfill_ground.dry_run_complete",
            agent_name="gold-auditor",
            progress_current=len(candidates),
            progress_total=len(candidates),
            artifact_path=str(args.out),
            notes=(
                f"candidate_count={len(candidates)} "
                f"browserbase_credentials={payload['browserbase_credentials']} "
                f"concurrency={args.concurrency}"
            ),
        )
        print(json.dumps(payload, indent=2))
        return 0

    if not have_browserbase_creds():
        summary = {
            "status": "blocked_no_browserbase_credentials",
            "candidate_count": len(candidates),
            "required_env": ["BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID"],
            "out": str(args.out),
        }
        emit(
            run_id=run_id,
            action="goldie_backfill_ground.blocked",
            agent_name="gold-auditor",
            status="blocked",
            progress_current=0,
            progress_total=len(candidates),
            artifact_path=str(args.out),
            notes=json.dumps(summary),
        )
        print(json.dumps(summary, indent=2))
        return 3

    done = 0
    state_counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(ground_one, candidate, args.evidence_dir): candidate for candidate in candidates}
        for fut in as_completed(futures):
            candidate = futures[fut]
            result = fut.result()
            write_result(args.out, candidate, result)
            done += 1
            state_counts[result.status] = state_counts.get(result.status, 0) + 1
            emit(
                run_id=run_id,
                action="goldie_backfill_ground.progress",
                agent_name="gold-auditor",
                progress_current=done,
                progress_total=len(candidates),
                artifact_path=str(args.out),
                notes=json.dumps(state_counts),
            )

    emit(
        run_id=run_id,
        action="goldie_backfill_ground.complete",
        agent_name="gold-auditor",
        progress_current=done,
        progress_total=len(candidates),
        artifact_path=str(args.out),
        notes=json.dumps(state_counts),
    )
    print(json.dumps({
        "status": "complete",
        "processed": done,
        "concurrency": args.concurrency,
        "state_counts": state_counts,
        "out": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
