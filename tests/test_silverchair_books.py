"""Silverchair book chapter and book pages (oxjob #2221).

Markup is cut down from stored pages of Duke, MIT Press, RSC, Karger, Emerald and GSA books (13 Nov 2026, #2221
EXPLORE § 1). The meta tags carry an empty ``citation_author``; the byline sits in the chapter's top widget (edited
volumes) or in the left rail's book byline (monographs, whose authors wrote every chapter). An editors-only left rail
credits nobody for the chapter. The left rail's abstract is the book's description, never the chapter's.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.silverchair_books import SilverchairBooks

URL = "https://read.dukeupress.edu/books/book/2542/chapter/1291617/Blur"


def _card(name, affs=(), note=None, instance="ChapterTopInfo_Chapter"):
    aff = ""
    if affs:
        aff = '<div class="info-card-affilitation">' + "".join(
            f'<div class="aff"><span class="label title-label">{chr(97 + i)}</span>{a}</div>' for i, a in enumerate(affs)
        ) + "</div>"
    bio = f'<div class="info-card-note"><p>{note}</p></div>' if note else ""
    return (f'<div class="al-author-name"><a class="linked-name js-linked-name" href="javascript:;">{name}</a>'
            f'<div class="al-author-info-wrap arrow-up"><div class="info-card-author authorInfo_{instance}">'
            f'<div class="name-role-wrap"><div class="info-card-name">{name}</div></div>{aff}{bio}'
            '<div class="info-card-search-label">Search for other works by this author on:</div></div></div>'
            '<span class="al-author-delim">; </span></div>')


def _left_rail(names, role="authors", affs=(), note=None, abstract=None):
    cards = "".join(_card(n, affs, note, instance="ChapterStandard_LeftRail_BookBasicInfo") for n in names)
    abs_html = (f'<div class="book-info__abstract"><section class="abstract"><p>{abstract}</p></section></div>'
                if abstract else "")
    return ('<div class="widget widget-BookBasicInfo widget-instance-ChapterStandard_LeftRail_BookBasicInfo">'
            '<div class="book-info__meta"><div class="book-info__title">A Book</div>'
            f'<div class="book-info__authors"><div class="al-authors-list book-info__author-list">'
            f'<div class="al-authors-list {role}"><div class="al-author-prefix">By</div>{cards}</div></div></div>'
            f'{abs_html}</div></div>')


def _chapter_top(names=(), affs=()):
    byline = ""
    if names:
        byline = ('<div class="wi-authors"><div class="al-authors-list"><div class="chapter-authors-prefix">By</div>'
                  + "".join(_card(n, affs) for n in names) + "</div></div>")
    return ('<div class="widget widget-ChapterTopInfo widget-instance-ChapterTopInfo_Chapter">'
            f'<div class="chapterTopInfo"><h1 class="chapter-title">A Chapter</h1>{byline}</div></div>')


def _chapter_text(abstract):
    return ('<div class="book-chapter-body"><div class="widget widget-BookSectionsText '
            'widget-instance-BookChaptertext_Chapter"><div class="content-section">'
            f'<section class="abstract"><p>{abstract}</p></section></div></div></div>')


def _page(body, og_url=URL, description="Bibliography. Adamowicz, Elsa. Surrealist Collage in Text and Image."):
    return ('<html><head><meta name="citation_author" content=""/><meta name="citation_title" content="A Chapter"/>'
            '<meta name="citation_doi" content="10.1215/9781478003434-002"/>'
            f'<meta property="og:url" content="{og_url}"/><meta name="description" content="{description}"/>'
            f'<script src="https://dup.silverchair-cdn.com/UI/app/js/x.js"></script></head><body>{body}</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in _parse(html)["authors"]]


CHAPTER_ABSTRACT = ("Drawing on archival work in three countries, this chapter traces how surrealist games turned "
                    "chance into a method, and what that method meant for the photographers who adopted it.")
BOOK_BLURB = ("Created by a leading practitioner, this newly revised problem-solver helps nurses and other staff "
              "advise patients. It is ideal for use on the phone and in the clinic, and it covers every common case.")


def test_chapter_byline_wins_over_the_volume_editors():
    html = _page(_left_rail(["Awanish Kumar", "Aditya Upadhyay"], role="editors")
                 + _chapter_top(["Venkteshwar Yadav", "Dharm Pal"], ["Department of Chemical Engineering, NIT Raipur, India"]))
    assert _authors(html) == [("Venkteshwar Yadav", ["Department of Chemical Engineering, NIT Raipur, India"]),
                              ("Dharm Pal", ["Department of Chemical Engineering, NIT Raipur, India"])]


def test_monograph_chapter_takes_the_book_authors_and_no_biography():
    html = _page(_left_rail(["Susan Laxton"], note="Susan Laxton is Associate Professor of Art History at the "
                                                   "University of California, Riverside.") + _chapter_top())
    assert _authors(html) == [("Susan Laxton", [])]


def test_monograph_chapter_reads_affiliation_cards():
    html = _page(_left_rail(["Thomas C. Hunt", "Monalisa Mullins"], affs=["University of Dayton, USA"]) + _chapter_top())
    assert _authors(html) == [("Thomas C. Hunt", ["University of Dayton, USA"]),
                              ("Monalisa Mullins", ["University of Dayton, USA"])]


def test_editors_only_chapter_credits_nobody():
    html = _page(_left_rail(["Joseph Masco", "Lisa Wedeen"], role="editors") + _chapter_top())
    assert _parse(html)["authors"] == []


def test_affiliation_drops_label_and_email():
    aff = ('Department of Chemistry, University of X, India <a href="/cdn-cgi/l/email-protection#37">'
           '<span class="__cf_email__">[email protected]</span></a>')
    html = _page(_chapter_top(["Dharm Pal"], [aff]))
    assert _authors(html) == [("Dharm Pal", ["Department of Chemistry, University of X, India"])]


def test_chapter_abstract_not_the_book_blurb():
    html = _page(_left_rail(["Maya Bunik"], abstract=BOOK_BLURB) + _chapter_top() + _chapter_text(CHAPTER_ABSTRACT))
    assert _parse(html)["abstract"] == CHAPTER_ABSTRACT


def test_chapter_without_its_own_abstract_gets_none():
    html = _page(_left_rail(["Maya Bunik"], abstract=BOOK_BLURB) + _chapter_top())
    assert _parse(html)["abstract"] in (None, "")


def test_book_page_reads_book_byline_and_description():
    book = ('<div class="widget widget-BookBasicInfo widget-instance-BookTocTopCenter"><div class="book-info__meta">'
            '<div class="book-info__authors"><div class="al-authors-list book-info__author-list">'
            '<div class="al-authors-list authors">'
            + _card("Alan L. Smith", ["Department of Geology, University of Puerto Rico, Mayaguez"], instance="BookTocTopCenter")
            + f'</div></div></div><div class="book-info__abstract"><section class="abstract"><p>{BOOK_BLURB}</p>'
            '</section></div></div></div><div class="widget widget-BookToc widget-instance-BookToc"></div>')
    out = _parse(_page(book))
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]] == [
        ("Alan L. Smith", ["Department of Geology, University of Puerto Rico, Mayaguez"])]
    assert out["abstract"] == BOOK_BLURB


def test_new_fields_are_empty():
    html = _page(_left_rail(["Susan Laxton"]) + _chapter_top())
    parsed = SilverchairBooks(BeautifulSoup(html, "lxml")).parse()
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None
    assert parsed["references"] is None and parsed["references_complete"] is False


def test_oxford_academic_chapters_are_left_to_the_oxford_parser():
    html = _page(_left_rail(["Susan Laxton"]) + _chapter_top(),
                 og_url="https://academic.oup.com/book/48504/chapter/421400177")
    assert not SilverchairBooks(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_article_page_is_not_claimed():
    article = ('<div class="widget widget-ArticleFulltext"><div class="wi-authors"><div class="al-authors-list">'
               + _card("Shu-Jen Kung", ["National Yang-Ming University, Taipei City, Taiwan"], instance="ArticleTopInfo")
               + '</div></div><section class="abstract"><p>Humans are able to find and tap to the beat.</p></section></div>')
    assert not SilverchairBooks(BeautifulSoup(_page(article), "lxml")).is_publisher_specific_parser()
