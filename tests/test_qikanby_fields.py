"""Xinlan International (qikanby.com) article pages: byline, affiliations, abstract, references (oxjob #2339).

Markup is cut down from stored qikanby.com pages (17 Nov 2026); names and numbers are made up. The site runs WordPress
with an empty byline block (div#authorString) and no citation_* meta tags: the article is pasted into
div#articleFullText > div.showtext, title, byline, affiliation lines, 摘要, 关键词, body, 参考文献. Before this parser no
publisher parser claimed the pages; the generic one read no authors and, on some pages, the abstract with a stray "：".
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.qikanby import Qikanby

URL = "https://qikanby.com/articles/10-67328-wslwpp0001/"
TITLE = "自动化设备机械设计中的可靠性分析与改进"
ABSTRACT = ("自动化设备是现代智能制造体系的核心载体，设备机械结构的设计可靠性直接决定设备运行稳定性、作业精度与服役周期，"
            "深刻影响工业生产连续性与安全性。本文立足自动化设备机械设计基本逻辑，提出系统性改进策略。")
REFS = ('<p class="wp-block-paragraph">参考文献</p>'
        '<p class="wp-block-paragraph">[1]高某某. 机械传动系统的优化设计研究[J]. 百科论坛电子杂志, 2026, (4): 22-24.</p>'
        '<p class="wp-block-paragraph">[2]冀某, 武某某. 自动化设备安全控制管理研究[J]. 工程抗震与加固改造, 2025, 47 (5): 206.'
        'DOI:10.20198/j.cnki.scsn.2026.06.055.</p>'
        '<p class="wp-block-paragraph">[3]张某某. 机械自动化设备的可靠性设计[J]. 今日制造与升级, 2023, (1): 55-57.</p>')


def _p(text):
    return f'<p class="wp-block-paragraph">{text}</p>'


def _page(header, refs=REFS, canonical=URL, title=TITLE, abstract=None):
    abstract = _p(f"摘要：{ABSTRACT}") if abstract is None else abstract
    body = (_p(f"<strong>{title}</strong>") + header + abstract + _p("关键词：自动化设备；机械设计；可靠性分析")
            + _p("引言") + _p("工业自动化与智能制造的快速普及，推动自动化设备广泛应用于各类工业生产场景。") + refs
            + '<p class="wp-block-paragraph"></p><p class="p_more">...</p><p><br></p>')
    link = f'<link rel="canonical" href="{canonical}" />' if canonical else ""
    return (f'<html lang="zh-Hans"><head><meta charset="UTF-8"><meta name="generator" content="WordPress 7.0" />'
            f'{link}</head><body><main id="main"><div class="container" id="pdfDom">'
            f'<header class="section-header"><h3 class="section-title">{title}</h3></header>'
            '<div id="authorString"><p></p><p></p></div>'
            f'<div id="articleFullText" class="mb-4"><div class="showtext">{body}</div>'
            '<a href="javascript:;" onclick="showmore()" class="btn btn-success">阅读全文</a></div>'
            '</div></main></body></html>')


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"])
            for a in parse_page(html.encode(), "doi", URL)["authors"]]


def _parse(html):
    return Qikanby(BeautifulSoup(html, "lxml")).parse()


def test_numbered_byline_links_each_author_to_their_affiliation():
    html = _page(_p("张三1 &nbsp;李四2") + _p("1.南充某电子有限公司 四川南充 637000")
                 + _p("2.广西某机械股份有限公司 广西壮族自治区柳州市 545000"))
    assert _authors(html) == [("张三", ["南充某电子有限公司 四川南充 637000"], False),
                              ("李四", ["广西某机械股份有限公司 广西壮族自治区柳州市 545000"], False)]


def test_id_card_number_is_never_an_affiliation():
    for line in ("1101**********1234", "身份证号：110101199001011234", "11010119900101123X"):
        assert _authors(_page(_p("王五") + _p(line))) == [("王五", [], False)]
    assert _authors(_page(_p("王五1101**********1234"))) == [("王五", [], False)]


def test_unnumbered_affiliation_and_address_lines_are_one_affiliation_for_every_author():
    html = _page(_p("姓名:张三 李四") + _p("单位：吴忠市某小学") + _p("邮编：751100"))
    assert _authors(html) == [("张三", ["吴忠市某小学 邮编：751100"], False),
                              ("李四", ["吴忠市某小学 邮编：751100"], False)]


def test_byline_and_affiliation_on_one_line():
    html = _page(_p("<strong>赵六</strong><strong></strong><strong>上海市某社区卫生服务中心</strong>"
                    "<strong>邮编：201112</strong>"))
    assert _authors(html) == [("赵六", ["上海市某社区卫生服务中心 邮编：201112"], False)]
    html = _page(_p("钱七 百色市某文史馆 533000"))
    assert _authors(html) == [("钱七", ["百色市某文史馆 533000"], False)]


def test_affiliations_in_a_list_and_wrapped_in_brackets():
    html = _page(_p("张三1，李四1，王五2") + '<ol class="wp-block-list"><li>邯郸市某医院 河北邯郸056001</li>'
                 '<li>磁县某医院 河北磁县056500</li></ol>')
    assert _authors(html) == [("张三", ["邯郸市某医院 河北邯郸056001"], False),
                              ("李四", ["邯郸市某医院 河北邯郸056001"], False),
                              ("王五", ["磁县某医院 河北磁县056500"], False)]
    html = _page(_p("张三 1 ， 李四 1") + _p("（1.柳州某钢铁股份有限公司，广西柳州，545000）"))
    assert _authors(html) == [("张三", ["柳州某钢铁股份有限公司，广西柳州，545000"], False),
                              ("李四", ["柳州某钢铁股份有限公司，广西柳州，545000"], False)]


def test_corresponding_author_only_where_the_page_says_so():
    html = _page(_p("张三&nbsp;李四<sup>通讯作者</sup>") + _p("某大学附属医院 吉林 延吉 133000"))
    assert _authors(html) == [("张三", ["某大学附属医院 吉林 延吉 133000"], False),
                              ("李四", ["某大学附属医院 吉林 延吉 133000"], True)]
    html = _page(_p("张三，李四<sup>△</sup>") + _p("（重庆市某中心医院，重庆 409000）"))
    assert [c for _, _, c in _authors(html)] == [False, False]  # a bare △ is not explained on the page


def test_biography_and_funding_lines_are_not_affiliations():
    html = _page(_p("张三") + _p("某医学院附属医院 吉林132013") + _p("基金课题:某省教育厅科学研究项目资助"))
    assert _authors(html) == [("张三", ["某医学院附属医院 吉林132013"], False)]


def test_abstract_without_label_or_stray_colon():
    out = parse_page(_page(_p("张三")).encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT
    out = parse_page(_page(_p("张三"), abstract=_p("<strong>摘要</strong>") + _p(ABSTRACT)).encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT
    out = parse_page(_page(_p("张三"), abstract=_p(f"<strong>摘要</strong> ：{ABSTRACT}")).encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT


def test_numbered_reference_list_is_whole():
    out = _parse(_page(_p("张三")))
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"].startswith("高某某. 机械传动系统")
    assert out["references"][1]["doi"] == "10.20198/j.cnki.scsn.2026.06.055"
    assert out["references_complete"] is True


def test_reference_list_with_a_gap_or_unnumbered_entry_is_not_whole():
    gap = REFS.replace("[3]", "[4]")
    assert _parse(_page(_p("张三"), refs=gap))["references_complete"] is False
    stray = REFS + _p("李某. 一条没有编号的文献[J]. 某杂志, 2024, (1): 1-2.")
    assert _parse(_page(_p("张三"), refs=stray))["references_complete"] is False


def test_reference_list_as_one_html_list_then_a_biography():
    refs = (_p("参考文献") + '<ul class="wp-block-list"><li>于某.装配式构件安装精度控制技术[J].四川水泥,2026,(6)147-148.</li>'
            '<li>付某.装配式建筑施工的质量控制要点[J].工程建设与设计,2026,(10)193-195.</li></ul>'
            + _p("作者简介：张三（1988—），女，硕士研究生。"))
    out = _parse(_page(_p("张三"), refs=refs))
    assert [r["position"] for r in out["references"]] == [1, 2]
    assert out["references_complete"] is True


def test_lw_subdomain_is_claimed():
    assert _authors(_page(_p("张三"), canonical="https://lw.qikanby.com/articles/x/")) == [("张三", [], False)]


def test_lookalike_wordpress_page_from_another_site_is_not_claimed():
    html = _page(_p("张三1 &nbsp;李四2") + _p("1.南充某电子有限公司 四川南充 637000"),
                 canonical="https://www.example-journal.cn/articles/1/")
    assert not Qikanby(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert not Qikanby(BeautifulSoup(_page(_p("张三"), canonical=None), "lxml")).authors_found()
    assert _authors(html) == []
