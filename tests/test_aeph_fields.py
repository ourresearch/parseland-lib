"""Academic Education Publishing House (aeph.press) article pages (oxjob #2210).

Markup is cut down from stored aeph.press pages (13 Nov 2026). The site has no citation meta tags: each field sits in a
`div.s4_9` after a `div.s4_8` label ("Author(s)", "Affiliation(s)", "Abstract", "References"). Bylines carry plain-text
markers ("Juanjuan Tan1,2,*"), affiliations are one per line with a leading number, and a "*Corresponding Author" line
explains the star.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.aeph import AEPH

URL = "http://www.aeph.press/hep/hep20266/2765.html"
FOOTER = ('<div class="z_box"><div class="s2_2">Copyright @ 2020-2035 Academic Education Publishing House '
          'All Rights Reserved</div></div>')
ABSTRACT = ("The construction of the new engineering paradigm involves four aspects of industrial demand, "
            "engineering practice, interdisciplinary integration and innovation capacity.")


def _page(authors, affs, refs="[1] A. Author. A title. A Journal, 2025(1): 1-2.", footer=FOOTER):
    sections = [("Author(s)", authors), ("Affiliation(s)", affs), ("Abstract", ABSTRACT),
                ("Keywords", "New Engineering; Teaching Reform"), ("References", refs)]
    body = "".join(f'<div class="s4_8">{label}</div>\n<div class="s4_9">{text}</div>\n' for label, text in sections)
    return ('<html><head><title>A title_Vol. 3 No. 6 (HEP 2026)_Higher Education and Practice_AEPH</title></head>'
            '<body><div class="z_box"><div class="s4_1"><div class="s4_3"><div class="s4_4">A title</div>'
            '<div class="s4_2"><div class="s4_6"><a href="/uploadfile/202607/f0f.pdf">Download PDF</a></div></div>'
            f'{body}</div></div></div>{footer}</body></html>')


def _parse_page(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(author):
    return [aff["name"] for aff in author["affiliations"]]  # parse_page returns {"name": ...} per affiliation


def _parse(html):
    return AEPH(BeautifulSoup(html, "lxml")).parse()


AFF1 = "School of Chemical and Environmental Engineering, Hanshan Normal University, Chaozhou, Guangdong, China"
AFF2 = "School of Materials Science and Engineering, Hanshan Normal University, Chaozhou, Guangdong, China"


def test_numbered_markers_link_affiliations_and_star_marks_corresponding():
    html = _page("Juanjuan Tan1,2,*, Jianhong Dong2, Huan Yang1",
                 f"1{AFF1}\r\n2{AFF2}\r\n*Corresponding Author")
    authors = _parse_page(html)["authors"]
    assert [a["name"] for a in authors] == ["Juanjuan Tan", "Jianhong Dong", "Huan Yang"]
    assert [_affs(a) for a in authors] == [[AFF1, AFF2], [AFF2], [AFF1]]
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_two_starred_authors_and_spaced_label():
    html = _page("Lin Haibo1, Chen Xuejun1,*, Yueqin Feng2,*",
                 "1Taizhou Vocational &amp; Technical College, Taizhou, China\r\n2 Linhai Vocational School, "
                 "Linhai, China\r\n*Corresponding Author")
    authors = _parse_page(html)["authors"]
    assert [a["name"] for a in authors] == ["Lin Haibo", "Chen Xuejun", "Yueqin Feng"]
    assert _affs(authors[2]) == ["Linhai Vocational School, Linhai, China"]
    assert [a["is_corresponding"] for a in authors] == [False, True, True]


def test_unmarked_byline_shares_the_affiliation():
    html = _page("Yongning Luo, Xinxin Zhang*",
                 "School of Information Engineering, Xi'an FanYi University, Xi'an, China\r\n*Corresponding Author.")
    authors = _parse_page(html)["authors"]
    assert [_affs(a) for a in authors] == [["School of Information Engineering, Xi'an FanYi University, "
                                                     "Xi'an, China"]] * 2
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_lone_author_with_a_corresponding_note_but_no_star():
    html = _page("Shuo Wang", "Mathematics Department, University of California, Santa Barbara, California, USA\r\n"
                              "Corresponding author")
    authors = _parse_page(html)["authors"]
    assert [(a["name"], a["is_corresponding"]) for a in authors] == [("Shuo Wang", True)]
    assert _affs(authors[0]) == ["Mathematics Department, University of California, Santa Barbara, "
                                          "California, USA"]


def test_star_without_a_note_is_no_mark():
    html = _page("Jiayun Wang1,*, Zeng Qu2", "1North University of China, Taiyuan, China\r\n2Jinzhong College, China")
    assert [a["is_corresponding"] for a in _parse_page(html)["authors"]] == [False, False]


def test_abstract():
    assert _parse_page(_page("Si Liu", "Hankou University, Wuhan, Hubei, China"))["abstract"] == ABSTRACT


def test_reference_list_numbered_one_to_n_is_complete():
    refs = ("[1] Xu Zhihong, Lin Wanzhen. Misalignment of Teaching. Fujian Textile, 2025(11): 91-94.\r\n"
            "[2]ZHANG N, GAO B J. Research on the formation of behavior. \r\nLibrary and information service, "
            "2021, 65(19): 96-104.\r\n"
            "[3] Kessler RC. Lifetime prevalence. Arch Gen Psychiatry, 2005, 62: 593-602. doi:10.1001/archpsyc.62.6.593.")
    out = _parse(_page("Si Liu", "Hankou University, Wuhan, Hubei, China", refs=refs))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"] == "Xu Zhihong, Lin Wanzhen. Misalignment of Teaching. Fujian Textile, 2025(11): 91-94."
    assert out["references"][1]["raw"] == ("ZHANG N, GAO B J. Research on the formation of behavior. "
                                           "Library and information service, 2021, 65(19): 96-104.")
    assert [r["doi"] for r in out["references"]] == [None, None, "10.1001/archpsyc.62.6.593"]
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_doi_broken_by_a_space_is_not_taken():
    refs = ("[1] Ye. Psychological Service Needs. Psychological Monthly, 2022 (14): 196-198. DOI: 10.19738/j.cnki. "
            "psy.2022.14.061\r\n[2] Liu. Big data. Computers, 2023, 110:11. DOI:10.1016/j.compeleceng.2023.108823.")
    out = _parse(_page("Si Liu", "Hankou University, Wuhan, Hubei, China", refs=refs))
    assert [r["doi"] for r in out["references"]] == [None, "10.1016/j.compeleceng.2023.108823"]


def test_reference_list_with_a_gap_is_not_complete():
    refs = "[1] One. J, 2020.\r\n[2] Two. J, 2021.\r\n[4] Four. J, 2023."
    out = _parse(_page("Si Liu", "Hankou University, Wuhan, Hubei, China", refs=refs))
    assert len(out["references"]) == 3
    assert out["references_complete"] is False


def test_similar_markup_on_another_site_is_not_claimed():
    other_footer = '<div class="z_box"><div class="s2_2">Copyright @ 2024 Some Other Press</div></div>'
    html = _page("Juanjuan Tan1,*, Jianhong Dong1", f"1{AFF1}\r\n*Corresponding Author", footer=other_footer)
    parser = AEPH(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert AEPH(BeautifulSoup(_page("Si Liu", "Hankou University"), "lxml")).is_publisher_specific_parser()
