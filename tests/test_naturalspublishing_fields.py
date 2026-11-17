"""Natural Sciences Publishing (naturalspublishing.com) article pages (oxjob #2339).

Markup is cut down from stored naturalspublishing.com pages (17 Nov 2026). The site is a classic ASP table layout with no
meta tags at all: the article sits between "Article Details" comments, each field under a `td.Title` row ("Author(s)",
"Abstract") with its value in the next `td.Content` row. The byline is one link per author to Author.asp; the page shows
no affiliations, no corresponding author and no reference list (the "Referance(s)" block is commented out).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.naturalspublishing import NaturalSciencesPublishing

URL = "https://www.naturalspublishing.com/Article.asp?ArtcID=25744"
TITLE = "<title>.:: Natural Sciences Publishing ::.</title>"
ABSTRACT = ("In the present paper, we propose a new generalized Lindley distribution, which generalizes the Lindley "
            "distribution and many extensions of it as proposed by various authors in recent years.")


def _row(cls, inner):
    return f'<tr><td valign="top" class="{cls}"><span lang="en-us">{inner}</span></td></tr><tr><td height="5"></td></tr>'


def _byline(names):
    return "".join(f'\r\n<a href="Author.asp?AuthID={41794 + i}&ArtcID=25744">{n}</a>,\r\n' for i, n in enumerate(names))


def _page(names, title=TITLE, author_label="Author(s)"):
    details = (_row("Title", "A New Generalized Lindley Distribution") + _row("Content", "PP: 125-133")
               + '<tr><td class="Article"><a href="http://dx.doi.org/10.18576/jsapl/090302">doi:10.18576/jsapl/090302</a>'
               '</td></tr>'
               + _row("Title", author_label) + _row("Content", _byline(names))
               + _row("Title", "Abstract")
               + f'<tr><td valign="top" height="10" class="Content">{ABSTRACT}\n</td></tr>'
               + '<!--\n<tr><td valign="top" class="TitlesIn"><span lang="en-us">Referance(s)</span></td></tr>\n-->')
    return (f'<html><head><meta http-equiv="Content-Type" content="text/html; charset=windows-1252">{title}'
            '<link rel="stylesheet" type="text/css" href="css/style.css"></head><body><center><table><tr><td>'
            '<table><tr><td width="100%" class="PageTitle"><span lang="en-us">Content</span></td></tr></table>'
            f'<table><!--Article Details Start--><tr><td bgcolor="#F3F3F3"><table>{details}</table></td></tr>'
            '<!--Article Details End--></table></td></tr></table></center></body></html>')


def _parse_page(html):
    return parse_page(html.encode("cp1252", "xmlcharrefreplace"), "doi", URL)


def _parser(html):
    return NaturalSciencesPublishing(BeautifulSoup(html, "lxml"))


NAMES = ["Mohamed Habibullah", "M. Ahsanullah", "M. Shakil"]


def test_byline_links_are_the_authors_in_order():
    authors = _parse_page(_page(NAMES))["authors"]
    assert [a["name"] for a in authors] == NAMES
    assert [a["affiliations"] for a in authors] == [[], [], []]
    assert [a["is_corresponding"] for a in authors] == [False, False, False]


def test_detached_combining_accent_joins_its_letter():
    authors = _parse_page(_page(["Adote &#769; Herve &#769; Gildas Akueson", "R. Jua &#769;rez-Amaro"]))["authors"]
    assert [a["name"] for a in authors] == ["Adoté Hervé Gildas Akueson", "R. Juárez-Amaro"]


def test_abstract_is_still_read_under_its_heading():
    assert _parse_page(_page(NAMES))["abstract"].startswith("In the present paper, we propose")


def test_commented_out_reference_block_gives_no_new_fields():
    parsed = _parser(_page(NAMES)).parse()
    for key in ("references", "acknowledgments", "funding_statement"):
        assert not parsed.get(key)
    assert not parsed.get("references_complete")


def test_issue_contents_page_is_not_read():
    # an issue's table of contents: "Authors:" with each author's affiliation, one block per article
    toc = _page(["Abbas Kareem Wanas</a> - Department of Mathematics, University of Al-Qadisiyah, Iraq<a>"],
                author_label="Authors:")
    assert not _parser(toc).authors_found()


def test_other_site_with_the_same_table_markup_is_not_claimed():
    other = _page(NAMES, title="<title>Journal of Something :: Article</title>")
    parser = _parser(other)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
