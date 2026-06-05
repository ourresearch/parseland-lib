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
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

DEFAULT_CANDIDATES = REPO_ROOT / "mismatches" / "goldie-backfilled-candidates.ndjson"
DEFAULT_OUT = REPO_ROOT / "mismatches" / "goldie-backfilled-grounded.ndjson"
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "mismatches" / "goldie-backfilled-evidence"

ABSTRACT_LOW_QUALITY_EXACT = {
    "this article has no abstract",
}
ABSTRACT_LOW_QUALITY_SNIPPETS = (
    "click to increase image size",
    "click to decrease image size",
)


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
    return bool(os.environ.get("BROWSERBASE_API_KEY"))


def resolve_browserbase_project_id(bb: Any) -> str | None:
    explicit = os.environ.get("BROWSERBASE_PROJECT_ID")
    if explicit:
        return explicit
    try:
        projects = bb.projects.list()
    except Exception:
        return None
    rows = projects if isinstance(projects, list) else list(projects)
    if not rows:
        return None
    project_id = getattr(rows[0], "id", None)
    return str(project_id) if project_id else None


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
            for aff in affs[:4]:
                if isinstance(aff, dict):
                    value = aff.get("name")
                else:
                    value = aff
                if str(value).strip():
                    needles.append(str(value).strip())
        authors = payload.get("authors") or []
        if isinstance(authors, list):
            for author in authors:
                if not isinstance(author, dict):
                    continue
                for aff in (author.get("affiliations") or []):
                    if isinstance(aff, dict):
                        value = aff.get("name")
                    else:
                        value = aff
                    if str(value).strip() and str(value).strip() not in needles:
                        needles.append(str(value).strip())
                    if len(needles) >= 4:
                        break
                if len(needles) >= 4:
                    break
    return needles


def candidate_quality_blocker(candidate: dict) -> str | None:
    """Return a conservative rejection reason for clear non-label candidates.

    This precheck prevents Browserbase spend on parser output that is visibly
    page chrome or an explicit no-abstract placeholder. Ambiguous short text is
    still grounded and sent to Referee.
    """
    if candidate.get("field") != "abstract":
        return None
    payload = candidate.get("parseland_candidate")
    if not isinstance(payload, dict):
        return None
    abstract = payload.get("abstract")
    if not isinstance(abstract, str):
        return None
    normalized = " ".join(abstract.split()).strip().lower()
    if normalized in ABSTRACT_LOW_QUALITY_EXACT:
        return "abstract_placeholder_no_abstract"
    if any(snippet in normalized for snippet in ABSTRACT_LOW_QUALITY_SNIPPETS):
        return "abstract_ui_chrome"
    return None


def _science_direct_pii(url: str) -> str | None:
    parts = [p for p in urlparse(url).path.split("/") if p]
    for i, part in enumerate(parts):
        if part == "pii" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def identity_needles(candidate: dict) -> list[str]:
    needles: list[str] = []
    doi = str(candidate.get("doi") or "").strip()
    if doi:
        needles.append(doi)
    payload = candidate.get("parseland_candidate")
    if isinstance(payload, dict):
        url = payload.get("pdf_url")
        if isinstance(url, str):
            pii = _science_direct_pii(url)
            if pii:
                needles.append(pii)
    return needles


def _matched_excerpt(html: str, needles: list[str]) -> tuple[str | None, str | None]:
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
    return None, None


def excerpt_for(html: str, candidate: dict) -> tuple[str | None, str | None, str]:
    excerpt, _ = _matched_excerpt(html, candidate_needles(candidate))
    if excerpt:
        return excerpt, "candidate-text-match", "candidate_text_match"
    excerpt, _ = _matched_excerpt(html, identity_needles(candidate))
    if excerpt:
        return excerpt, "page-identity", "page_identity_only"
    return html[:800].replace("\n", " ").strip() if html else None, "page-head", "page_rendered_only"


def safe_page_content(page: Any) -> str:
    for _ in range(3):
        try:
            return page.content()
        except Exception:
            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass
    return page.content()


def load_candidates(
    path: Path,
    fields: set[str] | None,
    statuses: set[str] | None,
    publishers: set[str] | None,
    limit: int | None,
) -> list[dict]:
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
            publisher = str(row.get("publisher") or "")
            key = (str(row.get("doi") or ""), field)
            if not key[0] or not field or key in seen:
                continue
            if fields is not None and field not in fields:
                continue
            if statuses is not None and status not in statuses:
                continue
            if publishers is not None and publisher not in publishers:
                continue
            if status not in {"pending", "pending_browserbase", "blocked_no_browserbase_credentials"}:
                continue
            seen.add(key)
            candidates.append(row)
    status_rank = {"pending_browserbase": 0, "pending": 1, "blocked_no_browserbase_credentials": 2}
    candidates.sort(key=lambda r: (status_rank.get(str(r.get("status")), 9), str(r.get("field") or ""), str(r.get("doi") or "")))
    if limit:
        candidates = candidates[:limit]
    return candidates


def ground_one(candidate: dict, evidence_dir: Path) -> GroundingResult:
    doi = str(candidate.get("doi") or "")
    field = str(candidate.get("field") or "")
    blocker = candidate_quality_blocker(candidate)
    if blocker:
        return GroundingResult(
            doi=doi,
            field=field,
            status="candidate_rejected_low_quality",
            confidence="candidate_precheck_failed",
            error=blocker,
        )

    from browserbase import Browserbase
    from playwright.sync_api import sync_playwright

    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    project_id = resolve_browserbase_project_id(bb)
    if not project_id:
        return GroundingResult(
            doi=doi,
            field=field,
            status="blocked_no_browserbase_project",
            error="Browserbase API key is set but no project id could be resolved",
        )
    session = bb.sessions.create(project_id=project_id)
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
            html = safe_page_content(page)
            final_url = page.url
            evidence_dir.mkdir(parents=True, exist_ok=True)
            stem = hashlib.sha1(f"{doi}|{field}".encode()).hexdigest()[:12]
            screenshot_path = evidence_dir / f"{stem}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            excerpt, selector, confidence = excerpt_for(html, candidate)
            status = (
                "candidate_evidence_needs_referee"
                if confidence == "candidate_text_match"
                else "page_rendered_needs_referee"
                if confidence == "page_identity_only"
                else "weak_page_render_needs_referee"
            )
            return GroundingResult(
                doi=doi,
                field=field,
                status=status,
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
    p.add_argument("--statuses", type=str, default=None)
    p.add_argument("--publishers", type=str, default=None)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    run_id = args.run_id or new_run_id()
    fields = set(args.fields.split(",")) if args.fields else None
    statuses = set(args.statuses.split(",")) if args.statuses else None
    publishers = set(args.publishers.split(",")) if args.publishers else None
    candidates = load_candidates(args.candidates, fields, statuses, publishers, args.limit)
    emit(
        run_id=run_id,
        action="goldie_backfill_ground.start",
        agent_name="gold-auditor",
        progress_total=len(candidates),
        artifact_path=str(args.out),
        notes=(
            f"fields={sorted(fields) if fields else 'all'} "
            f"statuses={sorted(statuses) if statuses else 'all'} "
            f"publishers={sorted(publishers) if publishers else 'all'} "
            f"limit={args.limit}"
        ),
    )

    if args.dry_run:
        payload = {
            "status": "dry_run",
            "candidate_count": len(candidates),
            "browserbase_credentials": have_browserbase_creds(),
            "concurrency": args.concurrency,
            "statuses": sorted(statuses) if statuses else None,
            "publishers": sorted(publishers) if publishers else None,
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
            "required_env": ["BROWSERBASE_API_KEY"],
            "optional_env": ["BROWSERBASE_PROJECT_ID"],
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
