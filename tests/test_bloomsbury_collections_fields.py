"""Bylines on the old Bloomsbury Collections chapter pages (Magnolia theme "collections") (oxjob #2268).

Markup is cut down from stored bloomsburycollections.com pages (backfill era, 16 Nov 2026). The page prints the book's
byline (`div.book-details p.book-author`) and, for a chapter with its own authors, the chapter byline
(`div.book-section h3.book-author`); each name is a `span.personname` inside a popover `<strong>`. Translators and
editors share the book byline ("Translated by ...", "... (eds)"). No other parser reads these pages, so the live works
of most of their chapters have no authors. The newer Bloomsbury platforms (`bloomsbury_assets/`) are another template.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.bloomsbury_collections import BloomsburyCollections
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

URL = "https://doi.org/10.5040/9780755621668.ch-014"
THEME = ('<link rel="stylesheet" type="text/css" '
         'href="/resources/templating-kit/themes/collections/css/styles.2021-08-09-08-13-41-216.cache.css" media="all">')


def person(first, last):
    return ('<strong data-container="body" data-toggle="popover" data-title="%s %s" '
            'data-content="%s %s is a historian.&lt;p class=&quot;italics&quot;&gt;Author affiliation details are '
            'correct at time of print publication&lt;/p&gt;"><span class="first-last personname">'
            '<span class="firstname">%s</span> <span class="surname">%s</span></span></strong>'
            % (first, last, first, last, first, last))


def page(book_bylines, chapter_byline=None, head=THEME):
    book = "".join(f'<p class="book-author">{b}</p>' for b in book_bylines)
    chapter = f'<h3 class="book-author">{chapter_byline}<br></h3>' if chapter_byline else ""
    return (f"<html><head><title>Bloomsbury Collections - A Book</title>{head}</head><body><div id=\"main\">"
            f'<div class="in-chapter"><div class="book-module"><div class="book-details require-highlight">'
            f'<h2 class="book-title"><a href="/book/a-book">A Book</a></h2>{book}'
            f'<p class="book-published-details">I.B.Tauris <span class="published-date">2015</span></p></div></div>'
            f'<div class="book-section book-chapter abstract"><h1>Chapter 14. A Chapter</h1>{chapter}'
            f'<div class="extract abstract"><h2 class="preview-banner">Extract</h2>The opening of the chapter, '
            f'a preview of its body text and not an abstract...</div></div></div></div></body></html>')


def names(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_monograph_chapter_takes_the_book_author():
    assert names(page([person("Richard", "Stevenson")])) == ["Richard Stevenson"]


def test_chapter_byline_wins_over_the_book_editors():
    html = page([person("Lori", "Gruen") + " and " + person("Fiona", "Probyn-Rapsey") + " (eds)"],
                chapter_byline=person("lynn", "mowson"))
    assert names(html) == ["lynn mowson"]


def test_chapter_byline_with_two_authors():
    html = page([person("Henri", "Lefebvre"), "Translated by " + person("Gerald", "Moore")],
                chapter_byline=person("Henri", "Lefebvre") + " and " + person("Catherine", "Régulier"))
    assert names(html) == ["Henri Lefebvre", "Catherine Régulier"]


def test_translator_is_not_an_author():
    html = page([person("Nawal", "El Saadawi") + "<br>Translated by " + person("Sherif", "Hetata") + "<br>"])
    assert names(html) == ["Nawal El Saadawi"]


def test_edited_volume_chapter_without_its_own_byline_credits_no_one():
    html = page([person("Jackie", "Keily") + " and " + person("Julia", "Hoffbrand") + " (eds)"])
    assert names(html) == []
    html = page([person("Hani A.", "Faris") + " (ed)"])
    assert names(html) == []


def test_no_affiliation_from_the_biography_popover_and_no_corresponding():
    out = parse_page(page([person("Richard", "Stevenson")]).encode(), "doi", URL)
    assert out["authors"][0]["affiliations"] == []
    assert out["authors"][0]["is_corresponding"] is False


def test_extract_is_not_an_abstract_and_no_new_fields():
    html = page([person("Richard", "Stevenson")])
    assert parse_page(html.encode(), "doi", URL)["abstract"] is None
    parsed = BloomsburyCollections(BeautifulSoup(html, "lxml")).parse()
    assert parsed["abstract"] is None
    for key in ("acknowledgments", "funding_statement", "references"):
        assert not parsed.get(key)


def test_abstract_stays_what_the_generic_readers_found():
    summary = ("In this book the author offers a critical introduction to the history of health, healing and illness "
               "in the region from the nineteenth century to the present day, drawing on archival sources, oral "
               "histories and the work of medical anthropologists to show how ideas of the body changed over time.")
    html = page([person("Richard", "Stevenson")]).replace(
        "</head>", f'<meta name="description" content="{summary}"></head>').replace(
        '<div class="book-section', f'<div class="book-section abstract"><h2 class="authors-abstract">Book Summary / '
        f'Abstract</h2><p>{summary}</p></div><div class="book-section', 1)
    soup = BeautifulSoup(html, "lxml")
    generic = GenericPublisherParser(soup).parse()["abstract"]
    assert generic
    assert BloomsburyCollections(soup).parse()["abstract"] == generic
    assert names(html) == ["Richard Stevenson"]


def test_error_page_of_the_theme_is_not_claimed_for_authors():
    html = (f"<html><head>{THEME}</head><body><div id=\"main\"><p>An error occurred whilst loading module content "
            f"Book not found.</p></div></body></html>")
    parser = BloomsburyCollections(BeautifulSoup(html, "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_other_magnolia_theme_is_not_claimed():
    other = ('<link rel="stylesheet" type="text/css" '
             'href="/resources/templating-kit/themes/pop/css/styles.cache.css" media="all">')
    parser = BloomsburyCollections(BeautifulSoup(page([person("Richard", "Stevenson")], head=other), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_new_bloomsbury_platform_page_is_not_claimed():
    html = ('<html><head><title>Bloomsbury Collections - Show Trials</title>'
            '<link rel="stylesheet" href="/bloomsbury_assets/css/bootstrap.css">'
            '<meta property="og:url" content="http://www.bloomsburycollections.com/collections/monograph-detail">'
            '</head><body><div class="book-details"><p class="book-author"><span class="personname">'
            'Ann Author</span></p></div></body></html>')
    parser = BloomsburyCollections(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
