"""Fuzzy affiliation comparison, scoped to matched author pairs.

Canonicalization is deliberately lightweight: strip emails/URLs, collapse whitespace,
drop common filler tokens ("department of", "institute of"). Full (org, city, country)
triple extraction is a future improvement (see future-ideas in plan).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from rapidfuzz import fuzz  # type: ignore[import-untyped]

from parseland_eval.score.normalize import normalize_alpha

_FILLER = {
    "department", "dept", "school", "institute", "faculty", "laboratory", "lab",
    "center", "centre", "group", "division", "of", "for", "and", "the",
}
_EMAIL = re.compile(r"\S+@\S+")
_URL = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class AffiliationResult:
    strict_f1: float
    soft_f1: float
    fuzzy_f1: float
    matched: int
    gold_total: int
    parsed_total: int


def _clean(text: str) -> str:
    t = _EMAIL.sub(" ", text)
    t = _URL.sub(" ", t)
    return normalize_alpha(t)


def _drop_filler(text: str) -> str:
    toks = [tok for tok in text.split() if tok and tok not in _FILLER]
    return " ".join(toks)


def _extract_affs(author: Any) -> list[str]:
    if isinstance(author, dict):
        raw = author.get("affiliations") or author.get("rasses") or []
    else:
        raw = getattr(author, "affiliations", []) or []
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get("name") or item.get("raw_string") or ""
        else:
            name = str(item)
        name = str(name).strip()
        if name:
            out.append(name)
    return out


def _pair_f1(gold: Sequence[str], parsed: Sequence[str], *, strict: bool, threshold: float) -> tuple[float, int]:
    if not gold and not parsed:
        return 1.0, 0
    if not gold or not parsed:
        return 0.0, 0
    used_g: set[int] = set()
    used_p: set[int] = set()
    tp = 0
    # Greedy: score every pair, sort desc, assign.
    scored: list[tuple[float, int, int]] = []
    for gi, g in enumerate(gold):
        for pi, p in enumerate(parsed):
            if strict:
                ratio = 100.0 if g == p else 0.0
            else:
                ratio = float(fuzz.token_set_ratio(g, p))
            scored.append((ratio, gi, pi))
    scored.sort(reverse=True)
    for ratio, gi, pi in scored:
        if ratio < threshold:
            break
        if gi in used_g or pi in used_p:
            continue
        tp += 1
        used_g.add(gi)
        used_p.add(pi)
    fp = len(parsed) - tp
    fn = len(gold) - tp
    if not tp:
        return 0.0, 0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    f1 = 2 * precision * recall / (precision + recall)
    return f1, tp


def score_affiliations(
    gold_author: Any,
    parsed_author: Any | None,
    *,
    fuzzy_threshold: float = 85.0,
) -> AffiliationResult:
    gold_raw = _extract_affs(gold_author)
    parsed_raw = _extract_affs(parsed_author) if parsed_author is not None else []

    strict_g = tuple(a for a in gold_raw)
    strict_p = tuple(a for a in parsed_raw)
    soft_g = tuple(_clean(a) for a in gold_raw)
    soft_p = tuple(_clean(a) for a in parsed_raw)
    fuzzy_g = tuple(_drop_filler(a) for a in soft_g)
    fuzzy_p = tuple(_drop_filler(a) for a in soft_p)

    strict_f1, _ = _pair_f1(strict_g, strict_p, strict=True, threshold=100.0)
    soft_f1, _ = _pair_f1(soft_g, soft_p, strict=False, threshold=95.0)
    fuzzy_f1, matched = _pair_f1(fuzzy_g, fuzzy_p, strict=False, threshold=fuzzy_threshold)

    return AffiliationResult(
        strict_f1=strict_f1,
        soft_f1=soft_f1,
        fuzzy_f1=fuzzy_f1,
        matched=matched,
        gold_total=len(gold_raw),
        parsed_total=len(parsed_raw),
    )
