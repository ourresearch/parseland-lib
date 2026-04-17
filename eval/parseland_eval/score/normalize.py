"""String and URL canonicalization for comparison keys.

Follows UAX#15 guidance: use NFKC+casefold for match keys only; preserve originals
for display. Diacritics are stripped so "Cédric" matches "Cedric".
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from unidecode import unidecode  # type: ignore[import-untyped]

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]+", flags=re.UNICODE)
_TRACKING_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "gclid", "fbclid", "mc_cid", "mc_eid",
    }
)


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_text(text: str | None) -> str:
    """NFKC + unidecode (handles ß, ligatures) + casefold + diacritic fold + whitespace collapse."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = unidecode(t)
    t = t.casefold()
    t = strip_diacritics(t)
    t = _WHITESPACE.sub(" ", t).strip()
    return t


def normalize_alpha(text: str | None) -> str:
    """As normalize_text but also drops punctuation — for fuzzy name/org keys."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = unidecode(t)
    t = t.casefold()
    t = strip_diacritics(t)
    t = _PUNCT.sub(" ", t)
    t = _WHITESPACE.sub(" ", t).strip()
    return t


def canonicalize_url(url: str | None) -> str:
    """Lowercase scheme+host, strip tracking params, drop trailing slash."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    scheme = parts.scheme.lower() or "https"
    host = parts.netloc.lower().removeprefix("www.")
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in _TRACKING_PARAMS]
    query = urlencode(query_pairs)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, query, ""))


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d
