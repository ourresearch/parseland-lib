"""Corresponding authors on A&V Publications article pages (rjptonline.org and its sister journals; oxjob #2339).

Markup is cut down from stored rjptonline.org pages (17 Nov 2026). The pages carry citation_* meta tags, which the
generic parser reads; the corresponding author is marked only in the "Address:" block, whose first line is the
byline with affiliation numbers glued to each name as plain text and a star on the corresponding author
("Kavitha A N1*, Monica C2"), explained by the block's last line ("*Corresponding Author").
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rjptonline import RJPTOnline

URL = "https://rjptonline.org/AbstractView.aspx?PID=2026-19-10-13"
ABSTRACT = ("Adoption of Novel Drug Delivery System approaches to make therapeutically viable formulation of BCS class "
            "2 and 4 is the most followed approach. In this work the drug is formulated as a SMEDDS formulation in a "
            "lean QbD approach and it was characterized by conventional in-vitro methods further augmented by in "
            "silico approaches as well.")


def _page(names, address, doi="10.52711/0974-360X.2026.00637",
          abstract_url="https://rjptonline.org/AbstractView.aspx?PID=2026-19-10-13"):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in names)
    return (
        "<html><head><title>RJPT - A title</title>"
        f'<meta name="Description" content="{ABSTRACT}" />'
        '<meta name="citation_title" content="A title" />'
        f"{metas}"
        '<meta name="citation_journal_title" content="Research Journal of Pharmacy and Technology" />'
        f'<meta name="citation_abstract_html_url" content="{abstract_url}" />'
        '<meta name="citation_publisher" content="Research Journal of Pharmacy and Technology" />'
        f'<meta name="citation_doi" content="{doi}" /></head><body><form method="post">'
        '<p><span style="color: red">Author(s):</span> <span id="ContentPlaceHolder1_AuthorName">'
        + ",  ".join(f"<a href='search.aspx?key={n}' >{n}</a>" for n in names)
        + "</span></p>"
        '<p><span style="color: red">Address:</span> '
        f'<span id="ContentPlaceHolder1_AuthorAddress">{address}</span></p>'
        '<p><span style="color: black; font-weight: bold">ABSTRACT:</span> <br />'
        f'<span id="ContentPlaceHolder1_Abstract" style="color:Black;">{ABSTRACT}</span></p>'
        "</form></body></html>")


def _parsed(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _parsed(html)["authors"] if a["is_corresponding"]]


TWO = ["Kavitha A N", "Monica C"]
TWO_ADDRESS = ("Kavitha A N1*, Monica C2<br>\n1Professor, Department of Quality Assurance, Krupanidhi College of "
               "Pharmacy, Bengaluru, Karnataka, India.<br>\n2Department of Quality Assurance, Krupanidhi College of "
               "Pharmacy, Bengaluru - 560035, Karnataka, India.<br>\n*Corresponding Author")


def test_star_after_glued_affiliation_number_marks_the_author():
    out = _parsed(_page(TWO, TWO_ADDRESS))
    assert [(a["name"], a["is_corresponding"]) for a in out["authors"]] == [("Kavitha A N", True), ("Monica C", False)]


def test_star_after_several_affiliation_numbers():
    names = ["Sarika B. Narade", "Yogesh V. Pore"]
    address = ("Sarika B. Narade1,2*, Yogesh V. Pore3<br>1Department of Pharmaceutical Chemistry, Karad.<br>"
               "2Department of Pharmaceutical Chemistry, Sangli.<br>3Department of Pharmaceutics, Kolhapur.<br>"
               "*Corresponding Author")
    assert _corr(_page(names, address)) == ["Sarika B. Narade"]


def test_star_on_the_last_author():
    names = ["Manan Grover", "Mansi Sharma", "Raman Chawla", "Navneet Sharma"]
    address = ("Manan Grover1, Mansi Sharma1, Raman Chawla2, Navneet Sharma1*<br>1Amity Institute of Pharmacy, Noida."
               "<br>2Institute of Nuclear Medicine and Allied Sciences, Delhi.<br>*Corresponding Author")
    assert _corr(_page(names, address)) == ["Navneet Sharma"]


def test_star_marks_the_name_spelled_the_same_before_a_look_alike():
    names = ["A. Anka Rao", "K. Pavan Kumar", "A. Narayana Rao"]
    address = ("A. Anka Rao1*, K. Pavan Kumar2,  A. Narayana Rao1<br>1KL College of Pharmacy, Guntur.<br>"
               "2Department of Pharmaceutics, Hyderabad.<br>*Corresponding Author")
    assert _corr(_page(names, address)) == ["A. Anka Rao"]


def test_no_star_in_the_byline_marks_no_one():
    names = ["Mythri Padaru", "Raksha Bhat", "Preethesh Shetty"]
    address = ("Mythri Padaru, Raksha Bhat, Preethesh Shetty<br>Nitte (Deemed to be University), Mangaluru, India."
               "<br>*Corresponding Author")
    assert _corr(_page(names, address)) == []


def test_star_without_its_legend_is_not_a_mark():
    names = ["Kavitha A N", "Monica C"]
    address = "Kavitha A N1*, Monica C2<br>1Krupanidhi College of Pharmacy.<br>2Krupanidhi College of Pharmacy."
    assert _corr(_page(names, address)) == []


def test_single_author_page_keeps_its_mark():
    address = "Sushil M R<br>\nAssociate Professor, Vindhya College of Nursing, Satna.<br>\n*Corresponding Author"
    assert _corr(_page(["Sushil M R"], address)) == ["Sushil M R"]


def test_authors_and_abstract_are_the_meta_tags():
    out = _parsed(_page(TWO, TWO_ADDRESS))
    assert [a["name"] for a in out["authors"]] == TWO
    assert all(a["affiliations"] == [] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_sister_journal_is_claimed():
    html = _page(TWO, TWO_ADDRESS, doi="10.52711/2321-5763.2022.00022",
                 abstract_url="https://ajmjournal.com/AbstractView.aspx?PID=2022-13-2-4")
    parser = RJPTOnline(BeautifulSoup(html, "lxml"))
    assert parser.is_publisher_specific_parser() and parser.authors_found()


def test_other_aspnet_site_is_not_claimed():
    # Same ASP.NET address block and abstract-page URL, another publisher's DOI prefix.
    html = _page(TWO, TWO_ADDRESS, doi="10.5958/2231-5713.2020.00001.2",
                 abstract_url="https://example-journal.in/AbstractView.aspx?PID=2020-10-1-1")
    parser = RJPTOnline(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_without_abstract_page_url_is_not_claimed():
    html = _page(TWO, TWO_ADDRESS, abstract_url="https://rjptonline.org/HTMLPaper.aspx?Journal=x;PID=2026-19-10-13")
    parser = RJPTOnline(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()
