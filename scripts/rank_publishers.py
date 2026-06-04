#!/usr/bin/env python3
"""Pathfinder — rank publishers by whole-Goldie KPI opportunity.

Reads merged-FINAL.csv, classifies every row via scripts/lib/publisher_index,
groups by publisher, computes priority, emits mismatches/publisher-queue.ndjson.

Priority formula:
    priority = (1 - current_f1) * row_volume * tractability

- current_f1: from --baseline-run JSON's summary.per_publisher.<pub>.authors_f1_soft
  (or any field present); default 0.5 if unknown.
- row_volume: row count for that publisher in merged-FINAL.csv.
- tractability: 1.0 if a dedicated parser file exists, 0.5 for generic-only,
  0.0 if marked unsupported.

Usage:
    python scripts/rank_publishers.py \\
        --corpus /Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval/data/merged-FINAL.csv \\
        --out mismatches/publisher-queue.ndjson

Emits NDJSON rows sorted by priority desc, plus a small JSON summary at
<out>.summary.json with row count, publisher count, unknown count, and the
top-10 publishers.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

# Make scripts/lib importable when run from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.publisher_index import (  # noqa: E402
    classify_row,
    doi_prefix,
    publisher_parser_file,
    _load_registrant_cache,
    _save_registrant_cache,
)
from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402


PARSERS_DIR = REPO_ROOT / "parseland_lib" / "publisher" / "parsers"


def discover_supported_publishers() -> set[str]:
    """Return the set of publisher_id slugs that have a dedicated parser file.

    A parser file is `<publisher_id>.py` (excluding parser.py, utils.py,
    generic.py, __init__.py).
    """
    if not PARSERS_DIR.exists():
        return set()
    excluded = {"__init__", "parser", "utils", "generic", "nejm_unformatted_utils"}
    return {
        p.stem
        for p in PARSERS_DIR.glob("*.py")
        if p.stem not in excluded
    }


def parser_status(publisher_id: str, supported: set[str]) -> tuple[str, float]:
    """Return (status, tractability) for a publisher."""
    if publisher_id == "unknown":
        return ("unsupported-no-parser", 0.0)
    parser_file = publisher_parser_file(publisher_id)
    if parser_file in supported:
        return ("supported", 1.0)
    return ("generic-only", 0.5)


def load_baseline_f1(path: Path | None) -> dict[str, float]:
    """Read a whole-Goldie run JSON and extract per-publisher current_f1.

    Picks the first available F1-style metric per publisher. Default 0.5 for
    publishers absent from the baseline.
    """
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    out: dict[str, float] = {}
    per_pub = (data.get("summary") or {}).get("per_publisher") or {}
    for pub, stats in per_pub.items():
        # Prefer authors_f1_soft, fall back to any *_f1 or *_accuracy metric
        if "authors_f1_soft" in stats:
            out[pub] = float(stats["authors_f1_soft"])
        elif "authors_f1_strict" in stats:
            out[pub] = float(stats["authors_f1_strict"])
        else:
            for k, v in stats.items():
                if isinstance(v, (int, float)) and ("_f1" in k or "accuracy" in k):
                    out[pub] = float(v)
                    break
    return out


FIXTURE_ALIAS: dict[str, str] = {
    "oxford": "oup-gold.ndjson",
    "lippincott": "wolters-kluwer-gold.ndjson",
    "elsevier": "elsevier-10k-gold.ndjson",
}


def discover_gold_fixture(publisher_id: str) -> str | None:
    """Best-effort lookup of a per-publisher gold fixture path."""
    fixtures_dir = REPO_ROOT / "tests" / "fixtures"
    candidates = [
        FIXTURE_ALIAS.get(publisher_id),
        f"{publisher_id}-10k-gold.ndjson",
        f"{publisher_id}-gold.ndjson",
        f"{publisher_id.replace('_', '-')}-gold.ndjson",
    ]
    for c in candidates:
        if not c:
            continue
        p = fixtures_dir / c
        if p.exists():
            return str(p.relative_to(REPO_ROOT))
    return None


def rank(
    corpus_path: Path,
    out_path: Path,
    *,
    baseline_run: Path | None = None,
    allow_network: bool = True,
    run_id: str | None = None,
) -> dict:
    """Build the ranked publisher queue."""
    run_id = run_id or new_run_id()
    t_start = time.time()

    emit(run_id=run_id, action="rank.start", agent_name="rank_publishers",
         notes=f"corpus={corpus_path.name}")

    supported = discover_supported_publishers()
    baseline_f1 = load_baseline_f1(baseline_run)
    reg_cache = _load_registrant_cache()

    by_pub: dict[str, dict] = {}
    total_rows = 0
    unknown_rows = 0

    with open(corpus_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            pub = classify_row(row, allow_network=allow_network, _cache=reg_cache)
            if pub == "unknown":
                unknown_rows += 1
            d = by_pub.setdefault(pub, {
                "publisher_id": pub,
                "row_count": 0,
                "doi_prefixes": set(),
                "sample_doi": row.get("DOI") or "",
                "sample_link": row.get("Link") or "",
            })
            d["row_count"] += 1
            prefix = doi_prefix(row.get("DOI") or "")
            if prefix:
                d["doi_prefixes"].add(prefix)

    # Persist any newly-resolved registrant entries
    _save_registrant_cache(reg_cache)

    # Compute priority + assemble output rows
    ranked: list[dict] = []
    for pub, d in by_pub.items():
        status, tractability = parser_status(pub, supported)
        current_f1 = baseline_f1.get(pub, 0.5)
        priority = (1.0 - current_f1) * d["row_count"] * tractability
        gold_fixture = discover_gold_fixture(pub)
        confidence_tier = "high" if pub in supported else ("medium" if pub != "unknown" else "low")
        ranked.append({
            "publisher_id": pub,
            "display_name": pub,
            "doi_prefixes": sorted(d["doi_prefixes"]),
            "row_count": d["row_count"],
            "current_f1": current_f1,
            "tractability": tractability,
            "parser_status": status,
            "confidence_tier": confidence_tier,
            "priority": round(priority, 4),
            "gold_fixture_path": gold_fixture,
            "sample_doi": d["sample_doi"],
            "sample_link": d["sample_link"],
            "artifact_pointers": {
                "baseline": None,
                "classified": None,
            },
        })
    ranked.sort(key=lambda r: r["priority"], reverse=True)

    # Cumulative coverage
    cumulative = 0
    for r in ranked:
        cumulative += r["row_count"]
        r["cumulative_coverage"] = round(cumulative / total_rows, 4) if total_rows else 0.0

    # Write NDJSON queue
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in ranked:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Summary
    top10 = [
        {"publisher_id": r["publisher_id"], "row_count": r["row_count"],
         "priority": r["priority"], "parser_status": r["parser_status"]}
        for r in ranked[:10]
    ]
    summary = {
        "run_id": run_id,
        "corpus_path": str(corpus_path),
        "out_path": str(out_path),
        "total_rows": total_rows,
        "publisher_count": len(ranked),
        "unknown_rows": unknown_rows,
        "supported_count": sum(1 for r in ranked if r["parser_status"] == "supported"),
        "generic_only_count": sum(1 for r in ranked if r["parser_status"] == "generic-only"),
        "unsupported_count": sum(1 for r in ranked if r["parser_status"] == "unsupported-no-parser"),
        "baseline_run_used": str(baseline_run) if baseline_run else None,
        "duration_ms": int((time.time() - t_start) * 1000),
        "top10": top10,
    }
    summary_path = out_path.with_suffix(out_path.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))

    emit(
        run_id=run_id,
        action="rank.complete",
        agent_name="rank_publishers",
        progress_current=total_rows,
        progress_total=total_rows,
        duration_ms=summary["duration_ms"],
        artifact_path=str(out_path),
        notes=f"{len(ranked)} publishers, {unknown_rows} unknown rows",
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus", type=Path, required=True,
        help="Path to merged-FINAL.csv (whole Goldie).",
    )
    p.add_argument(
        "--out", type=Path,
        default=REPO_ROOT / "mismatches" / "publisher-queue.ndjson",
        help="Output NDJSON path.",
    )
    p.add_argument(
        "--baseline-run", type=Path,
        help="Optional whole-Goldie run JSON for current_f1 seeding.",
    )
    p.add_argument(
        "--no-network", action="store_true",
        help="Disable CrossRef registrant lookups; use only cached + curated maps.",
    )
    p.add_argument("--run-id", type=str, help="Sprint run id (default: new).")
    args = p.parse_args()

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 2

    summary = rank(
        args.corpus,
        args.out,
        baseline_run=args.baseline_run,
        allow_network=not args.no_network,
        run_id=args.run_id,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
