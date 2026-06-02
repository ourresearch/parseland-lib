"""In-process tests for the CUP (Cambridge UP) citation_author meta fallback.

Older CUP journal pages and Cambridge eBook (cbo*) chapters use a template with
no `div.author` — authors live in `citation_author` meta tags (affiliations in
`citation_author_institution`). ~40% of the CUP gold slice (54/135 rows) hit
this template and returned zero authors before the fallback, dragging Authors
F1 to 0.59. CUP.parse() now falls back to parse_author_meta_tags() when the
div.author path finds nothing.

These pin: (1) meta fallback fires when div.author is absent; (2) the modern
div.author path is unchanged when present; (3) meta affiliations are picked up.

Hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.cup import CUP

CAMBRIDGE_OG = '<meta property="og:url" content="https://www.cambridge.org/core/x" />'


def _wrap(head_extra: str, body: str = "") -> str:
    return f"<html><head>{CAMBRIDGE_OG}{head_extra}</head><body>{body}</body></html>"


def _names(authors):
    out = []
    for a in authors:
        out.append(a.get("name") if isinstance(a, dict) else getattr(a, "name", None))
    return out


def test_meta_fallback_when_no_div_author():
    html = _wrap(
        '<meta name="citation_author" content="C. A. F. Rhys Davids" />'
        '<meta name="citation_author_institution" content="University of London" />'
    )
    out = CUP(BeautifulSoup(html, "lxml")).parse()
    assert _names(out["authors"]) == ["C. A. F. Rhys Davids"]
    a0 = out["authors"][0]
    affs = a0.get("affiliations") if isinstance(a0, dict) else getattr(a0, "affiliations", [])
    assert affs == ["University of London"]


def test_meta_fallback_multiple_authors():
    html = _wrap(
        '<meta name="citation_author" content="Alice Lovat" />'
        '<meta name="citation_author" content="R. E. Sackett" />'
    )
    out = CUP(BeautifulSoup(html, "lxml")).parse()
    assert _names(out["authors"]) == ["Alice Lovat", "R. E. Sackett"]


def test_div_author_path_still_used_when_present():
    # Modern template: div.author present → meta fallback must NOT override it.
    body = (
        '<div class="author"><dt>Jane Modern*</dt>'
        '<div class="d-sm-flex">Cambridge University, UK</div></div>'
    )
    html = _wrap('<meta name="citation_author" content="Should Not Win" />', body)
    out = CUP(BeautifulSoup(html, "lxml")).parse()
    assert _names(out["authors"]) == ["Jane Modern"]
    a0 = out["authors"][0]
    is_corr = a0.get("is_corresponding") if isinstance(a0, dict) else getattr(a0, "is_corresponding", None)
    assert is_corr is True  # the * marks corresponding on the modern template


# --- abstract: eBook div.abstract fallback ---------------------------------

_LONG_ABS = (
    "Frank Sinatra's recording and film careers reveal interesting parallels "
    "and divergences. " * 12
)


def test_ebook_abstract_falls_back_to_div_when_meta_is_short():
    # eBook page: og:description is just the book title; the real abstract is
    # in div.abstract. The fallback should pick up the long div text.
    html = _wrap(
        '<meta property="og:description" content="Frank Sinatra - June 2007" />',
        f'<div class="abstract">{_LONG_ABS}</div>',
    )
    out = CUP(BeautifulSoup(html, "lxml")).parse()
    assert out["abstract"] and out["abstract"].startswith("Frank Sinatra")
    assert len(out["abstract"]) > 200


def test_journal_meta_abstract_not_overridden_by_div():
    # Journal page: a full meta abstract is present → keep it (no regression).
    long_meta = "This is the real journal abstract. " * 12
    html = _wrap(
        f'<meta name="citation_abstract" content="{long_meta}" />',
        '<div class="abstract">short noise</div>',
    )
    out = CUP(BeautifulSoup(html, "lxml")).parse()
    assert out["abstract"].startswith("This is the real journal abstract")
