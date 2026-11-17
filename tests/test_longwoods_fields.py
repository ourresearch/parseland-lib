"""Longwoods Publishing article pages (longwoods.com, DOI prefix 10.12927), oxjob #2339.

Markup is cut down from stored pages of the in-house template: citation_author meta tags whose last tag joins the last
two names with " and ", an "About the Author(s)" section of biographies that may close with "Correspondence may be
directed to: <name>, ...", and <h4> back-matter sections whose content follows the heading as sibling nodes. The
biographies are not affiliations (label-v1), so no author gets one.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.longwoods import Longwoods

URL = "https://doi.org/10.12927/hcpol.2007.19175"
HEAD = ('<meta name="og:site_name" content="Longwoods Publication" />'
        '<meta name="og:url" content="https://www.longwoods.com/content/19175/healthcare-policy/turning-vision" />')
ABOUT = ('<h4 class="abstract_content" id="abtAuthor">About the Author(s)</h4>'
         '<p><B>Robert Wedel</b>, MD <br>Rural Family Physician <br>Co-Leader, Taber Health Project <br>Taber, AB '
         '<P><B>Ruth Grant Kalischuk</b>, RN, PhD <br>School of Health Sciences, University of Lethbridge </p>'
         '<P><B>Eileen Patterson</b>, MCE <br>Lethbridge, AB </p><P><B>Sharon Brown</b>, BSc <br>Lethbridge, AB </p>'
         '<P>Correspondence may be directed to: Robert Wedel, MD, Medical Director, Chinook Health Region, Taber, AB; '
         'e-mail: <a href="mailto:rw@example.net">rw@example.net</a>.</p>')
ACK = ('<!-- acknowledgement -->\n<h4 class="abstract_content">Acknowledgment</h4>\n'
       '   We are grateful to the nurse volunteers who participated in the pilot study.   \n')
REFS = ('<!-- references -->\n<h4 class="content_abstract">References</h4>\n'
        '<p>Beddome, G. 1993. &quot;Vision for the Future.&quot; <i>Canadian Nurse</i> 89: 13.</p>\n'
        '<p>Smith, J. 2004. &quot;A Study.&quot; <a href="https://doi.org/10.1000/xyz.123">doi</a></p>\n')


def _page(authors=("Robert Wedel", "Ruth Grant Kalischuk", "Eileen Patterson and Sharon Brown"), about=ABOUT,
          back=ACK + REFS, head=HEAD):
    metas = "".join(f'<meta name="citation_author" content="{a}" />' for a in authors)
    return (f'<html><head><title> Turning Vision into Reality</title>'
            f'<meta name="citation_title" content="Turning Vision into Reality" />{metas}{head}</head><body>'
            f'<h3> Turning Vision into Reality </h3><p><a href="#abtauth" class="redcolor">{", ".join(authors)}</a></p>'
            f'<div id="contentDesc" class="current_issue_main_text"><div class="editor_typo"><p>Body text.</p></div>'
            f'<div class="editor_typo">{about}{back}</div>'
            f'<div class="editor_typo"><h4 class="content_abstract">Comments</h4><p>Be the first to comment on this!</p>'
            f'</div></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return Longwoods(BeautifulSoup(html, "lxml")).parse()


def test_last_meta_tag_splits_on_and():
    out = _parse(_page())
    assert [a["name"] for a in out["authors"]] == ["Robert Wedel", "Ruth Grant Kalischuk", "Eileen Patterson",
                                                   "Sharon Brown"]


def test_biographies_are_not_affiliations():
    assert all(a["affiliations"] == [] for a in _parse(_page())["authors"])


def test_correspondence_line_marks_one_author():
    out = _parse(_page())
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False, False]


def test_correspondence_by_surname_with_title_and_short_given_name():
    about = ('<h4 class="abstract_content" id="abtAuthor">About the Author(s)</h4>'
             '<p><B>Donald J. Philippon</b>, PhD</p><p><B>Jeffrey Braithwaite</b>, PhD</p>'
             '<P>Correspondence may be directed to: Dr. Don Philippon, Professor, University of Alberta.</p>')
    out = _parse(_page(authors=("Donald J. Philippon and Jeffrey Braithwaite",), about=about))
    assert [(a["name"], a["is_corresponding"]) for a in out["authors"]] == [
        ("Donald J. Philippon", True), ("Jeffrey Braithwaite", False)]


def test_principal_author_and_contact_is_a_mark():
    about = ('<h4 class="abstract_content" id="abtAuthor">About the Author(s)</h4>'
             '<p><B>Edward Etchells</b>, MD, is a physician.<P><B>Cynthia Bailey</b> is a risk manager.'
             '<P>Principal author and contact: Dr. Edward Etchells, Staff Physician, Toronto, ON. E-mail: '
             '<a href="mailto:e@example.ca">e@example.ca</a>.</p>')
    out = _parse(_page(authors=("Edward Etchells and Cynthia Bailey",), about=about))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_email_for_every_author_is_not_a_mark():
    about = ('<h4 class="abstract_content" id="abtAuthor">About the Author(s)</h4>'
             '<p><b>Anne Wojtak</b> is a consultant. Anne can be reached by e-mail at a@example.ca.</p>'
             '<p><b>Neil Stuart</b> is a consultant. Neil can be reached by e-mail at n@example.ca.</p>')
    out = _parse(_page(authors=("Anne Wojtak and Neil Stuart",), about=about))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_names_double_escaped_and_mojibake_are_cleaned():
    out = _parse(_page(authors=("Michael A. O&amp;#39;Neill", "JosÃ©e Lavoie and Bryan Teskey")))
    assert [a["name"] for a in out["authors"]][:2] == ["Michael A. O'Neill", "Josée Lavoie"]


def test_empty_meta_tag_falls_back_to_biography_names():
    about = ('<h4 class="abstract_content" id="abtAuthor">About the Author(s)</h4>'
             '<p><b>Dr. Jack Silversin</b> is president of Amicus Inc., Cambridge, Mass.</p>')
    out = _parse(_page(authors=("",), about=about))
    assert [a["name"] for a in out["authors"]] == ["Jack Silversin"]


def test_acknowledgments_as_bare_text():
    assert _raw(_page())["acknowledgments"] == ("We are grateful to the nurse volunteers who participated in the "
                                                "pilot study.")


def test_acknowledgments_paragraphs_join_by_newline():
    ack = ('<!-- acknowledgement -->\n<h4 class="abstract_content">Acknowledgment</h4>'
           '<p>This study was funded by the CIHR.</p><p>We thank the participants.</p>'
           '<P>Correspondence may be directed to Dr. Robert Wedel, Taber, AB.\n')
    raw = _raw(_page(back=ack + REFS))
    assert raw["acknowledgments"] == "This study was funded by the CIHR.\nWe thank the participants."
    assert raw["funding_statement"] is None


def test_references_in_order_never_called_whole():
    raw = _raw(_page())
    assert [r["raw"] for r in raw["references"]] == [
        'Beddome, G. 1993. "Vision for the Future." Canadian Nurse 89: 13.', 'Smith, J. 2004. "A Study." doi']
    assert [r["doi"] for r in raw["references"]] == [None, "10.1000/xyz.123"]
    assert raw["references_complete"] is False


def test_no_back_matter():
    raw = _raw(_page(back=""))
    assert raw["acknowledgments"] is None and raw["references"] is None


def test_lookalike_page_from_another_site_is_not_claimed():
    head = ('<meta name="og:site_name" content="Healthcare Quarterly Mirror" />'
            '<meta name="og:url" content="https://example.org/content/19175/longwoods" />')
    soup = BeautifulSoup(_page(head=head), "lxml")
    assert not Longwoods(soup).is_publisher_specific_parser()
    assert not Longwoods(soup).authors_found()


def test_page_without_head_meta_is_not_claimed():
    soup = BeautifulSoup("<html><body><p>longwoods.com/content/1 Longwoods</p></body></html>", "lxml")
    assert not Longwoods(soup).authors_found()
