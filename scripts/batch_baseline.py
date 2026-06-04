#!/usr/bin/env python3
"""Pathfinder/Craftsman bridge — drive per-publisher baseline + classification.

Reads mismatches/publisher-queue.ndjson, slices by --range (1-based, inclusive),
and for each publisher:
- supported + has gold fixture → runs scripts/field_inprocess_diff.py --all-fields
  via subprocess; artifact lands at mismatches/baselines/<publisher>-batch<n>.json
- supported but no gold fixture → marks 'gold-needed' (Pathfinder schedules
  gold-builder downstream)
- unsupported-no-parser → marks 'unsupported-no-parser', skips

Also writes mismatches/classified-batch<n>.ndjson with a simple per-publisher
failure cluster label using these rules:
- 'parser-owned'        : parser ran, scored low on at least one field
- 'scorer/gold-owned'   : parser output looks plausible but score is anomalously low
                          (defer to Referee/gold-auditor for verdict)
- 'harvest/router-owned': all rows in fixture errored (no HTML, etc.)
- 'unsupported-no-parser': no parser file
- 'generic-only'         : parser falls back to generic; needs dedicated parser
- 'smoke-only'           : fixture has < 20 rows; too small to drive a decision

Usage:
    python scripts/batch_baseline.py \\
        --queue mismatches/publisher-queue.ndjson \\
        --range 1-100 \\
        --batch-id 1 \\
        --concurrency 4
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
PARSELAND_EVAL_PATH = os.environ.get(
    "PARSELAND_EVAL_PATH",
    "/Users/shubh-trips/Documents/OpenAlex/parseland-eval/eval",
)

BASELINES_DIR = REPO_ROOT / "mismatches" / "baselines"
DIFF_SCRIPT = REPO_ROOT / "scripts" / "field_inprocess_diff.py"

# Field-level thresholds for the classifier. Below these means "low score".
LOW_SCORE_THRESHOLDS = {
    "authors_f1_soft": 0.80,
    "affiliations_f1_fuzzy": 0.80,
    "abstract_ratio_fuzzy": 0.80,
    "pdf_url_accuracy": 0.80,
    "corresponding_accuracy": 0.80,
}

# Below 20 rows we treat results as smoke-only.
SMOKE_ONLY_THRESHOLD = 20


@dataclass
class PublisherTask:
    rank: int
    publisher_id: str
    row_count: int
    parser_status: str
    gold_fixture_path: str | None
    priority: float
    confidence_tier: str


def load_queue(queue_path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(queue_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def parse_range(spec: str, n: int) -> tuple[int, int]:
    """Parse '1-100' (1-based inclusive). Caller may pass beyond n; we clamp."""
    if "-" not in spec:
        i = int(spec)
        return (i, i)
    a, b = spec.split("-", 1)
    lo = max(1, int(a))
    hi = min(n, int(b)) if b else n
    return (lo, hi)


def run_field_diff(task: PublisherTask, batch_id: int, run_id: str) -> dict:
    """Subprocess into field_inprocess_diff.py for this publisher.

    Returns a dict describing what happened (artifact path, status, classifier).
    """
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    art_path = BASELINES_DIR / f"{task.publisher_id}-batch{batch_id}.json"

    if task.parser_status == "unsupported-no-parser":
        emit(run_id=run_id, action="baseline.skip", agent_name="batch_baseline",
             publisher=task.publisher_id, status="ok",
             notes="unsupported-no-parser")
        return {
            "publisher_id": task.publisher_id,
            "status": "unsupported-no-parser",
            "classifier": "unsupported-no-parser",
            "artifact_path": None,
            "notes": "no dedicated parser; skipped",
        }

    if not task.gold_fixture_path:
        emit(run_id=run_id, action="baseline.gold_needed",
             agent_name="batch_baseline", publisher=task.publisher_id,
             status="blocked", notes="no gold fixture")
        return {
            "publisher_id": task.publisher_id,
            "status": "gold-needed",
            "classifier": "gold-needed",
            "artifact_path": None,
            "notes": "no gold fixture; gold-builder agent should be scheduled",
        }

    if task.parser_status == "generic-only":
        emit(run_id=run_id, action="baseline.generic_only",
             agent_name="batch_baseline", publisher=task.publisher_id,
             status="ok", notes="parser maps to generic")
        return {
            "publisher_id": task.publisher_id,
            "status": "generic-only",
            "classifier": "generic-only",
            "artifact_path": None,
            "notes": "parser_status=generic-only; dedicated parser needed",
        }

    emit(run_id=run_id, action="baseline.start", agent_name="batch_baseline",
         publisher=task.publisher_id, status="started",
         notes=f"gold={Path(task.gold_fixture_path).name}")

    cmd = [
        str(VENV_PYTHON),
        str(DIFF_SCRIPT),
        "--publisher", task.publisher_id,
        "--gold", str(REPO_ROOT / task.gold_fixture_path),
        "--out", str(art_path),
    ]
    env = dict(os.environ)
    env["PARSELAND_EVAL_PATH"] = PARSELAND_EVAL_PATH

    t_start = time.time()
    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=1800
        )
        dur_ms = int((time.time() - t_start) * 1000)
        if proc.returncode != 0:
            emit(run_id=run_id, action="baseline.fail",
                 agent_name="batch_baseline", publisher=task.publisher_id,
                 status="failed", duration_ms=dur_ms,
                 notes=f"rc={proc.returncode} stderr={proc.stderr[:300]}")
            return {
                "publisher_id": task.publisher_id,
                "status": "failed",
                "classifier": "harvest/router-owned",  # most diff failures are R2/Taxicab
                "artifact_path": None,
                "duration_ms": dur_ms,
                "rc": proc.returncode,
                "stderr_head": proc.stderr[:500],
            }
    except subprocess.TimeoutExpired:
        return {
            "publisher_id": task.publisher_id,
            "status": "timeout",
            "classifier": "harvest/router-owned",
            "artifact_path": None,
            "duration_ms": 1800000,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "publisher_id": task.publisher_id,
            "status": "exception",
            "classifier": "harvest/router-owned",
            "artifact_path": None,
            "error": str(exc),
        }

    dur_ms = int((time.time() - t_start) * 1000)
    # Read the artifact, classify
    try:
        art = json.loads(art_path.read_text())
    except Exception:
        return {
            "publisher_id": task.publisher_id,
            "status": "artifact-missing",
            "classifier": "harvest/router-owned",
            "artifact_path": str(art_path),
            "duration_ms": dur_ms,
        }

    classification = classify_artifact(art, task)
    emit(run_id=run_id, action="baseline.complete",
         agent_name="batch_baseline", publisher=task.publisher_id,
         status="ok", duration_ms=dur_ms, artifact_path=str(art_path),
         notes=f"classifier={classification}")
    return {
        "publisher_id": task.publisher_id,
        "status": "ok",
        "classifier": classification,
        "artifact_path": str(art_path),
        "duration_ms": dur_ms,
    }


def classify_artifact(art: dict, task: PublisherTask) -> str:
    """Simple cluster label from a field_inprocess_diff artifact."""
    rows = art.get("rows") or art.get("per_row") or []
    if rows and len(rows) < SMOKE_ONLY_THRESHOLD:
        return "smoke-only"
    summary = art.get("summary") or {}
    # All errored?
    err_rate = summary.get("error_rate")
    if isinstance(err_rate, (int, float)) and err_rate > 0.9:
        return "harvest/router-owned"
    # Low score in at least one field?
    low_fields: list[str] = []
    for field, thresh in LOW_SCORE_THRESHOLDS.items():
        v = summary.get(field)
        if isinstance(v, (int, float)) and v < thresh:
            low_fields.append(field)
    if low_fields:
        # Heuristic: if parser produced any non-null output but scores low,
        # could be scorer/gold issue. Without deeper analysis, default to
        # parser-owned and let Referee re-classify.
        return "parser-owned"
    return "ok"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue", type=Path,
                   default=REPO_ROOT / "mismatches" / "publisher-queue.ndjson")
    p.add_argument("--range", type=str, default="1-100")
    p.add_argument("--batch-id", type=int, default=1)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--dry-run", action="store_true",
                   help="Don't actually run subprocesses; emit ledger only.")
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    if not args.queue.exists():
        print(f"ERROR: queue file not found: {args.queue}", file=sys.stderr)
        return 2

    rows = load_queue(args.queue)
    if not rows:
        print("ERROR: queue is empty", file=sys.stderr)
        return 2

    lo, hi = parse_range(args.range, len(rows))
    selected = rows[lo - 1: hi]
    tasks = [
        PublisherTask(
            rank=lo + i,
            publisher_id=r["publisher_id"],
            row_count=r["row_count"],
            parser_status=r["parser_status"],
            gold_fixture_path=r.get("gold_fixture_path"),
            priority=r["priority"],
            confidence_tier=r["confidence_tier"],
        )
        for i, r in enumerate(selected)
    ]

    run_id = args.run_id or new_run_id()
    emit(run_id=run_id, action="batch.start", agent_name="batch_baseline",
         progress_total=len(tasks),
         notes=f"batch={args.batch_id} range={args.range} dry_run={args.dry_run}")

    results: list[dict] = []
    if args.dry_run:
        for t in tasks:
            emit(run_id=run_id, action="baseline.dry_run",
                 agent_name="batch_baseline", publisher=t.publisher_id,
                 status="ok", notes=f"status={t.parser_status} "
                                    f"gold={'yes' if t.gold_fixture_path else 'no'}")
            results.append({
                "publisher_id": t.publisher_id,
                "status": "dry-run",
                "classifier": (
                    "unsupported-no-parser" if t.parser_status == "unsupported-no-parser"
                    else "generic-only" if t.parser_status == "generic-only"
                    else "gold-needed" if not t.gold_fixture_path
                    else "would-run"
                ),
                "rank": t.rank,
                "row_count": t.row_count,
                "priority": t.priority,
            })
    else:
        # Parallel execution; field_inprocess_diff is I/O-bound (Taxicab+R2).
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futs = {pool.submit(run_field_diff, t, args.batch_id, run_id): t for t in tasks}
            for fut in concurrent.futures.as_completed(futs):
                results.append(fut.result())

    # Write classified-batch<n>.ndjson
    classified_path = REPO_ROOT / "mismatches" / f"classified-batch{args.batch_id}.ndjson"
    classified_path.parent.mkdir(parents=True, exist_ok=True)
    with open(classified_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Summary
    label_counts: dict[str, int] = {}
    for r in results:
        c = r.get("classifier") or r.get("status") or "unknown"
        label_counts[c] = label_counts.get(c, 0) + 1
    summary = {
        "batch_id": args.batch_id,
        "range": args.range,
        "publishers": len(results),
        "label_counts": label_counts,
        "artifact_path": str(classified_path),
        "run_id": run_id,
    }
    emit(run_id=run_id, action="batch.complete", agent_name="batch_baseline",
         progress_current=len(results), progress_total=len(results),
         artifact_path=str(classified_path),
         notes=json.dumps(label_counts))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
