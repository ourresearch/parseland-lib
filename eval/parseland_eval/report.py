"""Serialize scorecard to a run JSON file consumable by the dashboard."""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parseland_eval import __version__
from parseland_eval.gold import GoldRow
from parseland_eval.paths import RUNS_DIR
from parseland_eval.runner import ParserRun
from parseland_eval.score.aggregate import RowScore


def _asdict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: _asdict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_asdict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _asdict(v) for k, v in obj.items()}
    return obj


def row_payload(gold: GoldRow, run: ParserRun, score: RowScore) -> dict[str, Any]:
    parsed = run.parsed or {}
    return {
        "no": gold.no,
        "doi": gold.doi,
        "link": gold.link,
        "publisher_domain": run.publisher_domain,
        "gold": {
            "authors": [
                {"name": a.name, "affiliations": list(a.affiliations), "is_corresponding": a.is_corresponding}
                for a in gold.authors
            ],
            "abstract": gold.abstract,
            "pdf_url": gold.pdf_url,
            "gold_quality": gold.gold_quality,
            "failure_modes": list(gold.failure_modes),
            "notes": gold.notes,
            "has_bot_check": gold.has_bot_check,
            "status": gold.status,
        },
        "parsed": {
            "authors": parsed.get("authors", []),
            "abstract": parsed.get("abstract"),
            "urls": parsed.get("urls", []),
            "license": parsed.get("license"),
            "version": parsed.get("version"),
        },
        "score": _asdict(score),
        "error": run.error,
        "duration_ms": run.duration_ms,
    }


def write_run(
    rows: list[GoldRow],
    runs: list[ParserRun],
    scores: list[RowScore],
    summary: dict[str, Any],
    *,
    label: str | None = None,
) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = f"{label}-{ts}.json" if label else f"run-{ts}.json"
    out = RUNS_DIR / fname

    payload: dict[str, Any] = {
        "run_id": ts,
        "label": label,
        "eval_version": __version__,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "rows": [row_payload(g, r, s) for g, r, s in zip(rows, runs, scores)],
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_index()
    return out


def _update_index() -> None:
    """Produce runs/index.json listing available runs newest-first."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for f in sorted(RUNS_DIR.glob("*.json")):
        if f.name == "index.json":
            continue
        try:
            head = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        entries.append(
            {
                "file": f.name,
                "run_id": head.get("run_id"),
                "label": head.get("label"),
                "timestamp_utc": head.get("timestamp_utc"),
                "summary": head.get("summary", {}).get("overall", {}),
            }
        )
    entries.sort(key=lambda e: e.get("timestamp_utc") or "", reverse=True)
    (RUNS_DIR / "index.json").write_text(
        json.dumps({"runs": entries}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
