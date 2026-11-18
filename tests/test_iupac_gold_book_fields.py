"""IUPAC Gold Book term pages (goldbook.iupac.org, DOIs 10.1351/goldbook.*) (oxjob #2338).

Markup is cut down from stored iupac.org pages (17 Nov 2026). The 3.0.1 term pages (2019 site, stored since the
backfill) credit the Compendium's corporate author in the term card's "Cite as: IUPAC. Compendium of Chemical
Terminology ..."; the page's author meta tag spells it out. The 5.0.0 term pages name IUPAC only as the publisher
("... 5th ed. International Union of Pure and Applied Chemistry; 2025.") and the Gold Book home page names no work at
all: neither credits an author. A term's definition is not an abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.iupac_gold_book import IupacGoldBook

URL = "https://doi.org/10.1351/goldbook.M03830"
IUPAC = "The International Union of Pure and Applied Chemistry (IUPAC)"
HEAD = ('<meta charset="UTF-8"/><title>IUPAC - mercaptals (M03830)</title>'
        '<meta name="description" content="The IUPAC Compendium of Chemical Terminology"/>'
        f'<meta name="author" content="{IUPAC}"/>'
        '<link rel="stylesheet" type="text/css" href="/css/iupac.css"/>')
DC = '<meta name="dc.identifier" content="https://doi.org/10.1351/goldbook.{code}"/>'
DEFINITION = ("<div id=\"definitions\"><div class='deftext'>A term once used for thioacetals derived from aldehydes; "
              "its use is discouraged.<div class='sources'><b><em>Source: </em></b><br/>PAC, 1995, <em>67</em>, 1307. "
              "[<a href='https://doi.org/10.1351/pac199567081307'>Paper</a>]</div></div></div>")
CITE_V3 = ('<div class="panel-footer text-justify"><b>Cite as</b>: <em>IUPAC. Compendium of Chemical Terminology, '
           '2nd ed. (the "Gold Book"). Compiled by A. D. McNaught and A. Wilkinson. Blackwell Scientific Publications, '
           'Oxford (1997). Online version (2019-) created by S. J. Chalk. ISBN 0-9678550-9-8. '
           'https://doi.org/10.1351/goldbook.</em></div>')
CITE_V5 = ("<div class=\"panel-footer text-justify\"><b>Citation:</b> 'explanatory variable' in <em>IUPAC Compendium "
           "of Chemical Terminology</em>, 5th ed. International Union of Pure and Applied Chemistry; 2025. Online "
           "version 5.0.0, 2025. https://doi.org/10.1351/goldbook.10051</div>")


def _page(head_extra, card_footer, head=HEAD):
    return (f"\t<!DOCTYPE html>\n\t<html lang=\"en\"><head>{head}{head_extra}</head><body>"
            '<div id="info" class="well well-sm"><h5>Version 3.0.1 (6465 Terms)</h5>'
            "<a href=\"/cdn-cgi/l/email-protection\">Stuart Chalk - Technical Editor</a></div>"
            '<div id="main"><div id="notecard" class="panel panel-default notecard">'
            '<div class="panel-heading"><h2 class="panel-title times_nr_h2">mercaptals</h2></div>'
            f'<div class="panel-body">{DEFINITION}</div>{card_footer}</div></div>'
            '<footer class="footer bg-gold">&copy; 2005-2023 International Union of Pure and Applied Chemistry</footer>'
            "</body></html>")


V3_TERM = _page(DC.format(code="M03830"), CITE_V3)
V5_TERM = _page(DC.format(code="10051"), CITE_V5)
HOME = ('<html><head><title>The IUPAC Compendium of Chemical Terminology</title>'
        f'<meta name="author" content="{IUPAC}"/></head><body><div id="main"><h1>Compendium of Chemical Terminology'
        '</h1><p>Welcome to the new interactive version of IUPAC Compendium of Chemical Terminology.</p>'
        '<p>The IUPAC Gold Book is licensed under Creative Commons Attribution-ShareAlike CC BY-SA 4.0.</p>'
        "</div></body></html>")


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _soup(html):
    return BeautifulSoup(html, parser="lxml", features="lxml")


def test_v3_term_page_credits_iupac_as_group_author():
    out = _out(V3_TERM)
    assert [a["name"] for a in out["authors"]] == [IUPAC]
    assert out["authors"][0]["affiliations"] == []
    assert out["authors"][0]["is_corresponding"] is False


def test_compilers_and_site_editors_are_not_authors():
    names = [a["name"] for a in _out(V3_TERM)["authors"]]
    assert not any("McNaught" in n or "Wilkinson" in n or "Chalk" in n for n in names)


def test_definition_is_not_an_abstract():
    assert _out(V3_TERM)["abstract"] is None
    assert IupacGoldBook(_soup(V3_TERM)).parse()["abstract"] is None


def test_v5_term_page_credits_no_author():
    # IUPAC is the publisher in the 5.0.0 citation; the author meta tag is the whole site's
    parser = IupacGoldBook(_soup(V5_TERM))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _out(V5_TERM)["authors"] == []


def test_home_page_is_not_claimed():
    parser = IupacGoldBook(_soup(HOME))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _out(HOME)["authors"] == []


def test_cite_as_without_iupac_credit_is_not_read():
    other = CITE_V3.replace("IUPAC. Compendium", "Compendium")
    assert not IupacGoldBook(_soup(_page(DC.format(code="M03830"), other))).authors_found()


def test_name_falls_back_to_the_cited_form_without_the_author_tag():
    head = HEAD.replace(f'<meta name="author" content="{IUPAC}"/>', "")
    out = IupacGoldBook(_soup(_page(DC.format(code="M03830"), CITE_V3, head=head))).parse()
    assert [a["name"] for a in out["authors"]] == ["IUPAC"]


def test_look_alike_page_of_another_site_is_not_claimed():
    # a De Gruyter Pure and Applied Chemistry page: same DOI prefix, IUPAC named, a "Cite as" line; not a Gold Book term
    pac = ('<html><head><meta name="citation_publisher" content="De Gruyter"/>'
           '<meta name="dc.identifier" content="https://doi.org/10.1351/pac199567081307"/>'
           f'<meta name="author" content="{IUPAC}"/>'
           '<meta name="citation_title" content="Glossary of class names of organic compounds"/></head><body>'
           '<div id="notecard"><div class="panel-footer"><b>Cite as</b>: <em>IUPAC. Pure and Applied Chemistry 67 '
           "(1995) 1307.</em></div></div></body></html>")
    parser = IupacGoldBook(_soup(pac))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
