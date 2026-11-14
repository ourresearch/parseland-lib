"""science-gate.com (IASE, International Journal of Advanced and Applied Sciences) article pages (oxjob #2210).

Markup is cut down from stored pages of the site (13 Nov 2026). One hand-made template since 2022: an "Author(s):"
heading over a comma-separated byline (<sup> affiliation numbers, a "*" explained by "* Corresponding Author."), an
"Affiliation(s):" heading over one <em> of numbered or unnumbered affiliations, then Abstract, Acknowledgment, an
optional Funding section and "References (N)" over one <ol>. Pages from 2024 on also carry citation_author meta tags
(institution attached only to the first author); 2023 pages carry none, so Parseland read no authors there.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.science_gate import ScienceGate

URL = "https://www.science-gate.com/IJAAS/2023/V10I7/1021833ijaas202307007.html"

HEAD_2023 = ('<meta name="citation_publisher" content="IASE" />'
             '<meta name="citation_title" content="A study of things">'
             '<meta name="citation_pdf_url" content="http://science-gate.com/IJAAS/Articles/2023/x.pdf" />'
             '<link href="http://www.science-gate.com/IJAAS/2023/V10I7/1021833ijaas202307007.html" />'
             '<meta name="citation_abstract_html_url" '
             'content="http://www.science-gate.com/IJAAS/2023/V10I7/1021833ijaas202307007.html" />')

HEAD_2024 = ('<link href="https://www.science-gate.com/IJAAS/2024/V11I12/1021833ijaas202412022.html" rel="canonical" />'
             '<meta content="A study of things" name="citation_title" />'
             '<meta content="Ana Example" name="citation_author"/>'
             '<meta content="Faculty of Science, Example University, Town, Country" name="citation_author_institution"/>'
             '<meta content="Ben Sample" name="citation_author"/>'
             '<meta content="Faculty of Science, Example University, Town, Country" name="citation_author_institution"/>'
             '<meta content="https://www.science-gate.com/IJAAS/2024/V11I12/1021833ijaas202412022.html" '
             'name="citation_abstract_html_url" />')

ABSTRACT = ("This study examines how small firms adopt new tools for their customers. Using a survey of ninety owners, "
            "it finds that tools built around the customer raise sales and loyalty, and it suggests ways to use them.")

NOTE = '<p style="text-align: justify;">&nbsp;*&nbsp;Corresponding Author.&nbsp;</p>'

BYLINE_NUMBERED = (
    '<p style="text-align: justify;"><strong>&nbsp;Author(s):&nbsp;</strong></p>'
    '<p style="text-align: justify;">&nbsp;Ana Example<sup> 1</sup>, Ben Sample<sup> 2, </sup>*, Chen Third<sup> 1, 3</sup></p>'
    '<p style="text-align: justify;"><strong>&nbsp;Affiliation(s):</strong></p>'
    '<p><sup>&nbsp;</sup><em><sup>1</sup>Faculty of Science, Example University, Town, Country<br />'
    '&nbsp;<sup>2</sup>Faculty of Accounting, Example University, Town, Country<br />'
    '&nbsp;<sup>3</sup>Institute of Climate, Other University, City, Country</em></p>')

BYLINE_SHARED = (
    '<p style="text-align: justify;"><strong>&nbsp;Author(s):&nbsp;</strong></p>'
    '<p class="citation_author" style="text-align: justify;">&nbsp;Ana Example *, Ben Sample</p>'
    '<p style="text-align: justify;"><strong>&nbsp;Affiliation(s):</strong></p>'
    '<p><sup>&nbsp;</sup><em>Faculty of Science, Example University, Town, Country</em></p>')


def _body_2023(byline=BYLINE_NUMBERED, note=NOTE, ack="No Acknowledgment.", extra=""):
    return (f'{byline}<p style="text-align: justify;"><a href="x.pdf">Full Text - PDF</a></p>{note}'
            '<p style="text-align: justify;"><strong>&nbsp;Abstract:</strong></p>'
            f'<p style="text-align: justify; margin-left: 40px;">{ABSTRACT}</p>'
            '<p style="text-align: justify;">&nbsp;&copy; 2023&nbsp;The Authors. Published by IASE.</p>'
            f'{extra}'
            '<p style="text-align: justify;"><strong>&nbsp;Acknowledgment&nbsp;</strong></p>'
            f'<p style="text-align: justify; margin-left: 40px;">{ack}</p>'
            '<p style="text-align: justify;"><strong>&nbsp;</strong><strong>Compliance with ethical standards</strong></p>')


def _page(head, body):
    return f"<html><head>{head}</head><body><table><tr><td>{body}</td></tr></table></body></html>"


def _parse_page(html):
    return parse_page(html.encode(), "doi", URL)


def _parse(html):
    return ScienceGate(BeautifulSoup(html, "lxml")).parse()


REF_1 = ('Doe J and Roe R (2020). A first paper. Journal of Things, 4(3): 228-247.&nbsp;'
         '<a href="https://doi.org/10.1108/JHTT-01-2013-0002" target="_blank">https://doi.org/10.1108/JHTT-01-2013-0002</a>'
         '&nbsp; &nbsp;<strong><a href="https://scholar.google.com/scholar?as_q=&quot;A first paper&quot;">'
         '[Google Scholar]</a></strong>')
REF_2 = ('Poe K (2017). A second book. Example Press, City.&nbsp; &nbsp;<strong><a href="https://scholar.google.com/'
         'scholar?as_q=&quot;A second book&quot;">[Google Scholar]</a></strong> <strong>PMid:34398916</strong>')


def _refs(heading, items):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return f'<p><span>------</span></p>{heading}<ol>{lis}</ol>'


# --- the six existing fields, through parse_page ---

def test_2023_page_without_meta_tags_reads_byline_and_numbered_affiliations():
    out = _parse_page(_page(HEAD_2023, _body_2023()))
    assert [a["name"] for a in out["authors"]] == ["Ana Example", "Ben Sample", "Chen Third"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Faculty of Science, Example University, Town, Country"],
        ["Faculty of Accounting, Example University, Town, Country"],
        ["Faculty of Science, Example University, Town, Country", "Institute of Climate, Other University, City, Country"],
    ]


def test_star_explained_by_the_note_marks_the_corresponding_author():
    out = _parse_page(_page(HEAD_2023, _body_2023()))
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ben Sample"]


def test_star_without_the_note_marks_no_one():
    out = _parse_page(_page(HEAD_2023, _body_2023(note="")))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_one_unnumbered_affiliation_goes_to_every_author():
    out = _parse_page(_page(HEAD_2024, _body_2023(byline=BYLINE_SHARED)))
    assert [a["name"] for a in out["authors"]] == ["Ana Example", "Ben Sample"]
    assert all([x["name"] for x in a["affiliations"]] == ["Faculty of Science, Example University, Town, Country"]
               for a in out["authors"])
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Example"]


def test_abstract_after_its_heading_2023():
    assert _parse_page(_page(HEAD_2023, _body_2023()))["abstract"] == ABSTRACT


def test_abstract_in_article_abstract_paragraph_2024():
    body = _body_2023(byline=BYLINE_SHARED).replace(
        '<p style="text-align: justify;"><strong>&nbsp;Abstract:</strong></p>', '<h3>&nbsp;Abstract</h3>').replace(
        '<p style="text-align: justify; margin-left: 40px;">This study',
        '<p class="article_abstract" style="text-align: justify; margin-left: 40px;">This study')
    assert _parse_page(_page(HEAD_2024, body))["abstract"] == ABSTRACT


def test_page_from_another_site_with_the_same_headings_is_not_claimed():
    head = HEAD_2023.replace("science-gate.com", "example-journals.org")
    html = _page(head, _body_2023())
    assert not ScienceGate(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert not ScienceGate(BeautifulSoup(html, "lxml")).authors_found()


# --- the three new fields, through parse() ---

def test_acknowledgment_text_is_returned_and_placeholder_is_none():
    ack = "We acknowledge the financial support granted by the Ministry under grant (600-X/5/3)."
    assert _parse(_page(HEAD_2023, _body_2023(ack=ack)))["acknowledgments"] == ack
    assert _parse(_page(HEAD_2023, _body_2023()))["acknowledgments"] is None
    assert _parse(_page(HEAD_2023, _body_2023(ack="<span>No Acknowledgment</span>.&nbsp;")))["acknowledgments"] is None


def test_funding_section_is_the_funding_statement():
    funding = "This work was supported by the Science Fund (20CXTD0062)."
    extra = ('<p style="text-align: justify;"><strong>&nbsp;Funding</strong></p>'
             f'<p style="text-align: justify; margin-left: 40px;">{funding}</p>')
    out = _parse(_page(HEAD_2023, _body_2023(extra=extra)))
    assert out["funding_statement"] == funding
    assert _parse(_page(HEAD_2023, _body_2023()))["funding_statement"] is None


def test_reference_list_with_matching_count_is_complete():
    refs = _refs("<h3>&nbsp;References (2)</h3>", [REF_1, REF_2])
    out = _parse(_page(HEAD_2024, _body_2023(byline=BYLINE_SHARED) + refs))
    assert out["references"] == [
        {"position": 1, "raw": "Doe J and Roe R (2020). A first paper. Journal of Things, 4(3): 228-247. "
                               "https://doi.org/10.1108/JHTT-01-2013-0002",
         "doi": "10.1108/JHTT-01-2013-0002"},
        {"position": 2, "raw": "Poe K (2017). A second book. Example Press, City. PMid:34398916", "doi": None},
    ]
    assert out["references_complete"] is True


def test_google_scholar_link_with_brackets_outside_it_is_dropped():
    ref = ('<span>Doe J (2020). A first paper. Journal of Things, 107: 509-521.&nbsp;</span>'
           '<a href="https://doi.org/10.1016/j.x.2020.02.002"><span>https://doi.org/10.1016/j.x.2020.02.002</span></a>'
           ' &nbsp;&nbsp;<strong>[</strong><a href="https://scholar.google.com/scholar?as_q=&quot;A first paper&quot;">'
           '<strong>Google Scholar</strong></a><strong>]</strong>')
    out = _parse(_page(HEAD_2024, _body_2023(byline=BYLINE_SHARED) + _refs("<h3>&nbsp;References (1)</h3>", [ref])))
    assert out["references"] == [{"position": 1, "raw": "Doe J (2020). A first paper. Journal of Things, 107: 509-521. "
                                                        "https://doi.org/10.1016/j.x.2020.02.002",
                                  "doi": "10.1016/j.x.2020.02.002"}]


def test_reference_list_under_a_2023_heading_is_read():
    refs = _refs('<p style="text-align: justify;"><strong>&nbsp;References (2)</strong></p>', [REF_1, REF_2])
    out = _parse(_page(HEAD_2023, _body_2023() + refs))
    assert len(out["references"]) == 2 and out["references_complete"] is True


def test_reference_count_that_does_not_match_is_not_complete():
    refs = _refs("<h3>&nbsp;References (3)</h3>", [REF_1, REF_2])
    out = _parse(_page(HEAD_2024, _body_2023(byline=BYLINE_SHARED) + refs))
    assert len(out["references"]) == 2
    assert out["references_complete"] is False
