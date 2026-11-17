"""Schweizerbart science publishers (schweizerbart.de) article pages (oxjob #2338).

Markup is cut down from stored Schweizerbart pages (17 Nov 2026). Each page prints its abstract in
``p.paper_abstract`` blocks, one per language version, each under an ``<h2>`` that names it ("Abstract",
"Kurzfassung", "Résumé"). The generic heading reader reads a block headed "Abstract"; on pages that print only a
"Kurzfassung" nothing read it, and the parser fills that gap only.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.schweizerbart import Schweizerbart

URL = "https://doi.org/10.1127/jm//76/1994/41"
HEAD = ('<meta name="citation_journal_title" content="Jahresberichte und Mitteilungen" />'
        '<meta name="citation_authors" content="Bärle, Frank; Udluff, Peter" />'
        '<meta name="citation_title" content="Die Heilquellen im Raum Bad Kissingen" />'
        '<meta name="citation_doi" content="10.1127/jmogv/76/1994/41" />'
        '<meta name="citation_publisher" content="Schweizerbart\'sche Verlagsbuchhandlung" />'
        '<meta name="DC.Publisher" content="Schweizerbart\'sche Verlagsbuchhandlung" />')

GERMAN = ("Die Historie berühmter Heilbäder reicht meist weit zurück, da bereits in der Vergangenheit an diesen "
          "hydrogeologisch prädestinierten Orten frei austretende Quellen genutzt wurden. Diese drei "
          "Kurgartenquellen sind Grundlage und Herz des Kissinger Kurbetriebes.")
ENGLISH = ("The history of famous spas usually reaches far back, because springs that emerged freely at these "
           "hydrogeologically favoured places were used in the past. These three springs in the spa garden are the "
           "basis and heart of the spa at Bad Kissingen.")


def _block(heading, text):
    return f'<h2>{heading}</h2>\n<p class="paper_abstract">\n        {text}\n</p>\n'


def _page(blocks, head=HEAD):
    return (f'<html><head><title>Die Heilquellen — Schweizerbart science publishers</title>{head}</head><body>'
            '<div id="content"><h3>Original paper</h3><!-- Title -->'
            '<h1>Die Heilquellen im Raum Bad Kissingen</h1><h2>\n\t<b>Bärle, Frank; Udluff, Peter</b>\n</h2>'
            '<div class="detail_item with_image"><div class="right"><!-- Ref count --><p>12 references</p>'
            '<p>published: Apr  5, 1994</p></div></div><div class="clearing"></div><!-- Abstracts -->'
            f'{"".join(blocks)}<!-- Keywords --><h2>Keywords</h2><p>Heilquellen &bull; Bad Kissingen</p></div>'
            '<div id="footer">&copy; 2026 by Schweizerbart science publishers</div></body></html>')


def _abstract(html):
    return parse_page(html.encode(), "doi", URL)["abstract"]


def _soup(html):
    return BeautifulSoup(html, parser="lxml", features="lxml")


def test_kurzfassung_only_page_gives_its_abstract():
    assert _abstract(_page([_block("Kurzfassung", GERMAN)])) == GERMAN


def test_english_abstract_heading_is_left_to_the_heading_reader():
    html = _page([_block("Abstract", ENGLISH), _block("Kurzfassung", GERMAN)])
    assert Schweizerbart(_soup(html)).parse()["abstract"] is None
    assert _abstract(html) == ENGLISH


def test_english_abstract_after_the_german_one_still_wins():
    assert _abstract(_page([_block("Kurzfassung", GERMAN), _block("Abstract", ENGLISH)])) == ENGLISH


def test_english_version_under_another_heading_comes_first():
    html = _page([_block("Kurzfassung", GERMAN), _block("Summary", ENGLISH)])
    assert Schweizerbart(_soup(html)).parse()["abstract"] == ENGLISH


def test_empty_block_is_no_abstract():
    html = _page([_block("Kurzfassung", "  ")])
    assert Schweizerbart(_soup(html)).parse()["abstract"] is None
    assert _abstract(html) is None


def test_parser_returns_no_authors_and_no_back_matter():
    parsed = Schweizerbart(_soup(_page([_block("Kurzfassung", GERMAN)]))).parse()
    assert parsed["authors"] == []
    assert not {"acknowledgments", "funding_statement", "references"} & parsed.keys()


def test_page_not_found_shell_is_not_claimed():
    html = ('<html><head><title>Page not found — Schweizerbart science publishers</title></head>'
            '<body><h1>Page not found</h1></body></html>')
    parser = Schweizerbart(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_look_alike_page_of_another_publisher_is_not_claimed():
    head = HEAD.replace("Schweizerbart'sche Verlagsbuchhandlung", "Verlag Dr. Friedrich Pfeil")
    html = _page([_block("Kurzfassung", GERMAN)], head=head)
    parser = Schweizerbart(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _abstract(html) != GERMAN
