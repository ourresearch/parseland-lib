"""Acknowledgments and funding statements on pre-LWW Medknow article pages (oxjob #2289).

Markup is cut down from stored Medknow pages (article.asp on the journals' own sites; many of these DOIs now resolve
to journals.lww.com, whose pages lippincott.py reads and this parser never claims). Medknow prints the back matter
as bold labels in the article body ("<b><i>Acknowledgements</i></b><br><br>text<br><br><b>Financial support and
sponsorship</b><br><br>Nil."), older pages give "Acknowledgment" its own section bar (td.pageSub, like References),
and every page's header says "Source of Support: ..., Conflict of Interest: ...". The four keys follow #2215's
contract and label-v2: text verbatim without its label; "Nil." under the funding label is the funding statement.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.medknow import MedKnow

URL = "https://www.example-medknow-journal.org/article.asp?issn=0000-0000;year=2020;volume=1;issue=1;spage=1"
HEAD = ('<head><meta name="description" content="A Journal, India">'
        '<meta name="DC.Title" content="A title">'
        '<link rel="SCHEMA.dc" href="https://purl.org/metadata/dublin_core_elements#title">'
        '<meta name="citation_publisher" content="Medknow Publications">'
        '<meta name="citation_title" content="A title"></head>')
BYLINE = ('<font class="articleAuthor"> <a href="/searchresult.asp?author=Ann+Rao">Ann Rao</a><sup>1</sup>,  '
          '<a href="/searchresult.asp?author=Ben+Iyer">Ben Iyer</a><sup>2</sup></font><br>'
          '<font class="AuthorAff"><sup>1</sup>&nbsp;Department of Surgery, A Medical College, Pune, India<br/>'
          '<sup>2</sup>&nbsp;Department of Medicine, B Hospital, Pune, India<br/></font>')
REFS_BAR = ('<br>&nbsp;<table width="100%" class="leftNav"><tr><td height="15px" class="pageSub"> '
            '<a name="Reference"></a>&nbsp;&nbsp;References</td></tr></table><br>'
            '<table width="100%" class="body"><tr><td width="5%" valign="top"><a class="ref" name="ref1" href="#ft1">1.'
            '</a></td><td><div class=\'rti\'>Doe J. A cited work. J Med 2001;1:1-2.</div></td></tr></table>')
FTR = '<div class="othrLnks"><script type="text/javascript" src="https://www.medknow.com/ss/ftr.js"></script></div>'


def _header(support="None"):
    return ('<p><font class="CorrsAdd"><b>Correspondence Address</b>:<br/>Dr. Ben Iyer<br>B Hospital, Pune<br>India'
            f'<p><b>Source of Support:</b> {support}, <b>Conflict of Interest:</b> None</p></font></p>')


def _page(body, support="None", head=HEAD, ftr=FTR):
    return (f"<html>{head}<body><table><tr><td>{BYLINE}{_header(support)}</td></tr>"
            f"<tr><td class=\"articleText\">Results were good.{body}{REFS_BAR}</td></tr></table>{ftr}</body></html>")


def _parse(html):
    return MedKnow(BeautifulSoup(html, "lxml")).parse()


BODY = ('<br><br><b><i>Acknowledgements</i></b><br><br>The authors thank the Radiology department, A Medical College, '
        'Pune.<br><br><b><i>Financial support and sponsorship</i></b><br><br>This study was supported by the B '
        'Research Council (grant 12/2019).<br><br><b><i>Conflicts of interest</i></b><br><br>There are no conflicts '
        'of interest.<br><br><br>\r\n\t\t\t')


def test_body_sections_are_read_without_their_labels():
    out = _parse(_page(BODY))
    assert out["acknowledgments"] == "The authors thank the Radiology department, A Medical College, Pune."
    assert out["funding_statement"] == "This study was supported by the B Research Council (grant 12/2019)."


def test_nil_under_the_funding_label_is_the_statement():
    body = ('<br><br><b>Financial support and sponsorship</b><br><br>Nil.<br><br><b>Conflicts of interest</b><br><br>'
            'There are no conflicts of interest.<br><br><br>')
    out = _parse(_page(body))
    assert out["funding_statement"] == "Nil."
    assert out["acknowledgments"] is None


def test_body_funding_section_wins_over_the_header_line():
    out = _parse(_page(BODY, support="None"))
    assert out["funding_statement"].startswith("This study was supported")


def test_header_source_of_support_when_the_body_has_no_funding_section():
    support = "This project was undertaken during a Senior Research Fellowship supported by the C Council, India"
    out = _parse(_page("<br><br>", support=support))
    assert out["funding_statement"] == support
    assert out["acknowledgments"] is None


def test_acknowledgment_after_the_funding_label_ends_at_the_references_bar():
    body = ('<br><br><b>Financial support and sponsorship</b><br><br>Nil.<br><br><b>Acknowledgment</b><br><br>'
            'We thank all nurses who took part in this study.<br>\r\n\t\t\t')
    out = _parse(_page(body))
    assert out["acknowledgments"] == "We thank all nurses who took part in this study."
    assert out["funding_statement"] == "Nil."


def test_paragraphs_are_joined_by_newlines_and_inline_markup_kept_as_text():
    body = ('<br><br><b>Acknowledgments</b><br><br>We thank the staff of <i>B Hospital</i>.<br><br>'
            'We also thank the patients.<br><br><b>Conflicts of interest</b><br><br>None.<br><br>')
    assert _parse(_page(body))["acknowledgments"] == "We thank the staff of B Hospital.\nWe also thank the patients."


def test_older_section_bar_acknowledgment():
    body = ('<br><br><br><table width="100%" class="leftNav"><tr><td class="pageSub"> <a name="Acknowledgment"></a>'
            '&nbsp;<img src="images/aboutbul.gif" alt="">&nbsp;&nbsp;Acknowledgment</td></tr></table><br><br>'
            'This research was supported by C University of Medical Sciences.<br>\r\n\t\t\t')
    out = _parse(_page(body))
    assert out["acknowledgments"] == "This research was supported by C University of Medical Sciences."
    assert out["funding_statement"] == "None"


def test_no_reference_list_is_returned():
    out = _parse(_page(BODY))
    assert out.get("references") is None and not out.get("references_complete")


def test_byline_still_read_through_parse_page():
    out = parse_page(_page(BODY).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Ann Rao", "Ben Iyer"]
    assert out["authors"][0]["affiliations"] == [{"name": "Department of Surgery, A Medical College, Pune, India"}]
    assert out["acknowledgments"].startswith("The authors thank")
    assert out["funding_statement"].startswith("This study was supported")


def test_page_without_the_dublin_core_schema_link_is_not_read():
    """A Yektaweb page carries DC.* meta tags too, but never Medknow's SCHEMA.dc link: never this parser's page."""
    head = ('<head><meta name="DC.Title" content="A title"><meta name="citation_publisher" content="Another Press">'
            '</head>')
    parser = MedKnow(BeautifulSoup(_page(BODY, head=head), "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()


def test_lww_article_page_is_not_read():
    html = ('<html><head><meta name="citation_publisher" content="Wolters Kluwer Medknow Publications">'
            '<link rel="canonical" href="https://journals.lww.com/jfmpc/fulltext/2023/06000/x.aspx"></head><body>'
            '<section id="ejp-article-authors"><p>Rao, Ann<sup>1</sup>; Iyer, Ben<sup>2</sup></p></section>'
            '<p><b>Financial support and sponsorship</b></p><p>Nil.</p></body></html>')
    parser = MedKnow(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()
    assert not parser.is_publisher_specific_parser()
