#!/usr/bin/env python3
"""Real-query corresponding-author validation lane.

Zendesk support tickets are used only as DOI-backed spot-check evidence. Raw
ticket payloads stay under mismatches/private/ and public artifacts contain
sanitized DOI-level rows only. This script never mutates Goldie.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html as html_lib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bs4 import BeautifulSoup  # noqa: E402
from parseland_lib.parse import parse_page  # noqa: E402
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402
from scripts.lib.publisher_index import classify_row, _load_registrant_cache  # noqa: E402
from scripts.whole_goldie_eval import _doi_hash, _html_block_reason  # noqa: E402

WORKFLOW_DIR_DEFAULT = REPO_ROOT / "mismatches" / "workflows" / "20260604T163736Z-77fe45"
RESULTS_DIR_DEFAULT = WORKFLOW_DIR_DEFAULT / "results"
PRIVATE_RAW_DIR_DEFAULT = REPO_ROOT / "mismatches" / "private" / "zendesk-corresponding-raw"
HTML_CACHE_DIR_DEFAULT = REPO_ROOT / "mismatches" / "whole-goldie-cache"
WHOLE_GOLDIE_DEFAULT = RESULTS_DIR_DEFAULT / "whole_goldie_batch84_after_publisher_index_tail_prefixes.json"
QUEUE_DEFAULT = WORKFLOW_DIR_DEFAULT / "publisher-field-queue.v2.ndjson"

CANDIDATES_DEFAULT = RESULTS_DIR_DEFAULT / "real_query_corresponding_candidates.ndjson"
JOINED_DEFAULT = RESULTS_DIR_DEFAULT / "real_query_corresponding_joined.ndjson"
SPOTCHECK_DEFAULT = RESULTS_DIR_DEFAULT / "real_query_corresponding_spotcheck.ndjson"
SUMMARY_DEFAULT = RESULTS_DIR_DEFAULT / "real_query_corresponding_summary.json"
GATE_DEFAULT = RESULTS_DIR_DEFAULT / "real_query_corresponding_gate.json"
EVIDENCE_DIR_DEFAULT = RESULTS_DIR_DEFAULT / "real_query_corresponding_evidence"
ZCLI_CONFIG_PATH = Path.home() / ".zcli"
ZCLI_CORE_REQUEST_JS = Path(
    "/opt/homebrew/lib/node_modules/@zendesk/zcli/node_modules/"
    "@zendesk/zcli-core/dist/lib/request.js"
)

ZCLI_REQUEST_BRIDGE = r"""
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const { requestAPI } = require(input.requestModule);

(async () => {
  const response = await requestAPI(input.path);
  process.stdout.write(JSON.stringify({
    status: response.status,
    data: response.data === undefined ? null : response.data
  }));
})().catch((err) => {
  process.stderr.write(err && err.message ? err.message : String(err));
  process.exit(1);
});
"""

DEFAULT_QUERY_TERMS = (
    "corresponding author",
    "corresponding_author",
    "missing corresponding author",
    "wrong corresponding author",
    "author email",
    "corresponding author openalex",
)

CLASSIFICATIONS = {
    "already_fixed_by_current_parseland",
    "still_parser_owned",
    "gold_or_ticket_disagreement",
    "retrieval_owned",
    "access_or_js_owned",
    "unsupported_publisher",
    "not_reproducible",
    "insufficient_private_context",
}

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
CA_TEXT_RE = re.compile(
    r"\b(corresponding author|correspondence|corresponding authors?|"
    r"to whom correspondence|author for correspondence|reprint requests?|"
    r"address correspondence|e-?mail\s+address)\b",
    re.I,
)
CA_ATTR_RE = re.compile(r"(correspond|email|e-mail|mailto|envelope)", re.I)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def public_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def clean_doi(raw: str) -> str:
    value = urllib.parse.unquote(str(raw or "")).strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    value = value.split("#", 1)[0].split("?", 1)[0]
    value = value.strip().strip("<>\"'")
    while value and value[-1] in ".,;:!?]}":
        value = value[:-1]
    if value.count("(") < value.count(")"):
        value = value.rstrip(")")
    return value.lower()


def extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in DOI_RE.finditer(text or ""):
        doi = clean_doi(match.group(0))
        if doi and doi not in seen:
            seen.add(doi)
            out.append(doi)
    return out


def redact_private_text(text: str, *, max_len: int = 500) -> str:
    cleaned = html_lib.unescape(str(text or ""))
    cleaned = EMAIL_RE.sub("[email]", cleaned)
    cleaned = re.sub(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", "[phone]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3].rstrip() + "..."
    return cleaned


def classify_issue(text: str) -> str:
    lower = (text or "").lower()
    if "wrong corresponding" in lower or "incorrect corresponding" in lower:
        return "wrong_corresponding_author"
    if "missing corresponding" in lower or "no corresponding" in lower:
        return "missing_corresponding_author"
    if "author email" in lower or "corresponding author email" in lower:
        return "author_email"
    if "corresponding" in lower:
        return "corresponding_author_general"
    return "unknown_corresponding_author_issue"


def ticket_hash(subdomain: str, ticket_id: Any) -> str:
    return stable_hash(f"{subdomain}:{ticket_id}")


def sanitize_ticket_rows(
    *,
    ticket: dict[str, Any],
    comments: list[dict[str, Any]],
    search_term: str,
    subdomain: str,
) -> list[dict[str, Any]]:
    subject = str(ticket.get("subject") or "")
    description = str(ticket.get("description") or "")
    comment_text = "\n".join(str(c.get("body") or c.get("html_body") or "") for c in comments)
    joined = "\n".join([subject, description, comment_text])
    issue_class = classify_issue(joined)
    thash = ticket_hash(subdomain, ticket.get("id", "unknown"))
    rows: list[dict[str, Any]] = []
    for doi in extract_dois(joined):
        rows.append(
            {
                "doi": doi,
                "publisher": "",
                "ticket_hash": thash,
                "matched_search_term": search_term,
                "sanitized_issue_class": issue_class,
                "source": "zendesk_support_api",
                "extracted_at_utc": now_utc(),
                "private_export_present": True,
            }
        )
    return rows


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def zcli_active_profile(
    *,
    config_path: Path = ZCLI_CONFIG_PATH,
    request_js_path: Path = ZCLI_CORE_REQUEST_JS,
) -> tuple[str | None, str]:
    if not request_js_path.exists():
        return None, "missing_zcli_core"
    if not config_path.exists():
        return None, "missing_zcli_profile"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid_zcli_profile"
    profile = data.get("activeProfile") or {}
    subdomain = str(profile.get("subdomain") or "").strip()
    if not subdomain:
        return None, "missing_zcli_subdomain"
    return subdomain, "zcli_core_keychain"


def zendesk_auth_headers() -> tuple[str | None, dict[str, str], str]:
    subdomain = os.environ.get("ZENDESK_SUBDOMAIN")
    oauth = os.environ.get("ZENDESK_OAUTH_TOKEN")
    email = os.environ.get("ZENDESK_EMAIL")
    token = os.environ.get("ZENDESK_API_TOKEN")
    headers = {"Accept": "application/json"}
    if subdomain and oauth:
        headers["Authorization"] = f"Bearer {oauth}"
        return subdomain, headers, "oauth"
    if subdomain and email and token:
        raw = f"{email}/token:{token}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
        return subdomain, headers, "api_token"
    zcli_subdomain, zcli_mode = zcli_active_profile()
    if zcli_subdomain:
        return zcli_subdomain, headers, zcli_mode
    if not subdomain:
        return None, headers, zcli_mode
    return subdomain, headers, "missing_zendesk_credentials"


def zendesk_api_path(url: str, *, subdomain: str) -> str:
    parsed = urllib.parse.urlparse(url)
    expected_host = f"{subdomain}.zendesk.com".lower()
    if parsed.scheme != "https" or parsed.netloc.lower() != expected_host:
        raise ValueError("Zendesk URL does not match active zcli profile")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return path


def zcli_core_get_json(url: str, *, subdomain: str) -> dict[str, Any]:
    path = zendesk_api_path(url, subdomain=subdomain)
    payload = {
        "path": path,
        "requestModule": str(ZCLI_CORE_REQUEST_JS),
    }
    result = subprocess.run(
        ["node", "-e", ZCLI_REQUEST_BRIDGE],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"zcli-core request failed: {(result.stderr or '').strip()[:300]}")
    response = json.loads(result.stdout or "{}")
    status = int(response.get("status") or 0)
    if status >= 400:
        raise RuntimeError(f"Zendesk API returned HTTP {status}")
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def zendesk_get_json(url: str, headers: dict[str, str], *, subdomain: str, auth_mode: str) -> dict[str, Any]:
    if auth_mode == "zcli_core_keychain":
        return zcli_core_get_json(url, subdomain=subdomain)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - explicit operator-supplied Zendesk URL
        return json.loads(resp.read().decode("utf-8"))


def fetch_zendesk_tickets(
    *,
    terms: list[str],
    limit: int,
    private_raw_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    subdomain, headers, auth_mode = zendesk_auth_headers()
    meta = {
        "zendesk_auth_mode": auth_mode,
        "query_terms": terms,
        "limit": limit,
        "fetched_tickets": 0,
        "raw_private_exports": 0,
        "errors": [],
        "started_at_utc": now_utc(),
    }
    if auth_mode.startswith("missing_") or not subdomain:
        private_raw_dir.mkdir(parents=True, exist_ok=True)
        (private_raw_dir / "zendesk_auth_unavailable.json").write_text(
            json.dumps(
                {
                    "status": auth_mode,
                    "notes": (
                        "Set ZENDESK_SUBDOMAIN plus ZENDESK_EMAIL/ZENDESK_API_TOKEN "
                        "or ZENDESK_OAUTH_TOKEN, or run zcli login -i so zcli-core "
                        "can use the local keychain profile."
                    ),
                    "query_terms": terms,
                    "timestamp_utc": now_utc(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        meta["completed_at_utc"] = now_utc()
        return [], meta

    private_raw_dir.mkdir(parents=True, exist_ok=True)
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for term in terms:
        if len(rows_by_key) >= limit:
            break
        query = f'type:ticket "{term}"'
        url = (
            f"https://{subdomain}.zendesk.com/api/v2/search.json?"
            + urllib.parse.urlencode({"query": query, "sort_by": "updated_at", "sort_order": "desc"})
        )
        try:
            payload = zendesk_get_json(url, headers, subdomain=subdomain, auth_mode=auth_mode)
        except Exception as exc:  # noqa: BLE001
            meta["errors"].append({"term": term, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for ticket in payload.get("results") or []:
            if len(rows_by_key) >= limit:
                break
            tid = ticket.get("id")
            if not tid:
                continue
            comments: list[dict[str, Any]] = []
            comments_url = f"https://{subdomain}.zendesk.com/api/v2/tickets/{tid}/comments.json"
            try:
                comments = list((zendesk_get_json(comments_url, headers, subdomain=subdomain, auth_mode=auth_mode).get("comments") or []))
            except Exception as exc:  # noqa: BLE001
                meta["errors"].append({"ticket_hash": ticket_hash(subdomain, tid), "error": f"{type(exc).__name__}: {exc}"})
            thash = ticket_hash(subdomain, tid)
            raw_path = private_raw_dir / f"{thash}.json"
            raw_path.write_text(json.dumps({"ticket": ticket, "comments": comments}, indent=2), encoding="utf-8")
            meta["fetched_tickets"] += 1
            meta["raw_private_exports"] += 1
            for row in sanitize_ticket_rows(ticket=ticket, comments=comments, search_term=term, subdomain=subdomain):
                key = (row["doi"], row["ticket_hash"])
                rows_by_key[key] = row
    meta["completed_at_utc"] = now_utc()
    return list(rows_by_key.values()), meta


def load_whole_goldie(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: dict[str, dict[str, Any]] = {}
    for row in data.get("rows") or []:
        doi = clean_doi(row.get("doi") or "")
        if doi:
            rows[doi] = row
    return rows


def load_queue(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return out
    for row in load_ndjson(path):
        pub = str(row.get("publisher_id") or row.get("publisher") or "")
        field = str(row.get("field") or "")
        if pub and field:
            out[(pub, field)] = row
    return out


def inferred_parser_ca_count(field_status: str) -> int | None:
    if field_status in {"empty_empty_pass", "gold_present_parser_empty", "retrieval_blocked"}:
        return 0
    if field_status in {"gold_present_parser_present", "gold_empty_parser_present"}:
        return 1
    return None


def classify_joined_ca(row: dict[str, Any] | None, field_status: str, score: dict[str, Any]) -> str:
    if row is None:
        return "insufficient_private_context"
    if field_status == "retrieval_blocked" or row.get("retrieval_blocked"):
        return "retrieval_owned"
    if field_status in {"empty_empty_pass", "gold_present_parser_present"}:
        return "already_fixed_by_current_parseland"
    try:
        if float(score.get("accuracy", 0.0)) >= 0.98:
            return "already_fixed_by_current_parseland"
    except (TypeError, ValueError):
        pass
    if field_status == "gold_present_parser_empty":
        return "still_parser_owned"
    if field_status == "gold_empty_parser_present":
        return "gold_or_ticket_disagreement"
    return "insufficient_private_context"


def join_candidate(
    candidate: dict[str, Any],
    *,
    whole_rows: dict[str, dict[str, Any]],
    queue: dict[tuple[str, str], dict[str, Any]],
    reg_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doi = clean_doi(candidate.get("doi") or "")
    row = whole_rows.get(doi)
    link = str((row or {}).get("link") or f"https://doi.org/{doi}")
    publisher = str(candidate.get("publisher") or (row or {}).get("publisher") or "")
    if not publisher:
        publisher = classify_row({"DOI": doi, "Link": link}, allow_network=False, _cache=reg_cache or {})
    field_status = str(((row or {}).get("field_status") or {}).get("corresponding") or "not_in_goldie")
    score = ((row or {}).get("score") or {}).get("corresponding") or {}
    task = queue.get((publisher, "corresponding")) or {}
    classification = classify_joined_ca(row, field_status, score)
    out = {
        "doi": doi,
        "publisher": publisher,
        "ticket_hash": candidate.get("ticket_hash"),
        "matched_search_term": candidate.get("matched_search_term"),
        "sanitized_issue_class": candidate.get("sanitized_issue_class"),
        "in_goldie": row is not None,
        "current_full10k_ca_status": field_status,
        "current_parseland_ca_count": inferred_parser_ca_count(field_status),
        "current_parseland_ca_names": [],
        "current_parseland_ca_source": "full10k_status_inferred" if row is not None else "not_in_full10k",
        "current_full10k_score": score,
        "page_grounded_ca_marker_type": None,
        "classification": classification,
        "classification_confidence": "needs_page_grounding" if classification in {"still_parser_owned", "gold_or_ticket_disagreement"} else "medium",
        "evidence_paths": [],
        "queue_task_id": task.get("task_id"),
        "queue_status": task.get("status"),
        "recommended_next_action": recommended_action(classification),
        "joined_at_utc": now_utc(),
    }
    return out


def recommended_action(classification: str) -> str:
    return {
        "already_fixed_by_current_parseland": "Use as representativeness evidence; no parser patch.",
        "still_parser_owned": "Page-ground the CA marker; patch only if repeated/high-volume pattern.",
        "gold_or_ticket_disagreement": "Send to Referee/gold-auditor after page grounding.",
        "retrieval_owned": "Recover HTML via cache/Taxicab/R2/Browserbase before judging parser.",
        "access_or_js_owned": "Use rendered retrieval evidence; do not patch parser until DOM is available.",
        "unsupported_publisher": "Route to onboarding queue if row volume justifies it.",
        "not_reproducible": "Keep as validation sample; no parser patch.",
        "insufficient_private_context": "Need Zendesk API rows or page evidence before classification.",
    }.get(classification, "Needs Referee classification.")


def cache_path(doi: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_doi_hash(doi)}.html"


def read_cached_html(doi: str, cache_dir: Path) -> str | None:
    path = cache_path(doi, cache_dir)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def parsed_corresponding_authors(parsed: dict[str, Any] | None) -> list[str]:
    names: list[str] = []
    for author in (parsed or {}).get("authors") or []:
        if not isinstance(author, dict):
            continue
        if author.get("is_corresponding") or author.get("corresponding_author"):
            name = str(author.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def detect_ca_marker(page_html: str) -> dict[str, Any]:
    soup = BeautifulSoup(page_html or "", "html.parser")
    meta = soup.find("meta", attrs={"name": re.compile(r"citation_author_email", re.I)})
    if meta and meta.get("content"):
        return {
            "marker_type": "citation_author_email",
            "selector": 'meta[name="citation_author_email"]',
            "excerpt": redact_private_text(str(meta.get("content"))),
        }
    mailto = soup.find("a", href=re.compile(r"^mailto:", re.I))
    if mailto:
        return {
            "marker_type": "mailto",
            "selector": "a[href^='mailto:']",
            "excerpt": redact_private_text(mailto.get_text(" ", strip=True) or str(mailto.get("href") or "")),
        }
    for text_node in soup.find_all(string=CA_TEXT_RE, limit=1):
        parent = text_node.parent
        excerpt = parent.get_text(" ", strip=True) if parent else str(text_node)
        return {
            "marker_type": "text_correspondence_marker",
            "selector": parent.name if parent else "text",
            "excerpt": redact_private_text(excerpt),
        }
    for tag in soup.find_all(True, limit=5000):
        attrs = " ".join(
            " ".join(v) if isinstance(v, list) else str(v)
            for k, v in tag.attrs.items()
            if k in {"class", "id", "title", "aria-label", "data-test", "data-testid"}
        )
        if attrs and CA_ATTR_RE.search(attrs):
            return {
                "marker_type": "attribute_correspondence_marker",
                "selector": tag.name,
                "excerpt": redact_private_text(tag.get_text(" ", strip=True) or attrs),
            }
    return {"marker_type": None, "selector": None, "excerpt": None}


def classify_spotcheck(
    *,
    block_reason: str | None,
    marker_type: str | None,
    parser_ca_names: list[str],
    joined_classification: str,
    gold_has_ca: bool,
) -> str:
    if block_reason:
        if block_reason in {"cached_bot_check", "js_rendered_required", "cached_router_only"}:
            return "access_or_js_owned"
        return "retrieval_owned"
    if marker_type and parser_ca_names:
        return "already_fixed_by_current_parseland"
    if marker_type and not parser_ca_names:
        return "still_parser_owned"
    if joined_classification == "already_fixed_by_current_parseland":
        return "already_fixed_by_current_parseland"
    if gold_has_ca:
        return "gold_or_ticket_disagreement"
    if joined_classification in CLASSIFICATIONS:
        return joined_classification
    return "not_reproducible"


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


def render_with_browserbase(doi: str, *, evidence_dir: Path) -> dict[str, Any]:
    from browserbase import Browserbase
    from playwright.sync_api import sync_playwright

    evidence_dir.mkdir(parents=True, exist_ok=True)
    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    project_id = resolve_browserbase_project_id(bb)
    if not project_id:
        return {"status": "blocked_no_browserbase_project", "error": "No Browserbase project id resolved."}
    session = bb.sessions.create(project_id=project_id)
    session_id = str(getattr(session, "id", ""))
    url = f"https://doi.org/{doi}"
    started = time.time()
    screenshot_path = evidence_dir / f"{_doi_hash(doi)}.png"
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(session.connect_url)
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(30000)
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            page.screenshot(path=str(screenshot_path), full_page=True, timeout=15000)
            return {
                "status": "ok",
                "html": page.content(),
                "final_url": page.url,
                "browserbase_session": session_id,
                "screenshot_path": str(screenshot_path),
                "duration_ms": int((time.time() - started) * 1000),
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "browserbase_error",
            "error": f"{type(exc).__name__}: {exc}",
            "browserbase_session": session_id,
            "duration_ms": int((time.time() - started) * 1000),
        }
    finally:
        try:
            session.stop()
        except Exception:
            pass


def spotcheck_row(
    row: dict[str, Any],
    *,
    cache_dir: Path,
    evidence_dir: Path,
    allow_browser: bool,
) -> dict[str, Any]:
    doi = clean_doi(row.get("doi") or "")
    html_text = read_cached_html(doi, cache_dir)
    render_meta: dict[str, Any] = {}
    if (not html_text or _html_block_reason(html_text)) and allow_browser and have_browserbase_creds():
        render_meta = render_with_browserbase(doi, evidence_dir=evidence_dir)
        if render_meta.get("html"):
            html_text = str(render_meta["html"])
            cache_path(doi, cache_dir).write_text(html_text, encoding="utf-8", errors="replace")

    block_reason = _html_block_reason(html_text)
    parsed: dict[str, Any] | None = None
    parser_error: str | None = None
    if html_text and not block_reason:
        try:
            parsed = parse_page(html_text, namespace="doi", resolved_url=f"https://doi.org/{doi}")
        except Exception as exc:  # noqa: BLE001
            parser_error = f"{type(exc).__name__}: {exc}"
    parser_ca_names = parsed_corresponding_authors(parsed)
    marker = detect_ca_marker(html_text or "") if html_text and not block_reason else {"marker_type": None, "selector": None, "excerpt": None}
    gold_has_ca = str(row.get("current_full10k_ca_status") or "").startswith("gold_present")
    classification = classify_spotcheck(
        block_reason=block_reason,
        marker_type=marker.get("marker_type"),
        parser_ca_names=parser_ca_names,
        joined_classification=str(row.get("classification") or ""),
        gold_has_ca=gold_has_ca,
    )
    evidence_paths = list(row.get("evidence_paths") or [])
    if render_meta.get("screenshot_path"):
        evidence_paths.append(str(render_meta["screenshot_path"]))
    cpath = cache_path(doi, cache_dir)
    if cpath.exists():
        evidence_paths.append(str(cpath))
    return {
        **row,
        "current_parseland_ca_count": len(parser_ca_names),
        "current_parseland_ca_names": parser_ca_names[:5],
        "current_parseland_ca_source": "live_parse_page" if parsed is not None else row.get("current_parseland_ca_source"),
        "page_grounded_ca_marker_type": marker.get("marker_type"),
        "page_grounded_selector": marker.get("selector"),
        "page_grounded_excerpt": marker.get("excerpt"),
        "classification": classification,
        "classification_confidence": "page_grounded" if html_text and not block_reason else "blocked_or_unavailable",
        "browserbase_final_url": render_meta.get("final_url"),
        "browserbase_session": render_meta.get("browserbase_session"),
        "browserbase_status": render_meta.get("status"),
        "screenshot_path": render_meta.get("screenshot_path"),
        "retrieval_blocked_reason": block_reason,
        "parser_error": parser_error,
        "evidence_paths": sorted(set(evidence_paths)),
        "recommended_next_action": recommended_action(classification),
        "spotchecked_at_utc": now_utc(),
    }


def public_artifact_violations(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    violations: list[str] = []
    patterns = {
        "browserbase_secret": r"bb_live_[A-Za-z0-9_-]+",
        "aws_access_key": r"AKIA[0-9A-Z]{16}",
        "email_address": EMAIL_RE,
        "raw_ticket_id_key": r'"ticket_id"\s*:',
        "requester_key": r'"requester',
        "raw_comment_key": r'"comments?"\s*:',
        "zendesk_token_key": r"ZENDESK_(?:API_TOKEN|OAUTH_TOKEN)",
        "authorization_header": r"\bAuthorization\b",
        "basic_auth_header": r"\bBasic\s+[A-Za-z0-9+/=]{12,}",
        "bearer_auth_header": r"\bBearer\s+[A-Za-z0-9._~-]{12,}",
    }
    for label, pattern in patterns.items():
        matched = pattern.search(text) if hasattr(pattern, "search") else re.search(pattern, text, re.I)
        if matched:
            violations.append(label)
    for env_name in ("ZENDESK_API_TOKEN", "ZENDESK_OAUTH_TOKEN", "BROWSERBASE_API_KEY", "AWS_SECRET_ACCESS_KEY"):
        value = os.environ.get(env_name)
        if value and value in text:
            violations.append(f"env_secret:{env_name}")
    return violations


def summarize_artifacts(
    *,
    candidates_path: Path,
    joined_path: Path,
    spotcheck_path: Path,
    summary_path: Path,
    gate_path: Path,
    query_terms: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = load_ndjson(candidates_path)
    joined = load_ndjson(joined_path)
    spotchecked = load_ndjson(spotcheck_path)
    meta_path = candidates_path.with_suffix(".meta.json")
    joined_rows = joined or candidates
    final_rows = spotchecked or joined
    classification_counts = Counter(str(r.get("classification") or "unclassified") for r in final_rows)
    issue_counts = Counter(str(r.get("sanitized_issue_class") or "unknown") for r in candidates)
    publisher_counts = Counter(str(r.get("publisher") or "unknown") for r in final_rows)
    repeated_patterns: list[dict[str, Any]] = []
    pattern_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in spotchecked:
        if row.get("classification") != "still_parser_owned":
            continue
        key = (str(row.get("publisher") or "unknown"), str(row.get("page_grounded_ca_marker_type") or "unknown_marker"))
        pattern_groups[key].append(str(row.get("doi")))
    for (publisher, marker), dois in sorted(pattern_groups.items(), key=lambda x: (-len(x[1]), x[0])):
        repeated_patterns.append({"publisher": publisher, "marker_type": marker, "doi_count": len(dois), "example_dois": dois[:5]})

    stop_reason = None
    if not candidates:
        stop_reason = "zendesk_returns_too_few_doi_backed_rows_or_credentials_missing"
    elif len(spotchecked) >= 30:
        stop_reason = "bounded_30_plus_spotchecks_completed"
    elif any(p["doi_count"] >= 3 for p in repeated_patterns):
        stop_reason = "repeated_parser_owned_pattern_found"
    elif spotchecked:
        owned = sum(classification_counts.get(k, 0) for k in ("retrieval_owned", "access_or_js_owned", "gold_or_ticket_disagreement"))
        if owned > classification_counts.get("still_parser_owned", 0):
            stop_reason = "most_failures_not_parser_owned"

    summary = {
        "title": "Real-query corresponding-author spot check",
        "updated_at_utc": now_utc(),
        "zendesk_queries_attempted": query_terms,
        "doi_backed_candidates_found": len(candidates),
        "rows_joined_to_current_goldie": len(joined),
        "rows_spotchecked": len(spotchecked),
        "already_fixed_by_current_parseland": classification_counts.get("already_fixed_by_current_parseland", 0),
        "still_parser_owned": classification_counts.get("still_parser_owned", 0),
        "retrieval_or_access_owned": classification_counts.get("retrieval_owned", 0) + classification_counts.get("access_or_js_owned", 0),
        "gold_or_ticket_disagreement": classification_counts.get("gold_or_ticket_disagreement", 0),
        "unsupported_publisher": classification_counts.get("unsupported_publisher", 0),
        "not_reproducible": classification_counts.get("not_reproducible", 0),
        "insufficient_private_context": classification_counts.get("insufficient_private_context", 0),
        "classification_counts": dict(sorted(classification_counts.items())),
        "issue_class_counts": dict(sorted(issue_counts.items())),
        "publisher_counts": dict(sorted(publisher_counts.items())),
        "repeated_ca_marker_patterns": repeated_patterns,
        "sanitized_artifacts": [
            public_path(meta_path),
            public_path(candidates_path),
            public_path(joined_path),
            public_path(spotcheck_path),
            public_path(gate_path),
        ] if meta_path.exists() else [
            public_path(candidates_path),
            public_path(joined_path),
            public_path(spotcheck_path),
            public_path(gate_path),
        ],
        "private_data_policy": "Raw Zendesk ticket payloads are local-only under mismatches/private and are not report assets.",
        "next_recommended_lane": next_lane(classification_counts, repeated_patterns, bool(candidates)),
        "stop_reason": stop_reason,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    public_paths = [p for p in (meta_path, candidates_path, joined_path, spotcheck_path, summary_path) if p.exists()]
    violations = {public_path(p): public_artifact_violations(p) for p in public_paths}
    violations = {p: v for p, v in violations.items() if v}
    gate = {
        "gate": "real_query_corresponding_validation",
        "timestamp_utc": now_utc(),
        "shield_verdict": "green" if not violations else "red_sanitizer_violation",
        "public_artifacts_checked": [public_path(p) for p in public_paths],
        "public_artifact_violations": violations,
        "private_raw_path_untracked_required": public_path(PRIVATE_RAW_DIR_DEFAULT),
        "zendesk_candidate_count": len(candidates),
        "joined_count": len(joined),
        "spotcheck_count": len(spotchecked),
        "notes": (
            "This gate validates sanitizer/tooling/reportability. It does not approve "
            "Zendesk complaints as Goldie truth and does not gate parser changes."
        ),
    }
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True), encoding="utf-8")
    return summary, gate


def next_lane(classification_counts: Counter, repeated_patterns: list[dict[str, Any]], has_candidates: bool) -> str:
    if not has_candidates:
        return "Set Zendesk Support API credentials or provide a sanitized DOI export; then rerun extraction."
    if any(p["doi_count"] >= 3 for p in repeated_patterns):
        return "Open a parser-owned CA patch lane for the repeated marker pattern with focused tests."
    if classification_counts.get("still_parser_owned", 0):
        return "Continue page-grounded spot checks until a repeated parser-owned pattern appears or 30-50 rows are classified."
    if classification_counts.get("retrieval_owned", 0) or classification_counts.get("access_or_js_owned", 0):
        return "Return to retrieval/rendering lane before parser edits."
    return "Use this as representativeness evidence and return to the ranked full-10K queue."


def parse_terms(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_QUERY_TERMS)
    return [v.strip() for v in value.split(",") if v.strip()]


def cmd_extract_zendesk(args: argparse.Namespace) -> int:
    terms = parse_terms(args.terms)
    rows, meta = fetch_zendesk_tickets(terms=terms, limit=args.limit, private_raw_dir=args.private_raw_dir)
    write_ndjson(args.out, rows)
    meta_path = args.out.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "rows": len(rows), "meta": meta}, indent=2))
    return 0


def cmd_join_current(args: argparse.Namespace) -> int:
    candidates = load_ndjson(args.candidates)
    whole_rows = load_whole_goldie(args.whole_goldie)
    queue = load_queue(args.queue)
    reg_cache = _load_registrant_cache()
    joined = [
        join_candidate(candidate, whole_rows=whole_rows, queue=queue, reg_cache=reg_cache)
        for candidate in candidates
    ]
    write_ndjson(args.out, joined)
    print(json.dumps({"out": str(args.out), "rows": len(joined), "whole_rows": len(whole_rows)}, indent=2))
    return 0


def cmd_spotcheck(args: argparse.Namespace) -> int:
    rows = load_ndjson(args.joined)
    if args.limit is not None:
        rows = rows[: args.limit]
    out_rows = [
        spotcheck_row(row, cache_dir=args.cache_dir, evidence_dir=args.evidence_dir, allow_browser=args.allow_browser)
        for row in rows
    ]
    write_ndjson(args.out, out_rows)
    print(json.dumps({"out": str(args.out), "rows": len(out_rows), "allow_browser": args.allow_browser}, indent=2))
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    summary, gate = summarize_artifacts(
        candidates_path=args.candidates,
        joined_path=args.joined,
        spotcheck_path=args.spotcheck,
        summary_path=args.summary,
        gate_path=args.gate,
        query_terms=parse_terms(args.terms),
    )
    emit(
        run_id=f"real-query-ca-{new_run_id()}",
        action="real_query_corresponding.summarized",
        status="blocked" if summary.get("stop_reason") else "ok",
        agent_name="build_report336",
        publisher="all",
        field="corresponding",
        stage="real_query_validation",
        progress_current=int(summary.get("rows_spotchecked") or 0),
        progress_total=max(int(summary.get("doi_backed_candidates_found") or 0), int(summary.get("rows_spotchecked") or 0)),
        artifact_path=public_path(args.summary),
        notes=(
            f"candidates={summary.get('doi_backed_candidates_found')} "
            f"joined={summary.get('rows_joined_to_current_goldie')} "
            f"spotchecked={summary.get('rows_spotchecked')} "
            f"stop_reason={summary.get('stop_reason') or 'none'}"
        ),
    )
    print(json.dumps({"summary": str(args.summary), "gate": str(args.gate), "verdict": gate["shield_verdict"], "rows_spotchecked": summary["rows_spotchecked"]}, indent=2))
    return 0 if gate["shield_verdict"] == "green" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("extract-zendesk", help="Pull Zendesk tickets via Support API and emit sanitized DOI candidates.")
    p.add_argument("--terms", help="Comma-separated Zendesk search terms.")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--private-raw-dir", type=Path, default=PRIVATE_RAW_DIR_DEFAULT)
    p.add_argument("--out", type=Path, default=CANDIDATES_DEFAULT)
    p.set_defaults(func=cmd_extract_zendesk)

    p = sub.add_parser("join-current", help="Join sanitized DOI candidates to current full-10K CA state.")
    p.add_argument("--candidates", type=Path, default=CANDIDATES_DEFAULT)
    p.add_argument("--whole-goldie", type=Path, default=WHOLE_GOLDIE_DEFAULT)
    p.add_argument("--queue", type=Path, default=QUEUE_DEFAULT)
    p.add_argument("--out", type=Path, default=JOINED_DEFAULT)
    p.set_defaults(func=cmd_join_current)

    p = sub.add_parser("spotcheck", help="Ground selected DOI rows against cache/Browserbase and parse current CA output.")
    p.add_argument("--joined", type=Path, default=JOINED_DEFAULT)
    p.add_argument("--out", type=Path, default=SPOTCHECK_DEFAULT)
    p.add_argument("--cache-dir", type=Path, default=HTML_CACHE_DIR_DEFAULT)
    p.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR_DEFAULT)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--allow-browser", action="store_true")
    p.set_defaults(func=cmd_spotcheck)

    p = sub.add_parser("summarize", help="Summarize sanitized artifacts and write a sanitizer gate.")
    p.add_argument("--terms", help="Comma-separated Zendesk search terms.")
    p.add_argument("--candidates", type=Path, default=CANDIDATES_DEFAULT)
    p.add_argument("--joined", type=Path, default=JOINED_DEFAULT)
    p.add_argument("--spotcheck", type=Path, default=SPOTCHECK_DEFAULT)
    p.add_argument("--summary", type=Path, default=SUMMARY_DEFAULT)
    p.add_argument("--gate", type=Path, default=GATE_DEFAULT)
    p.set_defaults(func=cmd_summarize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
