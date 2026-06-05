#!/usr/bin/env python3
"""Build the full publisher x field workflow queue from a whole-Goldie run.

The earlier workflow queue was seeded from a narrow ready-publisher list. This
builder uses the run's full coverage/per-publisher-field accounting, so ready,
generic-only, unsupported, unknown, retrieval-blocked, and Goldie-backfilled
cells all remain visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402
from scripts.rank_publishers import (  # noqa: E402
    discover_gold_fixture,
    discover_supported_publishers,
    parser_status,
)

FIELDS = ("authors", "affiliations", "abstract", "pdf_url", "corresponding")
FIELD_METRICS = {
    "authors": "authors_f1_soft",
    "affiliations": "affiliations_f1_fuzzy",
    "abstract": "abstract_ratio_fuzzy",
    "pdf_url": "pdf_url_accuracy",
    "corresponding": "corresponding_accuracy",
}


def latest_whole_goldie_run() -> Path | None:
    candidates = list((REPO_ROOT / "eval" / "runs").glob("whole-goldie*.json"))
    candidates += list((REPO_ROOT / "mismatches").glob("whole-goldie*.json"))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_claims(workflow_dir: Path) -> dict[str, dict]:
    claims: dict[str, dict] = {}
    path = workflow_dir / "task-claims.ndjson"
    if not path.exists():
        return claims
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            claims[row.get("task_id", "")] = row
    return claims


def classify_publisher(pub: str, *, parser_status_value: str, gold_fixture: str | None) -> str:
    if pub == "unknown":
        return "unknown"
    if parser_status_value == "supported" and gold_fixture:
        return "ready"
    if parser_status_value == "supported":
        return "onboarding"
    if parser_status_value == "generic-only":
        return "generic_only"
    return "unsupported"


def queue_type_for(
    publisher_class: str,
    counts: dict,
    *,
    current_kpi: float,
    distance_to_98: float,
) -> tuple[str, str, str]:
    backfill = int(counts.get("gold_empty_parser_present") or 0)
    html_available = int(counts.get("html_available") or 0)
    retrieval_blocked = int(counts.get("retrieval_blocked") or 0)
    scored = int(counts.get("scored_rows") or 0)

    if backfill > 0 and (current_kpi >= 0.98 or backfill >= max(2, scored // 3)):
        return ("goldie-backfilled", "goldie_backfill_pending", "browserbase-ground")
    if publisher_class == "unknown":
        return ("unknown", "publisher_unknown", "classify-publisher")
    if html_available == 0 and retrieval_blocked > 0:
        return ("harvest-blocked", "retrieval_blocked", "retrieve-html")
    if publisher_class == "unsupported":
        return ("unsupported", "unsupported", "add-parser-or-block")
    if publisher_class in {"generic_only", "onboarding"}:
        return ("onboarding", publisher_class, "onboard-or-baseline")
    if distance_to_98 <= 0:
        return ("ready", "above_98", "monitor")
    return ("ready", "needs_agent", "diagnose")


def build_queue(run_path: Path, workflow_dir: Path, *, run_id: str | None = None) -> dict:
    run_id = run_id or new_run_id()
    created_at = datetime.now(timezone.utc).isoformat()
    run = json.loads(run_path.read_text())
    summary = run.get("summary") or {}
    per_pub = summary.get("per_publisher") or {}
    per_pub_field = summary.get("per_publisher_field") or {}
    coverage = run.get("coverage") or summary.get("coverage") or {}
    supported = discover_supported_publishers()
    claims = load_claims(workflow_dir)

    workflow_dir.mkdir(parents=True, exist_ok=True)
    queue_path = workflow_dir / "publisher-field-queue.v2.ndjson"
    classification_path = workflow_dir / "publisher-classification.ndjson"
    summary_path = workflow_dir / "summary.json"

    classifications: list[dict] = []
    tasks: list[dict] = []
    by_queue_type: dict[str, int] = {}
    by_field: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for pub, field_counts in sorted(per_pub_field.items()):
        pub_stats = per_pub.get(pub) or {}
        pub_cov = (coverage.get("per_publisher") or {}).get(pub) or {}
        p_status, tractability = parser_status(pub, supported)
        fixture = discover_gold_fixture(pub)
        p_class = classify_publisher(pub, parser_status_value=p_status, gold_fixture=fixture)
        classifications.append({
            "publisher_id": pub,
            "publisher_class": p_class,
            "parser_status": p_status,
            "tractability": tractability,
            "gold_fixture_path": fixture,
            "total_rows": int(pub_cov.get("total_rows") or pub_stats.get("rows") or 0),
            "html_available": int(pub_cov.get("html_available") or 0),
            "retrieval_blocked": int(pub_cov.get("retrieval_blocked") or 0),
            "scored_rows": int(pub_cov.get("scored_rows") or pub_stats.get("scored") or 0),
        })

        for field in FIELDS:
            counts = field_counts.get(field) or {}
            total_rows = int(counts.get("total_rows") or 0)
            if total_rows <= 0:
                continue
            html_available = int(counts.get("html_available") or 0)
            retrieval_blocked = int(counts.get("retrieval_blocked") or 0)
            scored_rows = int(counts.get("scored_rows") or 0)
            metric = FIELD_METRICS[field]
            current_kpi = float(pub_stats.get(metric) or 0.0)
            if scored_rows == 0:
                current_kpi = 0.0
            distance_to_98 = max(0.0, 0.98 - current_kpi)
            html_coverage = html_available / max(total_rows, 1)
            effective_tractability = max(tractability, 0.05)
            priority = distance_to_98 * total_rows * effective_tractability * max(html_coverage, 0.05)
            backfill_count = int(counts.get("gold_empty_parser_present") or 0)
            if backfill_count:
                priority += backfill_count * 0.75
            queue_type, status, next_action = queue_type_for(
                p_class, counts, current_kpi=current_kpi, distance_to_98=distance_to_98
            )
            task_suffix = hashlib.sha1(f"{pub}|{field}|{total_rows}".encode()).hexdigest()[:8]
            task_id = f"v2_{pub}_{field}_{task_suffix}"
            claim = claims.get(task_id)
            task = {
                "task_id": task_id,
                "publisher_id": pub,
                "field": field,
                "queue_type": queue_type,
                "row_count": total_rows,
                "html_available": html_available,
                "retrieval_blocked": retrieval_blocked,
                "scored_rows_for_field": scored_rows,
                "current_kpi": round(current_kpi, 4),
                "target_kpi": 0.98,
                "distance_to_98": round(distance_to_98, 4),
                "headroom": round(max(0.0, 1.0 - current_kpi), 4),
                "empty_empty_passes": int(counts.get("empty_empty_pass") or 0),
                "misses": int(counts.get("gold_present_parser_empty") or 0),
                "gold_empty_parser_present": backfill_count,
                "tractability": tractability,
                "html_coverage": round(html_coverage, 4),
                "priority": round(priority, 4),
                "parser_status": p_status,
                "publisher_class": p_class,
                "gold_status": (
                    "fixture-present" if fixture else
                    "goldie-backfill-needed" if backfill_count else
                    "fixture-missing"
                ),
                "gold_fixture_path": fixture,
                "assigned_agent": claim.get("agent_id") if claim else None,
                "worktree_path": claim.get("worktree_path") if claim else None,
                "status": claim.get("status") if claim else status,
                "artifact_path": claim.get("artifact_path") if claim else None,
                "next_action": next_action,
                "latest_run": str(run_path),
                "created_at": created_at,
            }
            tasks.append(task)
            by_queue_type[queue_type] = by_queue_type.get(queue_type, 0) + 1
            by_field[field] = by_field.get(field, 0) + 1
            by_status[task["status"]] = by_status.get(task["status"], 0) + 1

    tasks.sort(key=lambda r: (-float(r["priority"]), r["publisher_id"], r["field"]))
    classifications.sort(key=lambda r: (-int(r["total_rows"]), r["publisher_id"]))

    with open(queue_path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task, ensure_ascii=False, separators=(",", ":")) + "\n")
    with open(classification_path, "w", encoding="utf-8") as f:
        for row in classifications:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    payload = {
        "run_id": run_id,
        "created_at": created_at,
        "source_whole_goldie": str(run_path),
        "total_tasks": len(tasks),
        "total_publishers": len(classifications),
        "coverage_total_rows": coverage.get("total_rows"),
        "coverage_html_available": coverage.get("html_available"),
        "coverage_retrieval_blocked_rows": coverage.get("retrieval_blocked_rows"),
        "coverage_gold_empty_parser_present_count": coverage.get("gold_empty_parser_present_count"),
        "by_queue_type": dict(sorted(by_queue_type.items())),
        "by_field": dict(sorted(by_field.items())),
        "by_status": dict(sorted(by_status.items())),
        "top_15_priority": tasks[:15],
        "classification_counts": {
            cls: sum(1 for row in classifications if row["publisher_class"] == cls)
            for cls in sorted({row["publisher_class"] for row in classifications})
        },
        "outputs": {
            "publisher_field_queue_v2": str(queue_path),
            "publisher_classification": str(classification_path),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(payload, indent=2))

    emit(
        run_id=run_id,
        action="publisher_field_queue_v2.complete",
        agent_name="rank_field_opportunity",
        progress_current=len(tasks),
        progress_total=len(tasks),
        artifact_path=str(queue_path),
        notes=(
            f"{len(tasks)} tasks, {len(classifications)} publishers, "
            f"source_rows={coverage.get('total_rows')}"
        ),
    )
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=None)
    p.add_argument(
        "--workflow-dir",
        type=Path,
        default=REPO_ROOT / "mismatches" / "workflows" / "20260604T163736Z-77fe45",
    )
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    run_path = args.run or latest_whole_goldie_run()
    if not run_path or not run_path.exists():
        print("ERROR: no whole-Goldie run found", file=sys.stderr)
        return 2
    payload = build_queue(run_path, args.workflow_dir, run_id=args.run_id)
    print(json.dumps({
        "source_whole_goldie": payload["source_whole_goldie"],
        "total_tasks": payload["total_tasks"],
        "total_publishers": payload["total_publishers"],
        "by_queue_type": payload["by_queue_type"],
        "by_field": payload["by_field"],
        "top_5": payload["top_15_priority"][:5],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
