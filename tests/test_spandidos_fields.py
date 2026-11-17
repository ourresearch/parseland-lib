"""Spandidos Publications article pages (oxjob #2338): Oncology Letters, Molecular Medicine Reports, International
Journal of Oncology and the house's other journals, ~83K works.

Markup is cut down from stored spandidos-publications.com pages (17 Nov 2026). The citation_* meta tags carry the
names, affiliations and abstract, so the generic parser's reading is kept; what it misses is the corresponding author,
which the byline marks as <li class="corresponding" title="<e-mail>"> (both blind labellers read it so on all six build
pages), and the reference list the full-text pages print as table.ref-list.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.spandidos import Spandidos

URL = "https://www.spandidos-publications.com/10.3892/ol.2018.9098"
ABSTRACT = ("The aryl hydrocarbon receptor is a ligand-dependent transcription factor whose role in osteosarcoma "
            "cells was studied here with chronic exposure to a dioxin and an antagonist, measuring COX-2, PGE2 and "
            "CXCR4 expression over time in MG-63 cells.")
NAMES = ["Yang,Shih-Chieh", "Wu,Chin-Hsien", "Chou,Pai-Chien"]
INST = "Department of Thoracic Medicine, Saint Paul's Hospital, Taoyuan 33069, Taiwan, R.O.C."


def _head(names, publisher="Spandidos Publications"):
    metas = "".join(f'<meta name="citation_author" content="{n}" /><meta name="citation_author_institution" '
                    f'content="{INST}" />' for n in names)
    return (f'<head><meta name="citation_title" content="A title" />{metas}'
            f'<meta name="citation_publisher" content="{publisher}" />'
            f'<meta name="citation_abstract" content="{ABSTRACT}" />'
            f'<meta property="og:url" content="{URL}" /></head>')


def _byline(items):
    return '<ul class="article_details"><li><span class="bold">Authors:</span><ul id="authorshipNames">' + \
        "".join(items) + "</ul></li></ul>"


def _page(names, items, body="", publisher="Spandidos Publications"):
    return f"<html>{_head(names, publisher)}<body><h1 id=\"titleId\">A title</h1>{_byline(items)}{body}</body></html>"


PLAIN = ["<li>Shih-Chieh Yang</li>", "<li>Chin-Hsien  Wu</li>"]
MARKED = '<li class="corresponding"\n\ttitle="baechainchou@gmail.com">Pai-Chien  Chou</li>'


def _flags(html):
    return [(a["name"], a["is_corresponding"]) for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_corresponding_class_marks_that_author_only():
    assert _flags(_page(NAMES, PLAIN + [MARKED])) == [
        ("Yang,Shih-Chieh", False), ("Wu,Chin-Hsien", False), ("Chou,Pai-Chien", True)]


def test_two_marked_authors():
    items = ['<li class="corresponding" title="a@x.cn">Shih-Chieh Yang</li>', PLAIN[1], MARKED]
    assert [flag for _, flag in _flags(_page(NAMES, items))] == [True, False, True]


def test_mark_without_an_email_still_counts():
    # pages from 2009 carry the class with no title
    items = PLAIN + ['<li class="corresponding">Pai-Chien Chou</li>']
    assert [flag for _, flag in _flags(_page(NAMES, items))] == [False, False, True]


def test_no_mark_leaves_flags_unset():
    # pages before 2008 print no mark at all
    items = PLAIN + ["<li>Pai-Chien Chou</li>"]
    assert [flag for _, flag in _flags(_page(NAMES, items))] == [None, None, None]


def test_meta_tags_listing_each_author_twice_mark_both_copies():
    names = ["Fan,Xiaoli", "Fan,Xiaoli", "Wang,Liming", "Wang,Liming"]
    items = ["<li>Xiaoli Fan</li>", '<li class="corresponding" title="w@x.com">Liming Wang</li>']
    assert [flag for _, flag in _flags(_page(names, items))] == [False, False, True, True]


def test_names_affiliations_and_abstract_stay_the_meta_tags():
    out = parse_page(_page(NAMES, PLAIN + [MARKED]).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == NAMES
    assert all(a["affiliations"] == [{"name": INST}] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_lookalike_byline_on_another_publishers_page_is_not_claimed():
    html = _page(NAMES, PLAIN + [MARKED], publisher="Other Science Press")
    assert not Spandidos(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert [flag for _, flag in _flags(html)] == [None, None, None]


def _ref_row(label, content):
    return (f'<tr><td class="ref-label" rowspan="1" colspan="1"><p class="ref-label"><span class="label">{label}</span>'
            f' <a name="b{label}" id="b{label}"></a></p></td><td class="ref-content" rowspan="1" colspan="1">'
            f"{content}</td></tr>")


def _citation(text, doi=None):
    links = (f'<a target="xrefwindow" href="http://dx.doi.org/{doi}">View Article</a> : ' if doi else "") + \
        ('<a target="xrefwindow" href="http://scholar.google.com/scholar_lookup?title=X">Google Scholar</a> : '
         '<a target="xrefwindow" href="http://www.ncbi.nlm.nih.gov/pubmed/12748654">PubMed/NCBI</a>')
    return f'<p class="citation"><a name="d7e556" id="d7e556"><!-- named anchor --></a>{text} {links}</p>'


def _refs_page(rows):
    body = '<h4>References</h4><table xmlns="http://www.w3.org/1999/xhtml" class="ref-list">' + "".join(rows) + \
        "</table>"
    return _page(NAMES, PLAIN + [MARKED], body)


def _parsed(html):
    return Spandidos(BeautifulSoup(html, "lxml")).parse()


def test_reference_list_text_doi_and_whole():
    rows = [_ref_row("1", _citation("Harada S and Rodan GA: Control of\nosteoblast function. Nature.\n423:349–355. "
                                    "2003.", "10.1038/nature01660")),
            _ref_row("2", _citation("Caetano-Lopes J and Fonseca JE: Osteoblasts and bone formation. Acta Reumatol "
                                    "Port. 32:103–110. 2007.")),
            _ref_row("3", '<div class="note"><p class="first">Annual reports of the Department of Health, Taiwan, '
                          "2012.</p></div>")]
    out = _parsed(_refs_page(rows))
    assert out["references"] == [
        {"position": 1, "raw": "Harada S and Rodan GA: Control of osteoblast function. Nature. 423:349–355. 2003.",
         "doi": "10.1038/nature01660"},
        {"position": 2, "raw": "Caetano-Lopes J and Fonseca JE: Osteoblasts and bone formation. Acta Reumatol Port. "
                               "32:103–110. 2007.", "doi": None},
        {"position": 3, "raw": "Annual reports of the Department of Health, Taiwan, 2012.", "doi": None}]
    assert out["references_complete"] is True


def test_numbers_printed_with_a_dot_are_whole():
    rows = [_ref_row(f"{i}.", _citation(f"Author {i}: Title {i}. J Med. 1:{i}. 2001.")) for i in (1, 2)]
    assert _parsed(_refs_page(rows))["references_complete"] is True


def test_a_gap_in_the_numbers_is_not_whole():
    rows = [_ref_row(str(i), _citation(f"Author {i}: Title {i}. J Med. 1:{i}. 2001.")) for i in (1, 2, 4)]
    out = _parsed(_refs_page(rows))
    assert len(out["references"]) == 3 and out["references_complete"] is False


def test_abstract_only_page_has_no_reference_keys():
    out = _parsed(_page(NAMES, PLAIN + [MARKED]))
    assert "references" not in out and "references_complete" not in out
