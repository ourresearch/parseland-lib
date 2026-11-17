"""Atlantis Press article pages on atlantis-press.com (oxjob #2330).

Markup is cut down from stored atlantis-press.com pages (17 Nov 2026). The site's own template prints the abstract
whole in a label/value list (<dt id="abstract-0">Abstract</dt><dd>...</dd>; older pages say id="abstract"). Some
authors end their abstract without a full stop, and the shared heading reader turns such a text down as a cut
preview, so the page lost its abstract. The parser reads that field; the byline stays the generic parser's.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.atlantis_press import AtlantisPress

URL = "https://doi.org/10.2991/icoie-18.2019.123"
ABS_URL = "https://www.atlantis-press.com/proceedings/icoie-18/55912978"
NO_STOP = ("The objective of this research is to find the influence of ethical leadership, integrity and affective "
           "commitment on the discretionary behaviour of teachers. This research uses a quantitative approach with a "
           "survey of 198 teachers, and the result shows a direct positive effect of ethical leadership on trust")
WITH_STOP = ("In this paper, the case study method is used to analyze the impact of performance commitment on a listed "
             "company. It is found that performance commitment to a certain extent reduces the risks taken by the "
             "acquirer in the acquisition process.")


def _page(abstract, abs_url=ABS_URL, label_id="abstract-0", names=("Ana Author", "Ben Writer")):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    byline = ", ".join(f"<span><span>{n}</span></span>" for n in names)
    abstract_row = (f'<dt class="src-components-detailLabel" id="{label_id}">Abstract</dt>'
                    f'<dd class="src-components-detailDefinition"><div class="src-components-content textContent">'
                    f"<p>{abstract}</p></div></dd>") if abstract else ""
    return (f'<html><head><meta charset="utf-8" />'
            f'<meta name="description" content="{(abstract or "")[:120]}"/>'
            f'<meta name="citation_title" content="A conference paper"/>{metas}'
            f'<meta name="citation_publisher" content="Atlantis Press"/>'
            f'<meta name="citation_abstract_html_url" content="{abs_url}"/>'
            f'<meta name="citation_doi" content="10.2991/icoie-18.2019.123"/></head><body><article>'
            f'<h1 class="src-components-title">A conference paper</h1>'
            f'<div class="src-components-detailList"><div><div class="src-components-detailLabel">Authors</div>'
            f'<div class="src-components-detailDefinition"><div>{byline}</div></div></div></div>'
            f'<div class="src-components-detailList"><div><div class="src-components-detailLabel">Corresponding Author'
            f'</div><div class="src-components-detailDefinition"><div><span><span>{names[0]}</span></span></div></div>'
            f'</div></div>'
            f'<dl class="src-components-detailList textContent"><dt class="src-components-detailLabel">DOI</dt>'
            f'<dd class="src-components-detailDefinition"><a href="https://dx.doi.org/10.2991/x">'
            f'https://doi.org/10.2991/x</a></dd><dt class="src-components-detailLabel">Keywords</dt>'
            f'<dd class="src-components-detailDefinition">leadership; trust</dd>{abstract_row}'
            f'<dt class="src-components-detailLabel">Copyright</dt>'
            f'<dd class="src-components-detailDefinitionCopyright textContent">&#169; 2019, the Authors. Published by '
            f'Atlantis Press.</dd></dl></article></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _soup(html):
    return BeautifulSoup(html, parser="lxml", features="lxml")


def test_abstract_without_a_closing_full_stop_is_read():
    assert _parse(_page(NO_STOP))["abstract"] == NO_STOP


def test_abstract_with_a_full_stop_is_read_as_before():
    assert _parse(_page(WITH_STOP))["abstract"] == WITH_STOP


def test_older_pages_label_the_abstract_without_a_number():
    assert _parse(_page(NO_STOP, label_id="abstract"))["abstract"] == NO_STOP


def test_byline_and_corresponding_author_are_the_generic_parsers():
    authors = _parse(_page(NO_STOP))["authors"]
    assert [a["name"] for a in authors] == ["Ana Author", "Ben Writer"]
    assert [a["is_corresponding"] for a in authors] == [True, False]
    assert all(a["affiliations"] == [] for a in authors)


def test_page_is_claimed_by_its_abstract_url():
    parser = AtlantisPress(_soup(_page(NO_STOP)))
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_page_without_an_abstract_field_is_left_to_the_generic_parser():
    parser = AtlantisPress(_soup(_page(None)))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_springer_link_copy_of_an_atlantis_chapter_is_not_claimed():
    # Atlantis moved its proceedings to Springer Link: those pages say "Atlantis Press" too, but are Springer's
    html = _page(NO_STOP, abs_url="https://link.springer.com/chapter/10.2991/978-94-6463-568-3_12")
    parser = AtlantisPress(_soup(html))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_look_alike_page_on_another_host_is_not_claimed():
    html = _page(NO_STOP, abs_url="https://www.example-press.com/proceedings/x/1")
    assert not AtlantisPress(_soup(html)).authors_found()


def test_no_new_fields_on_these_pages():
    out = AtlantisPress(_soup(_page(NO_STOP))).parse()
    assert not out.get("references") and not out.get("acknowledgments") and not out.get("funding_statement")
