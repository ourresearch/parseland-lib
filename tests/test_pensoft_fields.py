"""Affiliations and corresponding authors on Pensoft's ARPHA journal platform (oxjob #2289, template "pensoft").

Markup is cut down from stored ARPHA article pages (pensoft.net journals, *.arphahub.com, lib.jucs.org; 17 Nov 2026).
The article body renders in an iframe, so the stored page's citation_author tags carry the byline with no
affiliations, and the "Article Info" panel prints each author's card: name, a "- Corresponding author" note, and one
<div> per affiliation. The cards come in their own order with fuller names, so they are matched to the byline by name.
Every page of the platform loads its journal's stylesheet from /lib/css/journals/journal_<n>.css.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.pensoft import PensoftArpha

URL = "https://checklist.pensoft.net/article/12345/"
ARPHA_CSS = '<link type="text/css" rel="stylesheet" href="/lib/css/journals/journal_67.css?v=1659690715" />'
BYLINE = ["Ana Lima", "Bruno Costa", "Carla Souza"]


def _card(name, affs, corresponding=False, editor=False, email=True):
    corr = '<span class="AOF-Author-Corr"> - Corresponding author</span>' if corresponding else \
        ('' if editor else '<span class="AOF-Author-Corr"></span>')
    href = ' href="mailto:x@example.org"' if email else ''
    cls = "AOF-Single-Author-Preview AOF-Single-SE-Preview" if editor else "AOF-Single-Author-Preview"
    return (f'<div class="{cls}" data-author-id="1"><div class="AOF-Author-Details">'
            f'<div class="orcid-link"></div><div class="AOF-Author-Name">'
            f'<a class="AOF-Author-Email"{href}>{name}  <img src="/i/email_icon.svg"/></a>{corr}</div>'
            f'<div class="AOF-Author-Affiliation">{"".join(f"<div>{a}</div>" for a in affs)}</div>'
            f'<div class="AOF-Author-more">Articles by this author in: <a href="#">CrossRef</a></div>'
            f'</div></div>')


def _page(cards, byline=BYLINE, head=ARPHA_CSS, editor=None):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in byline)
    se = (f'<div class="P-SE-Label">Academic editor</div><div class="P-Authors-List">{editor}</div>'
          if editor else "")
    return (f'<html><head>{head}<meta name="description" content="Studies on the vertical distribution of larval '
            f'fish in water masses along the coast are very rare. The present study describes the composition, '
            f'abundance and seasonal patterns of fish larvae over four years of sampling at twelve stations on the '
            f'shelf."/>{metas}<meta name="citation_title" content="Larval fish of a coastal basin"/>'
            f'<meta name="citation_doi" content="10.15560/8.6.1280"/>'
            f'</head><body><div id="article-preview"><iframe src="article_preview.php?id=12345"></iframe></div>'
            f'<div class="P-Info-Content"><div class="P-Authors-Whole-List">'
            f'<div class="P-Authors-Label">Authors</div><div class="P-Authors-List">{"".join(cards)}</div>{se}'
            f'</div></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


# The cards print fuller names than the byline, and in another order.
CARDS = [_card("Ana Maria Pereira Lima", ["Universidade Federal do Rio de Janeiro, Brazil"], corresponding=True),
         _card("Carla de Souza", ["Universidade de São Paulo, Brazil",
                                   "Instituto Oceanográfico, São Paulo, Brazil"]),
         _card("Bruno Alves Costa", ["Universidade Federal do Rio de Janeiro, Brazil"], email=False)]


def test_affiliations_come_from_the_author_cards_in_byline_order():
    out = _parse(_page(CARDS))
    assert [a["name"] for a in out["authors"]] == BYLINE
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Universidade Federal do Rio de Janeiro, Brazil"],
        ["Universidade Federal do Rio de Janeiro, Brazil"],
        ["Universidade de São Paulo, Brazil", "Instituto Oceanográfico, São Paulo, Brazil"]]


def test_corresponding_author_is_the_card_with_the_note():
    out = _parse(_page(CARDS))
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Lima"]


def test_two_corresponding_notes_mark_both():
    cards = [_card("Ana Lima", ["A"], corresponding=True), _card("Bruno Costa", ["B"], corresponding=True),
             _card("Carla Souza", ["C"])]
    out = _parse(_page(cards))
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Lima", "Bruno Costa"]


def test_no_note_marks_no_one():
    cards = [_card(n, ["Museum of New Zealand Te Papa Tongarewa, Wellington, New Zealand"]) for n in BYLINE]
    out = _parse(_page(cards))
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert all(a["affiliations"] for a in out["authors"])


def test_academic_editor_card_is_not_an_author():
    editor = _card("Raul Editor", ["Universidad de la República, Montevideo, Uruguay"], editor=True)
    out = _parse(_page(CARDS, editor=editor))
    assert [a["name"] for a in out["authors"]] == BYLINE
    assert not any("Uruguay" in x["name"] for a in out["authors"] for x in a["affiliations"])


def test_abstract_is_kept():
    assert _parse(_page(CARDS))["abstract"].startswith("Studies on the vertical distribution")


def test_card_matching_no_byline_name_is_skipped():
    cards = CARDS + [_card("Someone Else Entirely", ["Elsewhere University"], corresponding=True)]
    out = _parse(_page(cards))
    assert [a["name"] for a in out["authors"]] == BYLINE
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Lima"]


def test_page_without_author_cards_is_not_claimed():
    # Many stored pensoft.net pages print no Article Info panel: the byline tags alone, nothing to add.
    html = _page([])
    parser = PensoftArpha(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()


def test_lookalike_page_without_the_platform_stylesheet_is_not_claimed():
    # The same card markup on a page that does not load ARPHA's journal stylesheet (another platform, a copy).
    html = _page(CARDS, head='<link rel="stylesheet" href="/static/css/journal.css"/>')
    parser = PensoftArpha(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_other_template_page_is_not_claimed():
    # An OJS article page with a byline and affiliations of its own.
    html = ('<html><head><meta name="generator" content="Open Journal Systems 3.3.0.10"/>'
            '<link rel="stylesheet" href="https://journal.example.org/lib/pkp/styles/fontawesome/fontawesome.css"/>'
            '<meta name="citation_author" content="Ana Lima"/>'
            '<meta name="citation_author_institution" content="Universidade de São Paulo"/></head>'
            '<body><section class="item authors"><ul class="authors"><li><span class="name">Ana Lima</span>'
            '<span class="affiliation">Universidade de São Paulo</span></li></ul></section></body></html>')
    parser = PensoftArpha(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
