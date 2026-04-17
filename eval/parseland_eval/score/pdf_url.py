"""PDF URL comparison after canonicalization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from parseland_eval.score.normalize import canonicalize_url


@dataclass(frozen=True)
class PdfUrlResult:
    strict_match: bool      # exact string match after canonicalization
    present: bool            # parser returned any PDF url
    expected_present: bool   # gold had a PDF url
    divergent: bool          # both present but differ


def _extract_pdf(parsed: dict[str, Any] | None) -> str | None:
    if not parsed:
        return None
    for url in parsed.get("urls") or []:
        if isinstance(url, dict) and url.get("content_type") == "pdf":
            return url.get("url")
    return parsed.get("pdf_url")


def score_pdf_url(gold_pdf: str | None, parsed: dict[str, Any] | None) -> PdfUrlResult:
    parsed_pdf = _extract_pdf(parsed)
    g = canonicalize_url(gold_pdf)
    p = canonicalize_url(parsed_pdf)

    expected_present = bool(g)
    present = bool(p)

    if not expected_present and not present:
        return PdfUrlResult(True, present, expected_present, False)
    if not expected_present or not present:
        return PdfUrlResult(False, present, expected_present, False)
    match = g == p
    return PdfUrlResult(match, present, expected_present, not match)
