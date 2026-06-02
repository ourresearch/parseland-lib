"""In-process tests for Cambridge UP (cambridge.org) PDF URL extraction.

CUP journal pages expose the PDF via a citation_pdf_url meta (handled by the
generic find_pdf_link). Cambridge eBook (cbo*) chapter pages have no such meta
and no PDF anchor — the aop-cambridge-core/content/view/<hash>/<file>.pdf link
lives only in a script/JSON blob, so ~49/50 PDF misses on the CUP gold slice
were eBooks. parse_publisher_fulltext_location now pulls it from markup when
find_pdf_link returns None, host-gated to cambridge.org.

Hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import (
    find_cup_pdf_link,
    parse_publisher_fulltext_location,
)

CUP_RESOLVED = "https://www.cambridge.org/core/books/abs/x/chapter"
CUP_PDF = (
    "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/"
    "6FD8B783E1C96EC149D10FADAEAE6E9C/9781139199209c2_p41-81_CBO.pdf/title.pdf"
)
# the relative path as it appears in the eBook page's script blob
CUP_PDF_REL = CUP_PDF.replace("https://www.cambridge.org", "")


def test_find_cup_pdf_link_from_script_blob():
    html = f'<html><body><script>var d={{"pdf":"{CUP_PDF_REL}"}};</script></body></html>'
    assert find_cup_pdf_link(html) == CUP_PDF


def test_find_cup_pdf_link_none_when_absent():
    assert find_cup_pdf_link("<html><body>no pdf</body></html>") is None


def test_find_cup_pdf_link_resolves_to_canonical_host():
    # The relative path in markup must resolve to the canonical www.cambridge.org
    # absolute URL (gold form).
    html = f'<div data-pdf="{CUP_PDF_REL}"></div>'
    assert find_cup_pdf_link(html) == CUP_PDF


# NOTE: the end-to-end "eBook page -> parse_publisher_fulltext_location emits the
# aop PDF" path is covered by the live CUP eval (cup-iter2-after.json, 143 real
# rows), not a synthetic fixture: on minimal hand-crafted HTML the generic
# find_pdf_link catches the bare .pdf itself and pre-empts the cambridge.org
# branch, which does not happen on real eBook pages (find_pdf_link returns None
# there). Unit-testing find_cup_pdf_link + the journal-not-overridden guard is
# the meaningful, non-brittle coverage.


def test_journal_citation_pdf_url_not_overridden():
    # When a citation_pdf_url meta is present (journal template), it wins; the
    # cambridge.org eBook fallback only fires when find_pdf_link is None.
    journal_pdf = (
        "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/"
        "AAAA/journal.pdf/title.pdf"
    )
    html = (
        '<html><head>'
        f'<meta property="og:url" content="{CUP_RESOLVED}" />'
        f'<meta name="citation_pdf_url" content="{journal_pdf}" />'
        f'</head><body><script>{{"x":"{CUP_PDF_REL}"}}</script></body></html>'
    )
    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(soup, CUP_RESOLVED)
    assert result["pdf_url"] == journal_pdf
