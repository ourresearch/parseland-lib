"""Tolerant loader for the 100-row hand-annotated gold standard.

Handles the documented quirks *in the adapter*, without mutating the source file:
  - "N/A" / "N/A`" in Authors  → authors=[] (expected-empty, annotator confirmed none available)
  - Row 5 has a journal title in Authors → gold_quality="journal-title-leaked"; skip Author scoring
  - Row 51 has unparsed JSON string in Authors → retry json.loads; else gold_quality="broken-json"
  - "rasses" key is accepted as an alias for "affiliations"
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parseland_eval.paths import GOLD_JSON


NA_MARKERS = {"N/A", "N/A`", "NA", "n/a", ""}


@dataclass(frozen=True)
class GoldAuthor:
    name: str
    affiliations: tuple[str, ...]
    is_corresponding: bool | None


@dataclass(frozen=True)
class GoldRow:
    no: int
    doi: str
    link: str
    authors: tuple[GoldAuthor, ...]
    abstract: str | None
    pdf_url: str | None
    status: bool
    notes: str
    has_bot_check: bool | None
    resolves_to_pdf: bool | None
    gold_quality: str = "ok"          # "ok" | "journal-title-leaked" | "broken-json"
    score_authors: bool = True         # False → skip Authors scoring for this row
    failure_modes: tuple[str, ...] = ()  # derived from notes


FAILURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("paywall", re.compile(r"\bpay(?:wall|.{0,6}view|.{0,6}access|.{0,6}subscription)\b|subscription based|need to pay|need to buy", re.I)),
    ("login", re.compile(r"login|institution|sign[-\s]?in|subscription", re.I)),
    ("bot_check", re.compile(r"bot|captcha|cloudflare|security", re.I)),
    ("no_abstract", re.compile(r"no abstract|abstract.*image|abstract.*not available", re.I)),
    ("broken_url", re.compile(r"broken|seems broken|not found|unspecified server error", re.I)),
    ("non_article", re.compile(r"obituary|dataset|video|journal\b|chapter|grant", re.I)),
    ("image_only", re.compile(r"image|screenshot", re.I)),
    ("login_screen", re.compile(r"thank[s]? for visit(?:i)?ng|oxford dictionary", re.I)),
)


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if s == "TRUE":
        return True
    if s == "FALSE":
        return False
    return None


def _derive_failure_modes(notes: str) -> tuple[str, ...]:
    if not notes:
        return ()
    hits: list[str] = []
    for label, pat in FAILURE_PATTERNS:
        if pat.search(notes):
            hits.append(label)
    return tuple(hits)


def _normalize_authors_field(raw: Any) -> tuple[list[dict[str, Any]] | None, str, bool]:
    """Returns (parsed_authors_or_None, gold_quality, score_authors).

    parsed_authors_or_None = None  means "expected empty" (N/A).
    """
    if isinstance(raw, list):
        return raw, "ok", True
    if raw is None:
        return None, "ok", True
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped in NA_MARKERS:
            return None, "ok", True
        if stripped.startswith("["):
            try:
                return json.loads(stripped), "ok", True
            except json.JSONDecodeError:
                return None, "broken-json", False
        return None, "journal-title-leaked", False
    return None, "journal-title-leaked", False


def _coerce_author(entry: dict[str, Any]) -> GoldAuthor:
    name = str(entry.get("name", "") or "").strip()
    raw_aff = entry.get("affiliations") or entry.get("rasses") or entry.get("address") or entry.get("addresses")
    if raw_aff is None:
        affs: tuple[str, ...] = ()
    elif isinstance(raw_aff, str):
        affs = (raw_aff,) if raw_aff.strip() else ()
    elif isinstance(raw_aff, (list, tuple)):
        affs = tuple(str(a).strip() for a in raw_aff if str(a).strip())
    else:
        affs = ()
    corresponding = entry.get("corresponding_author")
    if corresponding is None:
        corresponding = entry.get("is_corresponding")
    if isinstance(corresponding, str):
        corresponding = corresponding.strip().lower() in {"true", "1", "yes"}
    return GoldAuthor(
        name=name,
        affiliations=affs,
        is_corresponding=bool(corresponding) if corresponding is not None else None,
    )


def load_gold(path: Path | None = None) -> list[GoldRow]:
    source = Path(path) if path else GOLD_JSON
    with source.open(encoding="utf-8") as f:
        rows_raw = json.load(f)

    rows: list[GoldRow] = []
    for r in rows_raw:
        no = int(r["No"])
        doi = str(r.get("DOI", "")).strip()
        link = str(r.get("Link", "")).strip()
        abstract = (r.get("Abstract") or "").strip() or None
        pdf_url = (r.get("PDF URL") or "").strip() or None
        status = _parse_bool(r.get("Status")) or False
        notes = (r.get("Notes") or "").strip()

        parsed_authors, gold_quality, score_authors = _normalize_authors_field(r.get("Authors"))
        authors_tuple: tuple[GoldAuthor, ...]
        if parsed_authors is None:
            authors_tuple = ()
        else:
            authors_tuple = tuple(_coerce_author(a) for a in parsed_authors if isinstance(a, dict))

        rows.append(
            GoldRow(
                no=no,
                doi=doi,
                link=link,
                authors=authors_tuple,
                abstract=abstract,
                pdf_url=pdf_url,
                status=status,
                notes=notes,
                has_bot_check=_parse_bool(r.get("Has Bot Check")),
                resolves_to_pdf=_parse_bool(r.get("Resolves To PDF")),
                gold_quality=gold_quality,
                score_authors=score_authors,
                failure_modes=_derive_failure_modes(notes),
            )
        )
    return rows
