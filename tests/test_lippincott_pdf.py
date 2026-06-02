"""In-process tests for Lippincott / Wolters Kluwer (journals.lww.com) PDF URL
extraction.

LWW article landing pages emit **no** ``citation_pdf_url`` meta tag, so the
generic ``find_pdf_link`` path returns None and PDF URL scored ~0 on the WK
gold slice. The real PDF download link
(``.../_layouts/15/oaks.journals/downloadpdf.aspx?trckng_src_pg=<x>&an=<AN>``)
is present in the page markup. ``parse_publisher_fulltext_location`` now picks
it up via ``find_lww_pdf_link`` when the resolved host is journals.lww.com.

These pin:
  1. Extraction from a normal anchor (HTML-escaped ``&amp;``).
  2. Extraction from a script/JSON blob form.
  3. No false positive on a non-LWW host.
  4. ``an=`` article-number param is preserved (it identifies the resource).

All fixtures are minimal hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import (
    find_lww_pdf_link,
    parse_publisher_fulltext_location,
)

LWW_RESOLVED = (
    "https://journals.lww.com/jorthotrauma/abstract/1990/04030/example.10"
)
LWW_PDF = (
    "https://journals.lww.com/jorthotrauma/_layouts/15/oaks.journals/"
    "downloadpdf.aspx?trckng_src_pg=Other&an=00005131-199004030-00010"
)


def _wrap(body: str, og_url: str = LWW_RESOLVED) -> str:
    head = f'<meta property="og:url" content="{og_url}" />'
    return f"<html><head>{head}</head><body>{body}</body></html>"


def test_find_lww_pdf_link_from_anchor():
    # &amp; is how the ampersand appears in real markup.
    html = _wrap(
        '<a href="https://journals.lww.com/jorthotrauma/_layouts/15/'
        'oaks.journals/downloadpdf.aspx?trckng_src_pg=Other&amp;'
        'an=00005131-199004030-00010">PDF</a>'
    )
    got = find_lww_pdf_link(html)
    assert got == LWW_PDF


def test_find_lww_pdf_link_from_script_blob():
    html = _wrap(
        '<script>window.__data={"url":"https://journals.lww.com/jorthotrauma/'
        '_layouts/15/oaks.journals/downloadpdf.aspx?trckng_src_pg=Other&amp;'
        'an=00005131-199004030-00010"};</script>'
    )
    got = find_lww_pdf_link(html)
    assert got == LWW_PDF


def test_find_lww_pdf_link_none_when_absent():
    assert find_lww_pdf_link("<html><body>no pdf here</body></html>") is None


def test_parse_publisher_fulltext_location_emits_lww_pdf():
    html = _wrap(
        '<a href="https://journals.lww.com/jorthotrauma/_layouts/15/'
        'oaks.journals/downloadpdf.aspx?trckng_src_pg=Other&amp;'
        'an=00005131-199004030-00010">PDF</a>'
    )
    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(soup, LWW_RESOLVED)
    assert result is not None
    assert result["pdf_url"] == LWW_PDF
    assert "an=00005131-199004030-00010" in result["pdf_url"]


def test_non_lww_host_does_not_pick_lww_branch():
    # A non-LWW page with no citation_pdf_url meta should not get an LWW PDF
    # (the branch is host-gated).
    html = (
        '<html><head><meta property="og:url" '
        'content="https://example.com/article/1" /></head>'
        '<body><p>no pdf</p></body></html>'
    )
    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(soup, "https://example.com/article/1")
    assert result is not None
    assert result["pdf_url"] is None
