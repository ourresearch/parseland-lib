"""Scientific.Net (Trans Tech Publications) article pages: corresponding author and reference list (oxjob #2268).

Markup is cut down from stored scientific.net pages (16 Nov 2026, #2268). The byline starts with a "Send message to
Corresponding Author" mail icon and stars that author's name. Every page carries citation_reference meta tags, so a page
whose reference list names Elsevier ("Elsevier, Amsterdam") also satisfies Elsevier's meta-tag claim, and Elsevier's
parser, first in line, used to win the page and mark no one. The visible reference list (div.references-block, one
div.reference-text per entry, "[n]" in a span, a "DOI:" doi.org link when there is one) is the whole list; the meta tags
mix printed text with Highwire key=value entries, which the shared meta-tag reader rightly refuses. Hand-cut markup;
no network.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.trans_tech import TransTechPub

URL = "https://www.scientific.net/MSF.899.173"
PUBLISHER = '<meta name="citation_publisher" content="Trans Tech Publications Ltd"/>'
ABSTRACT = "A real abstract that states what the study did and what it found in the kinetics data. " * 3


def _byline(starred=True):
    icon = ('<a class="inline-icon mail-icon-red author-send-message" href="#" '
            'data-url="/Paper/_Message?paperId=1&amp;personId=2" title="Send message to Corresponding Author"></a>'
            if starred else "")
    star = "*" if starred else ""
    return ('<div class="papers-block-info col-lg-12"><div class="row">'
            '<div class="info-row-name normal-text-gray col-md-2"><div class="row"><p>Authors:</p></div></div>'
            '<div class="info-row-content semibold-middle-text col-md-10"><div class="row">'
            f'{icon}<a href="/author-papers/ada-author">Ada Author</a>{star}, '
            '<a href="/author-papers/bo-writer">Bo Writer</a>, <a href="/author-papers/cy-scholar">Cy Scholar</a>'
            '                    </div></div></div></div>')


def _entry(label, text, doi=None):
    doi_p = (f'<p>\n DOI: <a href="https://doi.org/{doi}">{doi}</a>\n</p>' if doi else "")
    return (f'<div class="reference-text volume-info-text"><p>\n<span>{label}</span>\n {text}\n</p>{doi_p}'
            '<p><a href="https://scholar.google.com/scholar_lookup?title=x&amp;doi=10.4028%2Fwww.scientific.net%2Fmsf.1">'
            'Google Scholar</a></p></div>')


def _references(*entries):
    return ('<div class="reference-collapse col-xs-12"><div class="panel-group" id="references-panel">'
            '<a class="panel-title" data-toggle="collapse" href="#reference-panel-element">References</a>'
            '<div id="reference-panel-element" class="panel-collapse collapse"><div class="panel-body">'
            '<div class="references-block">' + "".join(entries) + '</div></div></div></div></div>')


ENTRIES = [
    _entry("[1]", "A. T. Matos. Tratamento de residuos agroindustriais. Universidade Federal de Vicosa, (2005)."),
    _entry("[2]", "O. Levenspiel, Chemical Reaction Engineering, 3rd ed., Wiley, New York, 1999.",
           doi="10.1021/ie990488g"),
    _entry("[3]", "J. Smith, Thermal analysis of biomass, Elsevier, Amsterdam, 2010."),
]
METAS = ('<meta name="citation_reference" content="A. T. Matos. Tratamento de residuos agroindustriais."/>'
         '<meta name="citation_reference" content="citation_title=Chemical Reaction Engineering; citation_doi=10.1021/ie990488g"/>'
         '<meta name="citation_reference" content="J. Smith, Thermal analysis of biomass, Elsevier, Amsterdam, 2010."/>')


def _page(body, head=PUBLISHER + METAS):
    return (f'<html><head>{head}<meta name="citation_author" content="Ada Author"/>'
            f'<meta name="citation_author" content="Bo Writer"/><meta name="citation_author" content="Cy Scholar"/>'
            f'</head><body>{body}<div class="abstract-block-description"><h3>Abstract:</h3>'
            f'<p class="normal-text">{ABSTRACT}</p></div></body></html>')


def _parse(body, head=PUBLISHER + METAS):
    return TransTechPub(BeautifulSoup(_page(body, head), "lxml")).parse()


def test_starred_author_is_corresponding():
    out = parse_page(_page(_byline() + _references(*ENTRIES)).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Ada Author", "Bo Writer", "Cy Scholar"]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]
    assert out["abstract"].startswith("A real abstract")


def test_elsevier_in_a_reference_meta_does_not_steal_the_page():
    # the third citation_reference names Elsevier, which satisfies Elsevier's meta-tag claim
    out = parse_page(_page(_byline() + _references(*ENTRIES)).encode(), "doi", URL)
    assert out["authors"][0]["is_corresponding"] is True


def test_unstarred_byline_marks_no_one():
    out = parse_page(_page(_byline(starred=False) + _references(*ENTRIES)).encode(), "doi", URL)
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_reference_list_is_read_from_the_page():
    parsed = _parse(_byline() + _references(*ENTRIES))
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("A. T. Matos. Tratamento")
    assert not refs[0]["raw"].startswith("[1]")
    assert refs[1]["doi"] == "10.1021/ie990488g"
    assert refs[0]["doi"] is None  # the Google Scholar link's doi= is the citing article's, never the entry's
    assert parsed["references_complete"] is True


def test_reference_list_reaches_parse_page_with_key_value_metas():
    out = parse_page(_page(_byline() + _references(*ENTRIES)).encode(), "doi", URL)
    assert len(out["references"]) == 3
    assert out["references_complete"] is True


def test_numbering_with_a_hole_is_not_complete():
    parsed = _parse(_byline() + _references(ENTRIES[0], ENTRIES[1].replace("[2]", "[3]")))
    assert len(parsed["references"]) == 2
    assert parsed["references_complete"] is False


def test_meta_count_that_disagrees_is_not_complete():
    parsed = _parse(_byline() + _references(ENTRIES[0], ENTRIES[1]))  # 3 citation_reference tags, 2 entries shown
    assert parsed["references_complete"] is False


def test_page_without_references_has_none():
    parsed = _parse(_byline())
    assert not parsed.get("references")
    assert not parsed.get("references_complete")


def test_look_alike_page_of_another_publisher_is_not_claimed():
    head = '<meta name="citation_publisher" content="Elsevier"/>' + METAS
    soup = BeautifulSoup(_page(_byline() + _references(*ENTRIES), head), "lxml")
    assert TransTechPub(soup).is_publisher_specific_parser() is False
