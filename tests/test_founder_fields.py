"""Founder journal cloud (rc-pub) article pages: the funding statement (oxjob #2268).

Founder's Nuxt journal sites (cjig.cn, ygxb.ac.cn, *.lightpublishing.cn, *.publish.founderss.cn, wsp-publishing.com)
leave the author box empty and print authors and abstract only in citation_* tags, which the generic parser already
reads: those stay exactly as they were. What nothing read is the funding the page states, in a "基金信息" row of the
article's info block and as the article record's fund / enFund value in the preloaded page state. The pages also carry
HighWire's HW.* meta tags: neither a HighWire page nor SciEngine's (another platform with HW.* tags) is claimed.
Hand-cut markup; no network.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.founder import Founder
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

ABSTRACT = ("本文提出了一种基于知识蒸馏的低分辨率陶瓷基板瑕疵自动检测方法。该方法利用YOLOv5框架分别构建了教师网络和学生网络，"
            "基于知识蒸馏思想将教师网络获得的高分辨率图像特征信息指导学生网络的训练，以提高学生网络对低分辨率图像的瑕疵检测能力；"
            "同时在教师网络中引入基于坐标注意力思想的特征融合模块，使教师网络学习到的特征同时适应高分辨率和低分辨率图像信息。"
            "最后引入基于梯度协调机制的置信度损失函数以提高瑕疵的检出率。实验结果表明，本文方法对五类瑕疵的平均准确率和平均召回率"
            "分别达到了96.80%和90.01%，相比于目前主流的目标检测算法取得了更好的检测结果，可以满足工业现场的实时检测需求。")
HEAD = ('<meta name="HW.identifier" content="https://ope.example.cn/zh/article/doi/10.1/x/">'
        '<meta name="citation_title" content="基于知识蒸馏的图像瑕疵检测">'
        '<meta name="citation_author" content="郭峰"><meta name="citation_author" content="朱启兵">'
        f'<meta name="citation_abstract" content="{ABSTRACT}">'
        '<meta name="citation_doi" content="10.37188/OPE.20233120.3065">')
DOWNLOAD = '<a href="/rc-pub/front/front-article/download/43061641/lowqualitypdf/x.pdf">PDF下载</a>'
ROWS = ('<ul><li class="authors-company clearfix" style="display:none"><div class="fl">作者机构：</div>'
        '<div class="fl authors-company__text"><div><p>1.江南大学 轻工过程先进控制教育部重点实验室</p></div></div></li>'
        '<li class="authors-company clearfix" style="display:none"><div class="fl">基金信息：</div>'
        '<div class="fl authors-company__text">国家自然科学基金资助项目(62273166)</div></li></ul>')


def _state(fund='"国家自然科学基金项目(62376012)"', en_fund='"National Natural Science Foundation of China(62376012)"'):
    return ('<script>window.__NUXT__=(function(a,t,Co){return {data:[{articleInfo:{id:1,'
            f'authorCompany:"北京大学王选计算机研究所,北京,100871",fund:{fund},enFund:{en_fund},year:2025}},'
            'thesisData:{contribgroup:{author:[]}},fundList:[{id:9,name:"教育部人文社会科学研究规划项目"}]}]}'
            '}(null,void 0,"x"));</script>')


def _page(body, lang="zh", head=HEAD):
    return f'<html lang="{lang}"><head>{head}</head><body>{body}</body></html>'


def _parser(html):
    return Founder(BeautifulSoup(html, "lxml"))


def test_claims_a_founder_article_page():
    parser = _parser(_page(DOWNLOAD + ROWS + _state()))
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()


def test_funding_row_is_the_funding_statement():
    out = _parser(_page(DOWNLOAD + ROWS + _state())).parse()
    assert out["funding_statement"] == "国家自然科学基金资助项目(62273166)"
    assert out["acknowledgments"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_funding_from_the_article_record_when_no_row_is_rendered():
    out = _parser(_page(DOWNLOAD + _state())).parse()
    assert out["funding_statement"] == "国家自然科学基金项目(62376012)"


def test_english_page_gives_the_english_funding():
    out = _parser(_page(DOWNLOAD + _state(), lang="en")).parse()
    assert out["funding_statement"] == "National Natural Science Foundation of China(62376012)"


def test_english_page_without_english_funding_gives_the_one_stated():
    out = _parser(_page(DOWNLOAD + _state(en_fund="t"), lang="en")).parse()
    assert out["funding_statement"] == "国家自然科学基金项目(62376012)"


def test_no_funding_when_the_record_holds_none():
    out = _parser(_page(DOWNLOAD + _state(fund="a", en_fund="a"))).parse()
    assert out["funding_statement"] is None


def test_js_escapes_in_the_record_are_decoded():
    out = _parser(_page(DOWNLOAD + _state(fund='"国家重点研发计划项目(2019YFB1803404)\\u002F课题"'))).parse()
    assert out["funding_statement"] == "国家重点研发计划项目(2019YFB1803404)/课题"


def test_site_fund_list_is_never_the_funding_statement():
    state = _state(fund="a", en_fund="a")
    assert "教育部人文社会科学研究规划项目" in state
    assert _parser(_page(DOWNLOAD + state)).parse()["funding_statement"] is None


def test_authors_and_abstract_are_the_generic_parsers():
    html = _page(DOWNLOAD + ROWS + _state())
    founder = _parser(html).parse()
    generic = GenericPublisherParser(BeautifulSoup(html, "lxml")).parse()
    assert founder["authors"] == generic["authors"]
    assert founder["abstract"] == generic["abstract"]
    out = parse_page(html.encode(), "doi", "https://ope.example.cn/zh/article/doi/10.1/x/")
    assert [a["name"] for a in out["authors"]] == ["郭峰", "朱启兵"]
    assert all(not a["affiliations"] and not a["is_corresponding"] for a in out["authors"])
    assert out["abstract"].startswith("本文提出了一种基于知识蒸馏")
    assert out["funding_statement"] == "国家自然科学基金资助项目(62273166)"


HIGHWIRE = ('<html><head><meta name="HW.identifier" content="/jneuro/38/1/1.atom">'
            '<meta name="HW.pisa" content="jneuro;38/1/1">'
            '<meta name="citation_author" content="Jane Roe"><meta name="citation_author" content="John Doe">'
            f'<meta name="citation_abstract" content="{"A HighWire abstract sentence about neurons. " * 5}">'
            '<link rel="stylesheet" href="/sites/all/modules/highwire/highwire/highwire.css"></head><body>'
            '<div class="highwire-cite"><a href="/content/38/1/1.full.pdf">PDF</a></div>'
            '<ul><li class="fn-corresp">Correspondence should be addressed to Jane Roe.</li></ul>'
            '<div class="fn-group"><p>Funding: This work was supported by NIH grant R01.</p></div></body></html>')

SCIENGINE = ('<html><head><meta data-hid="HW.identifier" name="HW.identifier" content="10.1360/SSPMA-2023-0400">'
             '<meta name="citation_author" content="Jie ZHU">'
             f'<meta name="citation_abstract" content="{"Rapid sky survey using a large telescope. " * 5}"></head>'
             '<body><div id="__nuxt"></div><script>window.__NUXT__=(function(a){return {data:[{fund:"x"}]}}(null));'
             '</script></body></html>')


def test_highwire_page_is_not_claimed():
    parser = _parser(HIGHWIRE)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_other_nuxt_page_with_hw_tags_is_not_claimed():
    parser = _parser(SCIENGINE)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_highwire_page_parse_is_unchanged():
    out = parse_page(HIGHWIRE.encode(), "doi", "https://www.jneurosci.org/content/38/1/1")
    assert [a["name"] for a in out["authors"]] == ["Jane Roe", "John Doe"]
    assert out["funding_statement"] != "国家自然科学基金资助项目(62273166)"
