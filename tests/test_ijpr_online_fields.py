"""International Journal of Pharmaceutical Research (IJPR, Advanced Scientific Research; DOI prefix 10.31838/ijpr)
article pages (oxjob #2339).

Markup is cut down from stored pages (17 Nov 2026). The site is an ASP.NET app with no meta tags: the title is
"ViewArticleDetail" (or "ViewSpecialArticleDetail" for special issues), and a GridView prints the byline as one
comma-separated span (the first author in <FONT COLOR="GREEN">) and the abstract in its own span. Before this parser
only the generic one read these pages: the abstract under its "Abstract:" label, no authors.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ijpr_online import IJPROnline

URL = "https://doi.org/10.31838/ijpr/2021.13.01.1"
ABSTRACT = ("The aim of the study was to find out the prevalence of a condition among adults. The present retrospective "
            "study was conducted among 100 outpatients who reported to a private institution. Data regarding the type "
            "of attachment was collected and analysed, and no significant association was found between groups.")


def _page(byline, abstract=ABSTRACT, grid="gvArticle", title="ViewArticleDetail", logo="Images/ijprlogo.png",
          doi="10.31838/ijpr/2021.13.01.1"):
    p = f"ContentPlaceHolder1_{grid}"
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "x">
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>
	{title}
</title><link rel="icon" href="Images/favicon.ico" type="image/x-icon" /></head>
<body><form method="post" action="./{title}.aspx?ID=1" id="form1">
<img src="{logo}" alt="" /><p>INTERNATIONAL JOURNAL OF PHARMACEUTICAL RESEARCH</p>
<h2>Article Detail</h2>
<table id="{p}"><tr><td><table>
<tr><td><span id="{p}_lblArticleTitle_0" style="font-weight:bold;">A study of something</span></td></tr>
<tr><td><table>
<tr><td valign="top">Author:</td><td valign="top"><span id="{p}_lblAuthor_0">{byline}</span></td></tr>
<tr><td valign="top">Abstract:</td><td valign="top"><span id="{p}_lblAbstract_0">{abstract}</span></td></tr>
<tr><td valign="top">Keyword:</td><td valign="top"><span id="{p}_lblKeyword_0">prevalence, adults,</span></td></tr>
<tr id="{p}_trDOI_0"><td valign="top">DOI:</td><td valign="top"><span id="{p}_lblDOI_0">
<a href=https://doi.org/{doi} target=/"_blank/">https://doi.org/{doi}</a></span></td></tr>
<tr><td valign="top">Download:</td><td><a href="javascript:__doPostBack('x','')">Request For Article</a></td></tr>
</table></td></tr></table></td></tr></table>
</form></body></html>"""


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def test_byline_is_read_in_order():
    html = _page('<FONT COLOR="GREEN">ANITA RAO.S </FONT>,  KIRAN MENON,  LATA M')
    authors = _authors(html)
    assert [a["name"] for a in authors] == ["ANITA RAO.S", "KIRAN MENON", "LATA M"]
    assert all(a["affiliations"] == [] for a in authors)


def test_green_first_author_is_not_a_corresponding_mark():
    # the page never explains the green colour or a bare "*", so neither is a corresponding-author mark (label-v1)
    html = _page('<FONT COLOR="GREEN">ANITA RAO1*</FONT>, KIRAN MENON')
    authors = _authors(html)
    assert [a["name"] for a in authors] == ["ANITA RAO", "KIRAN MENON"]
    assert not any(a["is_corresponding"] for a in authors)


def test_empty_slots_and_titles_are_dropped():
    html = _page('<FONT COLOR="GREEN"> </FONT>,   P.R. KIRAN KUMAR,   DR.LATA MENON,  DR. ANITA RAO, VIJAY S., '
                 'DRAVID NAIR')
    assert [a["name"] for a in _authors(html)] == ["P.R. KIRAN KUMAR", "LATA MENON", "ANITA RAO", "VIJAY S",
                                                   "DRAVID NAIR"]


def test_abstract_is_the_abstract_span():
    out = parse_page(_page("KIRAN MENON").encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT


def test_abstract_whitespace_is_squashed():
    html = _page("KIRAN MENON", abstract="Background\nThe first part.\nConclusion\n" + ABSTRACT + "\n")
    assert parse_page(html.encode(), "doi", URL)["abstract"] == "Background The first part. Conclusion " + ABSTRACT


def test_special_issue_page_is_read():
    html = _page('<FONT COLOR="GREEN">ANITA RAO</FONT>, KIRAN MENON', grid="gvSpecialArticle",
                 title="ViewSpecialArticleDetail")
    assert [a["name"] for a in _authors(html)] == ["ANITA RAO", "KIRAN MENON"]


def test_parser_returns_no_new_fields():
    # the pages show no acknowledgments, funding statement or reference list
    soup = BeautifulSoup(_page("KIRAN MENON"), "lxml")
    parsed = IJPROnline(soup).parse()
    assert set(parsed) == {"authors", "abstract"}


def test_lookalike_aspnet_page_of_another_journal_is_not_claimed():
    # the same ASP.NET GridView markup on another journal's site (its own logo, another DOI prefix)
    html = _page("KIRAN MENON", logo="Images/otherlogo.png", doi="10.12345/abc.2021.1")
    parser = IJPROnline(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_with_another_title_is_not_claimed():
    html = _page("KIRAN MENON", title="Article")
    assert not IJPROnline(BeautifulSoup(html, "lxml")).authors_found()
