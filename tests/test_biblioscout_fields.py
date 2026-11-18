"""BiblioScout pages (biblioscout.net: Verlag Österreich, Franz Steiner Verlag and their imprints), oxjob #2338.

Markup is cut down from stored pages of the site (17 Nov 2026). Every page is a "block--product" record with
<link rel="canonical" href="https://biblioscout.net/...">. Two things the generic parser misses:
- book pages from the Franz Steiner template name their authors only in DC.creator tags (no citation_author), so the
  generic parser reads no authors there;
- article pages print the reference list as `div#references ul.u-list--references > li`, each entry numbered "1. ...".
Everything else (citation_author names, the citation_abstract) stays the generic parser's.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.biblioscout import BiblioScout

ARTICLE_URL = "https://biblioscout.net/article/10.25162/bdi202302009201"
BOOK_URL = "https://biblioscout.net/book/10.25162/9783515115629"
ABSTRACT = ("Der Beitrag rekonstruiert die Sozialisierungsdebatte der Jahre 1918 bis 1920 und fragt, welche "
            "Konzepte der Vergesellschaftung damals diskutiert wurden und was davon für heutige Debatten um "
            "Gemeinwirtschaft und Wirtschaftsdemokratie zu lernen ist.")


def _head(canonical, metas):
    return (f'<head><meta name="DC.rights" content="BiblioScout"><meta name="citation_title" content="A title">{metas}'
            f'<link href="{canonical}" rel="canonical"><title>Article - A title | BiblioScout</title></head>')


def _product(byline):
    return ('<div class="block block--product"><div class="container-fluid"><div class="row">'
            '<div class="col col--title"><div class="title"><span lang="de">A title</span></div>'
            f'<div class="authors text-small"><i>{byline}</i></div></div></div></div></div>')


def _references(items, extra=""):
    lis = "".join(f'<li class="lock" data-key="{i}">{item}</li>' for i, item in enumerate(items))
    return ('<div id="references" class="block block--product-details"><div class="container-fluid">'
            f'<h2>References</h2><div id="w0" class="list-view"><ul class="u-list u-list--rulers u-list--references">'
            f'{lis}</ul>{extra}</div></div></div>')


def _article(body_extra="", canonical=ARTICLE_URL, metas=None):
    if metas is None:
        metas = (f'<meta name="DC.creator" content="Jürgen Leibiger"><meta name="citation_author" content="Jürgen '
                 f'Leibiger"><meta name="citation_abstract" content="{ABSTRACT}">')
    return (f"<html>{_head(canonical, metas)}<body><main id=\"main-content\">{_product('Leibiger, Jürgen')}"
            f'<div id="abstract" class="block block--product-details"><div class="container-fluid"><h2>Abstract</h2>'
            f"<p>{ABSTRACT}</p></div></div>{body_extra}</main></body></html>")


def _book(canonical=BOOK_URL):
    metas = ('<meta name="DC.creator" content="Karl-Wilhelm Welwei">'
             '<meta name="DC.creator" content="Karl-Joachim  Hölkeskamp"><meta name="DC.creator" content="Mischa Meier">')
    bio = ('<div id="authors" class="block block--product-details-authors"><h3>Author information</h3><p>'
           '<b><a href="/search?detail%5Bauthor%5D=Mischa+Meier">Mischa Meier</a></b><br/>Seit 2004 Professor für '
           'Alte Geschichte an der Universität Tübingen.<br/></p></div>')
    byline = "Welwei, Karl-Wilhelm; Hölkeskamp, Karl-Joachim ; Meier, Mischa"
    product = _product(byline).replace('<div class="authors text-small"><i>', '<h3 class="authors">').replace(
        "</i></div></div></div></div></div>", "</h3></div></div></div></div>")
    return f"<html>{_head(canonical, metas)}<body><main id=\"main-content\">{product}{bio}</main></body></html>"


REFS = ["1. Arbeitsplan (1918): Arbeitsplan der Sozialisierungskommission. In: „Die Freiheit“. Berlin.",
        '2. Eulenburg, Franz (1920): Arten und Stufen der Sozialisierung. München: Duncker &amp; Humblot. DOI '
        '<a href="https://dx.doi.org/10.3790/978-3-428-56011-0" target="_blank">10.3790/978-3-428-56011-0</a>',
        "3. Neumayr / Reissner (Hg), Zeller Kommentar<sup>2</sup> (Stand: 1.9.2011, rdb.at)"]


def _parse(html):
    return BiblioScout(BeautifulSoup(html, "lxml")).parse()


def test_book_authors_from_dc_creator():
    out = parse_page(_book().encode(), "doi", BOOK_URL)
    assert [a["name"] for a in out["authors"]] == ["Karl-Wilhelm Welwei", "Karl-Joachim Hölkeskamp", "Mischa Meier"]
    # a biography is not an affiliation (label-v1)
    assert all(a["affiliations"] == [] for a in out["authors"])


def test_article_keeps_generic_authors_and_abstract():
    out = parse_page(_article().encode(), "doi", ARTICLE_URL)
    assert [a["name"] for a in out["authors"]] == ["Jürgen Leibiger"]
    assert out["abstract"] == ABSTRACT


def test_reference_list_is_read_whole():
    out = _parse(_article(_references(REFS)))
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("Arbeitsplan (1918): Arbeitsplan")
    assert refs[1]["raw"].endswith("DOI 10.3790/978-3-428-56011-0")
    assert refs[1]["doi"] == "10.3790/978-3-428-56011-0"
    assert refs[0]["doi"] is None
    assert refs[2]["raw"] == "Neumayr / Reissner (Hg), Zeller Kommentar2 (Stand: 1.9.2011, rdb.at)"
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_reference_list_reaches_parse_page():
    out = parse_page(_article(_references(REFS)).encode(), "doi", ARTICLE_URL)
    assert len(out["references"]) == 3
    assert out["references_complete"] is True


def test_gap_in_numbering_is_not_whole():
    out = _parse(_article(_references([REFS[0], REFS[2]])))
    assert len(out["references"]) == 2
    assert out["references_complete"] is False


def test_paginated_list_is_not_whole():
    pager = '<ul class="pagination"><li class="active"><a href="?page=1">1</a></li><li><a href="?page=2">2</a></li></ul>'
    out = _parse(_article(_references(REFS, extra=pager)))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_page_without_references():
    out = _parse(_article())
    assert out["references"] is None
    assert out["references_complete"] is False


def test_lookalike_pubengine_site_is_not_claimed():
    # the same eLibrary software on another publisher's domain: not this parser's page
    html = _book(canonical="https://elibrary.example-verlag.de/book/10.1234/9783000000000")
    soup = BeautifulSoup(html, "lxml")
    parser = BiblioScout(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert parse_page(html.encode(), "doi", None)["authors"] == []


def test_old_elibrary_layout_is_not_claimed():
    # elibrary.verlagoesterreich.at's older pages, stored under the same DOIs: no canonical link, no product block
    html = ('<html><head><meta name="citation_publisher" content="Verlag Österreich"><meta name="citation_author" '
            'content="Gunter Estermann"></head><body><div class="panel-group" id="article_tabs"></div></body></html>')
    assert not BiblioScout(BeautifulSoup(html, "lxml")).authors_found()
