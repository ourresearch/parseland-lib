"""Corresponding authors on Emerald Insight article pages (oxjob #2212).

Markup is cut down from stored emerald.com pages (#2150 EXPLORE § 1, 845 seeded pages). The retired Emerald Insight
template marks the corresponding author with JATS corresp="yes" on the author's div (2015+ articles: 211 of 214 marked
pages mark exactly one author). The Emerald parser read the names and affiliations but never the mark.
"""
from parseland_lib.parse import parse_page

URL = "https://www.emerald.com/insight/content/doi/10.1108/SHR-06-2016-0045/full/html"
CANONICAL = '<link rel="canonical" href="https://www.emerald.com/insight/content/doi/10.1108/SHR-06-2016-0045/full/html"/>'


def _author(given, surname, aff, corresp=False):
    mark = ' corresp="yes"' if corresp else ""
    return (f'<div class="contrib_block__contrib intent_contributor" contrib-type="author"{mark}>'
            f'<a rel="nofollow" class="contrib-search" href="/insight/search?q={given} {surname}">'
            f'<span class="given-names">{given}</span> <span class="surname">{surname}</span></a>'
            f'<span class="contrib_block__aff--italic intent_contributor_affiliate">({aff})</span></div>')


def _page(authors, canonical=CANONICAL):
    return (f'<html><head>{canonical}<meta name="citation_title" content="A title"/></head><body>'
            f'<section id="intent_contributors" class="mt-4 intent_contributors"><contributor-block>'
            f'<span class="m:contributor-display">{"".join(authors)}</span></contributor-block></section>'
            f'</body></html>')


def _parse(html, url=URL):
    return parse_page(html.encode(), "doi", url)["authors"]


def test_corresp_yes_marks_that_author_only():
    authors = _parse(_page([
        _author("Anna", "Berg", "University of Oslo, Oslo, Norway"),
        _author("Rahul", "Mehta", "IIM Bangalore, Bangalore, India", corresp=True),
        _author("Li", "Wei", "Fudan University, Shanghai, China"),
    ]))
    assert [a["name"] for a in authors] == ["Anna Berg", "Rahul Mehta", "Li Wei"]
    assert [a["is_corresponding"] for a in authors] == [False, True, False]
    assert authors[1]["affiliations"] == [{"name": "IIM Bangalore, Bangalore, India"}]


def test_single_author_page_with_mark():
    authors = _parse(_page([_author("VJ", "Bala", "hCentive, Reston, Virginia, USA", corresp=True)]))
    assert [(a["name"], a["is_corresponding"]) for a in authors] == [("VJ Bala", True)]


def test_page_with_no_mark_flags_no_one():
    # pre-2015 Insight pages and book chapters mark no one: leave the flag unknown, never guess from position
    authors = _parse(_page([
        _author("Anna", "Berg", "University of Oslo, Oslo, Norway"),
        _author("Rahul", "Mehta", "IIM Bangalore, Bangalore, India"),
    ]))
    assert [a["name"] for a in authors] == ["Anna Berg", "Rahul Mehta"]
    assert not any(a["is_corresponding"] for a in authors)


def test_other_site_with_jats_markup_is_not_read_by_the_emerald_parser():
    other = '<link rel="canonical" href="https://journals.example.org/doi/10.9999/abc"/>'
    html = _page([_author("Anna", "Berg", "Oslo", corresp=True), _author("Li", "Wei", "Fudan")], canonical=other)
    from bs4 import BeautifulSoup
    from parseland_lib.publisher.parsers.emerald import Emerald
    assert not Emerald(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
