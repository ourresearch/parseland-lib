"""Score an Anthropic extraction prompt against the 50-row holdout.

Mirrors `runner.py` → `aggregate.py` → `report.py`, but the parser is a
Claude model instead of parseland-lib. The resulting run JSON lands in
`eval/runs/prompt-<model>-<label>-<timestamp>.json` so the dashboard shows
it alongside parseland-lib baselines.

Pass gate (recommended, not enforced here): per-field F1 within ±5% of,
or above, parseland-lib's current baseline. Tune after first runs.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from parseland_eval.expand import DEFAULT_MODEL, PROMPT_VERSION, _load_client, extract_one
from parseland_eval.gold import load_gold
from parseland_eval.paths import GOLD_HOLDOUT_JSON
from parseland_eval.report import write_run
from parseland_eval.runner import ParserRun, _publisher_domain
from parseland_eval.score.aggregate import score_row, summarize

log = logging.getLogger(__name__)


def _silver_to_parser_run(row, silver) -> ParserRun:
    ext = silver.extraction or {}
    parsed = None if silver.error else {
        "authors": ext.get("authors") or [],
        "abstract": ext.get("abstract"),
        "pdf_url": ext.get("pdf_url"),
        "urls": [{"url": ext["pdf_url"], "content_type": "pdf"}] if ext.get("pdf_url") else [],
    }
    return ParserRun(
        doi=row.doi,
        parsed=parsed,
        error=silver.error,
        duration_ms=0.0,
        html_cached=True,
        publisher_domain=_publisher_domain(row.link),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--label", required=True, help="Short label, e.g. sonnet-v1")
    args = ap.parse_args()

    gold_rows = load_gold(path=GOLD_HOLDOUT_JSON)
    client = _load_client()

    parser_runs: list[ParserRun] = []
    for row in gold_rows:
        t0 = time.perf_counter()
        silver = extract_one(row.doi, client=client, model=args.model)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        pr = _silver_to_parser_run(row, silver)
        parser_runs.append(ParserRun(
            doi=pr.doi, parsed=pr.parsed, error=pr.error,
            duration_ms=elapsed_ms, html_cached=pr.html_cached,
            publisher_domain=pr.publisher_domain,
        ))
        log.info("row %s: %s (%.0fms)", row.no, "ok" if silver.error is None else silver.error, elapsed_ms)

    scores = [score_row(g, r) for g, r in zip(gold_rows, parser_runs)]
    summary = summarize(scores)
    label = f"prompt-{args.model}-{args.label}-{PROMPT_VERSION}"
    out = write_run(gold_rows, parser_runs, scores, summary, label=label)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
