"""Tech Science Press (techscience.com) article pages (oxjob #2210, Parseland swarm pilot).

Markup is cut down from stored techscience.com pages. Two layouts share one header block (div.bq2 > h1 + byline):
issue pages carry p.authors / p.affiliation / p.Corresponding and Highwire meta tags whose description is a truncated
SEO blurb; online-first pages ("/online/detail/") put authors, affiliations and the correspondence note in one <p>
split by <br/> and carry no citation meta at all. The abstract sits in div.bq4 under its "Abstract" heading.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.techscience import TechSciencePress

URL = "https://www.techscience.com/CMES/v144n1/63273"
ABSTRACT = ("This study aims to investigate the propagation of harmonic waves in nonlocal magneto-electro-elastic "
            "laminated composites with interface stress imperfections using an analytical approach. Dispersion curves, "
            "mode shapes, and natural frequencies were calculated for sandwich plates composed of BaTiO3 and CoFe2O4.")
ABSTRACT_HTML = ABSTRACT.replace("BaTiO3", "BaTiO<sub>3</sub>").replace("CoFe2O4", "CoFe<sub>2</sub>O<sub>4</sub>")
AFF1 = "Department of Civil Engineering, Example Tech University, Hsinchu, 30010, Taiwan"
AFF2 = "School of Mechanics, Example University of Technology, Dalian, 116024, China"

ISSUE_HEAD = ('<meta property="og:url" content="https://www.techscience.com/CMES/v144n1/63273"/>'
              '<meta name="citation_publisher" content="Tech Science Press"/>'
              '<meta name="citation_author" content="Ana Ruiz"/><meta name="citation_author" content="Bo Chen"/>'
              '<meta name="citation_author" content="Carl Diaz"/>'
              '<meta name="description" content="This study aims to investigate the propagation of harmonic waves in '
              'nonlocal magneto-electro-elastic laminated composites with interface stress imperfections using an '
              'analytical appr... | Find, read and cite all the research you need on Tech Science Press"/>')
ONLINE_HEAD = '<link rel="stylesheet" type="text/css" href="https://www.techscience.com/static/css/style.css?t=20230215"/>'


def _abstract_block(tag="h2"):
    return (f'<div class="bq4" id="section_abstract"><{tag} class="xiaobt">Abstract</{tag}> {ABSTRACT_HTML} <hr/>'
            f'<{tag} class="xiaobt">Keywords</{tag}><div itemprop="keywords">nonlocal; laminate</div><hr/></div>')


def _page(head, header, abstract_tag="h2"):
    return (f'<html><head>{head}</head><body><div class="html-article-content xxjs"><div class="bq2">'
            f'<div class="crossmark_svg_box"></div><h1 class="title citation_title">A title</h1>{header}</div>'
            f'<div class="bq3"><a href="{URL}/pdf">Download PDF</a></div>{_abstract_block(abstract_tag)}'
            '</div></body></html>')


ISSUE_HEADER = ('<p class="authors citation_author"> Ana Ruiz<sup>1,*</sup>, Bo Chen<sup>2</sup>, '
                'Carl Diaz<sup>1,2</sup> </p>'
                f'<p class="affiliation"> 1 {AFF1}<br/>2 {AFF2} </p>'
                '<p class="Corresponding"> * Corresponding Author: Ana Ruiz. Email: '
                '<img alt="email" src="https://www.techscience.com/psh.php?mailname=a@example.edu"/> </p>'
                '<p class="cite-info"><i>CMES</i> <b>2025</b>, <i>144</i>(1), 841-872.</p>')

ONLINE_HEADER = ('<p> Ana Ruiz<sup>1</sup>, Bo Chen<sup>2,*</sup> <br/>'
                 f' 1 {AFF1}<br/>2 {AFF2} <br/>'
                 ' * Corresponding Author: Bo Chen. Email: <img alt="email" src="https://www.techscience.com/psh.php?mailname=b@example.edu"/>'
                 ' <p class="cite-info"><i>Canadian Journal of Urology</i></p>'
                 ' <p><strong>Received</strong> 27 March 2025</p></p>')


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _soup(html):
    return BeautifulSoup(html, "lxml")


def _affs(author):
    return [a["name"] if isinstance(a, dict) else a for a in author["affiliations"]]


def test_issue_page_authors_and_numbered_affiliations():
    out = _out(_page(ISSUE_HEAD, ISSUE_HEADER))
    assert [a["name"] for a in out["authors"]] == ["Ana Ruiz", "Bo Chen", "Carl Diaz"]
    assert [_affs(a) for a in out["authors"]] == [[AFF1], [AFF2], [AFF1, AFF2]]


def test_issue_page_corresponding_star_with_note():
    out = _out(_page(ISSUE_HEAD, ISSUE_HEADER))
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Ruiz"]


def test_abstract_is_the_visible_block_not_the_truncated_meta():
    out = _out(_page(ISSUE_HEAD, ISSUE_HEADER))
    assert out["abstract"] == ABSTRACT


def test_visible_byline_name_beats_shortened_meta_name():
    head = ISSUE_HEAD.replace('content="Carl Diaz"', 'content="Carl"')
    header = ISSUE_HEADER.replace("Carl Diaz", "Carl Diaz Moreno")
    out = _out(_page(head, header))
    assert out["authors"][2]["name"] == "Carl Diaz Moreno"


def test_single_unnumbered_affiliation_goes_to_every_author():
    header = ('<p class="authors citation_author"> Ana Ruiz<sup>*</sup>, Bo Chen<sup></sup> </p>'
              f'<p class="affiliation"> {AFF1} </p>'
              '<p class="Corresponding"> * Corresponding Author: Ana Ruiz. Email: </p>')
    out = _out(_page(ISSUE_HEAD, header))
    assert [_affs(a) for a in out["authors"]] == [[AFF1], [AFF1]]
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Ruiz"]


def test_online_first_page_without_meta_tags():
    out = _out(_page(ONLINE_HEAD, ONLINE_HEADER, abstract_tag="h3"))
    assert [a["name"] for a in out["authors"]] == ["Ana Ruiz", "Bo Chen"]
    assert [_affs(a) for a in out["authors"]] == [[AFF1], [AFF2]]
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Bo Chen"]
    assert out["abstract"] == ABSTRACT


def test_correspondence_note_variant_and_unnumbered_affiliation():
    header = ('<p> Ana Ruiz<sup>*</sup>, Bo Chen<sup></sup> <br/>'
              f' {AFF1}<br/>\n* Correspondence: Ana Ruiz, a@example.edu <p class="cite-info"><i>J</i></p></p>')
    out = _out(_page(ONLINE_HEAD, header, abstract_tag="h3"))
    assert [a["name"] for a in out["authors"]] == ["Ana Ruiz", "Bo Chen"]
    assert [_affs(a) for a in out["authors"]] == [[AFF1], [AFF1]]
    assert [a["name"] for a in out["authors"] if a["is_corresponding"]] == ["Ana Ruiz"]


def test_star_without_a_note_marks_no_one():
    header = ISSUE_HEADER.split('<p class="Corresponding">')[0]
    out = _out(_page(ISSUE_HEAD, header))
    assert [a["name"] for a in out["authors"]] == ["Ana Ruiz", "Bo Chen", "Carl Diaz"]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_other_site_with_the_same_markup_is_not_claimed():
    head = (ISSUE_HEAD.replace("www.techscience.com", "www.example-press.org").replace("Tech Science Press", "Example Press")
            + ONLINE_HEAD.replace("www.techscience.com", "www.example-press.org"))
    parser = TechSciencePress(_soup(_page(head, ISSUE_HEADER)))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_pdf_viewer_page_is_not_read():
    html = (f'<html><head>{ISSUE_HEAD}</head><body id="pdf-view"><div class="sidebar"><ul id="pdf-article-tabs">'
            '<li><strong>PDF</strong></li></ul></div><div class="pdf"><p>The PDF file you selected should load here.</p>'
            '</div></body></html>')
    parser = TechSciencePress(_soup(html))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_new_fields_absent_on_abstract_pages():
    parsed = TechSciencePress(_soup(_page(ISSUE_HEAD, ISSUE_HEADER))).parse()
    assert parsed["acknowledgments"] is None
    assert parsed["funding_statement"] is None
    assert parsed["references"] is None
    assert parsed["references_complete"] is False


def test_affiliation_number_glued_to_its_text():
    header = ISSUE_HEADER.replace(f"2 {AFF2}", f"2{AFF2}")
    out = _out(_page(ISSUE_HEAD, header))
    assert [_affs(a) for a in out["authors"]] == [[AFF1], [AFF2], [AFF1, AFF2]]
