"""Acta Ecologica Sinica (生态学报, www.ecologica.cn) article pages: byline, affiliations, funding (oxjob #2339).

Markup is cut down from stored ecologica.cn abstract pages (17 Nov 2026). The site's byline is empty in the stored
page and filled in the browser from a JSON string in an inline script (strAuthorsJson); the institutions are printed
once, unlinked, under 作者单位; the funding text under 基金项目 / Fund Project. No parser claimed the pages: the generic
one read nothing, or both the Chinese and the English citation_author tags as one doubled byline.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ecologica import Ecologica

URL = "https://doi.org/10.5846/stxb201012011707"


def _authors_json(authors):
    """The inline script's string literal: JSON with its quotes escaped, as the site writes it."""
    rows = [{"cn_name": cn, "en_name": en, "cn_institution": inst, "en_institution": "", "email": email,
             "is_first_author": "1" if i == 0 else "0", "is_contact_author": "", "sequence": str(i + 1),
             "institute_superscript": ""} for i, (cn, en, inst, email) in enumerate(authors)]
    literal = json.dumps(json.dumps({"authors": rows}, ensure_ascii=False), ensure_ascii=False)
    return f'<script language="javascript">\n  var strCnAuthorsList="";\n  var strAuthorsJson={literal};\n</script>'


AUTHORS = [("韩大勇", "HAN Dayong", "同济大学环境科学与工程学院, 上海 200092", ""),
           ("杨永兴", "YANG Yongxing", "同济大学环境科学与工程学院, 上海 200092", "wetlands@example.edu.cn"),
           ("杨杨", "YANG Yang", "同济大学生命科学与技术学院, 上海 200092", "")]


def _page(institutions="", cn_fund="", en_fund="", journal="生态学报", authors=AUTHORS, script=True):
    metas = "".join(f'<meta name="citation_author" content="{cn}"/>' for cn, _, _, _ in authors)
    metas += "".join(f'<meta name="citation_author" content="{en}"/>' for _, en, _, _ in authors)
    return (f'<html><head><base href="/"><title>湿地退化研究进展</title>'
            f'<meta name="citation_title" content="湿地退化研究进展"/>'
            f'<meta name="citation_journal_title" content="{journal}"/>{metas}</head><body>'
            '<div class="zh"><div class="title">湿地退化研究进展</div>'
            '<div class="line m-row"><span class="tl">作者:</span><div class="tr"><ul id="CnAuthorList"></ul></div></div>'
            '<div class="line m-row" id="DisplayCnInstitution"><span class="tl">作者单位:</span>'
            f'<div class="tr"><p id="DisplayCnInstitutionValue">{institutions}</p></div></div>'
            '<div class="line m-row" id="ContactAuthor"><span class="tl">通讯作者:</span>'
            '<div class="tr"><p id="ContactAuthorValue"></p></div></div>'
            '<div class="line m-row" id="CnFundProject"><span class="tl">基金项目:</span>'
            f'<div class="tr"><p id="CnFundProjectValue">{cn_fund}</p></div></div></div>'
            '<div class="en" id="EnTitle"><div class="line m-row" id="EnFundProject"><span class="tl">Fund Project:</span>'
            f'<div class="tr"><p id="EnFundProjectValue">{en_fund}</p></div></div></div>'
            '<div class="zy"><div class="zh" id="CnAbstract"><span>摘要:</span><p id="CnAbstractValue">'
            + "受经济发展、城市扩张、气候变化的影响,湿地退化已经成为全球性现象。" * 4 + '</p></div>'
            '<div class="en" id="EnAbstract"><span>Abstract:</span><p id="EnAbstractValue">'
            + "Economic development and climate change have caused the degradation of wetlands. " * 4 + '</p></div></div>'
            '<div class="ckwx"><div class="title">参考文献</div><div class="list" id="ReferenceList"></div></div>'
            f'{_authors_json(authors) if script else ""}</body></html>')


def _parse(html):
    out = parse_page(html.encode(), "doi", URL)
    return [(a["name"], [x["name"] for x in a["affiliations"]], bool(a["is_corresponding"])) for a in out["authors"]]


def _raw(html):
    return Ecologica(BeautifulSoup(html, "lxml")).parse()


def test_byline_comes_from_the_script_json_in_chinese():
    assert _parse(_page()) == [("韩大勇", [], False), ("杨永兴", [], False), ("杨杨", [], False)]


def test_printed_institutions_go_to_every_author_unlinked_and_deduplicated():
    printed = ("同济大学环境科学与工程学院污染控制与资源化国家重点实验室,长江水环境教育部重点实验室,"
               "同济大学环境科学与工程学院污染控制与资源化国家重点实验室,同济大学生命科学与技术学院;四川省草原科学研究院")
    whole = ["同济大学环境科学与工程学院污染控制与资源化国家重点实验室", "长江水环境教育部重点实验室",
             "同济大学生命科学与技术学院", "四川省草原科学研究院"]
    assert _parse(_page(institutions=printed)) == [(n, whole, False) for n in ("韩大勇", "杨永兴", "杨杨")]


def test_an_english_institution_keeps_its_commas():
    printed = ("中国大熊猫保护研究中心,Department of Wildlife Ecology and Conservation, University of Florida,"
               "中国大熊猫保护研究中心,Institute for Environmental Genomics,University of Oklahoma,Norman,OK;"
               "Institute for Environmental Genomics,University of Oklahoma,Norman,OK")
    affs = _parse(_page(institutions=printed))[0][1]
    assert affs == ["中国大熊猫保护研究中心", "Department of Wildlife Ecology and Conservation, University of Florida",
                    "Institute for Environmental Genomics,University of Oklahoma,Norman,OK"]


def test_no_author_is_marked_corresponding():
    # every author's is_contact_author is empty; one author carrying an e-mail is not a mark the page explains
    assert not any(corr for _, _, corr in _parse(_page()))


def test_funding_statement_is_the_chinese_label_first():
    raw = _raw(_page(cn_fund="国家自然科学基金项目（32071594）；&quot;十四五&quot;国家重点研发计划（2021YFD2200403）",
                     en_fund="The National Natural Science Foundation of China"))
    assert raw["funding_statement"] == '国家自然科学基金项目（32071594）；"十四五"国家重点研发计划（2021YFD2200403）'


def test_funding_statement_falls_back_to_english_then_none():
    assert _raw(_page(en_fund="National Natural Science Foundation of China (41171074)"))["funding_statement"] == \
        "National Natural Science Foundation of China (41171074)"
    assert _raw(_page())["funding_statement"] is None


def test_no_acknowledgments_or_reference_list_on_the_stored_page():
    raw = _raw(_page())
    assert raw["acknowledgments"] is None
    assert raw["references"] is None
    assert raw["references_complete"] is False


def test_abstract_is_left_to_parse_page():
    assert _raw(_page())["abstract"] is None
    assert parse_page(_page().encode(), "doi", URL)["abstract"]


def test_another_qinyun_journal_is_not_claimed():
    # the same journal system serves other Chinese journals with the same script: not this site
    html = _page(journal="植物生态学报")
    parser = Ecologica(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_a_page_without_the_script_is_not_read():
    # the site's old view_abstract.aspx pages carry the journal tag but no strAuthorsJson
    parser = Ecologica(BeautifulSoup(_page(script=False), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
