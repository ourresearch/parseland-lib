"""Qeios (qeios.com): affiliations and funding statements from the page's embedded publication data (oxjob #2330).

Markup is cut down from stored Qeios pages (17 Nov 2026). Qeios pages are an unrendered Vue template: the citation_*
meta tags carry the byline (and an institution only when the author picked one from Qeios's list), and the page's
`GLOB.publication = {...}` script holds the rest. Two things the generic parser misses are read from it:
an author's own affiliation text (`affiliation_strings`) when no citation_author_institution tag names one, and the
funding sentence of the Declarations box (`declarations.funding`). A peer review's page also embeds the reviewed
article (`reviewable`): its declarations are that article's, never the review's.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.qeios import Qeios

URL = "https://www.qeios.com/read/UVS7QS"
HEAD = ('<meta name="app-base-url" content="https://www.qeios.com" />'
        '<meta name="citation_journal_title" content="Qeios">'
        '<meta name="citation_issn" content="2632-3834">')


def _page(metas, publication, head=HEAD):
    script = ("window.GLOB = window.GLOB || {};GLOB.publication = " + json.dumps(publication) +
              ";GLOB.publicationType = \"review\";")
    return (f'<html><head><meta charset="utf-8">{head}{metas}</head><body><div id="app">'
            f'<publication-authors-facepile :authors="publication.presentation_authors"></publication-authors-facepile>'
            f'</div><script>{script}</script></body></html>')


def _author(name, affiliation_strings=None, institution=None):
    return {"full_name": name, "affiliation_strings": affiliation_strings,
            "research_institution": {"name": institution} if institution else None}


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


ARTICLE_FUNDING = ("This research was funded by the Ministry of Science, Technological Development and Innovation of "
                   "the Republic of Serbia, grant number 451-03-136/2025-03/ 200017.")
ABSTRACT = ("Intrinsically disordered proteins pose challenges for conventional drug discovery. This study applied a "
            "computational technique to identify potential modulators, screening two databases of approved drugs and "
            "natural products against characteristic interaction frequencies derived from known ligands.")


def test_affiliation_text_fills_an_author_without_an_institution_tag():
    html = _page('<meta name="citation_author" content="Baharak Aghapour">',
                 {"publication_type": "review", "doi": "10.32388/4OS7FW", "declarations": {"coi": "None."},
                  "presentation_authors": [_author("Baharak Aghapour",
                                                   ["nutrition, Tabriz University of Medical Sciences, Iran"])]})
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Baharak Aghapour"]
    assert authors[0]["affiliations"] == [{"name": "nutrition, Tabriz University of Medical Sciences, Iran"}]


def test_institution_tag_is_kept_as_is():
    html = _page('<meta name="citation_author" content="Akhilesh Mishra">'
                 '<meta name="citation_author_institution" content="Maulana Azad Medical College (MAMC)">',
                 {"publication_type": "review", "doi": "10.32388/8DBAPU",
                  "presentation_authors": [_author("Akhilesh Mishra",
                                                   ["Maulana Azad Medical College (MAMC), New Delhi, India"],
                                                   "Maulana Azad Medical College (MAMC)")]})
    assert _parse(html)["authors"][0]["affiliations"] == [{"name": "Maulana Azad Medical College (MAMC)"}]


def test_group_author_of_a_definition_has_no_affiliation():
    html = _page('<meta name="citation_author" content="National Cancer Institute">',
                 {"publication_type": "definition", "doi": "10.32388/4C0926", "presentation_authors": [],
                  "vacant_authors": [{"name": "National Cancer Institute"}]})
    out = _parse(html)
    assert out["authors"] == [{"name": "National Cancer Institute", "affiliations": [], "is_corresponding": None}]
    assert out["funding_statement"] is None


def test_funding_statement_from_declarations():
    pub = {"publication_type": "article", "doi": "10.32388/5DGYBH.2",
           "declarations": {"coi": "No potential competing interests to declare.", "funding": ARTICLE_FUNDING},
           "presentation_authors": [_author("Milan Sencanski", None, "University of Belgrade")]}
    html = _page('<meta name="citation_author" content="Milan Sencanski">'
                 '<meta name="citation_author_institution" content="University of Belgrade">'
                 f'<meta name="citation_abstract" content="{ABSTRACT}">', pub)
    parsed = Qeios(BeautifulSoup(html, "lxml")).parse()
    assert parsed["funding_statement"] == ARTICLE_FUNDING
    assert "references" not in parsed
    out = _parse(html)
    assert out["funding_statement"] == ARTICLE_FUNDING
    assert out["abstract"] == ABSTRACT
    assert out["authors"][0]["affiliations"] == [{"name": "University of Belgrade"}]


def test_no_funding_sentence_is_still_the_funding_statement():
    pub = {"publication_type": "article", "doi": "10.32388/QEOPGL",
           "declarations": {"coi": "No potential competing interests to declare.",
                            "funding": "No specific funding was received for this work."},
           "presentation_authors": [_author("Joseph Bevelacqua")]}
    html = _page('<meta name="citation_author" content="Joseph Bevelacqua">', pub)
    assert _parse(html)["funding_statement"] == "No specific funding was received for this work."


def test_reviewed_articles_declarations_are_not_the_reviews():
    pub = {"publication_type": "review", "doi": "10.32388/8DBAPU",
           "declarations": {"coi": "No potential competing interests to declare."},
           "presentation_authors": [_author("Hossam Saad El-Deen", ["Independent researcher"])],
           "reviewable": {"publication_type": "article",
                          "declarations": {"funding": "This work was supported by a national grant."},
                          "presentation_authors": [_author("Someone Else", ["Another University"])]}}
    html = _page('<meta name="citation_author" content="Hossam Saad El-Deen">', pub)
    parsed = Qeios(BeautifulSoup(html, "lxml")).parse()
    assert parsed.get("funding_statement") is None
    out = _parse(html)
    assert out["funding_statement"] is None
    assert out["authors"] == [{"name": "Hossam Saad El-Deen", "affiliations": [{"name": "Independent researcher"}],
                               "is_corresponding": None}]


def test_page_without_publication_data_keeps_the_meta_tags():
    html = (f'<html><head>{HEAD}<meta name="citation_author" content="Joseph Bevelacqua"></head>'
            f'<body><script>window.GLOB = window.GLOB || {{}};GLOB.authUser = null;</script></body></html>')
    out = _parse(html)
    assert out["authors"] == [{"name": "Joseph Bevelacqua", "affiliations": [], "is_corresponding": None}]
    assert out["funding_statement"] is None


def test_look_alike_page_of_another_site_is_not_claimed():
    # another Laravel + Vue site that embeds the same kind of GLOB.publication data and Highwire tags
    head = ('<meta name="app-base-url" content="https://www.example-preprints.org" />'
            '<meta name="citation_journal_title" content="Example Preprints">')
    html = _page('<meta name="citation_author" content="Ana Lima">',
                 {"publication_type": "article", "declarations": {"funding": "Funded by an example grant."},
                  "presentation_authors": [_author("Ana Lima", ["Universidade Example"])]}, head=head)
    parser = Qeios(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    out = _parse(html)
    assert out["authors"][0]["affiliations"] == []
    assert out["funding_statement"] is None
