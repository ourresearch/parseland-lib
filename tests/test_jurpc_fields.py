"""JurPC (jurpc.de) court-decision pages: the editors' headnote is the abstract (oxjob #2339).

Markup is cut down from stored jurpc.de pages (17 Nov 2026). A decision page prints its headnote ("Leitsatz",
"Leitsätze (der Redaktion)", "Leitsatz (des Einsenders)") under its own heading, in a blue table cell, before the
reasons; the build labels take that headnote as the abstract. Authors stay as the citation_author tag gives them.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jurpc import JurPC

URL = "https://www.jurpc.de/jurpc/show?id=20170008"


def _page(body, journal="JurPC", author="München, OLG"):
    return ("<html><head>"
            '<meta name="Description" content="Die bloße Zusendung eines Product Keys für ein Computerprogramm" />'
            '<meta name="citation_title" content="Product-Key-Zusendung">'
            f'<meta Name="citation_author" content="{author}">'
            f'<meta name="citation_journal_title" content="{journal}">'
            '<meta name="citation_volume" content="2017">'
            "<title>München, OLG, Product-Key-Zusendung - JurPC-Web-Dok. 0008/2017</title></head><body>"
            '<div id="doc"><div class="leftCol"><div class="biblio"><b>JurPC Web-Dok. 8/2017 - DOI 10.7328/jurpcb20173218'
            f"</b></div>{body}</div></div></body></html>")


NEW_LAYOUT = (
    '<table><tr><td width="80%"><h2>OLG Karlsruhe</h2></td></tr><tr><td><h2>Beschluss vom 03.04.2019</h2></td></tr>'
    '<tr><td width="80%"><h3>Leitsatz:</h3></td></tr><tr><td width="8%"></td><td width="80%" bgcolor="#A4C8F0">'
    '<div class="box"><p>Die unterbliebene Beiziehung von Messunterlagen ber&uuml;hrt nicht den Anspruch auf '
    "rechtliches Geh&ouml;r.</p></div></td></tr>"
    '<tr><td width="80%"><h3>Gr&uuml;nde:</h3></td></tr><tr><td width="80%">Mit dem angefochtenen Urteil ...</td></tr>'
    "</table>")

OLD_LAYOUT_LIST = (
    '<TABLE WIDTH="100%"><TR><TD WIDTH="70%"><H2><gericht>OLG M&uuml;nchen</gericht>,<BR>Urteil vom 22.04.99</H2>'
    '</TD></TR></TABLE><TABLE WIDTH="100%"><TR><TD WIDTH="70%">MarkenG &#167; 15</TD></TR></TABLE>'
    '<TABLE WIDTH="100%"><TR><TD WIDTH="70%"><H4 ALIGN="CENTER">Leits&auml;tze (der Redaktion)</H4></TD></TR></TABLE>'
    '<TABLE WIDTH="100%"><TR><TD></TD></TR></TABLE>'
    '<TABLE WIDTH="100%"><TR><TD WIDTH="10%"></TD><TD WIDTH="70%" BGCOLOR="#A4C8F0"><OL><LI>Dem Firmenbestandteil '
    '"buecher.de" kommt keine namensm&auml;&szlig;ige\nKennzeichnungskraft zu.\n</LI><LI>Ein Namensschutz '
    'kommt nicht in Betracht.\n</LI></OL></TD></TR></TABLE>'
    '<TABLE WIDTH="100%"><TR><TD WIDTH="70%"><H4 ALIGN="CENTER">Tatbestand</H4></TD></TR></TABLE>')

OLD_LAYOUT_BREAKS = (
    '<TABLE><TR><TD WIDTH="70%"><H4 ALIGN="CENTER">Leits&auml;tze (der Redaktion)</H4></TD></TR></TABLE>'
    '<TABLE><TR><TD WIDTH="70%" BGCOLOR="#a4c8f0">1.Eine Klausel in den Allgemeinen Gesch&auml;ftsbedingungen\n'
    "ist unwirksam.\n<BR><BR>2.Eine Datenschutzklausel\nist unwirksam.</TD></TR></TABLE>"
    '<TABLE><TR><TD WIDTH="70%"><H4 ALIGN="CENTER">Gr&uuml;nde</H4></TD></TR></TABLE>')

ESSAY = (
    '<TABLE><TR><TD WIDTH="70%"><H2>Peter Becker <A HREF="#fn0" NAME="rfn0">*</A></H2>'
    "<H2>Zur Zukunft der anwaltlichen Arbeitsweise</H2><H3>JurPC Web-Dok. 3/2013, Abs. 1 - 40</H3></TD></TR></TABLE>"
    '<TABLE><TR><TD WIDTH="70%">Die Digitalisierung ver&auml;ndert die Kanzlei.</TD></TR></TABLE>')


def _soup(html):
    return BeautifulSoup(html, "lxml")


def test_new_layout_headnote_is_the_abstract():
    out = parse_page(_page(NEW_LAYOUT).encode(), "doi", URL)
    assert out["abstract"] == "Die unterbliebene Beiziehung von Messunterlagen berührt nicht den Anspruch auf " \
                              "rechtliches Gehör."


def test_court_stays_the_author_as_the_meta_tag_gives_it():
    out = parse_page(_page(NEW_LAYOUT).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["München, OLG"]
    assert out["authors"][0]["affiliations"] == []
    assert not out["authors"][0]["is_corresponding"]


def test_numbered_headnotes_one_per_line():
    parsed = JurPC(_soup(_page(OLD_LAYOUT_LIST))).parse()
    assert parsed["abstract"] == ('Dem Firmenbestandteil "buecher.de" kommt keine namensmäßige Kennzeichnungskraft zu.'
                                  "\nEin Namensschutz kommt nicht in Betracht.")


def test_breaks_split_headnotes_and_source_line_wraps_do_not():
    parsed = JurPC(_soup(_page(OLD_LAYOUT_BREAKS))).parse()
    assert parsed["abstract"] == ("1.Eine Klausel in den Allgemeinen Geschäftsbedingungen ist unwirksam."
                                  "\n2.Eine Datenschutzklausel ist unwirksam.")
    out = parse_page(_page(OLD_LAYOUT_BREAKS).encode(), "doi", URL)
    assert "Datenschutzklausel ist unwirksam" in out["abstract"]


def test_essay_without_headnote_is_not_claimed():
    parser = JurPC(_soup(_page(ESSAY, author="Becker, Peter")))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_authors_theses_on_an_essay_are_not_taken():
    body = ('<TABLE><TR><TD><H3 align="left"><A NAME="u1"><B><I>Leits&auml;tze der Verfasser</I></B></A></H3>'
            '</TD></TR></TABLE><TABLE><TR><TD WIDTH="70%" BGCOLOR="#A4C8F0">1. These eins.</TD></TR></TABLE>')
    assert not JurPC(_soup(_page(body, author="Seidl, Alexander"))).authors_found()


def test_headnote_heading_without_its_cell_reads_nothing():
    body = ('<TABLE><TR><TD><H4>Leitsatz</H4></TD></TR></TABLE><TABLE><TR><TD><H4>Gr&uuml;nde</H4></TD></TR></TABLE>'
            '<TABLE><TR><TD BGCOLOR="#A4C8F0">Ein Kasten weiter unten, kein Leitsatz.</TD></TR></TABLE>')
    assert not JurPC(_soup(_page(body))).authors_found()


def test_lookalike_page_from_another_legal_site_is_not_claimed():
    # Another German law site with the same headnote heading and blue cell, but its own journal title
    html = _page(NEW_LAYOUT, journal="Kommunikation & Recht")
    parser = JurPC(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert parse_page(html.encode(), "doi", "https://www.example-recht.de/urteil/1")["abstract"] is None
