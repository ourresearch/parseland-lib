"""Acta Horticulturae (actahort.org, ISHS) article pages (oxjob #2210, Parseland swarm pilot).

Markup is cut down from stored actahort.org pages (13 Nov 2026). The site has no citation meta tags, og:url or
canonical link, so no parser read it: 0 of 79 article pages gave authors or an abstract. Two page kinds share one
record table: the article record (/books/NNNN/NNNN_NN.htm) and the members login page (/members/showpdf?booknrarnr=)
that repeats the record under "After login you can download the full-text version of the following article".
The table has a bold "Authors:" (or "Author:") row, a "DOI:" row and an "Abstract:" cell; no affiliations,
corresponding marks, acknowledgments, funding or reference list (references sit behind a separate members link).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.actahort import ActaHorticulturae

URL = "https://www.actahort.org/books/1357/1357_43.htm"

NAV = ('<form method="post" action="https://www.actahort.org/members/search" name="actasearch">'
       '<a class="nav" href="https://www.actahort.org/index.htm">Acta<br>Horticulturae<br>Home</a></form>')


def _record(author_row, abstract_cell, doi="10.17660/ActaHortic.2023.1357.43", series="ISHS Acta Horticulturae 1357:"):
    return (
        f'<table width="100%" border="0"><tr><td align="left" valign="top" width="100%"><small><font color="#1C7A5F">'
        f'<b>{series}</b></font> <a href="index.htm"><b>XII International Vaccinium Symposium</b></a></small>'
        '<h2 style="margin: 6 0 6 0"><font color="#1C7A5F"><b>Water footprint and energy used per kg</b></font></h2>'
        '</td></tr></table>'
        '<table border="0" cellpadding="2" cellspacing="0" width="100%">'
        f'{author_row}'
        '<tr valign="middle" align="left"><td valign="top" align="left" width="12%"><b>Keywords:</b> &nbsp; </td>'
        '<td valign="top" align="left" width="88%">water management, water footprint</td></tr>'
        '<tr valign="middle" align="left"><td valign="top" align="left" width="12%"><b>DOI:</b> &nbsp; </td>'
        f'<td valign="top" align="left" width="88%"><a href="https://doi.org/{doi}">{doi}</a></td></tr>'
        '<tr valign="middle" align="left"><td valign="top" align="left" colspan="2"><b>Abstract:</b>\n<br>\n'
        f'{abstract_cell}</td></tr>'
        '<tr><td colspan="2"><small><ul>'
        '<li><b><a href="https://www.actahort.org/members/showpdf?booknrarnr=1357_43">Article - full text</a></b>'
        '<li><b><a href="https://www.actahort.org/members/references?booknrarnr=1357_43">References</a></b>'
        '</ul></small></td></tr></table>'
    )


def _row(label, names):
    return (f'<tr valign="middle" align="left"><td valign="top" align="left" width="12%"><b>{label}:</b> &nbsp; </td>'
            f'<td valign="top" align="left" width="88%">{names}</td></tr>')


ABSTRACT_HTML = ("<!-- Abstract start -->\nYield, water footprint and energy use for irrigation and frost protection "
                 "purposes were measured since 2010 in blueberry cultivar Snowchaser (<i>Vaccinium corymbosum</i> L.).\n"
                 "An irrigation drip system was used with drippers at 30 cm and a flow of 1.1 L h<sup>&#8209;1</sup>. "
                 "The objective of this study was to quantify the fresh fruit harvested and the water footprint.\n\n\n"
                 "<!-- Abstract end -->\n")
ABSTRACT_TEXT = ("Yield, water footprint and energy use for irrigation and frost protection purposes were measured since "
                 "2010 in blueberry cultivar Snowchaser (Vaccinium corymbosum L.). An irrigation drip system was used with "
                 "drippers at 30 cm and a flow of 1.1 L h‑1. The objective of this study was to quantify the fresh "
                 "fruit harvested and the water footprint.")


def _page(body, title="Water footprint and energy used per kg"):
    return (f'<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
            f'<title>{title}</title></head><body><table><tr><td>{NAV}</td><td valign="top">{body}</td></tr></table>'
            '</body></html>')


def _login_page(record):
    return _page('<h3 align="center"><font color="#1C7A5F">Login/Logout</font></h3>'
                 '<form method="post" action="showpdf?session=1"><input type="hidden" name="action" value="logincheck">'
                 '<input type="text" name="email"><input type="password" name="pw"></form><hr size="2" noshade>'
                 'After login you can download the full-text version of the following article:' + record,
                 title="Acta Horticulturae")


ARTICLE = _page(_record(_row("Authors", "A. Pannunzio, E.A. Holzapfel, P. Texeira Soria"), ABSTRACT_HTML))


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_record_page_authors_in_order_without_affiliations_or_marks():
    authors = _parse(ARTICLE)["authors"]
    assert [a["name"] for a in authors] == ["A. Pannunzio", "E.A. Holzapfel", "P. Texeira Soria"]
    assert all(a["affiliations"] == [] for a in authors)
    assert not any(a["is_corresponding"] for a in authors)


def test_record_page_abstract_keeps_sub_and_superscripts_inline():
    assert _parse(ARTICLE)["abstract"] == ABSTRACT_TEXT


def test_login_page_record_is_read_too():
    abstract = ("\nTolerance against stresses is species- and genotype-specific.\nScreening plants for different "
                "abiotic stresses is considered a backbone for plant breeding.\nChlorophyll fluorescence is sensitive "
                "to different types of stress and was used to screen tomato genotypes.\n\n\n\n")
    html = _login_page(_record(_row("Authors", "A. Shomali, S. Aliniaeifard, M.R. Bakhtiarizadeh"), abstract,
                               doi="10.17660/ActaHortic.2024.1391.91", series="ISHS Acta Horticulturae 1391:"))
    parsed = _parse(html)
    assert [a["name"] for a in parsed["authors"]] == ["A. Shomali", "S. Aliniaeifard", "M.R. Bakhtiarizadeh"]
    assert parsed["abstract"].startswith("Tolerance against stresses is species- and genotype-specific. Screening")


def test_single_author_row_and_entities():
    html = _page(_record(_row("Author", "J. Le&oacute;n Fuentes"), ABSTRACT_HTML))
    assert [a["name"] for a in _parse(html)["authors"]] == ["J. León Fuentes"]
    html = _page(_record(_row("Authors", "&#536;. Nanu, F.C. Fr&#259;tu&#539;u, H. Vanni&egrave;re , R. Tournebize "),
                         ABSTRACT_HTML))
    assert [a["name"] for a in _parse(html)["authors"]] == ["Ș. Nanu", "F.C. Frătuțu",
                                                            "H. Vannière", "R. Tournebize"]


def test_page_without_the_record_is_not_read():
    # the bare login form (no article under it) and the bot wall
    parser = ActaHorticulturae(BeautifulSoup(_page(NAV + '<h3>Login/Logout</h3><form><input name="pw"></form>'), "lxml"))
    assert not parser.authors_found()


def test_new_fields_are_not_claimed():
    # the page links to a members-only references page; it shows no reference list, acknowledgments or funding
    parsed = ActaHorticulturae(BeautifulSoup(ARTICLE, "lxml")).parse()
    for key in ("references", "references_complete", "acknowledgments", "funding_statement"):
        assert key not in parsed


def test_other_site_with_a_similar_record_table_is_not_claimed():
    # same table shape and an Acta Horticulturae DOI cited, but another site: no ISHS series line, no actahort.org links
    body = ('<table><tr><td><b>Authors:</b></td><td>A. Author, B. Author</td></tr>'
            '<tr><td><b>DOI:</b></td><td><a href="https://doi.org/10.17660/ActaHortic.2023.1357.43">x</a></td></tr>'
            '<tr><td colspan="2"><b>Abstract:</b><br>' + ABSTRACT_TEXT + '</td></tr></table>')
    html = f"<html><head><title>Other repository</title></head><body>{body}</body></html>"
    parser = ActaHorticulturae(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["authors"] == []
