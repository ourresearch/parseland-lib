"""BiblioVault book records (www.bibliovault.org, University of Chicago Press DOIs 10.7208/chicago/...), oxjob #2339.

Markup is cut down from stored BiblioVault pages (17 Nov 2026). A book's DOI and each of its chapters' DOIs resolve to
the same book record, which shows the book's description under "ABOUT THIS BOOK" and, for books whose chapters have
DOIs, each chapter's DOI and abstract in the table of contents. The labels (label-v1) take the description as a book's
abstract; it is never a chapter's (dev gold). The page alone cannot say which DOI was asked for, so the description is
read only on a record that lists no chapter DOIs: there the page can only be the book's own.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.bibliovault import BiblioVault

URL = "https://doi.org/10.7208/chicago/9780226377308.001.0001"

HEAD = ('<head><title>The Mirror of the Self</title>'
        '<meta name="keywords" content="BiblioVault,bibliovault,digital book repository"/>'
        '<meta property="book:title" content="The Mirror of the Self"/>'
        '<meta property="book:author" content="Shadi Bartsch"/>'
        '<meta property="book:description" content=""/>'
        '<link href="css/BV.landing.css" rel="stylesheet" type="text/css"/>'
        '<link rel="unapi-server" type="application/xml" title="unAPI" '
        'href="https://www.bibliovault.org/cgi-bin/unAPI.cgi"/></head>')

BOOKINFO = ('<div class="bookinfo"><span class="booktitle">The Mirror of the Self</span>'
            '<span class="booksubtitle"> Sexuality, Self-Knowledge, and the Gaze</span>'
            '<div class="bookauthor">by Shadi Bartsch</div>'
            '<div>University of Chicago Press, 2006<br/><b>Cloth</b>: <span class="isbn">978-0-226-03835-3</span>'
            '<br/><b>DOI:</b> 10.7208/chicago/9780226377308.001.0001</div></div>')

P1 = ("People in the ancient world thought of vision as both an ethical tool and a tactile sense, akin to touch. "
      "Gazing at oneself in the mirror was a way to know oneself.")
P2 = ("Weaving together literary theory, philosophy, and social history, Bartsch traces this complex notion of self "
      "from Plato to the Roman Stoics.")
DESCRIPTION = (f'<div class="box" id="mkcopy"><h3>ABOUT THIS BOOK</h3><div>{P1}<br/>\n<br/>\n'
               f'Weaving together literary theory, philosophy, and <i>social</i> history, Bartsch traces this complex '
               f'notion of self from Plato to the Roman Stoics.</div></div>')
BIO = ('<div class="box" id="authbio"><h3>AUTHOR BIOGRAPHY</h3>Shadi Bartsch is professor of classics at the '
       'University of Chicago.</div>')
TOC_PLAIN = ('<div class="box" id="toc"><h3>TABLE OF CONTENTS</h3><p><strong>Acknowledgments</strong></p>'
             '<p><strong>1. The Mirror of Philosophy</strong></p></div>')
TOC_CHAPTER_DOIS = (
    '<div class="box" id="toc"><h3>TABLE OF CONTENTS</h3><p><strong>Introduction</strong></p>'
    '<p style="padding-left:10px;"><strong><a href="#" class="expandable" id="ch9780226377308002">The Almanac</a>'
    '</strong> - Shadi Bartsch<br/><span class="expand_more">DOI: 10.7208/chicago/9780226377308.003.0002<br/>'
    '[<em>almanac, diary</em>]<br/>This chapter discusses how the almanac served as a diary. (pages 1 - 20)'
    '</span></p></div>')


def _page(description=DESCRIPTION, toc=TOC_PLAIN, head=HEAD):
    return (f'<!doctype html><html>{head}<body><div id="main"><div class="content">{BOOKINFO}'
            f'{description}{BIO}{toc}</div></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _own(html):
    return BiblioVault(BeautifulSoup(html, "lxml"))


def test_book_record_description_is_the_abstract():
    assert _parse(_page())["abstract"] == f"{P1}\n{P2}"


def test_heading_and_biography_are_left_out():
    abstract = _parse(_page())["abstract"]
    assert "ABOUT THIS BOOK" not in abstract
    assert "professor of classics" not in abstract


def test_review_quotes_after_the_description_are_left_out():
    reviews = ('<br/>\n<br/>\n"<i>Forests</i> is one of the most remarkable essays on the human place in nature I '
               'have ever read.—William Cronon, <i>Yale Review</i><br/>\n<br/>\n'
               '“A work of scholarship, and one of immense value.”—John Haines, <i>The New York Times Book Review</i>')
    description = DESCRIPTION.replace("Roman Stoics.</div>", "Roman Stoics." + reviews + "</div>")
    assert _parse(_page(description=description))["abstract"] == f"{P1}\n{P2}"


def test_a_paragraph_opening_with_a_quotation_is_kept():
    quoted = ("“Sincerely held religious belief” is now a common phrase in discussions of American religious "
              "freedom, from opinions of the Supreme Court to local controversies.")
    description = DESCRIPTION.replace("Roman Stoics.</div>", "Roman Stoics.<br/>\n<br/>\n" + quoted + "</div>")
    assert _parse(_page(description=description))["abstract"] == f"{P1}\n{P2}\n{quoted}"


def test_no_abstract_when_the_record_lists_chapter_dois():
    # a chapter's DOI resolves to this same record: the book's description is not the chapter's abstract
    out = _parse(_page(toc=TOC_CHAPTER_DOIS))
    assert not out["abstract"]
    assert out["authors"] == []
    assert not _own(_page(toc=TOC_CHAPTER_DOIS)).authors_found()


def test_no_authors_are_read():
    # the book's byline is not shipped: every sampled book's work already has its authors
    assert _parse(_page())["authors"] == []


def test_new_fields_are_empty():
    out = _own(_page()).parse()
    assert out["acknowledgments"] is None
    assert out["funding_statement"] is None
    assert out["references"] is None
    assert out["references_complete"] is False


def test_claims_bibliovault_records():
    parser = _own(_page())
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_record_without_a_description_is_not_read():
    assert not _own(_page(description="")).authors_found()


def test_look_alike_page_from_another_site_is_not_claimed():
    # another press's book page with the same Open Graph book tags and an "About this book" box, no BiblioVault marks
    other_head = ('<head><title>A Book</title><meta property="book:title" content="A Book"/>'
                  '<meta property="book:author" content="Jane Doe"/>'
                  '<link rel="unapi-server" type="application/xml" href="https://press.example.org/unapi"/>'
                  '<link href="css/landing.css" rel="stylesheet" type="text/css"/></head>')
    parser = _own(_page(head=other_head))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_without_a_head_is_not_claimed():
    parser = _own("<p>ABOUT THIS BOOK</p>")
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
