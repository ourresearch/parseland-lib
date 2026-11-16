"""Rhhz (Beijing Renhe Huizhi) journal pages: byline, affiliations, corresponding author, funding, references (#2268).

Markup is cut down from stored pages of AIMS Press, Acta Physica Sinica (wulixb.iphy.ac.cn), Acta Petrologica Sinica,
Chinese Optics, Chinese Journal of Space Science and Light: Advanced Manufacturing (16 Nov 2026). The meta tags list
every citation_author before every citation_author_institution (AIMS pages repeat the author tags), so the generic
parser hung all affiliations on the last author; the byline links them with superscript tags.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rhhz import Rhhz

URL = "https://doi.org/10.3934/math.2023999"


def _page(body, names=("Ann Lee", "Bo Chen"), insts=("Inst A", "Inst B")):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    metas += "".join(f'<meta name="citation_author_institution" content="{i}"/>' for i in insts)
    metas += "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)  # AIMS repeats them
    return (f'<html><head><meta name="citation_title" content="A title"/>{metas}'
            f'<meta name="citation_abstract" content="{"An abstract sentence that is long enough to keep. " * 6}"/>'
            f'</head><body><div class="articleEn">{body}</div></body></html>')


def _li(name, tags="", icon="", email=""):
    num = f'<a href="javascript:void(0);" class="com-num" data-tagVal="{tags}">{tags}</a>' if tags else ""
    return (f'<li><a href="javascript:void(0);" class="mainColor" data-relate="{email}">{name}</a>'
            f'<sup class="authorTag">{num}{icon}</sup>,&nbsp;</li>')


def _icon(title):
    return f'<a href="javascript:void(0);" class="com-user" title="{title}"></a>'


def _addr(label, text, tag="div"):
    return (f'<li class="article-author-address"><span class=""> {label} </span>'
            f'<{tag} class="lostOf">{text}</{tag}></li>')


def _parse(html):
    out = parse_page(html.encode(), "doi", URL)
    return [(a["name"], [x["name"] for x in a["affiliations"]], bool(a["is_corresponding"])) for a in out["authors"]]


def _raw(html):
    return Rhhz(BeautifulSoup(html, "lxml")).parse()


AIMS_BYLINE = ('<ul class="article-author clear">'
               + _li("Ann Lee", "1")
               + _li("Bo Chen", "2,3", _icon("Corresponding Author:&nbsp;Bo Chen,&nbsp;bo@example.cn"), "bo@example.cn")
               + '</ul><ul class="about-author">'
               + _addr("1.", "School of Management, Example University, Guangzhou 510520, China")
               + _addr("2.", "School of Mathematics, Example Institute of Technology, Guilin 541004, China")
               + _addr("3.", "Center for Applied Mathematics, Guilin 541004, China")
               + "</ul>")


def test_superscript_tags_link_each_author_to_their_affiliations():
    assert _parse(_page(AIMS_BYLINE)) == [
        ("Ann Lee", ["School of Management, Example University, Guangzhou 510520, China"], False),
        ("Bo Chen", ["School of Mathematics, Example Institute of Technology, Guilin 541004, China",
                     "Center for Applied Mathematics, Guilin 541004, China"], True),
    ]


def test_hidden_author_box_popup_is_not_read():
    popup = ('<div class="author-box"><div class="author-content"><h6><span>通讯作者: </span>陈某, x@example.cn</h6>'
             '<ul><li><span>1.&nbsp;</span><p>沈阳某大学 沈阳 110142</p></li></ul></div></div>')
    assert _parse(_page(AIMS_BYLINE + popup))[0][1] == ["School of Management, Example University, Guangzhou 510520, China"]


BILINGUAL = ('<div class="info-cn"><ul class="article-author">'
             + _li("王一", "1") + _li("李二", "2") + _li("张三", "1", email="zs@example.cn")
             + '</ul><ul class="about-author"><h6>'
             + _addr("1.", "某大学电气工程学院, 秦皇岛 066004;", "p") + _addr("2.", "某医院康复医学科, 秦皇岛 066100", "p")
             + '</h6><h6 class="com-author-info"><b>通信作者:</b> 张三, <a href="mailto:zs@example.cn">zs@example.cn</a></h6>'
             + '<li class="com-author-info article-fundPrjs"><div class="com-author-info"><b>基金项目:&nbsp;</b>'
               '国家自然科学基金（批准号：61271142）资助的课题.</div></li></ul></div>'
             + '<div class="info-en"><ul class="article-author">'
             + _li("Wang Yi", "1") + _li("Li Er", "2") + _li("Zhang San", "1")
             + '</ul><ul class="about-author"><h6>'
             + _addr("1.", "College of Electrical Engineering, Example University, Qinhuangdao 066004, China", "p")
             + _addr("2.", "Department of Rehabilitation, Example Hospital, Qinhuangdao 066100, China", "p")
             + '</h6><h6 class="com-author-info"><b>Corresponding author:</b> Zhang San, zs@example.cn</h6>'
             + '<li class="com-author-info article-fundPrjs"><div class="com-author-info"><b>Funds:&nbsp;</b>'
               'Project supported by the National Natural Science Foundation of China (Grant No. 61271142).</div></li>'
             + '</ul></div>')


def test_bilingual_page_keeps_the_first_byline_and_marks_the_named_corresponding_author():
    html = _page(BILINGUAL, names=("王一", "李二", "张三"), insts=())
    assert _parse(html) == [
        ("王一", ["某大学电气工程学院, 秦皇岛 066004"], False),
        ("李二", ["某医院康复医学科, 秦皇岛 066100"], False),
        ("张三", ["某大学电气工程学院, 秦皇岛 066004"], True),
    ]


def test_funding_statement_without_its_label_english_version_preferred():
    html = _page(BILINGUAL, names=("王一", "李二", "张三"), insts=())
    assert _raw(html)["funding_statement"] == ("Project supported by the National Natural Science Foundation of China "
                                               "(Grant No. 61271142).")


def test_one_affiliation_without_markers_goes_to_every_author():
    body = ('<ul class="article-author">' + _li("王一") + _li("李二") + '</ul><ul class="about-author"><h6>'
            + _addr("1.", "某大学物理电子学院, 成都 610054", "p") + "</h6></ul>")
    assert [a[1] for a in _parse(_page(body, names=("王一", "李二"), insts=()))] == [["某大学物理电子学院, 成都 610054"]] * 2


def test_label_printed_inside_the_text_and_editor_line_skipped():
    body = ('<ul class="article-author">' + _li("王一", "1,2") + _li("李二", "2")
            + '</ul><ul class="marginT addresswrap">'
            + '<li class="article-author-address"><span class=""> </span><p>1. 某研究所 北京 100190;</p></li>'
            + '<li class="article-author-address"><span class=""> </span><p>2. 某大学工程科学学院 北京 100049;</p></li>'
            + '<li class="article-author-address">Academic Editor: Someone Else</li></ul>')
    assert [a[1] for a in _parse(_page(body, names=("王一", "李二"), insts=()))] == [
        ["某研究所 北京 100190", "某大学工程科学学院 北京 100049"], ["某大学工程科学学院 北京 100049"]]


def test_unlabelled_icon_explained_by_a_corresponding_line_in_a_sibling_paragraph():
    body = ('<ul class="article-author">' + _li("王一", "1") + _li("赵四", "1", _icon("赵四,&nbsp;zs@example.cn"))
            + '</ul><ul class="addresswrap">' + _addr("1.", "某研究所 北京 100190", "p") + '</ul>'
            + '<ul class="about-author"><h6 class="com-author-info marginT"><b>通讯作者:</b>'
              '<p class="author-info-txzz"><span class="txzz"> 赵四,E-mail:zs@example.cn</span></p></h6></ul>')
    assert [a[2] for a in _parse(_page(body, names=("王一", "赵四"), insts=()))] == [False, True]


def test_unlabelled_icon_with_no_explanation_marks_no_one():
    body = ('<ul class="article-author">' + _li("王一", "1") + _li("赵四", "1", _icon("赵四,&nbsp;"))
            + '</ul><ul class="addresswrap">' + _addr("1.", "某研究所 北京 100190", "p") + '</ul>')
    assert [a[2] for a in _parse(_page(body, names=("王一", "赵四"), insts=()))] == [False, False]


def test_equal_contribution_note_after_the_corresponding_line_marks_no_one():
    body = ('<ul class="article-author">' + _li("Ann Lee", "1") + _li("Bo Chen", "1")
            + '</ul><ul class="addresswrap">' + _addr("1.", "Example Institute, Beijing 100094, China", "p") + '</ul>'
            + '<ul class="about-article"><li><div class="corr-tit"><b>Corresponding author:</b></div>'
              '<span class="prinAuthor">Bo Chen (<a href="mailto:bo@example.cn">bo@example.cn</a>)</span></li>'
              '<li><p>These authors contributed equally: Ann Lee, Bo Chen</p></li></ul>')
    assert [a[2] for a in _parse(_page(body))] == [False, True]


def _refs(rows, extra=""):
    return (AIMS_BYLINE + extra + '<div class="References-wrap"><table class="reference-tab">' + "".join(rows)
            + "</table></div>")


def _row(n, text):
    num = f'<td class="td1" valign="top">[{n}]</td>' if n else '<td style="width:2em;"></td>'
    return f'<tr class="document-box"><td></td></tr>'.replace('<td></td>', num + f'<td class="td2">{text}</td>')


def test_numbered_reference_list_is_whole_with_dois_and_no_link_buttons():
    rows = [_row(1, 'A. Author, <i>A title</i>, J. Ex., 2019, 9, 1-2. doi: <a href="https://doi.org/10.1016/j.ex.2019.01.002">10.1016/j.ex.2019.01.002</a>'
                    ' <p><span><a href="https://doi.org/10.1016/j.ex.2019.01.002">CrossRef</a></span> '
                    '<span><a href="http://scholar.google.com/scholar?q=x">Google Scholar</a></span></p>'),
            _row(2, "B. Author, Another title, J. Ex., 2020, 10, 3-4.")]
    out = _raw(_page(_refs(rows)))
    assert out["references_complete"] is True
    assert out["references"] == [
        {"position": 1, "raw": "A. Author, A title, J. Ex., 2019, 9, 1-2. doi: 10.1016/j.ex.2019.01.002", "doi": "10.1016/j.ex.2019.01.002"},
        {"position": 2, "raw": "B. Author, Another title, J. Ex., 2020, 10, 3-4.", "doi": None}]


def test_reference_numbers_with_a_gap_are_not_whole():
    out = _raw(_page(_refs([_row(1, "A. Author, Title one, 2019."), _row(3, "C. Author, Title three, 2021.")])))
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_unnumbered_list_is_whole_only_when_the_stated_count_matches():
    rows = [_row(None, "Agard P. 2009. Exhumation. Earth-Science Reviews, 92: 53-79"),
            _row(None, "Beaumont C. 1996. Mechanical model. Geology, 24: 675-678")]
    tab = '<a class="tablisttit" hrefs="#Referencetab">参考文献 ({})</a>'
    assert _raw(_page(_refs(rows, tab.format(2))))["references_complete"] is True
    assert _raw(_page(_refs(rows, tab.format(3))))["references_complete"] is False
    assert _raw(_page(_refs(rows)))["references_complete"] is False


def test_magtech_page_of_the_same_journals_is_not_claimed():
    html = ('<html><head><meta name="citation_authors" content="王一;李二"/></head><body>'
            '<td class="J_author_cn">王一;李二</td><td class="J_author_EN">某大学医学院,杭州,310006</td></body></html>')
    assert not Rhhz(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_other_templates_with_article_author_classes_are_not_claimed():
    springer = ('<html><body><ul class="c-article-author-list"><li class="c-article-author-list__item">'
                '<a data-test="author-name">Ann Lee</a><sup>1</sup></li></ul></body></html>')
    rendered = ('<html><body><div class="articleEn"><ul class="article-author clear"><li>'
                '<a href="javascript:void(0);" class="mainColor" data-relate="">Ann Lee</a>,&nbsp;</li></ul></div>'
                '</body></html>')  # the client-rendered variant: no authorTag, nothing more to read than the meta tags
    for html in (springer, rendered):
        assert not Rhhz(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_one_address_item_numbered_inside_is_split_and_notes_are_not_affiliations():
    body = ('<ul class="article-author">' + _li("王一", "2") + _li("李二", "1") + '</ul><ul class="about-author"><h6>'
            + '<li class="article-author-address"><p class="lostOf">(1)某大学物理系，北京 100871; (2)某研究所，北京 100085</p></li>'
            + _addr("3.", "These authors contributed equally", "p") + "</h6></ul>")
    assert [a[1] for a in _parse(_page(body, names=("王一", "李二"), insts=()))] == [
        ["某研究所，北京 100085"], ["某大学物理系，北京 100871"]]


def test_bare_number_labels_printed_in_the_text_link_each_author():
    # Chinese Birds (j-avianres.com): "1 School of ...;" with no stop after the number and an empty label span
    body = ('<ul class="article-author">' + _li("Ann Lee", "1") + _li("Bo Chen", "2")
            + '</ul><ul class="about-author addresswrap">'
            + '<li class="article-author-address"><span class=""> </span><p> 1 School of Life Sciences, Example '
              'University, Lanzhou 730000, China;</p></li>'
            + '<li class="article-author-address"><span class=""> </span><p> 2 Bureau of Quality Monitoring, '
              'Baise 533000, Guangxi, China</p></li></ul>')
    assert [a[1] for a in _parse(_page(body))] == [
        ["School of Life Sciences, Example University, Lanzhou 730000, China"],
        ["Bureau of Quality Monitoring, Baise 533000, Guangxi, China"]]


def test_one_item_holding_a_bare_numbered_list_is_split_and_et_al_is_not_an_author():
    # Nuclear Physics Review (npr.ac.cn): "1 X; 2 Y; 3 Z;" in one address item, and a shortened byline ending "et al."
    body = ('<ul class="article-author">' + _li("F. Miya", "1") + _li("M. Itoh", "2") + _li("et al.")
            + '</ul><ul class="about-author"><li class="article-author-address"><span class=""> </span><p>'
              '1 Laboratory of Nuclear Science, Example University Mikamine 121, Sendai 9820826, Japan; '
              '2 Radioisotope Center, Example University, Sendai 9808578, Japan; 3 KEK, Tsukuba 3050801, Japan;'
              '</p></li></ul>')
    assert _parse(_page(body, names=("F. Miya", "M. Itoh"), insts=())) == [
        ("F. Miya", ["Laboratory of Nuclear Science, Example University Mikamine 121, Sendai 9820826, Japan"], False),
        ("M. Itoh", ["Radioisotope Center, Example University, Sendai 9808578, Japan"], False)]


def _mail(email):
    return f'<a href="mailto:{email}" class="com-mail" title="mailto:&nbsp;{email}"></a>'


def test_envelope_beside_one_author_marks_them_when_the_byline_has_no_corresponding_icon():
    # Quaternary Sciences (dsjyj.com.cn): no com-user icon and no "通讯作者" line, only the envelope on the first author
    body = ('<ul class="article-author">' + _li("程一", "1", _mail("c@example.cn"), "c@example.cn") + _li("李二", "1")
            + _li("张三", "1") + '</ul><ul class="about-author">' + _addr("1.", "某大学全球变化研究院, 西安 710054", "p")
            + '</ul>')
    assert [a[2] for a in _parse(_page(body, names=("程一", "李二", "张三"), insts=()))] == [True, False, False]
    every = ('<ul class="article-author">' + _li("程一", "1", _mail("c@example.cn")) + _li("李二", "1", _mail("l@example.cn"))
             + '</ul><ul class="about-author">' + _addr("1.", "某大学全球变化研究院, 西安 710054", "p") + '</ul>')
    assert [a[2] for a in _parse(_page(every, names=("程一", "李二"), insts=()))] == [False, False]
