"""Pilot: extract gold-standard-shaped metadata for 50 random DOIs via
Vercel agent-browser + Claude.

Reads `eval/data/random-50.csv`, drives `agent-browser` in local headless
mode to fetch each DOI's landing page, then asks Claude Sonnet 4.6 (via
tool-use for schema-enforced JSON) to extract `Authors / Abstract / PDF URL`
and flag bot-checks. Writes two artefacts:

- `eval/data/random-50-extracted.csv` — gold-standard column order
- `eval/data/random-50-extracted.meta.json` — per-row cost, duration, snapshot path

Sequential for the pilot; concurrency belongs in Phase 5.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from parseland_eval.paths import EVAL_DIR
from parseland_eval.pricing import compute_anthropic_cost

try:
    from dotenv import load_dotenv
    load_dotenv(EVAL_DIR / ".env", override=True)
except ImportError:
    pass

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
INPUT_CSV = EVAL_DIR / "data" / "random-50.csv"
OUTPUT_CSV = EVAL_DIR / "data" / "random-50-extracted.csv"
META_JSON = EVAL_DIR / "data" / "random-50-extracted.meta.json"
SNAPSHOT_DIR = EVAL_DIR / "data" / "snapshots"

BODY_CHAR_LIMIT = 25_000
HEAD_CHAR_LIMIT = 8_000
AGENT_BROWSER_TIMEOUT = 45  # seconds per CLI call

GOLD_COLUMNS = [
    "No", "DOI", "Link", "Authors", "Abstract", "PDF URL",
    "Status", "Notes", "Has Bot Check", "Resolves To PDF",
    "broken_doi", "no english",
]

EXTRACTION_TOOL = {
    "name": "record_extraction",
    "description": (
        "Record the extracted metadata for a scholarly article's landing page. "
        "Fill only from the provided page content; never fabricate."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "authors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "affiliations": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            "abstract": {"type": ["string", "null"]},
            "pdf_url": {"type": ["string", "null"]},
            "has_bot_check": {"type": "boolean"},
            "resolves_to_pdf": {"type": "boolean"},
            "broken_doi": {"type": "boolean"},
            "no_english": {"type": "boolean"},
            "notes": {"type": ["string", "null"]},
        },
        "required": [
            "authors", "abstract", "pdf_url",
            "has_bot_check", "resolves_to_pdf", "broken_doi", "no_english",
        ],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "You extract scholarly-article metadata from publisher landing-page content. "
    "You will be given the resolved URL, a snippet of the page's <head> HTML "
    "(to catch `citation_*` and `og:*` meta tags), and the visible body text. "
    "Return ONLY the `record_extraction` tool call — no free-form text. "
    "Rules:\n"
    "- authors: list each author as seen on the page, in order. Include affiliations if present, empty array otherwise.\n"
    "- abstract: verbatim abstract paragraph(s) if present; null if the page shows no abstract.\n"
    "- pdf_url: absolute URL to the article PDF if the page links one; null otherwise.\n"
    "- has_bot_check: true if the page shows a captcha, Cloudflare challenge, "
    "  'access denied', 'there was a problem providing the content', Akamai-block, or similar.\n"
    "- resolves_to_pdf: true if the page's own URL ends in '.pdf'.\n"
    "- broken_doi: true if the DOI resolver returned a 404 / 'DOI not found' page.\n"
    "- no_english: true if the page's primary content language is not English.\n"
    "- notes: short free-text observations (paywall, partial metadata, etc.), or null."
)


@dataclass
class AgentBrowserResult:
    resolved_url: str | None
    head_html: str
    body_text: str
    open_stderr: str
    errors: list[str] = field(default_factory=list)


@dataclass
class ExtractedRow:
    no: int
    doi: str
    link: str
    extraction: dict[str, Any]
    resolved_url: str | None
    snapshot_path: str | None
    model: str
    usage: dict[str, int]
    cost_usd: float
    duration_s: float
    error: str | None


def _load_client():
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed") from e
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set (expected in eval/.env)")
    return Anthropic(api_key=api_key)


def _run_ab(args: list[str], timeout: int = AGENT_BROWSER_TIMEOUT) -> subprocess.CompletedProcess:
    """Invoke agent-browser CLI; never raise — callers inspect returncode."""
    return subprocess.run(
        ["agent-browser", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def fetch_page(url: str) -> AgentBrowserResult:
    errors: list[str] = []
    open_res = _run_ab(["open", url, "--headed"])
    if open_res.returncode != 0:
        errors.append(f"open failed rc={open_res.returncode}: {open_res.stderr.strip()[:200]}")

    url_res = _run_ab(["get", "url"])
    resolved = url_res.stdout.strip() if url_res.returncode == 0 else None

    head_res = _run_ab(["get", "html", "head"])
    head_html = head_res.stdout[:HEAD_CHAR_LIMIT] if head_res.returncode == 0 else ""
    if head_res.returncode != 0:
        errors.append(f"get html head rc={head_res.returncode}")

    body_res = _run_ab(["get", "text", "body"])
    body_text = body_res.stdout[:BODY_CHAR_LIMIT] if body_res.returncode == 0 else ""
    if body_res.returncode != 0:
        errors.append(f"get text body rc={body_res.returncode}")

    return AgentBrowserResult(
        resolved_url=resolved,
        head_html=head_html,
        body_text=body_text,
        open_stderr=open_res.stderr,
        errors=errors,
    )


def save_snapshot(doi: str, page: AgentBrowserResult) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(doi.encode("utf-8")).hexdigest()
    path = SNAPSHOT_DIR / f"{key}.json"
    path.write_text(
        json.dumps({
            "doi": doi,
            "resolved_url": page.resolved_url,
            "head_html": page.head_html,
            "body_text": page.body_text,
            "errors": page.errors,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_user_message(doi: str, page: AgentBrowserResult) -> str:
    return (
        f"DOI: {doi}\n"
        f"Resolved URL: {page.resolved_url or '(unknown)'}\n\n"
        f"<head> HTML ({len(page.head_html)} chars):\n{page.head_html}\n\n"
        f"Body text ({len(page.body_text)} chars):\n{page.body_text}"
    )


def call_claude(client, model: str, doi: str, page: AgentBrowserResult) -> tuple[dict, dict]:
    """Return (extraction_dict, usage_dict)."""
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_extraction"},
        messages=[{"role": "user", "content": build_user_message(doi, page)}],
    )
    tool_blocks = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
    if not tool_blocks:
        raise RuntimeError("Claude returned no tool_use block")
    extraction = dict(tool_blocks[0].input)
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
    }
    return extraction, usage


def extract_one(row: dict[str, str], client, model: str) -> ExtractedRow:
    no = int(row["No"])
    doi = row["DOI"]
    link = row["Link"]
    start = time.monotonic()
    try:
        page = fetch_page(link)
        snapshot_path = save_snapshot(doi, page)
        if not page.body_text and not page.head_html:
            duration = time.monotonic() - start
            return ExtractedRow(
                no=no, doi=doi, link=link,
                extraction={}, resolved_url=page.resolved_url,
                snapshot_path=str(snapshot_path),
                model=model, usage={}, cost_usd=0.0, duration_s=duration,
                error=f"empty page: {'; '.join(page.errors) or 'unknown'}",
            )
        extraction, usage = call_claude(client, model, doi, page)
        cost = compute_anthropic_cost(model, **usage)
        return ExtractedRow(
            no=no, doi=doi, link=link,
            extraction=extraction, resolved_url=page.resolved_url,
            snapshot_path=str(snapshot_path), model=model, usage=usage,
            cost_usd=cost, duration_s=time.monotonic() - start, error=None,
        )
    except subprocess.TimeoutExpired as e:
        return ExtractedRow(
            no=no, doi=doi, link=link, extraction={}, resolved_url=None,
            snapshot_path=None, model=model, usage={}, cost_usd=0.0,
            duration_s=time.monotonic() - start, error=f"timeout: {e}",
        )
    except Exception as e:
        return ExtractedRow(
            no=no, doi=doi, link=link, extraction={}, resolved_url=None,
            snapshot_path=None, model=model, usage={}, cost_usd=0.0,
            duration_s=time.monotonic() - start,
            error=f"{type(e).__name__}: {e}",
        )


def extraction_to_gold_row(row: ExtractedRow) -> dict[str, str]:
    e = row.extraction or {}
    authors = e.get("authors") or []
    status = "FALSE" if (e.get("has_bot_check") or row.error) else "TRUE"
    return {
        "No": row.no,
        "DOI": row.doi,
        "Link": row.link,
        "Authors": json.dumps(authors, ensure_ascii=False) if authors else "",
        "Abstract": e.get("abstract") or "",
        "PDF URL": e.get("pdf_url") or "",
        "Status": status,
        "Notes": e.get("notes") or (row.error or ""),
        "Has Bot Check": str(bool(e.get("has_bot_check"))).upper() if e else "",
        "Resolves To PDF": str(bool(e.get("resolves_to_pdf"))).upper() if e else "",
        "broken_doi": str(bool(e.get("broken_doi"))).upper() if e else "",
        "no english": str(bool(e.get("no_english"))).upper() if e else "",
    }


def write_outputs(results: list[ExtractedRow]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=GOLD_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow(extraction_to_gold_row(r))
    META_JSON.write_text(
        json.dumps({
            "rows": [asdict(r) for r in results],
            "totals": {
                "rows": len(results),
                "errors": sum(1 for r in results if r.error),
                "cost_usd": round(sum(r.cost_usd for r in results), 4),
                "wall_seconds": round(sum(r.duration_s for r in results), 2),
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(INPUT_CSV))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap the number of DOIs processed (for smoke tests).")
    args = ap.parse_args()

    client = _load_client()
    with open(args.input, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]

    log.info("extracting %d DOIs via agent-browser + %s", len(rows), args.model)
    results: list[ExtractedRow] = []
    for row in rows:
        r = extract_one(row, client, args.model)
        results.append(r)
        status = "err" if r.error else "ok"
        log.info("[%s] %s/%s %s  $%.4f  %.1fs",
                 status, r.no, len(rows), r.doi, r.cost_usd, r.duration_s)

    _run_ab(["close"], timeout=15)
    write_outputs(results)

    total_cost = sum(r.cost_usd for r in results)
    errors = sum(1 for r in results if r.error)
    print(f"wrote {len(results)} rows, {errors} errors, total cost ${total_cost:.4f}")
    print(f"  csv:  {OUTPUT_CSV}")
    print(f"  meta: {META_JSON}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
