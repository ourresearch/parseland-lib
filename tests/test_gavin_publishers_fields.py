"""Gavin Publishers article pages (gavinpublishers.com; oxjob #2339).

Markup cut down from stored pages (17 Nov 2026). Before this parser the generic meta-tag reader won these pages: no
affiliations (the site writes no institution tags), and on the older template one citation_author tag holding every
name ("A, B, C"). The parser reads the printed author block, its "Corresponding author" note, and the bold
"Acknowledgements" / "Funding" labels in the body.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.gavin_publishers import GavinPublishers

URL = "https://www.gavinpublishers.com/article/view/a-title"
PUBLISHER = '<meta name="citation_publisher" content="Gavin Publishers" />'


def _page(head_metas, body, publisher=PUBLISHER):
    return (f'<html><head><meta name="citation_title" content="A title">{head_metas}{publisher}</head>'
            f"<body><article>{body}</article></body></html>")


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


CURRENT = _page(
    '<meta name="citation_author" content="Michael Dasa"><meta name="citation_author" content="Mohammud Kurrimboccus">',
    '<h2 class="citation_title">A title</h2><div><div id="content">'
    '<h3 class="citation_author">by Michael Dasa<sup>1*</sup>, Mohammud Kurrimboccus<sup>2</sup></h3>'
    '<p><sup>1</sup>Department of Surgery, The Royal Oldham Hospital, Oldham, UK</p>'
    '<p><sup>2</sup>Department of Surgery, Salford Royal Hospital, Salford, UK</p>'
    '<p><strong>*C</strong><strong>orresponding author:</strong> Michael Dasa, Department of Surgery, Oldham, UK</p>'
    '</div><div id="border"><p id="received"><strong>Received Date:</strong> 15 May, 2024</p></div></div>'
    '<div class="abstract"><h4>Abstract</h4><p>' + "An abstract sentence about the study. " * 8 + "</p></div>"
    '<div class="content"><p><strong>Acknowledgements:</strong> We thank the clinic staff.</p>'
    '<p><strong>Funding Statement</strong></p><p>The study was funded by the Example Trust (grant 12).</p>'
    '<p><strong>Authors’ Contributions</strong></p><p>All authors wrote it.</p>'
    "<h4>References</h4><ol><li>Smith A (2020) A paper.</li></ol></div>")

OLDER = _page(
    '<meta name="citation_author" content="Anderson Galvao, Vandack Nobre, Lopes Felipe">',
    '<h1 class="citation_title">A title</h1><div class="col-md-12"><div>'
    "<h3><strong>Anderson Galv</strong><strong>a</strong><strong>o</strong><strong><sup>1*</sup></strong>"
    "<strong>, Vandack Nobre</strong><strong><sup>1</sup></strong><strong>,</strong> "
    "<strong>Lopes Felipe</strong><strong><sup>2</sup></strong></h3>"
    "<p><sup>1</sup>Department of Urology, Federal University of Minas Gerais, Belo Horizonte, Brazil</p>"
    "<p><sup>2</sup>Biocor Institute Nova Lima, Minas Gerais, Brazil</p>"
    "<p><strong><sup>*</sup></strong><strong>Corresponding author: </strong>Anderson Galvao, Department of Urology</p>"
    '<div id="border"><p id="a"><strong>Received Date: </strong>07 November, 2022</p></div></div></div>')


def test_current_template_affiliations_by_number():
    authors = _authors(CURRENT)
    assert [a["name"] for a in authors] == ["Michael Dasa", "Mohammud Kurrimboccus"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Department of Surgery, The Royal Oldham Hospital, Oldham, UK"],
        ["Department of Surgery, Salford Royal Hospital, Salford, UK"]]


def test_star_explained_by_note_is_corresponding():
    assert [a["is_corresponding"] for a in _authors(CURRENT)] == [True, False]


def test_older_template_splits_the_one_meta_tag_into_the_byline():
    authors = _authors(OLDER)
    assert [a["name"] for a in authors] == ["Anderson Galvao", "Vandack Nobre", "Lopes Felipe"]
    assert [len(a["affiliations"]) for a in authors] == [1, 1, 1]
    assert authors[2]["affiliations"][0]["name"] == "Biocor Institute Nova Lima, Minas Gerais, Brazil"
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_unnumbered_affiliation_goes_to_every_author():
    html = CURRENT.replace("by Michael Dasa<sup>1*</sup>, Mohammud Kurrimboccus<sup>2</sup>",
                           "by Michael Dasa<sup>*</sup>, Mohammud Kurrimboccus") \
        .replace("<p><sup>1</sup>Department of Surgery, The Royal Oldham Hospital, Oldham, UK</p>"
                 "<p><sup>2</sup>Department of Surgery, Salford Royal Hospital, Salford, UK</p>",
                 "<p>Oncology department, ABC Medical Center, Mexico City, Mexico.</p>")
    authors = _authors(html)
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Oncology department, ABC Medical Center, Mexico City, Mexico."]] * 2


def test_no_star_note_names_the_corresponding_author():
    html = CURRENT.replace("<sup>1*</sup>", "<sup>1</sup>").replace(
        "Michael Dasa, Department of Surgery, Oldham", "Mohammud Kurrimboccus, Department of Surgery, Salford")
    assert [a["is_corresponding"] for a in _authors(html)] == [False, True]


def test_star_without_a_note_is_not_a_mark():
    html = CURRENT.replace(
        '<p><strong>*C</strong><strong>orresponding author:</strong> Michael Dasa, Department of Surgery, Oldham, UK</p>',
        "")
    assert not any(a["is_corresponding"] for a in _authors(html))


def test_star_after_the_sup_and_ranges():
    html = CURRENT.replace("by Michael Dasa<sup>1*</sup>, Mohammud Kurrimboccus<sup>2</sup>",
                           "by Michael Dasa<sup>1-2</sup>*, Mohammud Kurrimboccus<sup>2</sup>")
    authors = _authors(html)
    assert authors[0]["is_corresponding"] and len(authors[0]["affiliations"]) == 2


def test_acknowledgments_and_funding():
    parsed = GavinPublishers(BeautifulSoup(CURRENT, "lxml")).parse()
    assert parsed["acknowledgments"] == "We thank the clinic staff."
    assert parsed["funding_statement"] == "The study was funded by the Example Trust (grant 12)."


def test_no_sections_no_keys():
    parsed = GavinPublishers(BeautifulSoup(OLDER, "lxml")).parse()
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None


def test_abstract_is_still_read():
    assert parse_page(CURRENT.encode(), "doi", URL)["abstract"].startswith("An abstract sentence")


def test_lookalike_page_from_another_publisher_is_not_claimed():
    other = CURRENT.replace(PUBLISHER, '<meta name="citation_publisher" content="Gavin Journals Press" />')
    parser = GavinPublishers(BeautifulSoup(other, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    assert not any(a["affiliations"] for a in _authors(other))


def test_title_in_byline_falls_back_to_meta_tags():
    html = OLDER.replace("<h3><strong>Anderson", "<h3><strong>Bacterial Superinfections of the Skin after Minor "
                         "Surgical Procedures </strong><strong>Anderson")
    assert not GavinPublishers(BeautifulSoup(html, "lxml")).authors_found()
