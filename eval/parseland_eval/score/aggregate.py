"""Aggregate per-row scores into scorecard (overall / per-publisher / per-failure-mode)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from parseland_eval.gold import GoldRow
from parseland_eval.runner import ParserRun
from parseland_eval.score.abstract import AbstractResult, score_abstract
from parseland_eval.score.affiliations import AffiliationResult, score_affiliations
from parseland_eval.score.authors import AuthorResult, score_authors
from parseland_eval.score.pdf_url import PdfUrlResult, score_pdf_url


@dataclass(frozen=True)
class RowScore:
    doi: str
    no: int
    publisher_domain: str
    parser_name: str | None
    duration_ms: float
    error: str | None
    gold_quality: str
    failure_modes: tuple[str, ...]
    has_bot_check: bool | None
    authors: AuthorResult | None
    affiliations: AffiliationResult | None
    abstract: AbstractResult
    pdf_url: PdfUrlResult
    bot_check_flag: bool  # from fetch layer, if available (None → False here)


def _parser_name(run: ParserRun) -> str | None:
    if not run.parsed:
        return None
    # parseland-lib's parse.py doesn't emit parser name in the ordered response.
    # We treat "which parser ran" as unknown for now; future work: expose it.
    return None


def _aff_for_row(gold: GoldRow, run: ParserRun, authors_result: AuthorResult | None) -> AffiliationResult | None:
    if not authors_result or not gold.score_authors:
        return None
    parsed_authors = (run.parsed or {}).get("authors") or []
    per_pair: list[AffiliationResult] = []
    for match in authors_result.matched:
        gold_author = gold.authors[match.gold_index]
        parsed_author = parsed_authors[match.parsed_index] if match.parsed_index < len(parsed_authors) else None
        per_pair.append(score_affiliations(gold_author, parsed_author))
    if not per_pair:
        return None
    # Mean across matched author pairs.
    return AffiliationResult(
        strict_f1=mean(p.strict_f1 for p in per_pair),
        soft_f1=mean(p.soft_f1 for p in per_pair),
        fuzzy_f1=mean(p.fuzzy_f1 for p in per_pair),
        matched=sum(p.matched for p in per_pair),
        gold_total=sum(p.gold_total for p in per_pair),
        parsed_total=sum(p.parsed_total for p in per_pair),
    )


def score_row(gold: GoldRow, run: ParserRun) -> RowScore:
    parsed = run.parsed or {}
    if gold.score_authors:
        authors_result = score_authors(list(gold.authors), parsed.get("authors") or [])
    else:
        authors_result = None
    abs_res = score_abstract(gold.abstract, parsed.get("abstract"))
    pdf_res = score_pdf_url(gold.pdf_url, parsed)
    aff_res = _aff_for_row(gold, run, authors_result)

    return RowScore(
        doi=gold.doi,
        no=gold.no,
        publisher_domain=run.publisher_domain,
        parser_name=_parser_name(run),
        duration_ms=run.duration_ms,
        error=run.error,
        gold_quality=gold.gold_quality,
        failure_modes=gold.failure_modes,
        has_bot_check=gold.has_bot_check,
        authors=authors_result,
        affiliations=aff_res,
        abstract=abs_res,
        pdf_url=pdf_res,
        bot_check_flag=bool(gold.has_bot_check),
    )


def _mean_f1(scores: list[RowScore], accessor) -> float:
    vals = [v for v in (accessor(s) for s in scores) if v is not None]
    return float(mean(vals)) if vals else 0.0


def summarize(scores: list[RowScore]) -> dict[str, Any]:
    authors_rows = [s for s in scores if s.authors is not None]
    aff_rows = [s for s in scores if s.affiliations is not None]

    overall = {
        "rows": len(scores),
        "authors_scored_rows": len(authors_rows),
        "authors_f1_strict": _mean_f1(authors_rows, lambda s: s.authors.f1 if s.authors else None),
        "authors_f1_soft": _mean_f1(authors_rows, lambda s: s.authors.f1_soft if s.authors else None),
        "affiliations_f1_strict": _mean_f1(aff_rows, lambda s: s.affiliations.strict_f1 if s.affiliations else None),
        "affiliations_f1_soft": _mean_f1(aff_rows, lambda s: s.affiliations.soft_f1 if s.affiliations else None),
        "affiliations_f1_fuzzy": _mean_f1(aff_rows, lambda s: s.affiliations.fuzzy_f1 if s.affiliations else None),
        "abstract_ratio_soft": _mean_f1(scores, lambda s: s.abstract.soft_ratio),
        "abstract_ratio_fuzzy": _mean_f1(scores, lambda s: s.abstract.fuzzy_ratio),
        "abstract_strict_match_rate": _mean_f1(scores, lambda s: 1.0 if s.abstract.strict_match else 0.0),
        "abstract_present_rate": _mean_f1(scores, lambda s: 1.0 if s.abstract.present else 0.0),
        "pdf_url_accuracy": _mean_f1(scores, lambda s: 1.0 if s.pdf_url.strict_match else 0.0),
        "pdf_url_divergence_rate": _mean_f1(scores, lambda s: 1.0 if s.pdf_url.divergent else 0.0),
        "errors": sum(1 for s in scores if s.error),
        "duration_ms_mean": _mean_f1(scores, lambda s: s.duration_ms),
    }

    by_publisher: dict[str, list[RowScore]] = defaultdict(list)
    for s in scores:
        by_publisher[s.publisher_domain or "unknown"].append(s)
    per_publisher = {
        domain: {
            "rows": len(rs),
            "authors_f1_soft": _mean_f1([r for r in rs if r.authors], lambda s: s.authors.f1_soft if s.authors else None),
            "affiliations_f1_fuzzy": _mean_f1([r for r in rs if r.affiliations], lambda s: s.affiliations.fuzzy_f1 if s.affiliations else None),
            "abstract_ratio_fuzzy": _mean_f1(rs, lambda s: s.abstract.fuzzy_ratio),
            "pdf_url_accuracy": _mean_f1(rs, lambda s: 1.0 if s.pdf_url.strict_match else 0.0),
            "errors": sum(1 for r in rs if r.error),
        }
        for domain, rs in sorted(by_publisher.items(), key=lambda kv: -len(kv[1]))
    }

    by_failure: dict[str, list[RowScore]] = defaultdict(list)
    for s in scores:
        tags = s.failure_modes or ("clean",)
        for t in tags:
            by_failure[t].append(s)
    per_failure_mode = {
        mode: {
            "rows": len(rs),
            "authors_f1_soft": _mean_f1([r for r in rs if r.authors], lambda s: s.authors.f1_soft if s.authors else None),
            "abstract_ratio_fuzzy": _mean_f1(rs, lambda s: s.abstract.fuzzy_ratio),
            "pdf_url_accuracy": _mean_f1(rs, lambda s: 1.0 if s.pdf_url.strict_match else 0.0),
        }
        for mode, rs in sorted(by_failure.items(), key=lambda kv: -len(kv[1]))
    }

    return {
        "overall": overall,
        "per_publisher": per_publisher,
        "per_failure_mode": per_failure_mode,
    }
