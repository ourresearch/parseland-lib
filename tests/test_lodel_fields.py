"""Authors from DC.creator and the bibliography on OpenEdition's Lodel pages (oxjob #2268, template "lodel").

Markup is cut down from stored OpenEdition pages (#2268's Lodel sample, 16 Nov 2026). A book chapter of a monograph,
a whole book and a journal book review print no "#authors" section: the item's authors are only in its DC.creator meta
tags ("Family, Given"; the reviewed book's author is DC.contributor), and the page's "#presentation-book" line repeats
the book's authors. The parser read only the section, so those pages had no authors (the gate's dev gold gives the
book's author on such chapter pages). Lodel prints the bibliography as one p.bibliographie per entry, with neither
numbers nor a count, so the page never shows that the list is whole.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.openedition import OpenEdition

BOOK = "https://books.openedition.org/septentrion/71918"
JOURNAL = "http://journals.openedition.org/abstractairanica/26762"


def _page(og, head="", body=""):
    return (f'<html><head><meta name="generator" content="Lodel 1.0"/><meta property="og:url" content="{og}"/>'
            f'{head}</head><body class="textes chapitre"><div id="text">Texte</div>{body}</body></html>')


def _creators(*names, tag="DC.creator"):
    return "".join(f'<meta name="author" content="{n}"/><meta name="{tag}" content="{n}"/>' for n in names)


def _names(html, url=BOOK):
    return [a["name"] for a in parse_page(html.encode(), "doi", url)["authors"]]


PRESENTATION = ('<div class="table-cell" id="presentation-book"><h2 class="inline">Jules Émile Scrive</h2>'
                '<span class="separator">|</span><div class="author inline">Claudine Wallart</div>'
                '<span class="separator">,</span><div class="author inline"> Didier Terrier</div></div>')


def test_chapter_without_author_section_reads_dc_creator():
    html = _page("​https://books.openedition.org/septentrion/71918",
                 _creators("Wallart, Claudine", "Terrier, Didier"), PRESENTATION)
    assert _names(html) == ["Claudine Wallart", "Didier Terrier"]


def test_book_review_takes_the_reviewer_not_the_reviewed_author():
    html = _page(JOURNAL, _creators("Kaim, Barbara") + _creators("Harper, Prudence O.", tag="DC.contributor"))
    assert _names(html, JOURNAL) == ["Barbara Kaim"]


def test_creator_names_are_turned_round_and_squashed():
    html = _page(BOOK, _creators("M., Kannan", "Hadj Belgacem, Samir", "Le Boulanger, Jean-Michel"))
    assert _names(html) == ["Kannan M.", "Samir Hadj Belgacem", "Jean-Michel Le Boulanger"]


def test_author_section_still_wins_over_dc_creator():
    section = ('<div class="authors" id="authors"><h2>Auteur</h2><div class="author">'
               '<div class="name">Sandrine Lavaud</div><div class="description">Université Bordeaux Montaigne</div>'
               '</div></div>')
    html = _page(BOOK, _creators("Somebody, Else"), section)
    authors = parse_page(html.encode(), "doi", BOOK)["authors"]
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in authors] == [
        ("Sandrine Lavaud", ["Université Bordeaux Montaigne"])]


def test_other_lodel_site_with_dc_creator_is_not_claimed():
    # fabula.org runs Lodel too and prints DC.creator; it is not OpenEdition, so this parser leaves it alone
    html = _page("https://www.fabula.org:443/acta/document14032.php", _creators(" \nFrançois Jacob "))
    assert OpenEdition(BeautifulSoup(html, "lxml")).authors_found() is False


def test_dc_creator_page_off_lodel_is_not_claimed():
    # a repository page with the same meta tags and no OpenEdition og:url
    html = ('<html><head><meta property="og:url" content="https://dspace.example.edu/handle/1/2"/>'
            '<meta name="DC.creator" content="Doe, Jane"/></head><body></body></html>')
    assert OpenEdition(BeautifulSoup(html, "lxml")).authors_found() is False


BIBLIOGRAPHY = ('<div class="section" id="bibliography"><h2 class="section"><span class="text">Bibliographie</span>'
                '</h2><div class="text">'
                '<h1 class="bibliographie">Sources</h1>'
                '<p class="bibliographie">ARLAUD S. et PERIGORG M. — « Pays » et développement local, <em>Norois</em>, '
                'n°181, 1999-1, 140 p.</p>'
                '<p class="separateur">*</p>'
                '<h1 class="bibliographie">Études</h1>'
                '<p class="bibliographie">Piché J., Larsen M., 2010, The Moving Targets of Penal Abolitionism, '
                '<em>Contemporary Justice Review</em>, 13, 4, 391-410. DOI : 10.1080/10282580.2010.517964</p>'
                '</div><a class="go-top" href="#article-4049">Haut de page</a></div>')


def _parsed(html):
    return OpenEdition(BeautifulSoup(html, "lxml")).parse()


def test_bibliography_entries_in_page_order_with_their_doi():
    parsed = _parsed(_page(JOURNAL, _creators("Kaim, Barbara"), BIBLIOGRAPHY))
    assert [(r["position"], r["raw"][:20], r["doi"]) for r in parsed["references"]] == [
        (1, "ARLAUD S. et PERIGOR", None), (2, "Piché J., Larsen M.,", "10.1080/10282580.2010.517964")]


def test_bibliography_is_never_called_whole():
    # no numbers and no count: nothing on the page shows the list is whole
    assert _parsed(_page(JOURNAL, _creators("Kaim, Barbara"), BIBLIOGRAPHY))["references_complete"] is False


def test_no_bibliography_no_references():
    parsed = _parsed(_page(JOURNAL, _creators("Kaim, Barbara")))
    assert parsed["references"] is None and parsed["references_complete"] is False
