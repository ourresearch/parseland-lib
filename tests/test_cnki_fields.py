"""CNKI (China National Knowledge Infrastructure) kcms8 article detail pages: byline, affiliations, abstract, funding (#2289).

Markup is cut down from stored CNKI detail pages behind DOIs of ~50 Chinese journals (10.13474, 10.16538, 10.13386 ...,
17 Nov 2026). The pages carry no citation meta tags, so the generic parser read nothing. The byline is
`h3#authorpart` (names, superscript labels when the affiliations are numbered), the affiliations the next `h3` (each a
link, or bare text when CNKI has no institution page for it), the abstract `span#ChDivSummary`, funding the `p.funds`
row labelled 基金资助. References load into an iframe and never show on the page.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.cnki import Cnki

URL = "https://doi.org/10.16257/j.cnki.1681-1070.2018.0017"
ASSETS = ('<link rel="stylesheet" type="text/css" href="https://piccache.cnki.net/2022/kdn/kcms8/detail/resource/gb/'
          'css_min/public.min.css?v=FBC16D09D6F9935E"><script type="text/javascript" src="https://piccache.cnki.net/'
          '2022/kdn/kcms8/detail/js/jquerybase.min.js?v=1"></script>')
ABSTRACT = "直接数字频率合成器在现代数字通信系统中有非常重要的应用。基于CORDIC算法的DDS在高速、高精度信号源领域已得到广泛应用。"


def _author(name, sup=""):
    sup = f"<sup>{sup}</sup>" if sup else ""
    return (f'<span><a target="_blank" onclick="TurnPageToKnetV(\'au\',\'{name}\',\'1\',\'x\');">{name}{sup}</a>'
            f'<input class="authorcode" type="hidden" value="000034245257"></span>')


def _page(byline, affs, abstract=ABSTRACT, funds="", head=ASSETS):
    fund_row = (f'<div class="row"><span class="rowtit">基金资助：</span><p class="funds">{funds}</p></div>'
                if funds else "")
    return (f'<html><head><meta charset="UTF-8"><title>A title - 中国知网</title>{head}</head><body>'
            '<div class="container"><div class="doc"><div class="doc-top"><div class="brief"><div class="wx-tit">'
            f'<h1>A title</h1><h3 class="author" id="authorpart">{byline}</h3><h3>{affs}</h3></div></div>'
            '<div class="row"><span class="rowtit">摘要：</span><span id="ChDivSummary" name="ChDivSummary" '
            f'class="abstract-text">{abstract}</span><span><a id="ChDivSummaryMore" style="display:none">更多</a>'
            f'</span></div>{fund_row}</div></div></div></body></html>')


def _parse(html):
    out = parse_page(html.encode(), "doi", URL)
    return [(a["name"], [x["name"] for x in a["affiliations"]], bool(a["is_corresponding"])) for a in out["authors"]]


def _raw(html):
    return Cnki(BeautifulSoup(html, "lxml")).parse()


UNLINKED = (_author("张三") + _author("李四") + _author("王五"),
            '<span><a class="author" target="_blank">四川大学物理科学与技术学院</a></span>'
            '<span><a class="author" target="_blank">四川农业大学资源环境学院</a></span>')
NUMBERED = (_author("LIU Yuqing", "1") + _author("REN Zheyu", "2") + _author("MA Zhuqiao", "1,2"),
            '<a class="author" target="_blank">1. Department of Mechanical Engineering, Example University</a>'
            '<a class="author" target="_blank">2. School of Intelligent Manufacturing,Example College</a>')


def test_unlinked_affiliations_go_to_every_author():
    affs = ["四川大学物理科学与技术学院", "四川农业大学资源环境学院"]
    assert _parse(_page(*UNLINKED)) == [("张三", affs, False), ("李四", affs, False), ("王五", affs, False)]


def test_numbered_affiliations_follow_the_superscripts():
    assert _parse(_page(*NUMBERED)) == [
        ("LIU Yuqing", ["Department of Mechanical Engineering, Example University"], False),
        ("REN Zheyu", ["School of Intelligent Manufacturing,Example College"], False),
        ("MA Zhuqiao", ["Department of Mechanical Engineering, Example University",
                        "School of Intelligent Manufacturing,Example College"], False)]


def test_bare_text_affiliation_between_links_is_read():
    # CNKI prints an institution it has no page for as bare text between the links, set off by &nbsp;
    byline = _author("鲁迪", "1,2") + _author("宋佳卉", "3")
    affs = ('<a class="author">1. 南京医科大学基础医学院</a><a class="author">2. 南京医科大学公共卫生学院</a>'
            '&nbsp;&nbsp;3. 江苏省南京亿科人群健康研究院&nbsp;&nbsp;')
    assert _parse(_page(byline, affs)) == [("鲁迪", ["南京医科大学基础医学院", "南京医科大学公共卫生学院"], False),
                                         ("宋佳卉", ["江苏省南京亿科人群健康研究院"], False)]


def test_plain_span_affiliations_and_name_punctuation():
    byline = _author("National Education Examinations Authority;")
    affs = "<span> 教育部考试中心 </span>"
    assert _parse(_page(byline, affs)) == [("National Education Examinations Authority", ["教育部考试中心"], False)]


def test_abstract():
    out = parse_page(_page(*UNLINKED).encode(), "doi", URL)
    assert out["abstract"] == ABSTRACT


def test_abstract_keeps_subscripts_inline():
    out = _raw(_page(*UNLINKED, abstract="超临界CO<sub>2</sub>储能做功过程的相似模化特性研究是特殊工质透平设计的基础。"))
    assert out["abstract"] == "超临界CO2储能做功过程的相似模化特性研究是特殊工质透平设计的基础。"


def test_body_text_shown_in_place_of_an_abstract_is_not_one():
    # "＜正＞" marks the opening lines of the article body, which CNKI shows when the article has no abstract
    out = _raw(_page(*UNLINKED, abstract="＜正＞各位领导、各位专家学者、同志们:大家上午好!今天我们在这里召开会议。"))
    assert out["abstract"] is None


def test_funding_statement():
    funds = ('<a target="_blank">国家自然科学基金（41974039,41774026）；</a>'
             '<a target="_blank">自然资源部国土环境与灾害监测重点实验室开放基金（LEDM2021B13）～～；</a>')
    out = _raw(_page(*UNLINKED, funds=funds))
    assert out["funding_statement"] == "国家自然科学基金（41974039,41774026）；自然资源部国土环境与灾害监测重点实验室开放基金（LEDM2021B13）"
    assert out["acknowledgments"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_no_funding_row():
    assert _raw(_page(*UNLINKED))["funding_statement"] is None


def test_byline_without_cnki_assets_is_not_claimed():
    # the same markup served without CNKI's kcms stylesheets (a copy on another site) is not this parser's
    page = _page(*UNLINKED, head='<link rel="stylesheet" href="/static/css/detail.css">')
    parser = Cnki(BeautifulSoup(page, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()


def test_rhhz_page_is_not_claimed():
    # the nearest other template: a Chinese journal on the Rhhz platform (byline in ul.article-author)
    page = ('<html><head><link rel="stylesheet" href="/style/web/css/public/base/base.css"/>'
            '<meta name="citation_title" content="A title"/></head><body><ul class="article-author">'
            '<li><a class="mainColor">张三</a><sup class="authorTag"><span class="com-num">1</span></sup></li></ul>'
            '<ul class="about-author"><li class="article-author-address"><span>1.</span>'
            '<p class="lostOf">四川大学</p></li></ul></body></html>')
    parser = Cnki(BeautifulSoup(page, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()


def test_login_shell_is_not_claimed():
    # CNKI's sign-up shell (注册管理系统) loads no kcms detail assets and shows no byline
    page = ('<html><head><title>注册管理系统--中国知网</title><link rel="stylesheet" '
            'href="https://login.cnki.net/members/css/style.css"></head><body><div id="reg"></div></body></html>')
    assert not Cnki(BeautifulSoup(page, "lxml")).authors_found()
