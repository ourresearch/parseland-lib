"""Hong Kong Anmai Publishing (anmaichuban.com) article pages (oxjob #2210).

The site runs its own CMS with two skins (an older `div.container2` page and a newer `div.body_txt` page) that share one
article body: a title <h2>, the byline in a second <h2>/<h4> or after a <br> in the title <h2>, one <p> per affiliation,
a "摘要：" paragraph, "关键词：", then "参考文献" and one "[n]" paragraph per reference. The pages carry no citation_*
meta tags, so the generic parser read nothing. Markup below is cut down from stored pages; names are placeholders.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.anmaichuban import Anmaichuban

URL = "https://www.anmaichuban.com/journal/gcjslt/3413.html"
HEAD = ('<head><title>某标题_工程技术论坛_香港安麦出版有限公司</title>'
        '<link rel="stylesheet" type="text/css" href="https://www.anmaichuban.com/css/base.css?v=66699"/></head>')
NEW_HEAD = ('<head><title>某标题_香港安麦出版有限公司</title>'
            '<link rel="stylesheet" type="text/css" href="https://www.anmaichuban.com/img/style.css?v=9987"/></head>')

ABSTRACT = "随着电力系统的规模不断扩大和复杂性增加，次同步振荡问题日益突出，对电网的安全稳定运行构成了潜在威胁。"
REFS = ('<p>参考文献</p>'
        '<p>[1]李立浧.浅谈电力系统次同步振荡的自适应阻尼控制策略[J].电力系统自动化,2023,31(7):17-19.</p>'
        '<p>[2]伍凌云.基于电力系统次同步振荡的同步阻尼控制设计[J].电力系统自动化,2024,31(11):21-23.DOI:10.16576/j.ISSN.1007-4414.2026.04.017.</p>'
        '<p>[3]周长春.论电力系统次同步振荡的宽频带监测技术[J].中国电机工程学报,2023,23(10):27-29.</p>')


def _old(article, head=HEAD):
    return (f'<html>{head}<body><div class="pro-detailed"><div class="info"><div class="tit">工程技术论坛</div></div></div>'
            f'<div class="container container2">{article}</div></body></html>')


def _new(article, head=NEW_HEAD):
    return f'<html>{head}<body><div class="ty01 m_30"><div class="ty02 qk05"><div class="body_txt">{article}</div></div></div></body></html>'


def _span(text):
    return f'<span style=";font-family:楷体;font-size:15px">{text}</span>'


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(author):
    return [a["name"] for a in author["affiliations"]]


SINGLE = (f'<h2 style="text-align: center;">{_span("电力系统次同步振荡的宽频带监测与自适应阻尼控制策略")}</h2>'
          f'<h2 style="text-align: center;">{_span("张三")}</h2>'
          f'<p style="text-align: center;">{_span("河南某电力工程有限公司")}{_span("，")}{_span("河南省新乡市")}'
          f'<span><span>，</span><span>453000；</span></span></p>'
          f'<p>摘要：{ABSTRACT}</p><p>关键词：电力系统次同步振荡；宽频带监测</p>' + REFS)


def test_old_skin_single_author_affiliation_and_abstract():
    out = _parse(_old(SINGLE))
    assert [a["name"] for a in out["authors"]] == ["张三"]
    assert _affs(out["authors"][0]) == ["河南某电力工程有限公司，河南省新乡市，453000"]
    assert out["authors"][0]["is_corresponding"] is False
    assert out["abstract"] == ABSTRACT


def test_new_skin_byline_after_br_with_shared_affiliation_and_corresponding_label():
    article = ('<h2 style="text-align: center;">长三角地区数字经济对服务贸易出口的促进作用<br/>'
               f'{_span("张三")}{_span("&nbsp;")}{_span("李四")}{_span("&nbsp;")}{_span("王五")}'
               '<sup><span>（</span></sup><sup><span>通讯作者</span></sup><sup><span>）</span></sup></h2>'
               '<p style="text-align: center;">上海某大学经济学院，上海，200080；</p>'
               f'<p>摘要：{ABSTRACT}</p><p>关键词：长三角；数字经济</p>')
    out = _parse(_new(article))
    assert [a["name"] for a in out["authors"]] == ["张三", "李四", "王五"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True]
    assert all(_affs(a) == ["上海某大学经济学院，上海，200080"] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_numbered_affiliations_link_by_sup_marker():
    article = ('<h2>民事检察监督的介入边界</h2><h2>张三<sup>1</sup> 李四<sup>2</sup></h2>'
               '<p>1长沙市某区人民检察院，湖南省长沙市，410000；</p><p>2 某政法大学，北京市海淀区，100088；</p>'
               f'<p>摘要：{ABSTRACT}</p><p>关键词：民事检察</p>')
    out = _parse(_new(article))
    assert [a["name"] for a in out["authors"]] == ["张三", "李四"]
    assert _affs(out["authors"][0]) == ["长沙市某区人民检察院，湖南省长沙市，410000"]
    assert _affs(out["authors"][1]) == ["某政法大学，北京市海淀区，100088"]


def test_plain_digit_markers_and_inline_corresponding_label():
    article = ('<h2>学科交叉与学科竞赛双驱动的人才培养研究<br/>张三1 李四(通讯作者)1 王五2</h2>'
               '<p>1某工学院智能机电工程学院，河南郑州，450007；</p><p>2某研究院腐蚀与防护研究所，陕西西安，710016；</p>'
               f'<p>摘要：{ABSTRACT}</p><p>关键词：学科交叉</p>')
    out = _parse(_new(article))
    assert [a["name"] for a in out["authors"]] == ["张三", "李四", "王五"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True, False]
    assert _affs(out["authors"][1]) == ["某工学院智能机电工程学院，河南郑州，450007"]
    assert _affs(out["authors"][2]) == ["某研究院腐蚀与防护研究所，陕西西安，710016"]


def test_masked_id_number_line_is_not_an_affiliation():
    article = ('<h2>建筑施工高处坠落事故致因分析及预防对策<br/>张三</h2><p>460102********1815</p>'
               f'<p>摘要：{ABSTRACT}</p><p>关键词：建筑施工</p>')
    out = _parse(_old(article))
    assert [a["name"] for a in out["authors"]] == ["张三"]
    assert out["authors"][0]["affiliations"] == []


def test_two_paragraph_abstract_stops_at_keywords():
    article = ('<h2>某题目</h2><h2>张三</h2><p>某发电分公司，云南昆明，650228；</p>'
               '<p>摘要：第一段摘要文字，说明研究背景与问题。</p><p>第二段摘要文字，说明方法与结论。</p>'
               '<p>关键词：国有企业；党建</p><p>正文不应进入摘要。</p>')
    out = _parse(_new(article))
    assert out["abstract"] == "第一段摘要文字，说明研究背景与问题。\n第二段摘要文字，说明方法与结论。"


def test_references_complete_list_with_doi():
    soup = BeautifulSoup(_old(SINGLE), "lxml")
    parsed = Anmaichuban(soup).parse()
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == "李立浧.浅谈电力系统次同步振荡的自适应阻尼控制策略[J].电力系统自动化,2023,31(7):17-19."
    assert refs[0]["doi"] is None
    assert refs[1]["doi"] == "10.16576/j.ISSN.1007-4414.2026.04.017"
    assert parsed["references_complete"] is True
    assert parsed["acknowledgments"] is None
    assert parsed["funding_statement"] is None


def test_reference_url_line_joins_its_entry_and_gap_is_not_complete():
    refs = ('<p>参考文献</p><p>[1]某作者.某文章[N].某报,2025-12-16.</p>'
            '<p>https://www.example.com/article/20251216/c1.html</p><p>[2]某作者.某书[M].北京:某出版社,2020.</p><p><br/></p>')
    soup = BeautifulSoup(_new(f'<h2>某题目</h2><h2>张三</h2><p>某大学，广东东莞，523668；</p><p>摘要：{ABSTRACT}</p>'
                              f'<p>关键词：某</p>{refs}'), "lxml")
    parsed = Anmaichuban(soup).parse()
    assert [r["position"] for r in parsed["references"]] == [1, 2]
    assert parsed["references"][0]["raw"].endswith("https://www.example.com/article/20251216/c1.html")
    assert parsed["references_complete"] is True
    gap = refs.replace("[2]", "[3]")
    soup = BeautifulSoup(_new(f'<h2>某题目</h2><h2>张三</h2><p>摘要：{ABSTRACT}</p><p>关键词：某</p>{gap}'), "lxml")
    assert Anmaichuban(soup).parse()["references_complete"] is False


def test_issue_listing_page_is_not_read():
    html = (f'<html>{NEW_HEAD}<body><div class="qk02_one"><h1>当代教育与艺术</h1></div>'
            '<ul class="list"><li><a href="/journal/ddjyyys/1.html">某题目</a></li></ul></body></html>')
    assert not Anmaichuban(BeautifulSoup(html, "lxml")).authors_found()


def test_same_markup_on_another_site_is_not_claimed():
    other = ('<head><title>某标题_某出版社</title>'
             '<link rel="stylesheet" type="text/css" href="https://www.example-press.com/img/style.css"/></head>')
    soup = BeautifulSoup(_new(SINGLE, head=other), "lxml")
    parser = Anmaichuban(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert "张三" not in [a["name"] for a in _parse(_new(SINGLE, head=other))["authors"]]
