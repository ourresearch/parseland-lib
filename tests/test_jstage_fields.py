"""J-STAGE article pages: starred corresponding authors and the reference list (oxjob #2223).

Markup cut down from stored J-STAGE pages (13 Nov 2026, #2223 EXPLORE § 1). J-STAGE stars the corresponding author in
the byline ('*Name'); the "Corresponding author" popup on every page is an empty template, not a mark. The reference
list is printed only in citation_reference meta tags (the visible list is filled in by script), and the article menu
states its length ('引用文献 (9)' / 'References (9)'): the list is whole when that count equals the tags (#2215's
contract: positive evidence only).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jsme import JSME

URL = "https://www.jstage.jst.go.jp/article/jsmemnm/2017.8/0/2017.8_PN-77/_article/-char/ja/"
OG = '<meta name="og:url" content="https://www.jstage.jst.go.jp/article/jsmemnm/2017.8/0/2017.8_PN-77/_article/-char/ja/"/>'
NAMES = ["中島 駿介", "川野 竜司", "尾上 弘晃"]


def _page(byline, refs=(), stated=None, menu_label="引用文献", og=OG):
    metas = "".join(f'<meta name="citation_author" content="{n}"/><meta name="citation_author_institution" content="慶大"/>'
                    for n in NAMES)
    metas += "".join(f'<meta name="citation_reference" content="{r}"/>' for r in refs)
    menu = (f'<ul><li><a href="#article-overiew-references-wrap" title="{menu_label}">{menu_label} ({stated})</a></li></ul>'
            if stated is not None else "")
    names = ",&nbsp;".join(f'<a class="customTooltip" title="{n}, 慶大"><span>{n}</span></a>' for n in byline)
    popup = ('<div class="corr-auth-sapopup-wrap" id="saPopup" style="display:none"><div class="corr-auth-sapopup-cont">'
             '<div class="sapopup-title"><h4>責任著者(Corresponding author)</h4></div></div></div>')
    return (f'<html><head>{og}{metas}<meta name="citation_title" content="A title"/>'
            f'<meta name="citation_doi" content="10.1299/jsmemnm.2017.8.pn-77"/></head><body>'
            f'<div class="global-authors-name-tags">{names}</div>{popup}{menu}'
            f'<div id="article-overiew-references-wrap"><div class="section-title-18" style="display:none;">'
            f'{menu_label} ({stated})</div></div></body></html>')


def _parse(html):
    return JSME(BeautifulSoup(html, "lxml")).parse()


def test_starred_author_is_corresponding():
    authors = parse_page(_page(["*" + NAMES[0], NAMES[1], NAMES[2]]).encode(), "doi", URL)["authors"]
    assert [a["name"] for a in authors if a["is_corresponding"]] == [NAMES[0]]


def test_empty_corresponding_popup_is_not_a_mark():
    authors = parse_page(_page(NAMES).encode(), "doi", URL)["authors"]
    assert [a["name"] for a in authors] == NAMES
    assert not any(a["is_corresponding"] for a in authors)


REFS = ["(1) Abe, M., Vehicle Dynamics and Control, (1979), p. 192.",
        "(2) Minami, M. et al., Magnetic Autonomous Guidance, Vol. 31, No. 5 (1987), pp. 382-391.",
        "(3) Shibata. K.: Urban Housing Sciences, No.89, pp.18-23, 2015 DOI: https://doi.org/10.11531/uhs.2015.89_18."]


def test_reference_list_is_read_in_order_without_its_numbers():
    parsed = _parse(_page(NAMES, REFS, stated=3))
    assert [r["position"] for r in parsed["references"]] == [1, 2, 3]
    assert parsed["references"][0]["raw"] == "Abe, M., Vehicle Dynamics and Control, (1979), p. 192."
    assert parsed["references"][0]["doi"] is None
    assert parsed["references"][2]["doi"] == "10.11531/uhs.2015.89_18"


def test_list_is_complete_when_the_stated_count_matches():
    assert _parse(_page(NAMES, REFS, stated=3))["references_complete"] is True
    assert _parse(_page(NAMES, REFS, stated=3, menu_label="References"))["references_complete"] is True


def test_list_is_not_complete_when_the_count_differs_or_is_missing():
    assert _parse(_page(NAMES, REFS, stated=5))["references_complete"] is False
    assert _parse(_page(NAMES, REFS))["references_complete"] is False


def test_other_numbering_styles_are_stripped_only_at_their_own_position():
    refs = ["1) Smith CT: Quintessence Int 1997; 28: 457-462.", "2. Wohlert A.B: JSLHR 1998; 41: 41-50.",
            "[3] Ito S: Blood 8: 2018.", "1998) not a number of this entry"]
    raws = [r["raw"] for r in _parse(_page(NAMES, refs, stated=4))["references"]]
    assert raws == ["Smith CT: Quintessence Int 1997; 28: 457-462.", "Wohlert A.B: JSLHR 1998; 41: 41-50.",
                    "Ito S: Blood 8: 2018.", "1998) not a number of this entry"]


def test_no_reference_tags_means_no_list():
    parsed = _parse(_page(NAMES, stated=10))
    assert parsed["references"] is None and parsed["references_complete"] is False
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None


def test_look_alike_page_from_another_site_is_not_claimed():
    other = _page(NAMES, REFS, stated=3, og='<meta property="og:url" content="https://journal.example.org/article/1"/>')
    assert not JSME(BeautifulSoup(other, "lxml")).is_publisher_specific_parser()
    assert JSME(BeautifulSoup(_page(NAMES, REFS, stated=3), "lxml")).is_publisher_specific_parser()


def test_numbering_with_gaps_or_split_entries_is_not_provably_whole():
    gaps = ["9) 平凡社発行:綴方風土記.", "10) 山口常助 (1954): 伊予史談, 138, 8-12.", "14) 若林秀泰編著 (1960): 87-132."]
    assert _parse(_page(NAMES, gaps, stated=3))["references_complete"] is False
    split = ["1) Inamura, K.: Text on Fishing Vessels.", "稲村桂吾: 漁船論.", "2) Matsuda, K.: Gillnet Fishing Vessel."]
    assert _parse(_page(NAMES, split, stated=3))["references_complete"] is False


def test_unnumbered_list_relies_on_the_stated_count():
    refs = ["Abe, M., Vehicle Dynamics and Control, 1979.", "Minami, M. et al., Magnetic Guidance, 1987."]
    assert _parse(_page(NAMES, refs, stated=2))["references_complete"] is True
