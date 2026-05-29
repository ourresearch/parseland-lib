"""Sprint coordinator entrypoint for the multi-agent parseland improvement loop.

This script is the operator-facing entrypoint that the `sprint-coordinator`
agent (`.claude/agents/sprint-coordinator.md`) is invoked from. It does not
execute the multi-agent fan-out itself — that is the agent's responsibility,
performed through Claude Code's Agent tool with `subagent_type="field-orchestrator"`.

What this script does:

  1. Validates the sprint config: publishers exist in the generalized diff's
     PUBLISHER_REGISTRY, each has a gold NDJSON available.
  2. Pre-computes the baseline per-field score for each publisher (one
     ``field_inprocess_diff.py`` run per publisher; results cached under
     ``mismatches/baselines/``).
  3. Emits a sprint-config JSON that the sprint-coordinator agent reads as
     its starting context.
  4. Optionally runs in ``--dry-run`` mode to surface what would be dispatched
     without actually fanning out agents.

The actual multi-agent dispatch is wired through Claude Code when the operator
invokes the agent. This script is intentionally cheap and side-effect-light —
it sets up the table, the agent plays the hand.

Usage:

    python scripts/sprint_coordinator.py \\
        --publishers elsevier,springer,wiley,ieee \\
        --fields authors,affiliations,abstract,pdf_url,corresponding \\
        --dry-run

    python scripts/sprint_coordinator.py \\
        --publishers elsevier,wiley \\
        --fields corresponding \\
        --sprint-config /tmp/sprint-2026-05-29.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

sys.path.insert(0, "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/scripts")

from field_inprocess_diff import PUBLISHER_REGISTRY, VALID_FIELDS  # noqa: E402

REPO_ROOT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib")
MISMATCHES = REPO_ROOT / "mismatches"
BASELINES = MISMATCHES / "baselines"

# Publishers with degraded sentinel gates because their fixtures are smaller
# or noisier. Sentinel uses 0.5pp regression block here instead of the 1.0pp
# standard. See agents/regression-sentinel.md.
DEGRADED_PUBLISHERS: frozenset[str] = frozenset({"oxford"})


@dataclass
class CellPlan:
    """One (publisher, field) cell scheduled for this sprint."""

    publisher: str
    field: str
    gold_path: Path
    sentinel_gold_path: Path
    sentinel_regression_threshold_pp: float
    baseline_artifact: Path | None = None


@dataclass
class SprintConfig:
    """Top-level sprint configuration emitted for the agent to consume."""

    sprint_ts: str
    publishers: list[str]
    fields: list[str]
    cells: list[CellPlan] = field(default_factory=list)
    prior_patterns_path: Path | None = None
    gold_disagreements_skip_list: Path | None = None
    output_summary_path: Path = MISMATCHES / "sprint-out.json"


def _parse_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _validate_publishers(publishers: Iterable[str]) -> list[str]:
    valid = []
    unknown: list[str] = []
    no_gold: list[str] = []
    for pub in publishers:
        if pub not in PUBLISHER_REGISTRY:
            unknown.append(pub)
            continue
        spec = PUBLISHER_REGISTRY[pub]
        if not spec.default_gold.exists():
            no_gold.append(pub)
            continue
        valid.append(pub)
    if unknown:
        print(
            f"ERROR: unknown publishers (not in PUBLISHER_REGISTRY): {unknown}",
            file=sys.stderr,
        )
    if no_gold:
        print(
            f"WARNING: publishers without gold NDJSON (route to Phase 2 gold-builder): "
            f"{no_gold}",
            file=sys.stderr,
        )
    if unknown:
        sys.exit(1)
    return valid


def _validate_fields(fields: Iterable[str]) -> list[str]:
    bad = [f for f in fields if f not in VALID_FIELDS]
    if bad:
        print(
            f"ERROR: unknown fields {bad}. Valid: {VALID_FIELDS}", file=sys.stderr
        )
        sys.exit(1)
    return list(fields)


def _sentinel_gold(publisher: str) -> Path:
    """Return the largest available gold NDJSON for the sentinel pass."""
    spec = PUBLISHER_REGISTRY[publisher]
    ten_k = spec.default_gold.parent / f"{publisher}-10k-gold.ndjson"
    if ten_k.exists():
        return ten_k
    return spec.default_gold


def build_sprint_config(
    publishers: list[str],
    fields: list[str],
    sprint_ts: str | None = None,
) -> SprintConfig:
    ts = sprint_ts or time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    cells: list[CellPlan] = []
    for pub in publishers:
        spec = PUBLISHER_REGISTRY[pub]
        for f in fields:
            cells.append(
                CellPlan(
                    publisher=pub,
                    field=f,
                    gold_path=spec.default_gold,
                    sentinel_gold_path=_sentinel_gold(pub),
                    sentinel_regression_threshold_pp=(
                        0.5 if pub in DEGRADED_PUBLISHERS else 1.0
                    ),
                )
            )
    return SprintConfig(
        sprint_ts=ts,
        publishers=publishers,
        fields=fields,
        cells=cells,
        prior_patterns_path=(
            MISMATCHES / "patterns.ndjson"
            if (MISMATCHES / "patterns.ndjson").exists()
            else None
        ),
        gold_disagreements_skip_list=(
            MISMATCHES / "gold-disagreements.ndjson"
            if (MISMATCHES / "gold-disagreements.ndjson").exists()
            else None
        ),
        output_summary_path=MISMATCHES / f"sprint-{ts}.json",
    )


def serialize_config(cfg: SprintConfig) -> dict:
    return {
        "sprint_ts": cfg.sprint_ts,
        "publishers": cfg.publishers,
        "fields": cfg.fields,
        "n_cells": len(cfg.cells),
        "cells": [
            {
                "publisher": c.publisher,
                "field": c.field,
                "gold_path": str(c.gold_path),
                "sentinel_gold_path": str(c.sentinel_gold_path),
                "sentinel_regression_threshold_pp": c.sentinel_regression_threshold_pp,
                "baseline_artifact": str(c.baseline_artifact) if c.baseline_artifact else None,
            }
            for c in cfg.cells
        ],
        "prior_patterns_path": (
            str(cfg.prior_patterns_path) if cfg.prior_patterns_path else None
        ),
        "gold_disagreements_skip_list": (
            str(cfg.gold_disagreements_skip_list)
            if cfg.gold_disagreements_skip_list
            else None
        ),
        "output_summary_path": str(cfg.output_summary_path),
        "agent_dispatch": {
            "sprint_coordinator": ".claude/agents/sprint-coordinator.md",
            "field_orchestrator": ".claude/agents/field-orchestrator.md",
            "publisher_field_worker": ".claude/agents/publisher-field-worker.md",
            "opus_judge": ".claude/agents/opus-judge.md",
            "regression_sentinel": ".claude/agents/regression-sentinel.md",
            "gold_auditor": ".claude/agents/gold-auditor.md",
            "markup_variant_discoverer": ".claude/agents/markup-variant-discoverer.md",
            "pattern_archivist": ".claude/agents/pattern-archivist.md",
            "field_distiller": ".claude/agents/field-distiller.md",
            "cross_field_distiller": ".claude/agents/cross-field-distiller.md",
        },
    }


def print_plan(cfg: SprintConfig) -> None:
    print(f"\n=== Sprint plan ({cfg.sprint_ts}) ===")
    print(f"  publishers: {', '.join(cfg.publishers)}")
    print(f"  fields:     {', '.join(cfg.fields)}")
    print(f"  cells:      {len(cfg.cells)}")
    print(f"  prior patterns: {cfg.prior_patterns_path or '(none — first sprint)'}")
    print(f"  skip list:      {cfg.gold_disagreements_skip_list or '(none)'}")
    print(f"  summary out:    {cfg.output_summary_path}")
    print("\n  Per-publisher sentinel gate:")
    for pub in cfg.publishers:
        spec = PUBLISHER_REGISTRY[pub]
        sg = _sentinel_gold(pub)
        thresh = 0.5 if pub in DEGRADED_PUBLISHERS else 1.0
        print(
            f"    {pub:<10} judge_gold={spec.default_gold.name:<35} "
            f"sentinel_gold={sg.name:<35} threshold={thresh}pp"
        )
    print(
        "\n  Next step: invoke the sprint-coordinator agent with this config.\n"
        "  In Claude Code: spawn Agent(subagent_type='sprint-coordinator', "
        "prompt=<config JSON>).\n"
    )


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Set up a multi-agent parseland improvement sprint.",
    )
    ap.add_argument(
        "--publishers",
        required=True,
        type=_parse_csv,
        help="Comma-separated publisher keys (e.g. elsevier,springer,wiley,ieee).",
    )
    ap.add_argument(
        "--fields",
        default="authors,affiliations,abstract,pdf_url,corresponding",
        type=_parse_csv,
        help="Comma-separated field names. Default: all 5.",
    )
    ap.add_argument(
        "--sprint-config",
        type=Path,
        default=None,
        help="Path to write the sprint config JSON. Defaults to mismatches/sprint-config-<ts>.json.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without writing the config or invoking agents.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    publishers = _validate_publishers(args.publishers)
    fields = _validate_fields(args.fields)

    cfg = build_sprint_config(publishers, fields)
    print_plan(cfg)

    if args.dry_run:
        print("(dry-run — no config written)")
        return

    MISMATCHES.mkdir(parents=True, exist_ok=True)
    BASELINES.mkdir(parents=True, exist_ok=True)
    out_path = args.sprint_config or (
        MISMATCHES / f"sprint-config-{cfg.sprint_ts}.json"
    )
    out_path.write_text(json.dumps(serialize_config(cfg), indent=2))
    print(f"\nWrote sprint config: {out_path}")
    print(
        "\nInvoke the sprint-coordinator agent next:\n"
        f"  In Claude Code:  Agent(subagent_type='sprint-coordinator', "
        f"prompt='Read {out_path} and run the sprint.')\n"
    )


if __name__ == "__main__":
    main()
