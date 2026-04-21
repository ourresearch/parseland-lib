"""Pilot Pass B: agentic extraction — Claude drives agent-browser via tool-use.

For each DOI in `eval/data/random-50.csv`, spins up an agent loop where Claude
can call a set of browser tools (open / snapshot / get_text / get_html / click /
scroll) to explore the landing page, then calls `record_extraction` to emit
gold-standard-shaped JSON.

Output mirrors P2a's layout with two extra meta fields per row:
- turn_count        : assistant turns until `record_extraction` (or abort)
- tool_calls_by_name: dict of tool_name -> int

Sequential per-DOI; the agent-browser daemon stays alive across DOIs so
navigation is fast. Claude API calls are sequential (one DOI at a time).
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
from collections import Counter
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
OUTPUT_CSV = EVAL_DIR / "data" / "random-50-agentic.csv"
META_JSON = EVAL_DIR / "data" / "random-50-agentic.meta.json"
SNAPSHOT_DIR = EVAL_DIR / "data" / "snapshots-agentic"

MAX_TURNS = 15
MAX_INPUT_TOKENS_PER_DOI = 40_000
AGENT_BROWSER_TIMEOUT = 45
TOOL_RESULT_CHAR_LIMIT = 12_000  # truncate tool outputs before sending back

GOLD_COLUMNS = [
    "No", "DOI", "Link", "Authors", "Abstract", "PDF URL",
    "Status", "Notes", "Has Bot Check", "Resolves To PDF",
    "broken_doi", "no english",
]

# -- Tool schemas --------------------------------------------------------------

BROWSER_TOOLS = [
    {
        "name": "browser_open",
        "description": (
            "Open a URL in the headless browser. Navigates the existing tab. "
            "Returns the resolved URL after any redirects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "browser_snapshot",
        "description": (
            "Return the accessibility-tree snapshot of the current page with @eN "
            "refs for each interactive element. Compact; good starting point. "
            "Re-snapshot after any action that changes the DOM (click, scroll, nav)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "interactive_only": {
                    "type": "boolean",
                    "description": "If true (default), only interactive elements. False = full tree.",
                },
            },
        },
    },
    {
        "name": "browser_get_text",
        "description": (
            "Get visible text of a DOM element. Default selector is 'body' "
            "(entire page). Use to grab the abstract paragraph, author list, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or @eN ref. Defaults to 'body'.",
                },
            },
        },
    },
    {
        "name": "browser_get_html",
        "description": (
            "Get innerHTML of a DOM element. Useful for 'head' to read meta tags "
            "(citation_author, citation_abstract, citation_pdf_url, og:*). "
            "Default selector is 'head'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or @eN ref. Defaults to 'head'.",
                },
            },
        },
    },
    {
        "name": "browser_click",
        "description": (
            "Click an element by @eN ref. Use for 'Show more' on truncated "
            "abstracts, tab switchers, disclosure triggers. Re-snapshot after."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ref": {"type": "string", "description": "Like '@e3'."}},
            "required": ["ref"],
        },
    },
    {
        "name": "browser_scroll",
        "description": (
            "Scroll the page. Use to reveal lazy-loaded content (authors, refs). "
            "Direction one of 'down', 'up'. Pixels default 600."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]},
                "pixels": {"type": "integer"},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "record_extraction",
        "description": (
            "Emit the final extraction. Calling this ends the session. "
            "Only call once you've gathered all fields you can from the page."
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
    },
]

SYSTEM_PROMPT = """You are a scholarly-metadata extractor. Given a single DOI URL, \
drive a headless Chrome browser to extract the article's metadata, then emit \
`record_extraction`.

Standard workflow per DOI:
1. browser_open(url) — navigate.
2. browser_snapshot() — see what's on the page.
3. browser_get_html(head) — read <head> meta tags (citation_author, \
citation_abstract, citation_pdf_url, og:*). Many publishers expose full metadata here.
4. browser_get_text(body) — if head doesn't have abstract / full author list, \
read the visible page text.
5. If content is behind UI (Show more, tabs, lazy-load) — click / scroll / re-snapshot.
6. Call record_extraction with what you found. If the page is bot-checked, \
broken, or non-English, set the appropriate flag and note it.

Rules:
- Be token-efficient. Prefer browser_snapshot (compact) and browser_get_html(head) \
(meta tags) before pulling body text.
- Don't loop indefinitely: call record_extraction as soon as you have enough.
- If a page shows a bot-check / captcha / Cloudflare / "problem providing content" \
message, set has_bot_check=true and move on — don't try to bypass it.
- Authors: list as they appear on the page, in order. Include affiliations if present.
- Abstract: verbatim if present, null otherwise.
- pdf_url: absolute URL if a PDF link is on the page, null otherwise.
"""


# -- Agent-browser subprocess helpers ------------------------------------------

def _run_ab(args: list[str], timeout: int = AGENT_BROWSER_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["agent-browser", *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def _truncate(s: str, limit: int = TOOL_RESULT_CHAR_LIMIT) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n\n[...truncated {len(s) - limit} more chars]"


def _exec_tool(name: str, args: dict[str, Any]) -> str:
    """Dispatch a Claude tool_use to an agent-browser CLI call. Return text."""
    if name == "browser_open":
        r = _run_ab(["open", args["url"], "--headed"])
        if r.returncode != 0:
            return f"ERROR: open returned rc={r.returncode}\n{r.stderr[:400]}"
        url_r = _run_ab(["get", "url"])
        resolved = url_r.stdout.strip() if url_r.returncode == 0 else "(unknown)"
        return f"opened. resolved_url={resolved}\n{r.stdout[:400]}"

    if name == "browser_snapshot":
        interactive = args.get("interactive_only", True)
        cmd = ["snapshot"] + (["-i"] if interactive else [])
        r = _run_ab(cmd)
        return _truncate(r.stdout if r.returncode == 0 else f"ERROR: {r.stderr}")

    if name == "browser_get_text":
        selector = args.get("selector", "body")
        r = _run_ab(["get", "text", selector])
        return _truncate(r.stdout if r.returncode == 0 else f"ERROR: {r.stderr}")

    if name == "browser_get_html":
        selector = args.get("selector", "head")
        r = _run_ab(["get", "html", selector])
        return _truncate(r.stdout if r.returncode == 0 else f"ERROR: {r.stderr}")

    if name == "browser_click":
        r = _run_ab(["click", args["ref"]])
        return r.stdout if r.returncode == 0 else f"ERROR: {r.stderr[:400]}"

    if name == "browser_scroll":
        direction = args["direction"]
        pixels = str(args.get("pixels", 600))
        r = _run_ab(["scroll", direction, pixels])
        return r.stdout if r.returncode == 0 else f"ERROR: {r.stderr[:400]}"

    return f"ERROR: unknown tool {name!r}"


# -- Client + loop -------------------------------------------------------------

def _load_client():
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed") from e
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set (expected in eval/.env)")
    return Anthropic(api_key=api_key)


@dataclass
class AgentRunResult:
    doi: str
    link: str
    extraction: dict[str, Any]
    turn_count: int
    tool_calls: dict[str, int]
    usage_total: dict[str, int]
    cost_usd: float
    error: str | None


def run_agent(client, model: str, doi: str, link: str) -> AgentRunResult:
    messages: list[dict[str, Any]] = [{
        "role": "user",
        "content": f"Extract metadata for DOI {doi} at {link}. Call record_extraction when done.",
    }]
    tool_counts: Counter[str] = Counter()
    usage_total = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
    }
    extraction: dict[str, Any] = {}
    error: str | None = None

    for turn in range(1, MAX_TURNS + 1):
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=BROWSER_TOOLS,
            messages=messages,
        )
        usage_total["input_tokens"] += resp.usage.input_tokens
        usage_total["output_tokens"] += resp.usage.output_tokens
        usage_total["cache_creation_input_tokens"] += (
            getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
        )
        usage_total["cache_read_input_tokens"] += (
            getattr(resp.usage, "cache_read_input_tokens", 0) or 0
        )
        if usage_total["input_tokens"] > MAX_INPUT_TOKENS_PER_DOI:
            error = f"input_token_budget_exceeded (turn {turn})"
            break

        # Record the assistant turn so tool_use IDs line up with tool_result.
        messages.append({"role": "assistant", "content": resp.content})

        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            error = f"assistant stopped without tool_use (stop_reason={resp.stop_reason})"
            break

        # Check for record_extraction -> final.
        final_block = next(
            (b for b in tool_uses if b.name == "record_extraction"), None
        )
        if final_block is not None:
            tool_counts["record_extraction"] += 1
            extraction = dict(final_block.input)
            break

        # Otherwise execute every tool_use and append results.
        tool_results = []
        for block in tool_uses:
            tool_counts[block.name] += 1
            try:
                output = _exec_tool(block.name, dict(block.input))
            except subprocess.TimeoutExpired as e:
                output = f"ERROR: timeout after {e.timeout}s"
            except Exception as e:  # noqa: BLE001 — tool failures are data, not crashes
                output = f"ERROR: {type(e).__name__}: {e}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })
        messages.append({"role": "user", "content": tool_results})
    else:
        error = f"max_turns ({MAX_TURNS}) reached without record_extraction"

    cost = compute_anthropic_cost(model, **usage_total)
    return AgentRunResult(
        doi=doi, link=link,
        extraction=extraction,
        turn_count=turn,
        tool_calls=dict(tool_counts),
        usage_total=usage_total,
        cost_usd=cost,
        error=error,
    )


# -- CSV writer ----------------------------------------------------------------

@dataclass
class AgenticRow:
    no: int
    doi: str
    link: str
    extraction: dict[str, Any]
    turn_count: int
    tool_calls: dict[str, int]
    usage: dict[str, int]
    cost_usd: float
    duration_s: float
    error: str | None


def extraction_to_gold_row(row: AgenticRow) -> dict[str, Any]:
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


def write_outputs(results: list[AgenticRow]) -> None:
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
                "total_turns": sum(r.turn_count for r in results),
                "tool_calls_by_name": dict(sum(
                    (Counter(r.tool_calls) for r in results), Counter()
                )),
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# -- Main ----------------------------------------------------------------------

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

    log.info("agentic extracting %d DOIs via %s", len(rows), args.model)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[AgenticRow] = []
    for row in rows:
        no = int(row["No"])
        doi = row["DOI"]
        link = row["Link"]
        start = time.monotonic()
        try:
            r = run_agent(client, args.model, doi, link)
            results.append(AgenticRow(
                no=no, doi=doi, link=link,
                extraction=r.extraction,
                turn_count=r.turn_count,
                tool_calls=r.tool_calls,
                usage=r.usage_total,
                cost_usd=r.cost_usd,
                duration_s=time.monotonic() - start,
                error=r.error,
            ))
        except Exception as e:  # noqa: BLE001
            results.append(AgenticRow(
                no=no, doi=doi, link=link,
                extraction={},
                turn_count=0,
                tool_calls={},
                usage={}, cost_usd=0.0,
                duration_s=time.monotonic() - start,
                error=f"{type(e).__name__}: {e}",
            ))
        last = results[-1]
        status = "err" if last.error else "ok"
        log.info("[%s] %s/%s %s  turns=%d  tools=%s  $%.4f  %.1fs",
                 status, last.no, len(rows), last.doi,
                 last.turn_count, sum(last.tool_calls.values()),
                 last.cost_usd, last.duration_s)

        # Save an intermediate snapshot of meta after every DOI so a crash
        # doesn't lose progress.
        (SNAPSHOT_DIR / f"{hashlib.sha1(doi.encode()).hexdigest()}.json").write_text(
            json.dumps(asdict(last), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
