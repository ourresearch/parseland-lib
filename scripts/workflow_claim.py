#!/usr/bin/env python3
"""Workflow task-claim helper.

Atomically claim N tasks from a publisher-field-queue.v2.ndjson (falling back
to publisher-field-queue.ndjson). Writes a row to
task-claims.ndjson with the claiming agent_id and a timestamp, and returns
the claimed tasks as JSON on stdout for an Agent caller to consume.

Used by the parallel fan-out: each Agent invocation calls this script to
claim its task, then runs diagnose/patch/test against the publisher × field
cell, and writes a result to mismatches/workflows/<run_id>/results/<task_id>.json.

Usage:
    python scripts/workflow_claim.py --run-id <id> --agent-id <id> --n 1
    python scripts/workflow_claim.py --run-id <id> --agent-id <id> \\
        --queue-type ready,onboarding --field authors
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIMABLE_STATUSES = {
    None,
    "",
    "queued",
    "needs_agent",
    "onboarding",
    "goldie_backfill_pending",
    "goldie_backfilled_needed",
    "above_98_with_backfill_pending",
    "retrieval_recovered_above_98_with_backfill_pending",
    "retrieval_recovered_needs_agent",
    "retrieval_recovered_near_98_needs_fixture_and_agent",
    "retrieval_recovered_near_98_needs_residual_diagnosis",
    "retrieval_recovered_goldie_backfill_heavy_needs_referee",
}

BACKFILL_REOPEN_STATUSES = {
    "shipped_full10k_measured",
    "shipped_full10k_measured_above_98",
    "shipped_full10k_measured_below_98_with_explainable_residual",
    "shipped_full10k_measured_with_backfill_pending",
    "shipped_parser_fix_above_98_with_backfill_pending",
    "shipped_parser_fix_above_98_with_residual_explained",
    "shipped_scorer_fix_above_98_with_backfill_pending",
}

ACTIVE_CLAIM_STATUSES = {"in_progress", "started", "claimed"}


def is_claimable_task(task: dict) -> bool:
    status = task.get("status")
    if status in CLAIMABLE_STATUSES:
        return True
    if task.get("queue_type") != "goldie-backfilled":
        return False
    try:
        backfill_count = int(task.get("gold_empty_parser_present") or 0)
    except (TypeError, ValueError):
        backfill_count = 0
    if (
        backfill_count > 0
        and isinstance(status, str)
        and status.startswith("goldie_backfill_")
        and (
            status.endswith("_scale_ready")
            or status.endswith("_scale_continue")
            or status.endswith("_pending_browserbase_exhausted")
        )
    ):
        return True
    return backfill_count > 0 and status in BACKFILL_REOPEN_STATUSES


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    p.add_argument("--agent-id", default=None)
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--queue-type", default=None,
                   help="Comma-separated filter")
    p.add_argument("--field", default=None,
                   help="Comma-separated filter")
    p.add_argument("--publisher", default=None)
    p.add_argument("--workflow-dir", type=Path, default=None)
    args = p.parse_args()

    wd = args.workflow_dir or REPO_ROOT / "mismatches" / "workflows" / args.run_id
    if not wd.exists():
        print(json.dumps({"error": f"workflow dir not found: {wd}"}))
        return 2
    queue_path = wd / "publisher-field-queue.v2.ndjson"
    if not queue_path.exists():
        queue_path = wd / "publisher-field-queue.ndjson"
    claims_path = wd / "task-claims.ndjson"
    lock_path = wd / ".claim.lock"

    queue_types = set(args.queue_type.split(",")) if args.queue_type else None
    fields = set(args.field.split(",")) if args.field else None
    agent_id = args.agent_id or f"agent-{uuid.uuid4().hex[:8]}"

    with open(lock_path, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        # Read current queue + claims
        tasks = [json.loads(l) for l in queue_path.read_text().split("\n") if l.strip()]
        latest_claim_status: dict[str, str | None] = {}
        if claims_path.exists():
            for ln in claims_path.read_text().split("\n"):
                if not ln.strip(): continue
                try:
                    c = json.loads(ln)
                    latest_claim_status[c["task_id"]] = c.get("status")
                except Exception: pass
        claimed_ids = {
            task_id
            for task_id, status in latest_claim_status.items()
            if status in ACTIVE_CLAIM_STATUSES
        }

        # Find next N matching unclaimed tasks
        selected = []
        for t in tasks:
            if t["task_id"] in claimed_ids: continue
            if queue_types and t["queue_type"] not in queue_types: continue
            if fields and t["field"] not in fields: continue
            if args.publisher and t["publisher_id"] != args.publisher: continue
            if not is_claimable_task(t): continue
            selected.append(t)
            if len(selected) >= args.n: break

        # Write claims
        now = datetime.now(timezone.utc).isoformat()
        with open(claims_path, "a") as f:
            for t in selected:
                t["assigned_agent"] = agent_id
                t["claimed_at"] = now
                t["status"] = "in_progress"
                t.pop("completed_at", None)
                f.write(json.dumps({
                    "run_id": args.run_id,
                    "task_id": t["task_id"],
                    "publisher_id": t["publisher_id"],
                    "field": t["field"],
                    "queue_type": t["queue_type"],
                    "agent_id": agent_id,
                    "claimed_at": now,
                    "status": "in_progress",
                }) + "\n")
        if selected:
            queue_path.write_text(
                "\n".join(
                    json.dumps(t, ensure_ascii=False, separators=(",", ":"))
                    for t in tasks
                ) + "\n"
            )
        fcntl.flock(lk, fcntl.LOCK_UN)

    print(json.dumps({
        "agent_id": agent_id,
        "claimed_count": len(selected),
        "queue_path": str(queue_path),
        "tasks": selected,
        "workflow_dir": str(wd),
        "results_dir": str(wd / "results"),
    }, indent=2))
    (wd / "results").mkdir(parents=True, exist_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
