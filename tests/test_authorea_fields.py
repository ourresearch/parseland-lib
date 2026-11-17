"""Authorea preprint pages (authorea.com/users/<id>/articles/<id>-<slug>, oxjob #2338).

Markup cut down from stored pages (17 Nov 2026). Authorea prints the byline as a preview list and one pop-up per
author (div.author-popover): the name, the institution and, for the corresponding author only, a
"Corresponding Author: <e-mail>" line. About one page in six writes no citation_author tags at all, so the generic
reader finds no authors there and the corresponding author is lost.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.authorea import Authorea

URL = "https://www.authorea.com/users/812597/articles/1221329-a-case-report"
CANONICAL = f'<link href="{URL}" rel="canonical"/>'


def _popover(cid, name, aff="", corresponding=False):
    corr = "<p>Corresponding Author:<a href=\"/cdn-cgi/l/email-protection\">[email protected]</a></p>" if corresponding else ""
    return (f'<div class="author-popover" data-collab-id="{cid}"><div class="author-popover-info">'
            f'<div class="author-popover-name">{name}</div><div class="author-popover-affiliations">{aff}</div>'
            f'{corr}<a class="author-popover-profile" href="/users/{cid}">Author Profile</a></div></div>')


def _page(authors, metas=True, canonical=CANONICAL, abstract="A study of things. It found that things happen."):
    tags = "".join(f'<meta name="citation_author" content="{a[0]}">' for a in authors) if metas else ""
    preview = "".join(f'<li class="preview-author"><span class="preview-author-name" data-collab-id="{i}">{a[0]}'
                      f'</span>, </li>' for i, a in enumerate(authors))
    pops = "".join(_popover(i, *a) for i, a in enumerate(authors))
    return (f'<html><head><meta charset="utf-8"><title>A case report - Authorea</title>'
            f'<meta name="description" content="{abstract}">{canonical}'
            f'<meta name="citation_publisher" content="Authorea">{tags}</head><body>'
            f'<div class="preview-authors"><ul class="preview-author-list">{preview}</ul></div>{pops}'
            f'</body></html>')


AUTHORS = [("Aashish Neupane", "Manipal College of Medical Sciences", True),
           ("Rashmi Dahal", "Nepal Medical College Teaching Hospital", False),
           ("Shreya Subedi", "Nobel Medical College", False)]


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_page_without_author_tags_gets_the_byline_and_its_corresponding_author():
    out = _parse(_page(AUTHORS, metas=False))
    assert [a["name"] for a in out["authors"]] == ["Aashish Neupane", "Rashmi Dahal", "Shreya Subedi"]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_page_with_author_tags_marks_the_same_author():
    out = _parse(_page(AUTHORS, metas=True))
    assert [a["name"] for a in out["authors"]] == ["Aashish Neupane", "Rashmi Dahal", "Shreya Subedi"]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_no_corresponding_line_marks_no_one():
    out = _parse(_page([(n, a, False) for n, a, _ in AUTHORS], metas=False))
    assert len(out["authors"]) == 3
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_byline_order_and_names_follow_the_pop_ups():
    # a byline name the citation_author tags leave out (the page shows two authors, the tags one)
    html = _page(AUTHORS[:2], metas=False).replace(
        '<meta name="citation_publisher" content="Authorea">',
        '<meta name="citation_publisher" content="Authorea"><meta name="citation_author" content="Aashish Neupane">')
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == ["Aashish Neupane", "Rashmi Dahal"]


def test_affiliations_are_not_read():
    # under the swarm's 1,000-works floor (#2338): the works lack an affiliation on about one page in 80
    out = _parse(_page(AUTHORS, metas=False))
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_abstract_is_the_generic_readers():
    text = ("Adaptations of organisms to different environments may be important in view of different stressors "
            "caused by climate change. Antarctic lichens provide a good model for studying resistance to environmental "
            "extremes. Our goal was to compare changes in water storage of one lichen from two localities.")
    html = _page(AUTHORS, metas=False).replace("</head>", f'<meta name="citation_abstract" content="{text}"></head>')
    soup = BeautifulSoup(html, "lxml")
    assert Authorea(soup).parse()["abstract"] == text
    assert _parse(html)["abstract"] == text


def test_parse_returns_no_new_field_keys():
    soup = BeautifulSoup(_page(AUTHORS, metas=False), "lxml")
    parser = Authorea(soup)
    assert parser.is_publisher_specific_parser() and parser.authors_found()
    assert not {"acknowledgments", "funding_statement", "references", "references_complete"} & set(parser.parse())


def test_lookalike_popovers_on_another_site_are_not_claimed():
    html = _page(AUTHORS, metas=False, canonical='<link href="https://www.example.org/articles/1" rel="canonical"/>')
    soup = BeautifulSoup(html, "lxml")
    parser = Authorea(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["authors"] == []


def test_authorea_page_without_pop_ups_is_left_to_the_other_readers():
    # Wiley's newer Authorea pages (www.authorea.com/doi/full/...) carry no pop-ups: the generic reader keeps them
    html = _page(AUTHORS, metas=True).replace('class="author-popover"', 'class="loa-author"').replace(
        URL, "https://www.authorea.com/doi/full/10.22541/au.1/v1")
    parser = Authorea(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()
