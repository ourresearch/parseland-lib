from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = ROOT / "eval"
GOLD_CSV = EVAL_DIR / "gold-standard.csv"
GOLD_JSON = EVAL_DIR / "gold-standard.json"
GOLD_SEED_JSON = EVAL_DIR / "gold-standard.seed.json"
GOLD_HOLDOUT_JSON = EVAL_DIR / "gold-standard.holdout.json"
HTML_CACHE = EVAL_DIR / "html-cache"
RUNS_DIR = EVAL_DIR / "runs"
SILVER_DIR = EVAL_DIR / "silver"
PROMPTS_DIR = ROOT / "eval" / "parseland_eval" / "prompts"
PARSELAND_LIB = ROOT
