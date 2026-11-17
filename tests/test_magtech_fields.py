"""Magtech (Beijing Magtech) journal pages: byline, affiliations, corresponding author, abstract, funding, references
(oxjob #2289).

Markup is cut down from stored pages of Journal of Inorganic Materials (jim.org.cn), Chemical Journal of Chinese
Universities (jlu.edu.cn), Chinese Journal of Organic Chemistry (sioc-journal.cn), Resources Science and Biodiversity
Science (17 Nov 2026). The meta tags carry one comma-joined citation_authors list: the generic parser hung no
affiliation, or the whole address block, on each name and marked no corresponding author.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.magtech import Magtech

URL = "https://doi.org/10.15541/jim20190426"
GEN = '<META NAME="GENERATOR" CONTENT="Beijing Magtech Co., Ltd">'
ABSTRACT = "The micro-arc oxidation ceramic coating on AZ31 magnesium alloy was treated by hydrothermal treatment. " * 3


def _page(body, head=GEN, lang="zh"):
    return (f'<html><head>{head}<meta name="citation_language" content="{lang}" />'
            f'<meta name="citation_title" content="A title" />'
            f'<meta name="citation_authors" content="WANG Zhihu,ZHANG Jumei" />'
            f'<script language="javascript" src="http://www.jim.org.cn/js/modelDialog1.js"></script>'
            f'</head><body><div class="abs-con">{body}</div></body></html>')


def _byline(panel, names, addresses, info=""):
    items = "".join(f"<li>{a}</li>" for a in addresses)
    return (f'<h3 class="abs-tit">A title</h3><p data-toggle="collapse" data-target="#{panel}"><span>{names}&nbsp;&nbsp;'
            f'<span data-placement="right" type="button"><i class="glyphicon"></i></span></span></p>'
            f'<div id="{panel}" class="collapse bs-callout"><address class="address"><ol class="list-unstyled">{items}'
            f'</ol></address><ul class="list-unstyled code-style">{info}</ul></div>')


def _info(label, value):
    return f'<li><code>{label}</code>{value}</li>'


def _abstract(*parts):
    return f'<div id="collapseOne" class="panel-collapse collapse"><div class="panel-body">{"".join(parts)}</div></div>'


def _parse(html):
    out = parse_page(html.encode(), "doi", URL)
    return [(a["name"], [x["name"] for x in a["affiliations"]], bool(a["is_corresponding"])) for a in out["authors"]]


def _raw(html):
    return Magtech(BeautifulSoup(html, "lxml")).parse()


MAIL = '(<a href="mailto:z@xaut.edu.cn"><img src="http://www.jim.org.cn/images/email.png" border="0" /></a>)'


def test_byline_labels_link_affiliations_split_at_br():
    names = f"WANG Zhihu<sup>1</sup>,ZHANG Jumei<sup>2</sup>,ZHANG Guojun<sup>1</sup>{MAIL}"
    addr = "<sup>1.</sup> School of Materials, Xi'an University of Technology<br/><sup>2.</sup> School of Materials, Xi'an University of Science and Technology"
    got = _parse(_page(_byline("divPanelEn", names, [addr], _info("Contact:", "")), lang="en"))
    assert got == [("WANG Zhihu", ["School of Materials, Xi'an University of Technology"], False),
                   ("ZHANG Jumei", ["School of Materials, Xi'an University of Science and Technology"], False),
                   ("ZHANG Guojun", ["School of Materials, Xi'an University of Technology"], True)]


def test_numbered_affiliations_in_one_line_and_named_contact():
    names = "张紫涵<sup>1</sup>, 崔慧娟<sup>1,2</sup>, 闫清波<sup>3</sup>"
    addr = "1. 中国科学院大学物理科学学院, 北京 100049; 2. 北京建筑大学理学院, 北京 102616; 3. 中国科学院大学材料科学与光电技术学院, 北京 100049"
    got = _parse(_page(_byline("divPanel", names, [addr], _info("通讯作者:", "闫清波 E-mail:yan@ucas.ac.cn"))))
    assert got == [("张紫涵", ["中国科学院大学物理科学学院, 北京 100049"], False),
                   ("崔慧娟", ["中国科学院大学物理科学学院, 北京 100049", "北京建筑大学理学院, 北京 102616"], False),
                   ("闫清波", ["中国科学院大学材料科学与光电技术学院, 北京 100049"], True)]


def test_chinese_byline_first_and_english_contact_by_position():
    cn = _byline("divPanel", "王翠玲, 刘建利", ["西北大学生命科学学院, 西安 710069"])
    en = _byline("divPanelEn", "WANG Cuiling, LIU Jianli<sup>&#x0002A;</sup>", ["School of Life Science, Northwest University"],
                 _info("Contact:", "LIU Jianli"))
    assert _parse(_page(cn + en)) == [("王翠玲", ["西北大学生命科学学院, 西安 710069"], False),
                                      ("刘建利", ["西北大学生命科学学院, 西安 710069"], True)]


def test_english_page_reads_the_english_byline():
    cn = _byline("divPanel", "张鑫伟, 黄晓雷<sup>*</sup>", ["浙江师范大学"])
    en = _byline("divPanelEn", "Xinwei Zhang, Xiaolei Huang<sup>*</sup>", ["Zhejiang Normal University, Jinhua"],
                 _info("Contact:", "* E-mail: huang@zjnu.edu.cn"))
    assert _parse(_page(cn + en, lang="en")) == [("Xinwei Zhang", ["Zhejiang Normal University, Jinhua"], False),
                                                 ("Xiaolei Huang", ["Zhejiang Normal University, Jinhua"], True)]


def test_named_contact_wins_over_mail_icons():
    names = f"杨喆{MAIL}, 褚琳{MAIL}, 王晨"
    got = _parse(_page(_byline("divPanel", names, ["华中农业大学资源与环境学院，武汉 430070"],
                                 _info("通讯作者:", "褚琳，女，湖北武汉人，副教授。E-mail: chulin@mail.hzau.edu.cn"))))
    assert [n for n, _, c in got if c] == ["褚琳"]


def test_unexplained_star_is_not_a_mark():
    got = _parse(_page(_byline("divPanel", "王丽嘉<sup>*</sup>, 林剑圣", ["上海理工大学"])))
    assert [c for _, _, c in got] == [False, False]


def test_unlabelled_byline_gets_every_listed_affiliation():
    got = _parse(_page(_byline("divPanel", "赵健，赵梦瑶", ["（1.北京工商大学，北京 100048；2.太原理工大学化学化工学院，太原 030024）"])))
    assert got[0][1] == got[1][1] == ["北京工商大学，北京 100048", "太原理工大学化学化工学院，太原 030024"]


def test_english_abstract_is_chosen_over_chinese():
    body = _byline("divPanel", "王翠玲", ["西北大学"]) + _abstract(
        "<p><strong>摘要： </strong><p>以药用植物体内存在的生物合成前体吲哚醌和邻氨基苯甲酸为反应物, 仿生合成了天然产物色胺酮.</p></p>",
        f'<form name="refForm"><p><strong>关键词: </strong><a href="#">色胺酮</a></p>'
        f"<p><strong>Abstract: </strong><p>{ABSTRACT}</p></p><p><strong>Key words: </strong>Tryptanthrin</p></form>")
    assert parse_page(_page(body).encode(), "doi", URL)["abstract"].startswith("The micro-arc oxidation")


def test_funding_and_whole_reference_list():
    rows = "".join(f'<tr><td valign="top">[{i}]</td><td><span class="magtech_ref_source">Author {i}. A cited paper '
                   f'title. J. Chem., 2014, 60:1-71.</span><br/><a href="http://dx.doi.org/10.1016/j.x.2013.{i}">DOI</a>'
                   f'</td></tr>' for i in (1, 2, 3))
    refs = (f'<div class="panel-heading" id="cankaowenxian"><h4><a id="reference">References <span class="badge">3'
            f'</span></a></h4></div><div id="collapseThree"><div class="panel-body"><table>{rows}</table></div></div>')
    body = _byline("divPanelEn", "WANG Zhihu", ["Xi'an University of Technology"],
                   _info("Supported by:", '<div class="pull-left">National Natural Science Foundation of China(51701162)</div>'))
    raw = _raw(_page(body + refs, lang="en"))
    assert raw["funding_statement"] == "National Natural Science Foundation of China(51701162)"
    assert [r["doi"] for r in raw["references"]] == ["10.1016/j.x.2013.1", "10.1016/j.x.2013.2", "10.1016/j.x.2013.3"]
    assert raw["references_complete"] is True
    short = refs.replace('<span class="badge">3', '<span class="badge">5')  # the stated count disagrees
    assert _raw(_page(body + short, lang="en"))["references_complete"] is False


def test_rhhz_page_with_the_same_script_is_not_claimed():
    # Rhhz (rhhz.py) pages load modelDialog1.js too, and carry a citation_state tag and style/web/ assets
    head = ('<meta name="citation_state" content="online"/>'
            '<link rel="stylesheet" href="/style/web/css/public/base/base.css"/>')
    html = _page(_byline("divPanel", "王翠玲, 刘建利", ["西北大学"]), head=head)
    assert not Magtech(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_page_without_the_platform_marks_is_not_claimed():
    html = _page(_byline("divPanel", "王翠玲, 刘建利", ["西北大学"]), head="").replace("modelDialog1.js", "dialog.js")
    assert not Magtech(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
