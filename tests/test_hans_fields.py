"""Hans Publishers (hanspub.org) article pages (oxjob #2289).

Markup is cut down from stored hanspub.org pages (17 Nov 2026). The generic parser read no authors on them: the page's
only author tags are a semicolon list (citation_authors) and dc.creator, with no affiliations. The byline prints each
author as a search link, grouped by affiliation: "A：aff 1；B, C*：aff 2" (an author may carry several affiliations,
split by "；"). A starred author is the corresponding one only when the page's NOTES say "* 通讯作者" (some say
"* 第一作者", first author). The full text closes with "基金项目" / "致谢" sections, and the reference list is a table
numbered [1]..[n].
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.hans import HansPublishers

URL = "https://www.hanspub.org/journal/paperinformation?paperid=100001"
HANS_HEAD = ('<meta name="citation_journal_title" content="Advances in Clinical Medicine" />'
             '<meta name="citation_publisher" content="中文学术期刊,汉斯出版社,Hans Publishers" />'
             '<meta name="citation_authors" content="王一;李二;张三;赵四" />'
             '<meta name="citation_title" content="一个题目" />'
             '<meta name="citation_doi" content="10.12677/ACM.2024.11001" />'
             '<meta name="dc.creator" content="王一" /><meta name="dc.creator" content="李二" />')


def _link(name, star=""):
    mark = f"<sup>{star}</sup>" if star else ""
    return (f"<a href='/journal/articles?searchcode=x&searchfield=authors&page=1' target='_blank'>{name}{mark}</a>")


ABSTRACTS = ('<div class="p_br"><div id="ctl00_ContentPlaceHolder1_div_abs_zw"><b><a name="abstract"></a>摘要: </b>'
             '本文研究了一个问题。</div>'
             '<div id="ctl00_ContentPlaceHolder1_div_abs_yw"><b>Abstract: </b>\nThis paper studies a problem in some '
             'depth and reports what it found.</div></div>')


def _new_layout(byline):
    return ('<div class="articles_main"><div class="art_title"><b>一个题目</b><br>A Title</div>'
            '<div style="float: left; width: 100%;"><span><b>DOI:</b>&nbsp;<a href="https://doi.org/10.12677/'
            'ACM.2024.11001">10.12677/ACM.2024.11001</a>, </span><br />'
            f'<span style="clear: left;"><strong>作者: </strong></span>\n{byline} <br />'
            "<span><strong>关键词: </strong></span><a href='articles?searchcode=k&searchfield=keyword'>词</a></div>"
            f"{ABSTRACTS}")


def _page(body, head=HANS_HEAD, back=""):
    return f"<html><head><title>一个题目</title>{head}</head><body>{body}{back}</body></html>"


GROUPED = (_link("王一") + "：青海大学研究生院临床医学院，青海 西宁；甲大学，机械工程学院，浙江 宁波；"
           + _link("李二") + ", " + _link("张  三", "*") + "：青海大学附属医院重症医学科，青海 西宁")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return HansPublishers(BeautifulSoup(html, "lxml")).parse()


def test_byline_groups_give_each_author_its_affiliations():
    authors = _parse(_page(_new_layout(GROUPED)))["authors"]
    assert [a["name"] for a in authors] == ["王一", "李二", "张 三"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["青海大学研究生院临床医学院，青海 西宁", "甲大学，机械工程学院，浙江 宁波"],
        ["青海大学附属医院重症医学科，青海 西宁"],
        ["青海大学附属医院重症医学科，青海 西宁"]]


def test_older_layout_byline_in_a_paragraph():
    body = ('<div class="absBox"><h1><b>一个题目</b></h1><p><b>DOI:</b>&nbsp;<a href="https://doi.org/x">x</a></p>'
            "<p>\n<b>作者: </b>\n" + _link("赵四") + "：海南师范大学历史文化学院，海南 海口</p>"
            "<p><b>关键词: </b><a href='articles.aspx?searchCode=k&searchField=keyword'>词</a></p>" + ABSTRACTS + "</div>")
    authors = _parse(_page(body))["authors"]
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in authors] == [
        ("赵四", ["海南师范大学历史文化学院，海南 海口"])]


def test_star_is_corresponding_with_the_notes_line():
    back = '<p class="E-Title1"> NOTES</p><p><sup>*</sup>通讯作者。</p>'
    authors = _parse(_page(_new_layout(GROUPED), back=back))["authors"]
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_star_without_a_corresponding_note_marks_no_one():
    for back in ("", '<p class="E-Title1"> NOTES</p><p><sup>*</sup>第一作者。</p>'):
        authors = _parse(_page(_new_layout(GROUPED), back=back))["authors"]
        assert not any(a["is_corresponding"] for a in authors)


def test_english_abstract_without_its_label():
    assert _parse(_page(_new_layout(GROUPED)))["abstract"] == (
        "This paper studies a problem in some depth and reports what it found.")


def test_funding_and_acknowledgments_sections():
    back = ('<p class="E-Title1">5. 结论</p><p>正文。</p><p class="E-Title1">致谢</p><p>感谢某教授的帮助。</p>'
            '<p class="E-Title1">基金项目</p><p>1) 省级课题(2016D01C209)。</p><p>2) 国家自然科学基金(82060395)。</p>'
            '<p class="E-Title1"> NOTES</p><p><sup>*</sup>通讯作者。</p>')
    raw = _raw(_page(_new_layout(GROUPED), back=back))
    assert raw["acknowledgments"] == "感谢某教授的帮助。"
    assert raw["funding_statement"] == "1) 省级课题(2016D01C209)。\n2) 国家自然科学基金(82060395)。"


def _refs(numbers):
    rows = "".join(
        f'<tr><td width="45" valign="top">[{n}]</td><td valign="top"><a target="_self" name="ref{n}" id="ref{n}"></a> '
        f"Author, A. ({2000 + n}) Title {n}. Journal, {n}, 1-9. <br><a href='https://doi.org/10.1000/x{n}' "
        f"target='_blank'>https://doi.org/10.1000/x{n}</a></td></tr>" for n in numbers)
    return ('<div><p><b><a name="reference"></a>参考文献</b><table width="100%" border="0">' + rows + "</table></p></div>")


def test_reference_table_is_a_whole_list():
    raw = _raw(_page(_new_layout(GROUPED), back=_refs([1, 2, 3])))
    assert [r["position"] for r in raw["references"]] == [1, 2, 3]
    assert raw["references"][1]["raw"] == "Author, A. (2002) Title 2. Journal, 2, 1-9. https://doi.org/10.1000/x2"
    assert raw["references"][1]["doi"] == "10.1000/x2"
    assert raw["references_complete"] is True
    out = _parse(_page(_new_layout(GROUPED), back=_refs([1, 2, 3])))
    assert out["references_complete"] is True and len(out["references"]) == 3


def test_reference_table_with_a_gap_is_not_whole():
    raw = _raw(_page(_new_layout(GROUPED), back=_refs([1, 2, 4])))
    assert len(raw["references"]) == 3 and raw["references_complete"] is False


def test_scirp_page_with_the_same_byline_is_not_claimed():
    # SCIRP (scirp.org), Hans's English-language sister site, prints the same search-link byline
    head = HANS_HEAD.replace("中文学术期刊,汉斯出版社,Hans Publishers", "Scientific Research Publishing")
    soup = BeautifulSoup(_page(_new_layout(GROUPED), head=head), "lxml")
    parser = HansPublishers(soup)
    assert not parser.authors_found() and not parser.is_publisher_specific_parser()


def test_page_without_a_byline_is_not_read():
    soup = BeautifulSoup(_page("<div>没有作者</div>"), "lxml")
    assert HansPublishers(soup).is_publisher_specific_parser() and not HansPublishers(soup).authors_found()
