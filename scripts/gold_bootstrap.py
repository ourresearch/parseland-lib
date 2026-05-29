"""Phase 2 gold-builder entrypoint — bootstrap draft gold for publishers without fixtures.

Operator-facing wrapper for the `gold-builder` agent
(`.claude/agents/gold-builder.md`). This script:

  1. Validates the publisher key and resolves its CrossRef DOI prefix.
  2. Samples DOIs from CrossRef.
  3. Emits a gold-builder config JSON that the agent reads.
  4. The agent performs the actual HTML fetch + LLM extraction + draft write.

This script does NOT do the extraction itself — that requires the
`eval/parseland_eval/expand.py` extraction scaffold and Anthropic API access,
which is the gold-builder agent's responsibility.

Hard rules enforced here:
  - Never write to ``tests/fixtures/<publisher>-gold.ndjson`` — drafts only go
    to ``tests/fixtures/<publisher>-gold-draft.ndjson``.
  - Default n=50; refuse to proceed at n>200 without ``--allow-large``.
  - Bot-check skipping is the agent's job, but we surface the policy here.

Usage:

    python scripts/gold_bootstrap.py --publisher taylor_francis --n 50
    python scripts/gold_bootstrap.py --publisher sage --n 10  # smoke test
    python scripts/gold_bootstrap.py --publisher acs --n 500 --allow-large
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path("/Users/shubh-trips/Documents/OpenAlex/parseland-lib")
FIXTURES = REPO_ROOT / "tests" / "fixtures"
MISMATCHES = REPO_ROOT / "mismatches"
GOLD_DRAFTS = MISMATCHES / "gold-drafts"


@dataclass(frozen=True)
class PublisherGoldSpec:
    """Per-publisher gold-bootstrap configuration."""

    key: str
    name: str
    crossref_prefixes: tuple[str, ...]
    expected_landing_hosts: tuple[str, ...]


# Phase 2 publishers (no existing gold). Phase 1 publishers (Elsevier, Springer,
# Wiley, IEEE) are deliberately omitted — they already have gold and shouldn't
# be re-bootstrapped through this path.
PHASE_2_REGISTRY: dict[str, PublisherGoldSpec] = {
    "taylor_francis": PublisherGoldSpec(
        key="taylor_francis",
        name="Taylor & Francis",
        crossref_prefixes=("10.1080",),
        expected_landing_hosts=("tandfonline.com",),
    ),
    "sage": PublisherGoldSpec(
        key="sage",
        name="SAGE",
        crossref_prefixes=("10.1177",),
        expected_landing_hosts=("journals.sagepub.com",),
    ),
    "wolters_kluwer": PublisherGoldSpec(
        key="wolters_kluwer",
        name="Wolters Kluwer (LWW)",
        crossref_prefixes=("10.1097",),
        expected_landing_hosts=("journals.lww.com",),
    ),
    "cambridge": PublisherGoldSpec(
        key="cambridge",
        name="Cambridge University Press",
        crossref_prefixes=("10.1017",),
        expected_landing_hosts=("cambridge.org",),
    ),
    "acs": PublisherGoldSpec(
        key="acs",
        name="American Chemical Society",
        crossref_prefixes=("10.1021",),
        expected_landing_hosts=("pubs.acs.org",),
    ),
}


def _existing_gold_path(publisher: str) -> Path:
    return FIXTURES / f"{publisher}-gold.ndjson"


def _draft_gold_path(publisher: str) -> Path:
    return FIXTURES / f"{publisher}-gold-draft.ndjson"


def _check_no_clobber(publisher: str) -> None:
    """Refuse to proceed if production gold already exists — protects from accidental overwrite."""
    prod = _existing_gold_path(publisher)
    if prod.exists():
        print(
            f"ERROR: {prod} already exists. Phase 2 gold-builder is for publishers WITHOUT "
            f"production gold. Use the Phase 1 improvement loop for this publisher instead.",
            file=sys.stderr,
        )
        sys.exit(1)


def build_bootstrap_config(spec: PublisherGoldSpec, n: int) -> dict:
    ts = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    return {
        "sprint_ts": ts,
        "publisher": spec.key,
        "publisher_name": spec.name,
        "n_target_rows": n,
        "crossref_prefixes": list(spec.crossref_prefixes),
        "expected_landing_hosts": list(spec.expected_landing_hosts),
        "draft_output_path": str(_draft_gold_path(spec.key)),
        "coverage_report_path": str(
            MISMATCHES / f"gold-builder-coverage-{spec.key}-{ts}.json"
        ),
        "log_append_path": str(MISMATCHES / "gold-builder-log.ndjson"),
        "extraction_scaffold": "/Users/shubh-trips/Documents/OpenAlex/parseland-lib/eval/parseland_eval/expand.py",
        "html_cache_dir": str(REPO_ROOT / "html-cache"),
        "rules": {
            "never_overwrite_production_gold": True,
            "production_gold_path": str(_existing_gold_path(spec.key)),
            "min_confidence_for_no_human_review": 0.7,
            "skip_bot_check_html": True,
            "max_n_without_explicit_flag": 200,
        },
        "agent_dispatch": {
            "gold_builder": ".claude/agents/gold-builder.md",
        },
    }


def print_plan(cfg: dict) -> None:
    print(f"\n=== Gold-builder plan ({cfg['sprint_ts']}) ===")
    print(f"  publisher:           {cfg['publisher']}  ({cfg['publisher_name']})")
    print(f"  n target rows:       {cfg['n_target_rows']}")
    print(f"  CrossRef prefixes:   {cfg['crossref_prefixes']}")
    print(f"  Expected hosts:      {cfg['expected_landing_hosts']}")
    print(f"  Draft output:        {cfg['draft_output_path']}")
    print(f"  Coverage report:     {cfg['coverage_report_path']}")
    print(f"  Extraction scaffold: {cfg['extraction_scaffold']}")
    print(
        "\n  Next: invoke gold-builder agent. In Claude Code:\n"
        "    Agent(subagent_type='gold-builder', prompt=<config JSON>).\n"
    )


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Bootstrap draft gold NDJSON for a Phase 2 publisher.",
    )
    ap.add_argument(
        "--publisher",
        required=True,
        choices=sorted(PHASE_2_REGISTRY.keys()),
        help="Phase 2 publisher key (no existing production gold).",
    )
    ap.add_argument(
        "--n",
        type=int,
        default=50,
        help="Target draft row count. Default 50; >200 requires --allow-large.",
    )
    ap.add_argument(
        "--allow-large",
        action="store_true",
        help="Allow n > 200. Use sparingly — LLM extraction is the cost driver.",
    )
    ap.add_argument(
        "--config-out",
        type=Path,
        default=None,
        help="Path to write the bootstrap config JSON.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without writing the config.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    spec = PHASE_2_REGISTRY[args.publisher]
    _check_no_clobber(args.publisher)

    if args.n > 200 and not args.allow_large:
        print(
            f"ERROR: n={args.n} exceeds default cap (200). Pass --allow-large to proceed.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.n <= 0:
        print(f"ERROR: --n must be positive, got {args.n}", file=sys.stderr)
        sys.exit(1)

    cfg = build_bootstrap_config(spec, args.n)
    print_plan(cfg)

    if args.dry_run:
        print("(dry-run — no config written)")
        return

    MISMATCHES.mkdir(parents=True, exist_ok=True)
    GOLD_DRAFTS.mkdir(parents=True, exist_ok=True)
    out_path = args.config_out or (
        MISMATCHES / f"gold-builder-config-{spec.key}-{cfg['sprint_ts']}.json"
    )
    out_path.write_text(json.dumps(cfg, indent=2))
    print(f"\nWrote gold-builder config: {out_path}")


if __name__ == "__main__":
    main()
