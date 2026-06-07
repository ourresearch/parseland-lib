#!/usr/bin/env python3
"""Browserbase-ground Goldie-backfilled candidates.

This script does not approve labels and does not mutate merged-FINAL.csv. It
only attaches rendered-page evidence to candidate rows so a Referee/gold-auditor
can approve or reject them into a separate derived ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bs4 import BeautifulSoup  # noqa: E402
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402
from parseland_lib.parse import parse_page  # noqa: E402

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
GENERIC_CORRESPONDENCE_NEEDLES = {
    "address",
    "email",
    "e-mail",
    "mail",
    "mailto",
    "correspondence",
    "corresponding",
    "reprint",
    "reprints",
    "author information",
}


@dataclass
class GroundingResult:
    doi: str
    field: str
    status: str
    final_url: str | None = None
    browserbase_session: str | None = None
    screenshot_path: str | None = None
    verified_candidate_url: str | None = None
    verified_candidate_final_url: str | None = None
    verified_candidate_status: int | None = None
    verified_candidate_screenshot_path: str | None = None
    resolved_candidate: dict[str, Any] | None = None
    resolved_candidate_source: str | None = None
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


def _candidate_correspondence_needles(candidate: dict) -> list[str]:
    if candidate.get("field") != "corresponding":
        return []
    payload = candidate.get("parseland_candidate")
    if not isinstance(payload, dict):
        return []
    markers = ("correspond", "reprint", "e-mail", "email", "mailto:", "address")
    needles: list[str] = []
    for author in payload.get("authors") or []:
        if not isinstance(author, dict) or not author.get("is_corresponding"):
            continue
        for affiliation in author.get("affiliations") or []:
            if isinstance(affiliation, dict):
                value = affiliation.get("name") or affiliation.get("value")
            else:
                value = affiliation
            text = " ".join(str(value or "").split())
            lower = text.lower()
            normalized = lower.strip(" :;,.")
            if normalized in GENERIC_CORRESPONDENCE_NEEDLES:
                continue
            if text and any(marker in lower for marker in markers) and text not in needles:
                needles.append(text)
    return needles


def candidate_pdf_url(candidate: dict) -> str | None:
    if candidate.get("field") != "pdf_url":
        return None
    payload = candidate.get("parseland_candidate")
    if isinstance(payload, str):
        payload = {"pdf_url": payload}
    if not isinstance(payload, dict):
        return None
    url = payload.get("pdf_url")
    return url.strip() if isinstance(url, str) and url.strip() else None


def candidate_author_count(candidate: dict) -> int | None:
    if candidate.get("field") != "authors":
        return None
    payload = candidate.get("parseland_candidate")
    if not isinstance(payload, dict):
        return None
    count = payload.get("n_authors")
    return count if isinstance(count, int) and count > 0 else None


def candidate_abstract_len(candidate: dict) -> int | None:
    if candidate.get("field") != "abstract":
        return None
    payload = candidate.get("parseland_candidate")
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("abstract"), str) and payload.get("abstract").strip():
        return None
    abstract_len = payload.get("abstract_len")
    return abstract_len if isinstance(abstract_len, int) and abstract_len > 100 else None


def _clean_affiliation_value(value: Any) -> str:
    text = html_lib.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" ;,.")
    return text


def candidate_affiliation_values(candidate: dict) -> list[str]:
    if candidate.get("field") != "affiliations":
        return []
    payload = candidate.get("parseland_candidate")
    if not isinstance(payload, dict):
        return []
    values: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, dict):
            value = value.get("name") or value.get("value")
        cleaned = _clean_affiliation_value(value)
        if cleaned and cleaned not in values:
            values.append(cleaned)

    for aff in payload.get("affiliations") or []:
        add(aff)
    for author in payload.get("authors") or []:
        if not isinstance(author, dict):
            continue
        for aff in author.get("affiliations") or []:
            add(aff)
    return values


def resolve_affiliation_candidate(
    html: str,
    candidate: dict,
) -> tuple[dict[str, Any], str] | None:
    values = candidate_affiliation_values(candidate)
    if not values:
        return None
    html_unescaped = html_lib.unescape(html)
    lower = html_unescaped.lower()
    chunks: list[str] = []
    for value in values:
        pos = lower.find(value.lower())
        if pos < 0:
            return None
        start = max(0, pos - 180)
        end = min(len(html_unescaped), pos + len(value) + 180)
        chunk = html_unescaped[start:end].replace("\n", " ").strip()
        if chunk and chunk not in chunks:
            chunks.append(chunk)
    return {"affiliations": values}, " ... ".join(chunks)


def abstract_len_matches(expected: int, actual: int) -> bool:
    tolerance = max(25, int(expected * 0.05))
    return abs(expected - actual) <= tolerance


def resolve_abstract_len_candidate(
    html: str, candidate: dict, resolved_url: str | None
) -> tuple[dict[str, Any], str] | None:
    expected_len = candidate_abstract_len(candidate)
    if not expected_len:
        return None
    try:
        parsed = parse_page(html, namespace="doi", resolved_url=resolved_url)
    except Exception:
        return None
    abstract = (parsed or {}).get("abstract")
    if not isinstance(abstract, str) or len(abstract.strip()) <= 100:
        return None
    abstract = " ".join(abstract.split())
    if not abstract_len_matches(expected_len, len(abstract)):
        return None
    return {"abstract": abstract}, abstract[:1000]


def abstract_followup_url(page_url: str, html: str) -> str | None:
    meta_patterns = (
        r'<meta[^>]+name=["\']wkhealth_abstract_html_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']wkhealth_abstract_html_url["\']',
    )
    for pattern in meta_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return html_lib.unescape(match.group(1))
    if "/citation/" in page_url:
        return page_url.replace("/citation/", "/abstract/", 1)
    return None


def extract_author_names_from_html(html: str) -> list[str]:
    match = re.search(r'"authorNames"\s*:\s*"([^"]+)"', html)
    if not match:
        return []
    raw = match.group(1)
    try:
        raw = json.loads(f'"{raw}"')
    except Exception:
        pass
    names = [" ".join(part.split()) for part in raw.split(";")]
    return [name for name in names if name]


def resolve_author_count_candidate(html: str, candidate: dict) -> tuple[dict[str, Any], str] | None:
    expected_count = candidate_author_count(candidate)
    if not expected_count:
        return None
    names = extract_author_names_from_html(html)
    if len(names) != expected_count:
        return None
    resolved = {
        "authors": [
            {
                "name": name,
                "affiliations": [],
                "is_corresponding": None,
            }
            for name in names
        ]
    }
    excerpt, _ = _matched_excerpt(html, ['"authorNames"'])
    return resolved, excerpt or f"authorNames={';'.join(names)}"


def _clean_person_name(value: Any) -> str:
    text = html_lib.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _person_name_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_person_name(value).casefold())


def candidate_corresponding_author_names(candidate: dict) -> list[str]:
    if candidate.get("field") != "corresponding":
        return []
    payload = candidate.get("parseland_candidate")
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for author in payload.get("authors") or []:
        if not isinstance(author, dict) or not author.get("is_corresponding"):
            continue
        name = _clean_person_name(author.get("name"))
        key = _person_name_key(name)
        if name and key and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def resolve_mdpi_starred_corresponding_candidate(
    html: str,
    candidate: dict,
) -> tuple[dict[str, Any], str] | None:
    """Ground MDPI corresponding authors against starred author byline markup."""
    names = candidate_corresponding_author_names(candidate)
    if not names:
        return None
    soup = BeautifulSoup(html or "", "html.parser")
    author_root = soup.find("div", class_="art-authors")
    if not author_root:
        return None
    matched: list[dict[str, Any]] = []
    chunks: list[str] = []
    for name in names:
        name_key = _person_name_key(name)
        found = None
        for author_span in author_root.find_all("span", class_="inlineblock"):
            sup = author_span.find("sup")
            if not sup or "*" not in sup.get_text(" ", strip=True):
                continue
            name_node = author_span.find("div") or author_span.find("a")
            byline_name = _clean_person_name(
                name_node.get_text(" ", strip=True) if name_node else author_span.get_text(" ", strip=True)
            )
            if _person_name_key(byline_name) == name_key:
                found = {
                    "name": byline_name,
                    "affiliations": [],
                    "is_corresponding": True,
                }
                chunks.append(str(author_span).replace("\n", " ").strip())
                break
        if not found:
            return None
        matched.append(found)
    return {"authors": matched}, " ... ".join(chunks)


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
    if candidate.get("field") == "corresponding":
        excerpt, _ = _matched_excerpt(html, _candidate_correspondence_needles(candidate))
        if excerpt:
            return (
                excerpt,
                "correspondence-candidate-text-match",
                "correspondence_candidate_text_match",
            )
        excerpt, _ = _matched_excerpt(html, candidate_needles(candidate))
        if excerpt:
            return excerpt, "corresponding-author-name-only", "corresponding_author_name_only"
    excerpt, _ = _matched_excerpt(html, candidate_needles(candidate))
    if excerpt:
        return excerpt, "candidate-text-match", "candidate_text_match"
    excerpt, _ = _matched_excerpt(html, identity_needles(candidate))
    if excerpt:
        return excerpt, "page-identity", "page_identity_only"
    return html[:800].replace("\n", " ").strip() if html else None, "page-head", "page_rendered_only"


def pdf_url_resolution_is_usable(status_code: int | None, final_url: str) -> bool:
    if status_code is not None and status_code >= 400:
        return False
    final_lower = final_url.lower()
    if not final_lower.startswith(("http://", "https://")):
        return False
    blocked_markers = ("error", "denied", "captcha", "login", "signin")
    if any(marker in final_lower for marker in blocked_markers):
        return False
    return any(marker in final_lower for marker in ("/pdf", "pdfft", ".pdf"))


def _pdf_shaped_url(url: str) -> bool:
    lower = url.lower()
    return any(
        marker in lower
        for marker in (
            "pdf.sciencedirectassets.com",
            "/pdfft",
            "/pdf",
            ".pdf",
            "downloadpdf",
            "pdfdownload",
            "citation_pdf_url",
        )
    )


def _clean_url(value: str, base_url: str) -> str | None:
    url = html_lib.unescape(str(value or "")).strip()
    if not url or url.startswith(("javascript:", "mailto:", "#")):
        return None
    return urljoin(base_url or "https://www.sciencedirect.com", url)


def _meta_content(html: str, name: str) -> list[str]:
    values: list[str] = []
    for tag_match in re.finditer(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
        tag = tag_match.group(0)
        if not re.search(
            rf"\b(?:name|property)=['\"]{re.escape(name)}['\"]",
            tag,
            flags=re.IGNORECASE,
        ):
            continue
        content = re.search(r"\bcontent=['\"]([^'\"]+)['\"]", tag, flags=re.IGNORECASE)
        if content:
            values.append(content.group(1))
    return values


def _raw_pdf_urls(html: str) -> list[str]:
    patterns = (
        r"https?://pdf\.sciencedirectassets\.com/[^'\"<>\s\\]+",
        r"https?://www\.sciencedirect\.com/science/article/pii/[^'\"<>\s\\]+/(?:pdf|pdfft)[^'\"<>\s\\]*",
        r"https?://[^'\"<>\s\\]+\.pdf(?:\?[^'\"<>\s\\]*)?",
    )
    urls: list[str] = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, html, flags=re.IGNORECASE))
    return urls


def _science_direct_pdfft_from_metadata(html: str, candidate: dict, page_url: str) -> str | None:
    if "sciencedirect.com" not in page_url and "sciencedirect.com" not in str(candidate_pdf_url(candidate) or ""):
        return None
    pii = None
    for value in _meta_content(html, "citation_pii"):
        if value.strip():
            pii = value.strip()
            break
    if not pii:
        match = re.search(r'"pii"\s*:\s*"([^"]+)"', html)
        if match:
            pii = match.group(1)
    if not pii:
        pii = _science_direct_pii(str(candidate_pdf_url(candidate) or "")) or _science_direct_pii(page_url)
    md5_match = re.search(r'"md5"\s*:\s*"([^"]+)"', html)
    pid_match = re.search(r'"pid"\s*:\s*"([^"]+)"', html)
    if not pii or not md5_match or not pid_match:
        return None
    md5 = html_lib.unescape(md5_match.group(1)).strip()
    pid = html_lib.unescape(pid_match.group(1)).strip()
    if not md5 or not pid:
        return None
    return f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?md5={md5}&pid={pid}"


def extract_pdf_link_candidates(html: str, page_url: str, candidate: dict) -> list[dict[str, str]]:
    """Return rendered/meta PDF-like links that still need navigation proof."""
    html_unescaped = html_lib.unescape(html or "")
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url_value: str | None, selector: str) -> None:
        if not url_value:
            return
        cleaned = _clean_url(url_value, page_url)
        if not cleaned or not _pdf_shaped_url(cleaned):
            return
        if cleaned in seen:
            return
        seen.add(cleaned)
        candidates.append({"url": cleaned, "selector": selector})

    for value in _meta_content(html_unescaped, "citation_pdf_url"):
        add(value, "meta[citation_pdf_url]")

    for attr_match in re.finditer(
        r"\b(?:href|data-href|action|content)=['\"]([^'\"]+)['\"]",
        html_unescaped,
        flags=re.IGNORECASE,
    ):
        value = attr_match.group(1)
        if _pdf_shaped_url(value):
            add(value, "rendered-pdf-link")

    for raw_url in _raw_pdf_urls(html_unescaped):
        add(raw_url, "raw-pdf-url")

    add(_science_direct_pdfft_from_metadata(html_unescaped, candidate, page_url), "sciencedirect-md5-pid-pdfft")
    return candidates


def verify_pdf_links_from_page(
    page: Any,
    html: str,
    page_url: str,
    candidate: dict,
    evidence_dir: Path,
    stem: str,
) -> dict[str, Any] | None:
    links = extract_pdf_link_candidates(html, page_url, candidate)
    if not links:
        return {
            "candidate_url": candidate_pdf_url(candidate),
            "candidate_final_url": None,
            "candidate_status": None,
            "confidence": "visible_or_metadata_pdf_url_not_found",
            "selector": "rendered-or-metadata-pdf-link-discovery",
            "excerpt": "extracted_pdf_link_count=0",
        }
    attempts: list[dict[str, Any]] = []
    for i, link in enumerate(links[:8], start=1):
        url = link["url"]
        try:
            response = page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            final_url = page.url
            status_code = response.status if response is not None else None
            attempts.append(
                {
                    "url": url,
                    "final_url": final_url,
                    "status": status_code,
                    "selector": link["selector"],
                }
            )
            if not pdf_url_resolution_is_usable(status_code, final_url):
                continue
            screenshot_path = evidence_dir / f"{stem}-pdf-link-{i}.png"
            screenshot_value, screenshot_error = safe_screenshot(page, screenshot_path)
            return {
                "candidate_url": url,
                "candidate_final_url": final_url,
                "candidate_status": status_code,
                "candidate_screenshot_path": screenshot_value,
                "confidence": "visible_or_metadata_pdf_url_resolves",
                "selector": link["selector"],
                "resolved_candidate": {"pdf_url": final_url or url},
                "resolved_candidate_source": "browserbase_visible_or_metadata_pdf_url",
                "excerpt": (
                    f"verified_pdf_url={url} final_url={final_url} "
                    f"status={status_code} selector={link['selector']}"
                ),
                "error": f"screenshot_failed: {screenshot_error}" if screenshot_error else None,
            }
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "url": url,
                    "final_url": None,
                    "status": None,
                    "selector": link["selector"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    first = attempts[0]
    return {
        "candidate_url": first.get("url"),
        "candidate_final_url": first.get("final_url"),
        "candidate_status": first.get("status"),
        "confidence": "visible_or_metadata_pdf_url_not_verified",
        "selector": "rendered-or-metadata-pdf-link-navigation",
        "excerpt": f"tried_pdf_link_count={len(attempts)} attempts={json.dumps(attempts[:3], ensure_ascii=False)}",
    }


def verify_pdf_candidate_url(page: Any, candidate: dict, evidence_dir: Path, stem: str) -> dict[str, Any] | None:
    """Verify the proposed PDF URL itself, not just the DOI landing page.

    A successful result is still candidate evidence that needs Referee approval.
    It only proves that the parser-emitted URL resolves through Browserbase.
    """
    url = candidate_pdf_url(candidate)
    if not url:
        return None
    try:
        response = page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        final_url = page.url
        status_code = response.status if response is not None else None
        if not pdf_url_resolution_is_usable(status_code, final_url):
            return {
                "candidate_url": url,
                "candidate_final_url": final_url,
                "candidate_status": status_code,
                "confidence": "candidate_pdf_url_not_verified",
                "selector": "candidate-pdf-url-navigation",
                "excerpt": (
                    f"candidate_pdf_url={url} final_url={final_url} "
                    f"status={status_code}"
                ),
            }
        screenshot_path = evidence_dir / f"{stem}-pdf.png"
        screenshot_value, screenshot_error = safe_screenshot(page, screenshot_path)
        return {
            "candidate_url": url,
            "candidate_final_url": final_url,
            "candidate_status": status_code,
            "candidate_screenshot_path": screenshot_value,
            "confidence": "candidate_pdf_url_resolves",
            "selector": "candidate-pdf-url-navigation",
            "excerpt": (
                f"candidate_pdf_url={url} final_url={final_url} "
                f"status={status_code}"
            ),
            "error": f"screenshot_failed: {screenshot_error}" if screenshot_error else None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "candidate_url": url,
            "candidate_final_url": None,
            "candidate_status": None,
            "confidence": "candidate_pdf_url_navigation_failed",
            "selector": "candidate-pdf-url-navigation",
            "excerpt": f"candidate_pdf_url={url}",
            "error": f"{type(exc).__name__}: {exc}",
        }


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


def safe_screenshot(page: Any, path: Path) -> tuple[str | None, str | None]:
    """Capture a screenshot without losing rendered DOM evidence on timeout."""
    try:
        page.screenshot(path=str(path), full_page=True, timeout=10000)
        return str(path), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def load_candidates(
    path: Path,
    fields: set[str] | None,
    statuses: set[str] | None,
    publishers: set[str] | None,
    skip: int,
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
    if skip > 0:
        candidates = candidates[skip:]
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

    session = None
    session_id = None
    t0 = time.time()
    try:
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
            screenshot_value, screenshot_error = safe_screenshot(page, screenshot_path)
            excerpt, selector, confidence = excerpt_for(html, candidate)
            resolved_candidate = None
            resolved_candidate_source = None
            if field == "affiliations":
                affiliation_resolution = resolve_affiliation_candidate(html, candidate)
                if affiliation_resolution:
                    resolved_candidate, excerpt = affiliation_resolution
                    selector = "all-affiliation-candidate-text-match"
                    confidence = "all_affiliation_candidate_text_match"
                    resolved_candidate_source = "browserbase_rendered_affiliations"
            author_resolution = None
            if field == "authors" and confidence != "candidate_text_match":
                author_resolution = resolve_author_count_candidate(html, candidate)
                if author_resolution:
                    resolved_candidate, excerpt = author_resolution
                    selector = "authorNames-count-match"
                    confidence = "author_count_author_names_match"
                    resolved_candidate_source = "browserbase_rendered_authorNames"
            corresponding_resolution = None
            if field == "corresponding" and confidence != "correspondence_candidate_text_match":
                corresponding_resolution = resolve_mdpi_starred_corresponding_candidate(html, candidate)
                if corresponding_resolution:
                    resolved_candidate, excerpt = corresponding_resolution
                    selector = "mdpi-starred-author-byline"
                    confidence = "mdpi_starred_author_byline_match"
                    resolved_candidate_source = "browserbase_rendered_mdpi_starred_byline"
            abstract_resolution = None
            if field == "abstract" and confidence != "candidate_text_match":
                abstract_resolution = resolve_abstract_len_candidate(html, candidate, final_url)
                if abstract_resolution:
                    resolved_candidate, excerpt = abstract_resolution
                    selector = "rendered-abstract-len-match"
                    confidence = "abstract_len_rendered_parse_match"
                    resolved_candidate_source = "browserbase_rendered_parse_page"
                else:
                    followup = abstract_followup_url(final_url, html)
                    if followup and followup != final_url:
                        page.goto(followup, wait_until="domcontentloaded")
                        try:
                            page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception:
                            pass
                        html = safe_page_content(page)
                        final_url = page.url
                        screenshot_path = evidence_dir / f"{stem}-abstract.png"
                        screenshot_value, followup_screenshot_error = safe_screenshot(page, screenshot_path)
                        screenshot_error = screenshot_error or followup_screenshot_error
                        excerpt, selector, confidence = excerpt_for(html, candidate)
                        abstract_resolution = resolve_abstract_len_candidate(html, candidate, final_url)
                        if abstract_resolution:
                            resolved_candidate, excerpt = abstract_resolution
                            selector = "rendered-abstract-followup-len-match"
                            confidence = "abstract_len_rendered_parse_match"
                            resolved_candidate_source = "browserbase_rendered_abstract_followup_parse_page"
            pdf_verification = None
            if field == "pdf_url" and confidence != "candidate_text_match":
                pdf_verification = verify_pdf_candidate_url(page, candidate, evidence_dir, stem)
                if pdf_verification and pdf_verification.get("confidence") == "candidate_pdf_url_resolves":
                    excerpt = pdf_verification.get("excerpt")
                    selector = pdf_verification.get("selector")
                    confidence = str(pdf_verification.get("confidence"))
                else:
                    link_verification = verify_pdf_links_from_page(
                        page,
                        html,
                        final_url,
                        candidate,
                        evidence_dir,
                        stem,
                    )
                    if link_verification:
                        if (
                            pdf_verification
                            and link_verification.get("confidence")
                            in {
                                "visible_or_metadata_pdf_url_not_found",
                                "visible_or_metadata_pdf_url_not_verified",
                            }
                        ):
                            link_verification["candidate_final_url"] = pdf_verification.get("candidate_final_url")
                            link_verification["candidate_status"] = pdf_verification.get("candidate_status")
                            link_verification["excerpt"] = (
                                f"{link_verification.get('excerpt')}; "
                                f"direct_candidate_final_url={pdf_verification.get('candidate_final_url')} "
                                f"direct_candidate_status={pdf_verification.get('candidate_status')}"
                            )
                        pdf_verification = link_verification
                    if pdf_verification and pdf_verification.get("confidence") == "visible_or_metadata_pdf_url_resolves":
                        excerpt = pdf_verification.get("excerpt")
                        selector = pdf_verification.get("selector")
                        confidence = str(pdf_verification.get("confidence"))
                        resolved_candidate = pdf_verification.get("resolved_candidate")
                        resolved_candidate_source = str(pdf_verification.get("resolved_candidate_source"))
                    elif pdf_verification and pdf_verification.get("confidence") in {
                        "candidate_pdf_url_not_verified",
                        "candidate_pdf_url_navigation_failed",
                        "visible_or_metadata_pdf_url_not_found",
                        "visible_or_metadata_pdf_url_not_verified",
                    }:
                        excerpt = pdf_verification.get("excerpt")
                        selector = pdf_verification.get("selector")
                        confidence = str(pdf_verification.get("confidence"))
            status = (
                "candidate_evidence_needs_referee"
                if confidence in {
                    "candidate_text_match",
                    "candidate_pdf_url_resolves",
                    "visible_or_metadata_pdf_url_resolves",
                    "author_count_author_names_match",
                    "abstract_len_rendered_parse_match",
                    "all_affiliation_candidate_text_match",
                    "correspondence_candidate_text_match",
                    "mdpi_starred_author_byline_match",
                }
                else "page_rendered_needs_referee"
                if confidence == "page_identity_only"
                else "weak_page_render_needs_referee"
            )
            if status == "candidate_evidence_needs_referee" and not screenshot_value:
                status = "weak_page_render_needs_referee"
                screenshot_error = screenshot_error or "required screenshot was not captured"
            result_error = (
                (pdf_verification or {}).get("error")
                if pdf_verification
                else None
            ) or screenshot_error
            return GroundingResult(
                doi=doi,
                field=field,
                status=status,
                final_url=final_url,
                browserbase_session=str(session_id) if session_id else None,
                screenshot_path=screenshot_value,
                verified_candidate_url=(
                    pdf_verification or {}
                ).get("candidate_url") if pdf_verification else None,
                verified_candidate_final_url=(
                    pdf_verification or {}
                ).get("candidate_final_url") if pdf_verification else None,
                verified_candidate_status=(
                    pdf_verification or {}
                ).get("candidate_status") if pdf_verification else None,
                verified_candidate_screenshot_path=(
                    pdf_verification or {}
                ).get("candidate_screenshot_path") if pdf_verification else None,
                resolved_candidate=resolved_candidate,
                resolved_candidate_source=resolved_candidate_source,
                html_excerpt=excerpt,
                selector=selector,
                confidence=confidence,
                error=result_error,
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
        if session is not None:
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
        "verified_candidate_url": result.verified_candidate_url,
        "verified_candidate_final_url": result.verified_candidate_final_url,
        "verified_candidate_status": result.verified_candidate_status,
        "verified_candidate_screenshot_path": result.verified_candidate_screenshot_path,
        "resolved_candidate": result.resolved_candidate,
        "resolved_candidate_source": result.resolved_candidate_source,
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
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    run_id = args.run_id or new_run_id()
    fields = set(args.fields.split(",")) if args.fields else None
    statuses = set(args.statuses.split(",")) if args.statuses else None
    publishers = set(args.publishers.split(",")) if args.publishers else None
    candidates = load_candidates(args.candidates, fields, statuses, publishers, args.skip, args.limit)
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
            f"skip={args.skip} "
            f"limit={args.limit}"
        ),
    )

    if args.dry_run:
        payload = {
            "status": "dry_run",
            "candidate_count": len(candidates),
            "browserbase_credentials": have_browserbase_creds(),
            "concurrency": args.concurrency,
            "skip": args.skip,
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
            try:
                result = fut.result()
            except Exception as exc:  # noqa: BLE001
                result = GroundingResult(
                    doi=str(candidate.get("doi") or ""),
                    field=str(candidate.get("field") or ""),
                    status="grounding_failed",
                    error=f"worker_unhandled_exception: {type(exc).__name__}: {exc}",
                )
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
