"""AERA Online Paper Repository pages (aera.net, DOI prefix 10.3102), oxjob #2210.

Markup is cut down from stored pages of the repository viewer (a DNN site): one RadGrid table of "label:" / value rows.
The page has no citation_* meta tags, so the generic parser reads nothing. "Author(s):" holds
"Name, Affiliation; Name, Affiliation" (an affiliation may itself hold commas); "Abstract:" holds the abstract. The
"Owner Email:" row is not a corresponding-author mark (label-v1: nothing on the page calls anyone corresponding).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.aera import AERA

URL = "https://www.aera.net/Publications/Online-Paper-Repository/AERA-Online-Paper-Repository-Viewer/ID/2196328"
TITLE = "<title>AERA Online Paper Repository Viewer</title>"
ABSTRACT = ("Video analysis can support the development of more effective teaching practice through refining "
            "professional noticing. This qualitative case study analyzes the links between noticing and equity.")


def _row(i, label, value):
    cls = "rgRow" if i % 2 == 0 else "rgAltRow"
    return (f'<tr class="{cls}" id="dnn_ctr49536_ViewRepository_ctl00_rgDetails_ctl00__{i}">'
            f'<td valign="top">{label}</td><td valign="top">'
            f'<span id="dnn_ctr49536_ViewRepository_ctl00_rgDetails_ctl00_ctl{i:02d}_lblMetaData">{value}</span></td></tr>')


def _page(authors, abstract=ABSTRACT, title=TITLE):
    rows = [("Owner:", "Anna Arias"),
            ("Owner Email:", "<a href='mailto:aarias@example.edu' target='_blank'>aarias@example.edu</a>"),
            ("Paper Title:", "Using Video Analysis to Support Noticing"),
            ("Session Title:", "Science Teacher Learning"),
            ("Author(s):", authors),
            ("Unit:", "SIG-Science Teaching and Learning"),
            ("Abstract:", abstract),
            ("DOI:", "<a href='https://doi.org/10.3102/2196328'>https://doi.org/10.3102/2196328</a>")]
    body = "".join(_row(i, k, v) for i, (k, v) in enumerate(rows))
    return (f"<html><head>{title}<meta name=\"DESCRIPTION\" content=\"AERA Online Paper Repository Viewer\"/></head>"
            f"<body><div id=\"dnn_ctr49536_ViewRepository_ctl00_rgDetails\" class=\"RadGrid RadGrid_NOAH\">"
            f"<table class=\"rgMasterTable\" id=\"dnn_ctr49536_ViewRepository_ctl00_rgDetails_ctl00\">"
            f"<thead><tr><th>Information</th><th>Contents</th></tr></thead><tbody>{body}</tbody></table></div>"
            f"<a href=\"//www.aera.net/Membership\">AERA Membership</a></body></html>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in _parse(html)["authors"]]


def test_authors_and_affiliations_split_on_first_comma():
    html = _page("Anna Arias, Kennesaw State University; Jessica Riccio, Teachers College, Columbia University")
    assert _authors(html) == [("Anna Arias", ["Kennesaw State University"]),
                              ("Jessica Riccio", ["Teachers College, Columbia University"])]


def test_author_without_affiliation():
    html = _page("Haya Shamir, Waterford Institute; Erik Yoder")
    assert _authors(html) == [("Haya Shamir", ["Waterford Institute"]), ("Erik Yoder", [])]


def test_abstract_from_abstract_row():
    assert _parse(_page("Anna Arias, Kennesaw State University"))["abstract"] == ABSTRACT


def test_owner_email_is_not_a_corresponding_mark():
    html = _page("Anna Arias, Kennesaw State University; Michelle Forsythe, Texas State University")
    assert [a["is_corresponding"] for a in _parse(html)["authors"]] == [False, False]


def test_new_fields_absent():
    parsed = AERA(BeautifulSoup(_page("Anna Arias, Kennesaw State University"), "lxml")).parse()
    assert parsed["acknowledgments"] is None
    assert parsed["funding_statement"] is None
    assert parsed["references"] is None
    assert parsed["references_complete"] is False


def test_other_dnn_site_with_same_grid_is_not_claimed():
    html = _page("Anna Arias, Kennesaw State University", title="<title>Conference Paper Viewer</title>")
    parser = AERA(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["abstract"] != ABSTRACT
