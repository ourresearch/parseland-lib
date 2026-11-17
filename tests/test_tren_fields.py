"""TREN e-docs record pages (Theological Research Exchange Network, tren.com; DOI prefix 10.2986) (oxjob #2339).

Every 10.2986 DOI resolves to a TREN search page showing the one matching thesis record: a label/value table with
School, Author (as "FAMILY, Given"), degree and year, Pages and TREN Id. No meta tags name the author, so the generic
parser reads nothing. The label-v1 labels take the School row as the sole author's affiliation. Markup is cut down
from stored pages (17 Nov 2026).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.tren import TREN

URL = "https://doi.org/10.2986/tren.088-0090"
HEAD = ('<head><title>Theological Research Exchange Network : e-docs</title>'
        '<meta property="og:title" content="Theological Research Exchange Network (TREN) - e-docs" />'
        '<meta property="og:type" content="website" />'
        '<meta property="og:site_name" content="TREN.com" /></head>')


def _row(label, value):
    return (f'<tr> <td align="right" valign="top" nowrap><font face="Verdana, Arial, Helvetica" size="1">{label}</font></td>'
            '<td align="left" valign="top" nowrap><img src="/images/blank.gif" height="1" width="10"></td>'
            f'<td align="left" valign="top"><font face="Verdana, Arial, Helvetica" size="1">{value}</font></td></tr>')


def _author(name):
    href = "search.cfm?oid=x&exact=TRUE&author=" + name.replace(",", "%2C").replace(" ", "%20") + "&action=query"
    return f'<a href="{href}">{name}</a>'


DEGREE = ' &nbsp; &nbsp; <a href="search.cfm?oid=x&degreeid=Psy%2ED%2E&action=query">Psy.D.</a> ' \
         '<a href="search.cfm?oid=x&degreeyear=2004&action=query">2004</a>'


def _record(rows, tren_id="088-0090"):
    rows = rows + [_row("Pages:", "65"), _row("TREN Id:", tren_id)]
    return ('<table border="0" cellspacing="0" cellpadding="8" width="100%"><tr><td align="left" valign="top" width="100%">'
            '<font face="Verdana, Arial, Helvetica" size="2"><b><a href="search.cfm?oid=x&action=query&title=Church">'
            '<font color="#AA0000">Church</font></a></b></font><br><table border="0" cellspacing="0" cellpadding="1">'
            + "".join(rows) + '</table><form method="post" action="order.cfm" name="thisform"></form></td></tr></table>')


def _page(records, head=HEAD, n=None):
    n = len(records) if n is None else n
    return (f'<html>{head}<body><p><font face="Verdana, Arial, Helvetica" size="2">There were {n} items matching\n'
            f'your search criteria.</font></p>{"".join(records)}</body></html>')


ONE = _page([_record([
    _row("School:", '<a href="search.cfm?oid=x&schoolid=088&action=query">Wheaton College Graduate School</a>'),
    _row("Author:", _author("SUMMERS, Christopher A.") + DEGREE)])])


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_author_and_school_are_read():
    out = _parse(ONE)
    assert [a["name"] for a in out["authors"]] == ["Christopher A. SUMMERS"]
    assert out["authors"][0]["affiliations"] == [{"name": "Wheaton College Graduate School"}]
    assert out["authors"][0]["is_corresponding"] is False
    assert out["abstract"] is None


def test_degree_and_year_links_are_not_authors():
    names = [a["name"] for a in _parse(ONE)["authors"]]
    assert "Psy.D." not in names and "2004" not in names and len(names) == 1


def test_mixed_case_family_name_is_reordered():
    html = ONE.replace("SUMMERS, Christopher A.", "Lai, Calvin K.")
    assert [a["name"] for a in _parse(html)["authors"]] == ["Calvin K. Lai"]


def test_record_without_school_has_no_affiliation():
    html = _page([_record([_row("Author:", _author("SPARKS, Glenn R.") + DEGREE)])])
    out = _parse(html)
    assert [a["name"] for a in out["authors"]] == ["Glenn R. SPARKS"]
    assert out["authors"][0]["affiliations"] == []


def test_parse_returns_no_back_matter():
    out = TREN(BeautifulSoup(ONE, "lxml")).parse()
    assert out.get("references") is None and out.get("acknowledgments") is None
    assert out.get("funding_statement") is None


def test_results_list_with_several_records_is_not_claimed():
    rec = _record([
        _row("School:", '<a href="search.cfm?oid=x&schoolid=030&action=query">Covenant Theological Seminary</a>'),
        _row("Author:", _author("SPARKS, Glenn R.") + DEGREE)])
    html = _page([rec, rec.replace("088-0090", "030-0166"), rec.replace("088-0090", "030-0167")])
    parser = TREN(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()
    assert _parse(html)["authors"] == []


def test_error_shell_is_not_claimed():
    html = "<html><body>The service is unavailable.</body></html>"
    parser = TREN(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    assert _parse(html)["authors"] == []


def test_lookalike_label_table_from_another_site_is_not_claimed():
    # Another catalogue's record page with the same School/Author label table, but not TREN's head.
    head = ('<head><title>Seminary Thesis Catalogue</title>'
            '<meta property="og:site_name" content="Example Library" /></head>')
    html = ONE.replace(HEAD, head)
    parser = TREN(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert all(a["name"] != "Christopher A. SUMMERS" for a in _parse(html)["authors"])
