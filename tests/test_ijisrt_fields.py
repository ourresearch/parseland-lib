"""IJISRT (International Journal of Innovative Science and Research Technology, ijisrt.com) article pages (oxjob #2210).

Markup is cut down from stored ijisrt.com pages (13 Nov 2026). The site has no citation_* meta tags: the byline is one
"Authors : A; B; C" paragraph in the Authors tab, the abstract sits in the Abstract tab pane (div#profile), and the
reference list is an <ol> after a "References :" paragraph. No affiliations or corresponding-author marks are shown.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ijisrt import IJISRT

URL = "https://www.ijisrt.com/a-sample-article"
ABSTRACT = ("This research investigates the use of Long-\nterm Recurrent Convolutional Networks (LRCNs) for violence "
            "detection in video surveillance systems and integrates the model with a bot for real-time alerting.")

REFS_ONE_LIST = ('<p style="text-align: justify;"><strong>References : </strong>\n<ol>'
                 '<li><span>Traore, A. (2020). Violence Detection in Videos. 154-159. 10.1109/SMC42975.2020.9282971.</span></li>'
                 '<li><span>Allen, R. (2013). <em>The International Handbook of Public Financial Management </em>. Palgrave.</span></li>'
                 '<li><span>Zou, J. (2019). A primer. <a href="https://doi.org/10.1038/s41588-018-0295-5">https://doi.org/10.1038/s41588-018-0295-5</a></span></li>'
                 '</ol>')


def _page(authors="Ashwin Saji Kumar; Dr. Bency Wilson; Roshan Xavier", refs=REFS_ONE_LIST, abstract_in_authors=True,
          doi="10.38124/ijisrt/IJISRT24APR2603"):
    abstract_p = (f'<p style="text-align: justify;"><strong>Abstract : </strong>\n{ABSTRACT} </p>'
                  if abstract_in_authors else "")
    return (f'<html><head><title>A sample article| International Journal of Innovative Science and Research Technology'
            f'</title><meta name="description" content=""/></head><body>'
            f'<p class="title-paper"><strong>A Sample Article</strong></p>'
            f'<div class="tabbable"><div class="tab-content">'
            f'<div id="authors" class="tab-pane active">'
            f'<p><strong>Authors : </strong>\n {authors} </p>'
            f'<p><strong>Volume/Issue : </strong> Volume 9 - 2024, Issue 4 - April </p>'
            f'<p><strong>DOI : </strong><a href="https://doi.org/{doi}" class="black">https://doi.org/{doi}</a></p>'
            f'{abstract_p}'
            f'<p style="text-align: justify;"><strong>Keywords : </strong> Violence Detection, LSTM. </p>'
            f'{refs}</div>'
            f'<div id="profile" class="tab-pane">\n{ABSTRACT} </div>'
            f'<div id="messages" class="tab-pane"><p><strong>Keywords : </strong> Violence Detection, LSTM.</p></div>'
            f'</div></div></body></html>')


def _parse(html):
    return IJISRT(BeautifulSoup(html, "lxml")).parse()


def test_byline_split_on_semicolons_without_honorifics():
    out = parse_page(_page().encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Ashwin Saji Kumar", "Bency Wilson", "Roshan Xavier"]


def test_no_affiliations_and_no_corresponding_author():
    out = parse_page(_page().encode(), "doi", URL)
    assert all(a["affiliations"] == [] for a in out["authors"])
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_abstract_from_abstract_tab():
    out = parse_page(_page().encode(), "doi", URL)
    assert out["abstract"].startswith("This research investigates the use of Long-")
    assert out["abstract"].endswith("real-time alerting.")
    assert "Abstract :" not in out["abstract"] and "Keywords" not in out["abstract"]


def test_abstract_when_only_the_abstract_tab_holds_it():
    out = parse_page(_page(abstract_in_authors=False, refs="").encode(), "doi", URL)
    assert out["abstract"].startswith("This research investigates")
    assert len(out["authors"]) == 3


def test_reference_list_in_order_with_dois():
    refs = _parse(_page())["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("Traore, A. (2020). Violence Detection in Videos.")
    assert refs[0]["doi"] == "10.1109/SMC42975.2020.9282971"
    assert refs[1]["doi"] is None
    assert refs[2]["doi"] == "10.1038/s41588-018-0295-5"


def test_single_ordered_list_is_complete():
    assert _parse(_page())["references_complete"] is True


def test_list_continued_in_a_second_ol_is_complete():
    refs = ('<p><strong>References : </strong></p><div class="WordSection1"><ol><li>First, A. (2020). One.</li>'
            '<li>Second, B. (2021). Two.</li></ol><ol><li value="3">Third, C. (2022). Three.</li></ol></div>')
    out = _parse(_page(refs=refs))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references_complete"] is True


def test_gap_in_numbering_is_not_complete():
    refs = ('<p><strong>References : </strong></p><ol><li>First, A. (2020). One.</li></ol>'
            '<ol><li value="5">Fifth, E. (2022). Five.</li></ol>')
    assert _parse(_page(refs=refs))["references_complete"] is False


def test_reference_text_outside_the_list_is_not_complete():
    refs = ('<p><strong>References : </strong></p><ol><li>First, A. (2020). One.</li></ol>'
            '<p>2. Sekaran, U. (2016). Research methods for business.</p>')
    out = _parse(_page(refs=refs))
    assert len(out["references"]) == 1
    assert out["references_complete"] is False


def test_no_reference_list():
    out = _parse(_page(refs=""))
    assert out["references"] == []
    assert out["references_complete"] is False


def test_no_acknowledgments_or_funding_on_these_pages():
    out = _parse(_page())
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_same_markup_on_another_site_is_not_claimed():
    html = _page(doi="10.5281/zenodo.1234567").replace("International Journal of Innovative Science and Research "
                                                       "Technology", "Another Journal")
    parser = IJISRT(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
