"""Sciendo article pages (oxjob #2289): the reference list Sciendo's Next.js app embeds in the page.

Markup is cut down from stored Sciendo pages (sciendo.com and the society sites it serves, 17 Nov 2026). The page's
References tab is rendered from `articleData.referenceList` in `__NEXT_DATA__`; each entry's JATS id numbers the
publisher's whole list ("..._ref_001" or "..._ref_001_w2aab..."), and some lists also type "[1]" into the text.
Sciendo's app takes every page's og:image from its own S3 bucket ("sciendo-parsed..."), whichever host serves the page;
DeGruyterOpen checks that one <head> tag before any whole-page search, so other templates' pages cost it nothing.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.de_gruyter_open import DeGruyterOpen

URL = "https://sciendo.com/article/10.2478/czoto-2023-0003"
IMAGE = "https://sciendo-parsed.s3.eu-central-1.amazonaws.com/6594e0d279f7550bc9ea2531/cover-image.jpg"
CONTRIB = [
    {"name": {"given-names": "Andrzej", "surname": "Pacana"}, "xref": {"rid": "aff1"}, "corresp": "yes"},
    {"name": {"given-names": "Dominika", "surname": "Siwiec"}, "xref": {"rid": "aff1"}, "corresp": None},
]
AFF = [{"id": "aff1", "institution": ["Rzeszow University of Technology", {"content": "Rzeszow"}]}]


def _ref(n, cite, markup=None, numbered_id=True):
    ref_id = f"j_czoto-2023-0003_ref_{n:03d}" if numbered_id else None
    return {"refId": ref_id, "citeString": cite, "doi": None,
            "mixed-citation": markup or f"<ref><mixed-citation>{cite}</mixed-citation></ref>"}


THREE = [
    _ref(1, "Apkarian, P. (1995). Self-scheduled control, Automatica 31(9): 1251-1261.10.1016/0005-1098(95)00038-X",
         '<ref><mixed-citation>Apkarian, P. (1995). Self-scheduled control, <italic>Automatica</italic> 31(9): 1251-1261.'
         '<dgdoi:pub-id xmlns:dgdoi="http://degruyter.com/resources/doi-from-crossref" pub-id-type="doi">'
         '10.1016/0005-1098(95)00038-X</dgdoi:pub-id></mixed-citation></ref>'),
    _ref(2, "Andreoni, J. (2017). All pay auctions. J Econ Behav Organ, 137, 361-373. https://doi.org/10.1016/j.jebo.2017.03.17",
         '<ref><mixed-citation>Andreoni, J. (2017). All pay auctions. <italic>J Econ Behav Organ, 137,</italic> 361-373. '
         '<ext-link ext-link-type="uri" xlink:href="https://doi.org/10.1016/j.jebo.2017.03.17">'
         'https://doi.org/10.1016/j.jebo.2017.03.17</ext-link></mixed-citation></ref>'),
    _ref(3, "Calado, E.A., 2019. Integrating LCA and LCC, Int J Life Cycle Assess, 24, 2091-2110, DOI: 10.1007/s11367-019-01632-8"),
]


def _page(refs, image=IMAGE, footer="Sciendo is a De Gruyter company"):
    data = {"props": {"pageProps": {"product": {"articleData": {
        "contribGroup": {"contrib": CONTRIB, "aff": AFF}, "referenceList": refs}}}}}
    return (f'<!DOCTYPE html><html lang="en"><head><meta property="og:image" content="{image}"/>'
            '<meta name="citation_title" content="Improving products"/>'
            '<meta name="citation_author" content="Andrzej Pacana"/><meta name="citation_author" content="Dominika Siwiec"/>'
            '</head><body><div class="Article_author-popup__2Pq1x">Andrzej Pacana</div>'
            '<div class="Article_author-popup__2Pq1x">Dominika Siwiec</div>'
            f'<footer><p>{footer}</p></footer>'
            f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>')


def _parse(html):
    return DeGruyterOpen(BeautifulSoup(html, "lxml")).parse()


def test_reference_list_from_the_page_data():
    out = _parse(_page(THREE))
    assert [r["raw"] for r in out["references"]] == [
        "Apkarian, P. (1995). Self-scheduled control, Automatica 31(9): 1251-1261. 10.1016/0005-1098(95)00038-X",
        "Andreoni, J. (2017). All pay auctions. J Econ Behav Organ, 137, 361-373. https://doi.org/10.1016/j.jebo.2017.03.17",
        "Calado, E.A., 2019. Integrating LCA and LCC, Int J Life Cycle Assess, 24, 2091-2110, DOI: 10.1007/s11367-019-01632-8",
    ]
    assert [r["doi"] for r in out["references"]] == [
        "10.1016/0005-1098(95)00038-X", "10.1016/j.jebo.2017.03.17", "10.1007/s11367-019-01632-8"]
    assert out["references_complete"] is True


def test_typed_numbers_are_not_part_of_the_reference():
    refs = [_ref(n, f"[{n}] Gabor D., 2018 Study number {n} of ignition risk, Petrosani, Pag. 157-162;") for n in (1, 2, 3)]
    for ref in refs:
        ref["refId"] += "_w2aab3b7c16b1b6b1ab1ab1Aa"
    out = _parse(_page(refs))
    assert out["references"][0]["raw"] == "Gabor D., 2018 Study number 1 of ignition risk, Petrosani, Pag. 157-162;"
    assert out["references_complete"] is True


def test_a_gap_in_the_numbering_is_not_a_whole_list():
    refs = [THREE[0], THREE[1], dict(THREE[2], refId="j_czoto-2023-0003_ref_004")]
    out = _parse(_page(refs))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_entries_with_no_numbers_are_not_called_whole():
    refs = [_ref(n, r["citeString"], r["mixed-citation"], numbered_id=False) for n, r in enumerate(THREE, 1)]
    out = _parse(_page(refs))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_a_page_with_no_list_returns_no_reference_keys():
    assert "references" not in _parse(_page([]))


def test_authors_and_references_through_parse_page():
    out = parse_page(_page(THREE).encode(), "doi", URL)
    assert [(a["name"], a["is_corresponding"]) for a in out["authors"]] == [
        ("Andrzej Pacana", True), ("Dominika Siwiec", False)]
    assert out["authors"][0]["affiliations"] == [{"name": "Rzeszow University of Technology, Rzeszow"}]
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references_complete"] is True


def test_newer_build_without_the_footer_line_is_still_read():
    # sciendo.com's 2024 build drops "Sciendo is a De Gruyter company"; the parser is not specific there but still
    # wins on its affiliations, as before
    out = parse_page(_page(THREE, footer="Sciendo").encode(), "doi", URL)
    assert len(out["references"]) == 3


def test_other_nextjs_site_is_not_read():
    html = _page(THREE, image="https://cdn.example-press.org/covers/journal.jpg", footer="Example Press")
    assert DeGruyterOpen(BeautifulSoup(html, "lxml")).authors_found() is False
    assert parse_page(html.encode(), "doi", URL)["references"] is None


def test_paradigm_app_router_build_is_left_to_its_citation_tags():
    # reference-global.com (Sciendo's newer app-router build) shares the image bucket but has no author pop-ups;
    # parse_page already reads its whole list from citation_reference tags
    html = (f'<html><head><meta property="og:image" content="{IMAGE}"/>'
            '<meta name="citation_author" content="Silvana Naunova Timovska"/></head>'
            '<body><p>By: Silvana Naunova Timovska</p></body></html>')
    assert DeGruyterOpen(BeautifulSoup(html, "lxml")).authors_found() is False
