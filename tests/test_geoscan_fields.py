"""Bylines on Natural Resources Canada GEOSCAN record pages (DOI prefix 10.4095; oxjob #2338).

Markup is cut down from stored GEOSCAN "Fastlink" pages (geoscan.nrcan.gc.ca starweb): every record is one
<table class="table"> of <th>label</th><td>value</td> rows, the byline in the "Author" row as "Family, Initials"
names split by semicolons, corporate authors as they are, ORCID icons after a name, editors marked "(ed.)". No parser
read that row, so these reports had no authors; the abstract row was already read by the generic heading reader and
must stay as it was.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.geoscan import Geoscan

URL = "https://doi.org/10.4095/222278"
HEAD = ('<head><script type="text/javascript" src="jquery.js"></script>\n\t</meta\n>\n'
        '<title>GEOSCAN Search Results: Fastlink</title\n>'
        '<meta content="GEOSCAN Search Results: Fastlink" name="dcterms.title"></meta>'
        '<meta content="GEOSCAN supports the mission of Natural Resources Canada through the timely access to '
        'information." name="description"></meta></head>')


def _page(rows, head=HEAD):
    cells = "".join(f'<tr align=left valign=top> <th>{k}</th><td>{v}</td></tr>\n' for k, v in rows)
    return (f'<!DOCTYPE html><html lang="en">{head}<body><main class="container" role="main">'
            f'<h1 id="wb-cont" property="name">GEOSCAN Search Results: Fastlink</h1><br><table class="table">{cells}'
            f'</table></main></body></html>')


def _record(author, extra=()):
    return [("Title", "First vertical derivative of the magnetic field, Wuskwatim Lake aeromagnetic survey"),
            ("Licence", 'Please note the adoption of the <a href="https://open.canada.ca/en/open-government-licence-'
                        'canada">Open Government Licence - Canada</a> supersedes any previous licences.'),
            ("Author", author),
            ("Source", 'Geological Survey of Canada, Open File 5137, 2006, 1 sheet, '
                       '<a href="https://doi.org/10.4095/222278">https://doi.org/10.4095/222278</A>'),
            *extra,
            ("Publisher", "Natural Resources Canada"), ("GEOSCAN ID", "222278")]


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _names(html):
    return [a["name"] for a in _authors(html)]


def test_people_and_a_corporate_author_in_byline_order():
    authors = _authors(_page(_record("Coyle, M; Kiss, F; Goldak Airborne Surveys")))
    assert [a["name"] for a in authors] == ["M Coyle", "F Kiss", "Goldak Airborne Surveys"]
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in authors)


def test_a_corporate_author_alone():
    assert _names(_page(_record("Canada Centre for Mapping and Earth Observation"))) == [
        "Canada Centre for Mapping and Earth Observation"]


def test_a_corporate_author_with_a_comma_is_not_turned_round():
    assert _names(_page(_record("Canada Bureau of Geology and Topography, Topographical Survey"))) == [
        "Canada Bureau of Geology and Topography, Topographical Survey"]


def test_orcid_icons_and_line_breaks_are_not_names():
    orcid = ('<a target=" blank" href="https://orcid.org/0000-0001-8944-1432"><img alt="ORCID logo" '
             'src="https://info.orcid.org/wp-content/uploads/2019/11/orcid_16x16.png" width="16" height="16" /></a>')
    assert _names(_page(_record(f"McClenaghan, M B{orcid};\nMcCurdy, M W{orcid}; Farrell, R -E"))) == [
        "M B McClenaghan", "M W McCurdy", "R-E Farrell"]


def test_editors_only_when_nobody_else_is_credited():
    assert _names(_page(_record("Wright, D F (ed.); Lemkow, D (ed.); Harris, J R (ed.)"))) == [
        "D F Wright", "D Lemkow", "J R Harris"]
    assert _names(_page(_record("Poulsen, K H; Eckstrand, O R (ed.)"))) == ["K H Poulsen"]


def test_abstract_row_is_still_read_as_before():
    text = ("A new type of sprayed concrete using coarse-grained aggregates and cement, with special additives to "
            "accelerate the hardening of the concrete, has been developed in Europe. Known as shotcrete, it has found "
            "increasing application as a means of ground support for underground excavations in Europe and North "
            "America. Its use in Canadian underground mines has been largely experimental.")
    out = parse_page(_page(_record("Verity, T W", [("Abstract", text)])).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["T W Verity"]
    assert out["abstract"] and out["abstract"].startswith("A new type of sprayed concrete")


def test_new_fields_are_empty():
    soup = BeautifulSoup(_page(_record("Norris, D K")), parser="lxml", features="lxml")
    parsed = Geoscan(soup).parse()
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None
    assert parsed["references"] is None and parsed["references_complete"] is False


def test_record_without_an_author_row_is_not_read():
    soup = BeautifulSoup(_page([("Title", "Geophysical series"), ("GEOSCAN ID", "116107")]),
                         parser="lxml", features="lxml")
    assert not Geoscan(soup).authors_found()


def test_a_look_alike_label_value_table_elsewhere_is_not_claimed():
    # STAR web, the same catalogue software, serves other libraries' records with the same label/value rows
    head = '<head><title>Library Search Results: Full record</title></head>'
    soup = BeautifulSoup(_page(_record("Smith, J; Jones, K"), head=head), parser="lxml", features="lxml")
    parser = Geoscan(soup)
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    error = '<head><title>STAR Web Error Detected</title></head>'
    assert not Geoscan(BeautifulSoup(_page([], head=error), parser="lxml", features="lxml")).authors_found()
