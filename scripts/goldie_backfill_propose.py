#!/usr/bin/env python3
"""Goldie-backfilled candidate proposer.

For rows where current Goldie has a missing field but Parseland extracted a
plausible value, propose a candidate for Goldie-backfilled enrichment. The
candidate is NOT a label - it's a proposal that must be Browserbase-grounded
and Referee-approved before becoming a derived corpus row.

Per the user's policy:
- Parseland output is only a candidate claim.
- Browserbase-rendered page evidence is the grounding source (handled by a
  separate goldie_backfill_ground.py / Browserbase agent).
- Referee/gold-auditor must approve before status flips from `pending` to
  `approved`.
- Never mutate merged-FINAL.csv.
- Do not count Goldie-backfilled as current-Goldie parser KPI lift.

Schema per candidate (NDJSON):
    doi, publisher, field, gold_value (null), parseland_candidate,
    browserbase_url (null), browserbase_session (null), evidence_excerpt (null),
    confidence, approving_agent (null), status, rejection_reason (null),
    proposed_at, source_run

Initial priority order:
  1. IEEE authors where gold has 0 authors but page visibly has them
  2. affiliations/rasses missing in gold but parser found them
  3. abstracts missing in gold but parser found them
  4. corresponding author missing in gold but parser flagged is_corresponding=True
  5. PDF URL missing in gold but parser found one

Usage:
    python scripts/goldie_backfill_propose.py
    python scripts/goldie_backfill_propose.py --run eval/runs/<latest>.json \\
        --fields authors,abstract,affiliations,corresponding,pdf_url
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from parseland_lib.parse import parse_page  # noqa: E402
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402
from scripts.lib.publisher_index import classify_row, _load_registrant_cache  # noqa: E402

DEFAULT_CACHE_DIR = REPO_ROOT / "mismatches" / "whole-goldie-cache"


def latest_run() -> Path | None:
    runs = sorted((REPO_ROOT / "eval" / "runs").glob("whole-goldie-*.json"),
                  key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None


def _doi_hash(doi: str) -> str:
    return hashlib.sha1(doi.lower().encode()).hexdigest()


def _read_cached_html(doi: str, cache_dir: Path) -> str | None:
    path = cache_dir / f"{_doi_hash(doi)}.html"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _affiliation_values(raw: Any) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    if not raw:
        return values
    items = raw.split(";") if isinstance(raw, str) else raw
    for item in items:
        if isinstance(item, dict):
            value = item.get("name") or item.get("raw_string") or item.get("value")
        else:
            value = item
        text = " ".join(str(value or "").split()).strip()
        if text:
            values.append({"name": text})
    return values


def _author_to_candidate_dict(author: Any) -> dict[str, Any] | None:
    if isinstance(author, dict):
        name = " ".join(str(author.get("name") or "").split()).strip()
        affiliations = _affiliation_values(author.get("affiliations") or author.get("rasses") or [])
        is_corresponding = author.get("is_corresponding")
        if is_corresponding is None:
            is_corresponding = author.get("corresponding_author")
    else:
        name = " ".join(str(getattr(author, "name", "") or "").split()).strip()
        affiliations = _affiliation_values(getattr(author, "affiliations", []) or [])
        is_corresponding = getattr(author, "is_corresponding", None)
        if is_corresponding is None:
            is_corresponding = getattr(author, "corresponding_author", None)
    if not name:
        return None
    return {
        "name": name,
        "affiliations": affiliations,
        "is_corresponding": bool(is_corresponding) if is_corresponding is not None else None,
    }


def _corresponding_authors_from_cached_html(
    *,
    doi: str,
    link: str,
    cache_dir: Path,
) -> tuple[list[dict[str, Any]], str | None]:
    html = _read_cached_html(doi, cache_dir)
    if not html:
        return [], "missing_cached_html"
    try:
        parsed = parse_page(html, namespace="doi", resolved_url=link)
    except Exception as exc:  # noqa: BLE001
        return [], f"parse_failed:{type(exc).__name__}"
    authors = (parsed or {}).get("authors") or []
    corresponding: list[dict[str, Any]] = []
    for author in authors:
        row = _author_to_candidate_dict(author)
        if row and row.get("is_corresponding"):
            corresponding.append(row)
    return corresponding, None


def propose_for_row(row: dict, gold_row: dict, publisher: str,
                    fields: set[str], cache_dir: Path = DEFAULT_CACHE_DIR) -> list[dict]:
    """Yield candidate dicts for fields where gold is missing and parser found
    something plausible."""
    out: list[dict] = []
    parsed = row.get("parsed") or {}
    gold_info = row.get("gold") or {}
    score = row.get("score") or {}

    # Authors: gold_n_authors == 0 but parser found > 0
    if "authors" in fields:
        if gold_info.get("n_authors", 0) == 0 and parsed.get("n_authors", 0) > 0:
            # Need the raw parsed authors; load directly from run
            out.append({
                "field": "authors",
                "gold_value": None,
                "parseland_candidate": {
                    "n_authors": parsed.get("n_authors", 0),
                    # We don't have the actual names here; need to read the
                    # row's full parsed payload. The summary lite shape used
                    # by whole_goldie_eval doesn't keep author names per row.
                    # Flag for re-resolution by Browserbase agent.
                    "note": "n_authors only - full author list to be resolved from cached HTML by Browserbase agent",
                },
                "confidence": "high",  # parser found authors and gold has zero - gold-missing case
                "evidence_excerpt": None,
            })

    # Abstract: gold_abstract empty but parser found > 100 chars
    if "abstract" in fields:
        if gold_info.get("abstract_len", 0) == 0 and parsed.get("abstract_len", 0) > 100:
            out.append({
                "field": "abstract",
                "gold_value": None,
                "parseland_candidate": {
                    "abstract_len": parsed.get("abstract_len", 0),
                    "note": "full text in cached HTML; Browserbase agent to extract + ground",
                },
                "confidence": "medium",  # gold-empty + parser-found is plausible but needs verification
                "evidence_excerpt": None,
            })

    # PDF URL: gold has none but parser produced one
    if "pdf_url" in fields:
        urls = parsed.get("urls", [])
        parser_pdf = next(
            (u["url"] for u in urls if isinstance(u, dict) and u.get("content_type") == "pdf"),
            None,
        )
        if not gold_info.get("has_pdf_url") and parser_pdf:
            out.append({
                "field": "pdf_url",
                "gold_value": None,
                "parseland_candidate": {"pdf_url": parser_pdf},
                "confidence": "medium",
                "evidence_excerpt": None,
            })

    # Corresponding: newer whole-Goldie rows preserve the branch status but not
    # the flagged author payload, so reparse the cached Taxicab/R2 HTML to carry
    # exact candidate names into Browserbase grounding.
    if "corresponding" in fields:
        status = (row.get("field_status") or {}).get("corresponding")
        if status == "gold_empty_parser_present":
            authors, blocker = _corresponding_authors_from_cached_html(
                doi=str(row.get("doi") or ""),
                link=str(row.get("link") or ""),
                cache_dir=cache_dir,
            )
            if authors:
                out.append({
                    "field": "corresponding",
                    "gold_value": None,
                    "parseland_candidate": {"authors": authors},
                    "confidence": "candidate",
                    "evidence_excerpt": None,
                })
            elif blocker:
                out.append({
                    "field": "corresponding",
                    "gold_value": None,
                    "parseland_candidate": {
                        "authors": [],
                        "blocker": blocker,
                    },
                    "confidence": "blocked",
                    "evidence_excerpt": None,
                    "status": "blocked_candidate_reparse",
                    "rejection_reason": blocker,
                })

    # Affiliations also need per-author detail that the lite whole-goldie
    # payload doesn't preserve; leave that to publisher-specific proposers for
    # now rather than emitting weak labels.

    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=None,
                   help="Whole-Goldie run JSON")
    p.add_argument("--corpus", type=Path,
                   default=Path("/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv"))
    p.add_argument("--out", type=Path,
                   default=REPO_ROOT / "mismatches" / "goldie-backfilled-candidates.ndjson")
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                   help="Cached landing-page HTML directory keyed by SHA1(lowercase DOI)")
    p.add_argument("--fields", type=str,
                   default="authors,abstract,pdf_url",
                   help="Comma-separated fields to propose for")
    p.add_argument("--publishers", type=str,
                   help="Optional comma-separated publisher ids to include")
    p.add_argument("--limit", type=int, help="Max candidates to propose")
    p.add_argument("--append", action="store_true",
                   help="Append to existing candidates file (default: overwrite)")
    args = p.parse_args()

    run_path = args.run or latest_run()
    if not run_path or not run_path.exists():
        print("ERROR: no run found", file=sys.stderr)
        return 2

    run = json.loads(run_path.read_text())
    fields = {field.strip() for field in args.fields.split(",") if field.strip()}
    publishers = {pub.strip() for pub in args.publishers.split(",") if pub.strip()} if args.publishers else None
    reg_cache = _load_registrant_cache()
    seen: set[tuple[str, str]] = set()
    if args.append and args.out.exists():
        with open(args.out, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seen.add((str(existing.get("doi", "")).lower(), str(existing.get("field", ""))))

    # Map DOI → gold row
    with open(args.corpus, "r", encoding="utf-8") as f:
        gold_by_doi = {r["DOI"]: r for r in csv.DictReader(f)}

    run_id = new_run_id()
    emit(run_id=run_id, action="goldie_backfill.start",
         agent_name="goldie_backfill_propose",
         notes=f"fields={sorted(fields)} run={run_path.name}")

    candidates: list[dict] = []
    for row in run.get("rows", []):
        if row.get("skipped_no_html") or row.get("error"):
            continue
        doi = row.get("doi", "")
        gr = gold_by_doi.get(doi, {})
        publisher = classify_row({"DOI": doi, "Link": row.get("link", "")},
                                 allow_network=False, _cache=reg_cache)
        if publishers is not None and publisher not in publishers:
            continue
        proposals = propose_for_row(row, gr, publisher, fields, args.cache_dir)
        for prop in proposals:
            key = (str(doi).lower(), str(prop.get("field") or ""))
            if key in seen:
                continue
            cand = {
                "doi": doi,
                "publisher": publisher,
                **prop,
                "browserbase_url": None,
                "browserbase_session": None,
                "approving_agent": None,
                "status": prop.get("status", "pending_browserbase"),
                "rejection_reason": prop.get("rejection_reason"),
                "proposed_at": datetime.now(timezone.utc).isoformat(),
                "source_run": str(run_path.name),
            }
            candidates.append(cand)
            seen.add(key)
            if args.limit and len(candidates) >= args.limit:
                break
        if args.limit and len(candidates) >= args.limit:
            break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"
    with open(args.out, mode, encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # Summary
    by_field: dict[str, int] = {}
    by_publisher: dict[str, int] = {}
    for c in candidates:
        by_field[c["field"]] = by_field.get(c["field"], 0) + 1
        by_publisher[c["publisher"]] = by_publisher.get(c["publisher"], 0) + 1

    emit(run_id=run_id, action="goldie_backfill.complete",
         agent_name="goldie_backfill_propose",
         artifact_path=str(args.out),
         notes=f"proposed {len(candidates)}: by_field={by_field}")

    print(json.dumps({
        "candidates_proposed": len(candidates),
        "by_field": by_field,
        "by_publisher_top": dict(sorted(by_publisher.items(), key=lambda kv: -kv[1])[:10]),
        "out": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
