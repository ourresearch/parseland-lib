from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = ROOT / "eval"
GOLD_JSON = EVAL_DIR / "Gold Standard For Parseland - Sheet1.json"
HTML_CACHE = EVAL_DIR / "html-cache"
RUNS_DIR = EVAL_DIR / "runs"
PARSELAND_LIB = ROOT
