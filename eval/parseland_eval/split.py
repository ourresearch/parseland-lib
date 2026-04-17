"""Deterministic 50/50 split of gold-standard.json into seed + holdout.

- Seed: rows 1-50 by `No` ascending — used as few-shot examples in the
  Anthropic extraction prompt.
- Holdout: rows 51-100 — used to score the prompt/model before we trust
  it to label thousands more DOIs.
"""
from __future__ import annotations

import json
import sys

from parseland_eval.paths import GOLD_HOLDOUT_JSON, GOLD_JSON, GOLD_SEED_JSON

SEED_SIZE = 50


def split() -> tuple[list[dict], list[dict]]:
    rows = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: int(r["No"]))
    seed = rows[:SEED_SIZE]
    holdout = rows[SEED_SIZE:]
    return seed, holdout


def main() -> int:
    seed, holdout = split()
    GOLD_SEED_JSON.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    GOLD_HOLDOUT_JSON.write_text(json.dumps(holdout, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seed:    {len(seed)} rows → {GOLD_SEED_JSON}")
    print(f"holdout: {len(holdout)} rows → {GOLD_HOLDOUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
