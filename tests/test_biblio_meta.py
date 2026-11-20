"""Volume, issue and pages from a page's citation meta tags (oxjob #1098 step 2a).

OJS repositories lose the volume and issue on the way into OpenAlex (oai_dc repeats dc:source and only the ISSN is
kept); the article page states them in its Highwire tags. The head below is cut down from an OJS 3 article page
(Global Age, 18 Nov 2026: citation_volume 1, citation_issue 1), with the host swapped for the tests' example host.
"""
from bs4 import BeautifulSoup

from parseland_lib.biblio_meta import meta_biblio
from parseland_lib.parse import parse_page

URL = "https://journals.example.org/index.php/ojs/article/view/2"
OJS_HEAD = (
    '<meta name="generator" content="Open Journal Systems 3.4.0.5"/>'
    '<meta name="DC.Source.Issue" content="1"/><meta name="DC.Source.Volume" content="1"/>'
    '<meta name="citation_journal_title" content="Global Age"/><meta name="citation_issn" content="3103-3660"/>'
    '<meta name="citation_author" content="A. Author"/><meta name="citation_title" content="An article"/>'
    '<meta name="citation_date" content="2025/06/30"/>'
    '<meta name="citation_volume" content="1"/><meta name="citation_issue" content="1"/>'
    '<meta name="citation_firstpage" content="5"/><meta name="citation_lastpage" content="24"/>'
    f'<meta name="citation_abstract_html_url" content="{URL}"/>'
    '<meta name="citation_pdf_url" content="https://journals.example.org/index.php/ojs/article/download/2/1"/>'
)


def _soup(head):
    return BeautifulSoup(f"<html><head>{head}</head><body><p>text</p></body></html>", "lxml")


def test_ojs_article_head():
    assert meta_biblio(_soup(OJS_HEAD)) == {"volume": "1", "issue": "1", "first_page": "5", "last_page": "24"}


def test_parse_page_returns_biblio_for_pmh_and_doi():
    html = f"<html><head>{OJS_HEAD}</head><body><h1>An article</h1></body></html>"
    for namespace in ("pmh", "doi"):
        assert parse_page(html.encode(), namespace, URL)["biblio"] == {
            "volume": "1", "issue": "1", "first_page": "5", "last_page": "24"}


def test_no_tags_is_none():
    assert meta_biblio(_soup('<meta name="citation_title" content="An article"/>')) is None
    assert parse_page("<html><body><p>hello world</p></body></html>", "pmh")["biblio"] is None


def test_prism_fallback():
    head = ('<meta name="prism.volume" content="53"/><meta name="prism:number" content="3"/>'
            '<meta name="prism.startingPage" content="e1021"/>')
    assert meta_biblio(_soup(head)) == {"volume": "53", "issue": "3", "first_page": "e1021", "last_page": None}


def test_citation_tag_beats_prism_and_first_usable_value_wins():
    head = ('<meta name="prism.volume" content="99"/><meta name="citation_volume" content=" "/>'
            '<meta name="citation_volume" content="12"/><meta name="citation_volume" content="13"/>'
            '<meta name="citation_issue" content="Suppl\n 2"/>')
    assert meta_biblio(_soup(head)) == {"volume": "12", "issue": "Suppl 2", "first_page": None, "last_page": None}


def test_a_sentence_or_a_dash_is_not_a_volume():
    head = ('<meta name="citation_volume" content="Volume information is not available for this article yet"/>'
            '<meta name="citation_issue" content="-"/><meta name="citation_firstpage" content="117"/>')
    assert meta_biblio(_soup(head)) == {"volume": None, "issue": None, "first_page": "117", "last_page": None}
