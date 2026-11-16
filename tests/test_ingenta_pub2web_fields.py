"""Ingenta's pub2web platform (Ingenta Edify: UN, WTO and OECD iLibrary, EarthDoc, Intellect, John Benjamins ...)
read by ingenta_connect.py (oxjob #2268). Markup cut down from stored pages."""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ingenta_connect import IngentaConnect

URL = "https://doi.org/10.18356/37ec2189-es"
CRAWLER = '<link rel="schema.CRAWLER" href="http://labs.ingenta.com/2006/06/16/crawler" />'


def page(head, body):
    return f"<html><head><title>t</title>{head}</head><body>{body}</body></html>"


def chapter(byline, head=CRAWLER):
    """A UN / WTO iLibrary chapter page: no citation_author tags, the byline in the item's metadata box, and a
    related-content list whose own bylines are not this item's."""
    return page(
        head + '<meta name="dc.title" content="Gases inflamables" />',
        '<div class="title-box item-metadata__maindata"><ul class="list-unstyled"><li>'
        '<span class="meta-key authors_label"><strong> Author:</strong></span> ' + byline + '</li>'
        '<li><span class="meta-key chapter_source_label"><strong>Main Title:</strong></span></li></ul></div>'
        '<ul class="related"><li><span class="meta-key authors_label">Author(s):</span>'
        '<span class="author-list__item"><a href="/search?value1=X&option1=author">Someone Else</a></span></li></ul>')


def link(name):
    return (f'<span class="author-list__item"><a href="/search?value1={name}&amp;option1=author&amp;noRedirect=true"'
            f' class="nonDisambigAuthorLink">{name}</a></span>')


def names(out):
    return [a["name"] for a in out["authors"]]


def test_chapter_byline_group_author_is_read():
    out = parse_page(chapter(link("United Nations")).encode(), "doi", URL)
    assert names(out) == ["United Nations"]


def test_chapter_byline_reads_every_name_and_skips_related_bylines():
    out = parse_page(chapter(link("Rebecca Surtees") + " and " + link("Anette Brunovskis")).encode(), "doi", URL)
    assert names(out) == ["Rebecca Surtees", "Anette Brunovskis"]


def test_oecd_sidebar_author_on_a_table_page():
    html = page(CRAWLER + '<meta name="dc.title" content="China: Estimates of support to agriculture" />',
                '<div class="block-infos-sidebar date-daily col-xs-12"><p><strong class="entitled"> Author(s)</strong>'
                '<br> OECD </p><p><strong class="entitled">18 Oct 2019</strong></p></div>')
    assert names(parse_page(html.encode(), "doi", "https://doi.org/10.1787/2a8ea1de-en")) == ["OECD"]


def test_oecd_author_line_with_several_names_is_left_alone():
    html = page(CRAWLER, '<div class="block-infos-sidebar"><p><strong class="entitled"> Author(s)</strong>'
                         '<br> Jane Doe, John Roe </p></div>')
    assert parse_page(html.encode(), "doi", "https://doi.org/10.1787/x")["authors"] == []


OECD_BOOK_ABSTRACT = ("La transición hacia la economía circular para la ciudad de Valladolid, España, representa una "
                      "oportunidad para un mayor atractivo y competitividad, a la vez que proporciona respuestas a los "
                      "retos medioambientales.")


def oecd_book(item_id):
    return page(CRAWLER + f'<meta name="stats-meta" content="stats" data-itemid="{item_id}" />',
                '<div class="main-content"><h2 class="block-title">La Economía Circular en Valladolid</h2>'
                f'<div class="description js-desc-fade"><p>{OECD_BOOK_ABSTRACT}</p></div>'
                '<p><span class="meta-item"> Author(s): OECD </span></p></div>')


def test_oecd_book_page_reads_its_own_description_as_abstract():
    out = parse_page(oecd_book("/content/publication/34c34508-es").encode(), "doi", "https://doi.org/10.1787/34c34508-es")
    assert names(out) == ["OECD"]
    assert out["abstract"] == OECD_BOOK_ABSTRACT


def test_oecd_chapter_page_does_not_take_the_parent_book_description():
    out = parse_page(oecd_book("/content/component/383f63fa-en").encode(), "doi", "https://doi.org/10.1787/383f63fa-en")
    assert out["abstract"] != OECD_BOOK_ABSTRACT


REFS = ('<li class=" tabIcon" id="references"><a href="#referenceContainer"><strong class="titleIcon"> References ({n})'
        '</strong></a></li>'
        '<div class="references tab-pane" id="referenceContainer"><div id="referencedetails">'
        '<p class="description"><span class="tl-main-part">References</span></p>'
        '<ol class="list-unstyled" id="articlereference">'
        '<li class="refbody" id="ref-CIT0001"><span><span class="reference-person-group-apa">Auer, P.</span>'
        '<div class="refline"> (<span>1996</span>) The pre-front field in spoken German <a class="doilink" '
        'href="http://dx.doi.org/10.1075/prag.6.3.03aue">10.1075/prag.6.3.03aue</a></div></span>'
        '<span class="refExternalLink"><a class="externallink" href="https://doi.org/10.1075/prag.6.3.03aue">'
        'https://doi.org/10.1075/prag.6.3.03aue</a> <a class="js-externallink" href="http://scholar.google.com/'
        'scholar_lookup?doi=10.9999%2Fnot.this">[Google Scholar]</a></span></li>'
        '<li class="refbody" id="ref-CIT0002"><span><span class="reference-person-group-apa">Veeken, P.</span>'
        '<div class="refline"> [2007] Seismic Stratigraphy. Elsevier.</div></span>'
        '<a class="js-externallink" href="http://scholar.google.com/scholar_lookup?title=x">[Google Scholar]</a></li>'
        '</ol></div></div>')
JOURNAL_HEAD = (CRAWLER + '<meta name="citation_title" content="Seismic inversion" />'
                '<meta name="citation_author" content="Ahmed Ali" />'
                '<meta name="citation_author_institution" content="Cairo University" />')


def journal_soup(n):
    return BeautifulSoup(page(JOURNAL_HEAD, REFS.format(n=n)), "lxml")


def test_journal_reference_list_with_matching_count_is_complete():
    out = IngentaConnect(journal_soup(2)).parse()
    assert [r["position"] for r in out["references"]] == [1, 2]
    assert out["references"][0]["doi"] == "10.1075/prag.6.3.03aue"
    assert out["references"][0]["raw"].startswith("Auer, P. (1996) The pre-front field in spoken German")
    assert "Google Scholar" not in out["references"][0]["raw"]
    assert out["references"][1]["doi"] is None
    assert out["references_complete"] is True


def test_journal_reference_list_short_of_its_stated_count_is_not_complete():
    assert IngentaConnect(journal_soup(5)).parse()["references_complete"] is False


def test_journal_page_keeps_the_meta_tag_byline_and_affiliations():
    out = parse_page(page(JOURNAL_HEAD, REFS.format(n=2)).encode(), "doi", "https://doi.org/10.3997/x")
    assert [(a["name"], [f["name"] for f in a["affiliations"]]) for a in out["authors"]] == [
        ("Ahmed Ali", ["Cairo University"])]


def test_lookalike_byline_without_the_ingenta_crawler_mark_is_not_claimed():
    soup = BeautifulSoup(chapter(link("United Nations"), head=""), "lxml")
    assert not IngentaConnect(soup).is_publisher_specific_parser()
    assert parse_page(chapter(link("United Nations"), head="").encode(), "doi", URL)["authors"] == []


def test_ingenta_connect_page_is_not_read_as_pub2web():
    html = page('<meta name="IC.identifier" content="x" />', REFS.format(n=2))
    soup = BeautifulSoup(html, "lxml")
    assert not IngentaConnect(soup).is_publisher_specific_parser()
