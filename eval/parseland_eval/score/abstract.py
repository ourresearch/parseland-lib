"""Abstract comparison: Levenshtein ratio + length-ratio sanity check.

We deliberately avoid BLEU (tokenizer-biased per SacreBLEU) and keep the scorer
deterministic and character-based. The length ratio is kept as a side-signal so
truncation bugs are visible even when the ratio is OK (e.g., parsed only the
first paragraph but phrasing matches).
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz  # type: ignore[import-untyped]

from parseland_eval.score.normalize import normalize_text


@dataclass(frozen=True)
class AbstractResult:
    strict_match: bool
    soft_ratio: float     # 0-1 on NFKC+casefold-normalized text
    fuzzy_ratio: float    # 0-1 on raw text, rapidfuzz ratio
    length_ratio: float   # parsed length / gold length (1.0 = equal; <1 = truncated)
    present: bool         # did parser return any non-empty abstract?


def score_abstract(gold: str | None, parsed: str | None) -> AbstractResult:
    gold_s = (gold or "").strip()
    parsed_s = (parsed or "").strip()
    present = bool(parsed_s)

    if not gold_s and not parsed_s:
        return AbstractResult(True, 1.0, 1.0, 1.0, present)
    if not gold_s or not parsed_s:
        return AbstractResult(False, 0.0, 0.0, 0.0, present)

    gold_n = normalize_text(gold_s)
    parsed_n = normalize_text(parsed_s)

    strict = gold_s == parsed_s
    soft = fuzz.ratio(gold_n, parsed_n) / 100.0
    fuzzy = fuzz.ratio(gold_s, parsed_s) / 100.0
    length_ratio = len(parsed_s) / len(gold_s) if gold_s else 0.0

    return AbstractResult(
        strict_match=strict,
        soft_ratio=soft,
        fuzzy_ratio=fuzzy,
        length_ratio=length_ratio,
        present=present,
    )
