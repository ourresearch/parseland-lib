"""
ScienceDirect affiliations from the page-state JSON when the text is nested (oxjob #1794).

Older ScienceDirect state gives an affiliation's text directly: {"#name":"textfn","_":"Dept..."}. Newer pages nest it,
{"#name":"textfn","$$":[{"#name":"__text__","_":"Dept..."}]}, or wrap it in formatting ({"#name":"italic",...}); the
parser skipped those, so authors came out with no affiliations (4 of 21 dev pages in the 'authors without
affiliations' ScienceDirect class). Fragments mirror the real state; no network.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.sciencedirect import ScienceDirect


def page(affiliation_textfn):
    state = {"authors": {"content": [{"#name": "author-group", "$$": [
        {"#name": "author", "$$": [{"#name": "given-name", "_": "R."}, {"#name": "surname", "_": "Cortez"},
                                   {"#name": "cross-ref", "$": {"refid": "A0"}}]},
        {"#name": "author", "$$": [{"#name": "given-name", "_": "M."}, {"#name": "surname", "_": "Minion"},
                                   {"#name": "cross-ref", "$": {"refid": "A1"}}]},
        {"#name": "affiliation", "$": {"id": "A0"}, "$$": [{"#name": "label", "_": "a"}, affiliation_textfn]},
        {"#name": "affiliation", "$": {"id": "A1"}, "$$": [
            {"#name": "textfn", "_": "Department of Mathematics, University of North Carolina"}]},
    ]}]}}
    html = (f'<html><head><link rel="canonical" href="https://www.sciencedirect.com/science/article/pii/S1"></head>'
            f'<body><script>window.__PRELOADED_STATE__ = {json.dumps(state)};</script></body></html>')
    return ScienceDirect(BeautifulSoup(html, "lxml")).parse()


def test_nested_text_affiliation():
    out = page({"#name": "textfn", "$$": [{"#name": "__text__", "_": "Department of Mathematics, Tulane University"}]})
    assert [a["affiliations"] for a in out["authors"]] == [
        ["Department of Mathematics, Tulane University"], ["Department of Mathematics, University of North Carolina"]]


def test_formatted_text_affiliation():
    out = page({"#name": "textfn", "$$": [{"#name": "italic", "_": "Duke University, Durham, NC, USA"}]})
    assert out["authors"][0]["affiliations"] == ["Duke University, Durham, NC, USA"]


def test_split_text_affiliation_is_joined():
    out = page({"#name": "textfn", "$$": [{"#name": "__text__", "_": "Laboratoire LEP,"},
                                          {"#name": "__text__", "_": "  Limeil-Brévannes, France"}]})
    assert out["authors"][0]["affiliations"] == ["Laboratoire LEP, Limeil-Brévannes, France"]


def test_nested_footnote_is_not_affiliation_text():
    out = page({"#name": "textfn", "$$": [
        {"#name": "__text__", "_": "Laboratoire de Physique Théorique de L' École Normale Supérieure"},
        {"#name": "cross-ref", "$": {"refid": "FN2"}, "$$": [{"#name": "sup", "_": "2"}]},
        {"#name": "footnote", "$": {"id": "FN2"}, "$$": [{"#name": "label", "_": "2"},
                                                        {"#name": "note-para", "_": "Unité Mixte associée au CNRS"}]},
        {"#name": "__text__", "_": ", 24 Rue Lhomond, F-75231, Paris CEDEX 05, France."}]})
    assert out["authors"][0]["affiliations"] == [
        "Laboratoire de Physique Théorique de L' École Normale Supérieure, 24 Rue Lhomond, F-75231, Paris CEDEX 05, France."]


def test_phone_and_page_reference_are_dropped():
    out = page({"#name": "textfn", "$$": [
        {"#name": "__text__", "_": "Department of Agricultural Sciences, La Trobe University, Victoria 3086, Australia "},
        {"#name": "math", "$$": [{"#name": "rm", "$$": [{"#name": "__text__", "_": "Tel.: +61-3-9479-1111"}]}]}]})
    assert out["authors"][0]["affiliations"] == ["Department of Agricultural Sciences, La Trobe University, Victoria 3086, Australia"]
    out = page({"#name": "textfn", "$$": [
        {"#name": "__text__", "_": "("}, {"#name": "intra-ref", "_": "159"},
        {"#name": "__text__", "_": "), Center for the Study of Reading, University of Illinois"}]})
    assert out["authors"][0]["affiliations"] == ["Center for the Study of Reading, University of Illinois"]


def test_plain_text_affiliation_unchanged():
    out = page({"#name": "textfn", "_": "Department of Mathematics, Tulane University"})
    assert out["authors"][0]["affiliations"] == ["Department of Mathematics, Tulane University"]
