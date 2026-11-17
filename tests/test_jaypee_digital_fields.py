"""Jaypee Digital chapter pages (jaypeedigital.com, Jaypee Brothers, DOI prefix 10.5005), oxjob #2330.

Markup is cut down from stored chapter pages reached by DOI (10.5005/jp/books/...). The page has no citation_* meta
tags, so the generic parser reads nothing. A label/value grid in div.bookDetailsPage holds "Author" as a numbered list
("1. Surname Given", one per <br>) and "Author Affiliations" as a numbered list in the same order; an author's
affiliation is the entry with the same number, kept as one string (label-v1: the page joins variants into one entry).
The "Abstract" tab is usually empty. Nothing on the page marks a corresponding author, and it shows no
acknowledgments, funding or references.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jaypee_digital import JaypeeDigital

URL = "https://doi.org/10.5005/jp/books/12430_17"
TITLE = "<title>\nJaypeeDigital | Dissertation Writing\n</title>"
ABSTRACT = ("The pathoanatomy of the elbow joint makes posttraumatic elbow stiffness more prevalent and difficult to "
            "treat. The contracture may be extraarticular or intra-articular.")


def _row(label, value):
    return (f'<div class="col-12 col-md-3 font-weight-bold my-md-2">{label}</div>'
            f'<div class="col-12 col-md-8 my-md-2 mb-3 mb-md-2">{value}</div>')


def _numbered(items):
    return "\n<br>\n".join(f"\n\t\t{i}. \n\t\t\t{x}" for i, x in enumerate(items, 1))


def _page(authors, affs, abstract="", title=TITLE, rows=None):
    grid = rows if rows is not None else (
        _row("Author", _numbered(authors)) + _row("ISBN", "9789351526315")
        + _row("DOI", "10.5005/jp/books/12430_17") + _row("Author Affiliations", _numbered(affs))
        + _row("Chapter keywords", "Dissertation Writing, Format of Dissertation"))
    return (f'<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<link rel="icon" href="/assets/img/smallLogoJP.png"/>'
            f'\n<script src="/assets/js/x.js"></script>\n{title}\n<meta name="referrer" content="unsafe-url">\n</head>'
            f'<body><header><a href="/home">JaypeeDigital</a></header>'
            f'<div class="col-12 col-sm-8 col-md-8 col-lg-8"><div class="bookDetailsPage">'
            f'<h3 class="bookdetailHeading">Chapter-16 Dissertation Writing</h3>'
            f'<p class="py-3 text-muted">BOOK TITLE: <a href="/book/9789351526315">Basics in Epidemiology</a></p>'
            f'<div class="row">{grid}</div></div></div>'
            f'<div class="custTabbing"><ul class="tabs"><li class="active" rel="tab1"><a href="javascript:;">Abstract</a></li></ul>'
            f'<div class="tab_container"><h3 class="d_active tab_drawer_heading" rel="tab1">Abstract</h3>'
            f'<div id="tab1" class="tab_content" style="display: block;"><div class="col-md-12">\n\t\t{abstract}\n\t</div></div>'
            f'</div></div>'
            f'<div class="relatedBooksVideos"><p class="desc-text textEllipsis">Tejinder Singh, Rajiv Mahajan</p></div>'
            f'</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in _parse(html)["authors"]]


def test_authors_take_the_affiliation_with_their_number():
    html = _page(["Kazmi Waqar H", "Khan Farida Habib"],
                 ["Karachi Medical and Dental College/Abbasi Shaheed Hospital, Karachi, Pakistan",
                  "Princess Nora Bint Abdulrahman University, Riyadh, Kingdom of Saudi Arabia"])
    assert _authors(html) == [
        ("Kazmi Waqar H", ["Karachi Medical and Dental College/Abbasi Shaheed Hospital, Karachi, Pakistan"]),
        ("Khan Farida Habib", ["Princess Nora Bint Abdulrahman University, Riyadh, Kingdom of Saudi Arabia"])]


def test_an_entry_of_joined_variants_stays_one_affiliation():
    aff = ("Maulana Azad Medical College, New Delhi, India, All India Institute of Hygiene and Public Health, "
           "Kolkata; Maulana Azad Medical College, New Delhi–110002")
    assert _authors(_page(["Banerjee Bratati"], [aff])) == [("Banerjee Bratati", [aff])]


def test_author_without_an_affiliation_entry():
    html = _page(["Singh Nisha"], [])
    assert _authors(html) == [("Singh Nisha", [])]


def test_affiliation_for_a_number_that_has_no_author_is_dropped():
    html = _page(["Sharma Tarun"], ["Sankara Nethralaya, Chennai, India", "City Hospital, Birmingham, UK"])
    assert _authors(html) == [("Sharma Tarun", ["Sankara Nethralaya, Chennai, India"])]


def test_nobody_is_marked_corresponding():
    html = _page(["Jain Anil K", "Dhammi Ish K"], ["UCMS, Delhi, India", "AIIMS, Rishikesh, India"])
    assert [a["is_corresponding"] for a in _parse(html)["authors"]] == [False, False]


def test_abstract_from_the_abstract_tab():
    html = _page(["Jain Anil K"], ["UCMS, Delhi, India"], abstract=ABSTRACT)
    assert _parse(html)["abstract"] == ABSTRACT


def test_empty_abstract_tab_gives_no_abstract():
    assert _parse(_page(["Jain Anil K"], ["UCMS, Delhi, India"]))["abstract"] is None


def test_new_fields_absent():
    parsed = JaypeeDigital(BeautifulSoup(_page(["Jain Anil K"], ["UCMS, Delhi, India"]), "lxml")).parse()
    assert parsed["acknowledgments"] is None
    assert parsed["funding_statement"] is None
    assert parsed["references"] is None
    assert parsed["references_complete"] is False


def test_chapter_with_empty_author_row_is_not_read():
    page = JaypeeDigital(BeautifulSoup(_page([], []), "lxml"))
    assert page.is_publisher_specific_parser()
    assert not page.authors_found()


def test_book_page_without_author_row_is_left_to_other_parsers():
    rows = _row("ISBN", "9789352703302") + _row("Publishing Year", "2014")
    page = JaypeeDigital(BeautifulSoup(_page([], [], rows=rows), "lxml"))
    assert not page.authors_found()


def test_same_grid_on_another_site_is_not_claimed():
    html = _page(["Kazmi Waqar H"], ["Karachi Medical and Dental College, Karachi, Pakistan"],
                 title="<title>MedOnline Library | Dissertation Writing</title>")
    page = JaypeeDigital(BeautifulSoup(html, "lxml"))
    assert not page.is_publisher_specific_parser()
    assert not page.authors_found()
    assert _parse(html)["authors"] == []


def test_title_outside_head_does_not_claim():
    html = ("<html><head><meta charset='utf-8'></head><body><p><title>JaypeeDigital | x</title></p>"
            "<div class='bookDetailsPage'></div></body></html>")
    assert not JaypeeDigital(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
