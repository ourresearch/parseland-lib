#!/usr/bin/env python3
"""Scribe — post a batch milestone to #parseland-multiagent.

Reads the latest row of evidence/kpi-by-publisher-count.csv plus the most
recent classified-batch<n>.ndjson and posts a formatted milestone. Queues if
Slack credentials are missing — never blocks the sprint.

Slack credentials are read from env:
    SLACK_BOT_TOKEN   (xoxb-...)
    SLACK_CHANNEL_ID  (default: configured channel for #parseland-multiagent)

Usage:
    python scripts/post_slack_milestone.py --dry-run
    python scripts/post_slack_milestone.py --batch-id 1
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.event_ledger import emit, new_run_id  # noqa: E402

EVIDENCE_DIR = Path(
    "/Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence"
)
QUEUE_PATH = REPO_ROOT / "mismatches" / "publisher-queue.ndjson.summary.json"

REPORT_URL = "https://oxjobs.org/reports/336"
SLACK_QUEUE_PATH = REPO_ROOT / "mismatches" / "slack-queue.ndjson"


def load_kpi(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_classified(batch_id: int) -> list[dict]:
    p = REPO_ROOT / "mismatches" / f"classified-batch{batch_id}.ndjson"
    if not p.exists():
        return []
    rows: list[dict] = []
    with open(p, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return rows


def format_milestone(batch_id: int, kpi_rows: list[dict], classified: list[dict]) -> str:
    if not kpi_rows:
        return f"_Batch {batch_id} milestone: KPI CSV not yet populated._"
    latest = kpi_rows[-1]
    prev = kpi_rows[-2] if len(kpi_rows) > 1 else None

    def fmt_delta(curr_k: str) -> str:
        try:
            curr = float(latest.get(curr_k, 0.0))
            if prev is None:
                return f"{curr:.3f}"
            prv = float(prev.get(curr_k, 0.0))
            return f"{curr:.3f} ({curr - prv:+.3f})"
        except (TypeError, ValueError):
            return latest.get(curr_k, "—")

    label_counts: dict[str, int] = {}
    for r in classified:
        c = r.get("classifier") or r.get("status") or "unknown"
        label_counts[c] = label_counts.get(c, 0) + 1

    parts = [
        f"*Parseland Improver — Batch {batch_id} milestone*",
        f"• Publishers processed: *{latest.get('publishers_processed', '?')}*  rows covered: *{latest.get('cumulative_rows', '?')}*",
        f"• Whole-Goldie KPIs (Δ vs prev batch):",
        f"   – Authors F1 (soft): {fmt_delta('overall_authors_f1_soft')}",
        f"   – Affs F1 (fuzzy): {fmt_delta('overall_affiliations_f1_fuzzy')}",
        f"   – Abstract ratio: {fmt_delta('overall_abstract_ratio_fuzzy')}",
        f"   – PDF URL accuracy: {fmt_delta('overall_pdf_url_accuracy')}",
        f"   – Corresponding accuracy: {fmt_delta('overall_corresponding_accuracy')}",
        f"• Marginal lift / 100 publishers: *{latest.get('marginal_lift_per_100', '—')}*",
        f"• Shipped commits: *{latest.get('shipped_count', 0)}*   Blocked: *{latest.get('blocked_count', 0)}*",
    ]
    if label_counts:
        parts.append("• Cluster labels: " + ", ".join(
            f"{k}={v}" for k, v in sorted(label_counts.items(), key=lambda kv: -kv[1])
        ))
    parts.append(f"• Live report: {REPORT_URL}")
    return "\n".join(parts)


def post_to_slack(text: str, token: str, channel: str) -> dict:
    data = urllib.parse.urlencode({
        "channel": channel,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def queue_milestone(text: str, batch_id: int) -> None:
    SLACK_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_id": batch_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
    }
    with open(SLACK_QUEUE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-id", type=int, default=1)
    p.add_argument("--dry-run", action="store_true",
                   help="Print the formatted message instead of posting.")
    p.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR)
    p.add_argument("--run-id", type=str)
    args = p.parse_args()

    run_id = args.run_id or new_run_id()
    kpi_rows = load_kpi(args.evidence_dir / "kpi-by-publisher-count.csv")
    classified = load_classified(args.batch_id)
    text = format_milestone(args.batch_id, kpi_rows, classified)

    if args.dry_run:
        emit(run_id=run_id, action="slack.dry_run",
             agent_name="post_slack_milestone",
             notes=f"batch={args.batch_id}")
        print(text)
        return 0

    token = os.environ.get("SLACK_BOT_TOKEN") or ""
    channel = os.environ.get("SLACK_CHANNEL_ID") or "#parseland-multiagent"
    if not token:
        queue_milestone(text, args.batch_id)
        emit(run_id=run_id, action="slack.queued",
             agent_name="post_slack_milestone", status="blocked",
             notes="SLACK_BOT_TOKEN missing; milestone queued")
        print(f"queued to {SLACK_QUEUE_PATH}")
        return 0

    res = post_to_slack(text, token, channel)
    ok = bool(res.get("ok"))
    emit(run_id=run_id, action="slack.post",
         agent_name="post_slack_milestone",
         status="ok" if ok else "blocked",
         notes=str(res.get("error") or res.get("ts") or ""))
    if not ok:
        queue_milestone(text, args.batch_id)
        print(json.dumps({"posted": False, "queued": True, "slack_error": res.get("error")}, indent=2))
        return 0
    print(json.dumps({"posted": True, "ts": res.get("ts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
