"""Corresponding authors on World Scientific (worldscientific.com) pages from the author info cards (oxjob #2211).

Markup is cut down from stored pages sampled 10 Nov 2026 (#2145 EXPLORE § 1). Each byline author has an info card;
the corresponding author's card holds a paragraph "Corresponding author." The World Scientific parser throws on most
pages, so the winning parser (which reads the names) marked no one.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.parser import world_scientific_corresponding_names

_CONTEXT = '<meta name="pbContext" content=";website:website:wspc-site;article:article:10.1142/S0000;">'


def _card(i, name, paras):
    body = "".join(f"<p>{p}</p>" for p in paras)
    return (f'<div class="accordion-tabbed__tab-mobile"><a href="#" title="{name}" data-id="a{i}" '
            f'class="author-name accordion-tabbed__control visible-x"><span>{name}</span>'
            f'<i aria-hidden="true" class="icon-arrow_d_n"></i></a><span></span>'
            f'<div class="author-info accordion-tabbed__content"><p class="author-type"></p>{body}'
            f'<div class="bottom-info"><p><a href="/author/x">Search for more papers by this author</a></p></div>'
            f'</div></div><span class="author-name"><span class="author-separator">, </span></span>')


def _page(authors, context=_CONTEXT):
    metas = "".join(f'<meta name="dc.Creator" content="{n}"><meta name="citation_author" content="{n}">'
                    for n, _ in authors)
    cards = "".join(_card(i + 1, n, p) for i, (n, p) in enumerate(authors))
    return (f'<html><head>{context}{metas}<meta name="dc.Title" content="A paper">'
            f'<meta name="citation_title" content="A paper"></head><body>'
            f'<div class="loa-wrapper hidden-xs"><div id="sb-1" class="accordion"><div class="accordion-tabbed '
            f'loa-accordion">{cards}</div></div></div></body></html>')


AFF = "School of Mathematics and Physics, China University of Geosciences, Wuhan, 430074, P. R. China"
EMAIL = '<a href="/cdn-cgi/l/email-protection#d5">E-mail Address: <span class="__cf_email__">[email&#160;protected]</span></a>'
THREE = [("WADHAH AL-SADI", [AFF, EMAIL]), ("ZHOUCHAO WEI", [AFF, EMAIL, "Corresponding author."]),
         ("IRENE MOROZ", ["Mathematical Institute, Oxford University, Oxford, OX2 6GG, UK"])]


def _parsed(html):
    return parse_page(html.encode(), "doi", "https://www.worldscientific.com/doi/10.1142/S0000")["authors"]


def test_card_paragraph_names_the_corresponding_author():
    html = _page(THREE)
    assert world_scientific_corresponding_names(BeautifulSoup(html, "lxml")) == ["ZHOUCHAO WEI"]
    authors = _parsed(html)
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["ZHOUCHAO WEI"]
    assert len(authors) == 3 and all(a["is_corresponding"] is not None for a in authors)


def test_an_email_alone_is_not_a_mark():
    html = _page([("WADHAH AL-SADI", [AFF, EMAIL]), ("IRENE MOROZ", [AFF])])
    assert world_scientific_corresponding_names(BeautifulSoup(html, "lxml")) == []
    assert not any(a["is_corresponding"] for a in _parsed(html))


def test_two_corresponding_authors_and_plural_label():
    html = _page([("Xiang Liu", [AFF, "Corresponding authors."]), ("Ping Xiang", [AFF]),
                  ("Lizhong Jiang", [AFF, "Corresponding author"])])
    assert world_scientific_corresponding_names(BeautifulSoup(html, "lxml")) == ["Xiang Liu", "Lizhong Jiang"]


def test_an_affiliation_that_mentions_correspondence_is_not_a_mark():
    html = _page([("Jun Iizuka", ["Department of Corresponding Studies, Tokai University"]),
                  ("Teruyuki Kitabayashi", [AFF])])
    assert world_scientific_corresponding_names(BeautifulSoup(html, "lxml")) == []


def test_other_sites_on_the_same_template_are_left_alone():
    other = '<meta name="pbContext" content=";website:website:aom-site;article:article:10.5465/x;">'
    html = _page(THREE, context=other)
    assert world_scientific_corresponding_names(BeautifulSoup(html, "lxml")) == []


def test_older_wordings_in_the_same_card():
    for note in ("Author for correspondence.", "Corresponding author, tel: +1 819-564-5409.",
                 "Correspondence to: Dr. Johan E. van Lier, Department of Nuclear Medicine, Sherbrooke, Canada.",
                 "Corresponding author: Johan E. van Lier, Sherbrooke, Canada."):
        html = _page([("Hasrat Ali", [AFF]), ("Johan E. van Lier", [AFF, note])])
        assert world_scientific_corresponding_names(BeautifulSoup(html, "lxml")) == ["Johan E. van Lier"], note
