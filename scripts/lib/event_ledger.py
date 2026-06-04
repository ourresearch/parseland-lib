"""Append-only NDJSON event ledger for the autonomous Parseland improver.

Writes events to:
    /Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence/live-agent-events.ndjson

The path is also the asset listed in report 336's report.yaml allowlist so the
ledger is served live at https://oxjobs.org/reports/336.

Every wrapper agent (Pathfinder, Craftsman, Referee, Shield, Scribe, Courier)
calls `emit(...)`. The helper normalizes underlying agent names (e.g.
"sprint-coordinator") to the public 6-role taxonomy.

Schema (all keys optional except run_id, timestamp, agent_role, action, status):

    {"run_id": str, "report_id": 336, "timestamp": ISO8601 str,
     "agent_name": str, "agent_role": str (one of the 6 public roles),
     "publisher": str | null, "field": str | null,
     "stage": str | null, "action": str, "status": str,
     "progress_current": int, "progress_total": int,
     "duration_ms": int, "artifact_path": str | null,
     "commit_sha": str | null,
     "kpi_before": float | null, "kpi_after": float | null,
     "notes": str | null}
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPORT_ID = 336

LEDGER_PATH = Path(
    os.environ.get(
        "PARSELAND_EVENT_LEDGER",
        "/Users/shubh-trips/Documents/OpenAlex/oxjobs/working/parseland-work-reporting/evidence/live-agent-events.ndjson",
    )
)

# Mapping from underlying-agent-name → public role.
# Add to this whenever an existing agent is wrapped under a new role.
AGENT_NAME_TO_ROLE: dict[str, str] = {
    # Pathfinder family
    "sprint-coordinator": "Pathfinder",
    "field-orchestrator": "Pathfinder",
    "rank_publishers": "Pathfinder",
    "batch_baseline": "Pathfinder",
    # Craftsman family
    "publisher-field-worker": "Craftsman",
    "field-distiller": "Craftsman",
    "cross-field-distiller": "Craftsman",
    # Referee family
    "opus-judge": "Referee",
    "gold-auditor": "Referee",
    "markup-variant-discoverer": "Referee",
    # Shield family
    "regression-sentinel": "Shield",
    "auto_push_gate": "Shield",
    # Scribe family
    "pattern-archivist": "Scribe",
    "build_curve": "Scribe",
    "build_console_html": "Scribe",
    "build_report336": "Scribe",
    "post_slack_milestone": "Scribe",
    "agent_console": "Scribe",
    # Courier family (net-new)
    "courier": "Courier",
    "gold-builder": "Pathfinder",
}

VALID_ROLES = {"Pathfinder", "Craftsman", "Referee", "Shield", "Scribe", "Courier"}
VALID_STATUSES = {"started", "ok", "blocked", "failed"}

# Thread-safe append lock so concurrent agents don't interleave bytes.
_LEDGER_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_run_id() -> str:
    """Generate a fresh sprint run id (UTC timestamp + short suffix)."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:6]


def normalize_role(agent_name: str | None, agent_role: str | None) -> str:
    """Return a valid public role string.

    If agent_role is one of the 6 valid roles, use it.
    Otherwise look up the agent_name in AGENT_NAME_TO_ROLE.
    Fall back to Scribe (the catch-all reporter role) so the ledger never
    drops an event.
    """
    if agent_role and agent_role in VALID_ROLES:
        return agent_role
    if agent_name and agent_name in AGENT_NAME_TO_ROLE:
        return AGENT_NAME_TO_ROLE[agent_name]
    return "Scribe"


def emit(
    *,
    run_id: str,
    action: str,
    status: str = "ok",
    agent_role: str | None = None,
    agent_name: str | None = None,
    publisher: str | None = None,
    field: str | None = None,
    stage: str | None = None,
    progress_current: int = 0,
    progress_total: int = 0,
    duration_ms: int = 0,
    artifact_path: str | None = None,
    commit_sha: str | None = None,
    kpi_before: float | None = None,
    kpi_after: float | None = None,
    notes: str | None = None,
    timestamp: str | None = None,
    ledger_path: Path | None = None,
) -> dict:
    """Append one event to the ledger and return the event dict.

    Status defaults to 'ok' so simple action logs need only run_id + action.
    Unknown statuses are coerced to 'ok' to keep schema strict but never raise.
    Unknown roles fall back via normalize_role() to 'Scribe'.
    """
    role = normalize_role(agent_name, agent_role)
    if status not in VALID_STATUSES:
        status = "ok"
    event = {
        "run_id": run_id,
        "report_id": REPORT_ID,
        "timestamp": timestamp or _now_iso(),
        "agent_name": agent_name,
        "agent_role": role,
        "publisher": publisher,
        "field": field,
        "stage": stage,
        "action": action,
        "status": status,
        "progress_current": progress_current,
        "progress_total": progress_total,
        "duration_ms": duration_ms,
        "artifact_path": artifact_path,
        "commit_sha": commit_sha,
        "kpi_before": kpi_before,
        "kpi_after": kpi_after,
        "notes": notes,
    }
    path = ledger_path or LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    with _LEDGER_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    return event


def tail_events(
    *,
    ledger_path: Path | None = None,
    since_run_id: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Read recent events from the ledger. Used by the TUI."""
    path = ledger_path or LEDGER_PATH
    if not path.exists():
        return []
    events: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since_run_id and ev.get("run_id") != since_run_id:
                continue
            events.append(ev)
    if limit and limit > 0:
        events = events[-limit:]
    return events


__all__ = [
    "REPORT_ID",
    "LEDGER_PATH",
    "AGENT_NAME_TO_ROLE",
    "VALID_ROLES",
    "VALID_STATUSES",
    "new_run_id",
    "normalize_role",
    "emit",
    "tail_events",
]
