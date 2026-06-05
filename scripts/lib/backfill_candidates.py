"""Goldie-backfilled candidate ledger helpers."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO_ROOT / "mismatches" / "goldie-backfilled-candidates.ndjson"


def append_candidate(
    *,
    doi: str,
    publisher: str,
    field: str,
    gold_value: Any,
    parseland_candidate: Any,
    source_run: str,
    ledger_path: Path = DEFAULT_LEDGER,
) -> bool:
    """Append a DOI+field-deduped Browserbase-grounding candidate."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    with open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        seen: set[tuple[str, str]] = set()
        rows: list[dict[str, Any]] = []
        if ledger_path.exists():
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rows.append(row)
                    seen.add((str(row.get("doi", "")).lower(), str(row.get("field", ""))))
        key = (doi.lower(), field)
        if key in seen:
            return False
        rows.append({
            "doi": doi,
            "publisher": publisher,
            "field": field,
            "gold_value": gold_value,
            "parseland_candidate": parseland_candidate,
            "confidence": "candidate",
            "evidence_excerpt": None,
            "browserbase_url": None,
            "browserbase_session": None,
            "approving_agent": None,
            "status": "pending_browserbase",
            "rejection_reason": None,
            "proposed_at": datetime.now(timezone.utc).isoformat(),
            "source_run": source_run,
        })
        tmp_path = ledger_path.with_suffix(ledger_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp_path, ledger_path)
        return True
