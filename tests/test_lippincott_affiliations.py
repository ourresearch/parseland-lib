"""Regression tests for Lippincott.get_affiliations crash-hardening.

On a chunk of real LWW pages (13/125 of the WK gold slice) the affiliation
extractor raised and crashed the *entire* parse — losing authors, abstract,
AND pdf_url for those rows (the in-process harness early-returns urls=[] on a
parse exception). Three distinct crash paths were found and fixed:

  1. ``cleanup_aff`` was handed ``aff.next_element.next_element`` which is
     sometimes a bs4 Tag (e.g. <em>), not a NavigableString. ``Tag.split``
     triggers bs4's child-tag lookup → returns None → ``None(...)`` →
     "NoneType is not callable".
  2. ``affiliations[0].text`` IndexError when ``findAll("p")`` is empty.
  3. ``aff_text.split(aff_id)[-1]`` IndexError when parse_aff_ids returns None
     and the segment is empty (``''.split(None)`` is []).

These pin that get_affiliations returns a list (never raises) on each shape.
Hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.lippincott import Lippincott


def _info_holder(inner: str) -> str:
    # #ejp-article-authors makes is_publisher_specific_parser / authors_found
    # fire; the info-holder div is what get_affiliations reads.
    return (
        '<html><head>'
        '<meta property="og:url" content="https://journals.lww.com/j/x" />'
        '</head><body>'
        '<div id="ejp-article-authors">Author, A.</div>'
        f'<div class="ejp-article-authors-info-holder">{inner}</div>'
        '</body></html>'
    )


def _affs(inner: str):
    soup = BeautifulSoup(_info_holder(inner), "lxml")
    return Lippincott(soup).get_affiliations()


def test_sup_followed_by_tag_does_not_crash():
    # <sup> immediately followed by a Tag (<em>) — crash path 1.
    html = '<p><sup>1</sup><em>University of Example, City, Country</em></p>'
    result = _affs(html)
    assert isinstance(result, list)


def test_empty_p_list_does_not_crash():
    # info-holder with a <sup> but no <p> at all — crash path 2.
    html = '<span><sup>1</sup>Some Institute</span>'
    result = _affs(html)
    assert isinstance(result, list)


def test_semicolon_segment_without_aff_id_does_not_crash():
    # A <p> whose ';' split yields an empty / id-less segment — crash path 3.
    html = '<p>; University of Example, City</p>'
    result = _affs(html)
    assert isinstance(result, list)


def test_full_parse_does_not_crash_on_tag_after_sup():
    soup = BeautifulSoup(
        _info_holder('<p><sup>*</sup><em>Dept of X, Y University</em></p>'),
        "lxml",
    )
    # The whole parse() must not raise (it previously did, zeroing the row).
    out = Lippincott(soup).parse()
    assert "authors" in out
    assert "abstract" in out
