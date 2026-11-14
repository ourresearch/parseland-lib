"""opticsjournal.net (Chinese Laser Press, 中国光学期刊网) article pages (oxjob #2210).

Markup is cut down from stored pages of the site (13 Nov 2026, Parseland swarm pilot). The abstract page carries the
byline (names linked to /Articles/SameAuthor/, superscript affiliation numbers), the affiliation list (each numbered
Chinese line may be followed by an unnumbered English translation, class "uniten"), a Chinese and an English abstract,
the full text and the numbered reference list. No publisher parser claimed the site, so the generic parser read the
citation_author tags (no affiliations) and the Chinese description meta tag as the abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.opticsjournal import OpticsJournal

URL = "https://www.opticsjournal.net/Articles/OJa0585e2f0ed95b79/Abstract"
CN_ABS = "天文观测仪器的蓬勃发展推动了对小体积、低成本、高效率的新一代仪器的研究工作。" * 4
EN_ABS = "Astrophotonics is the application of versatile photonic technologies to channel guided light. " * 4


def _byline(authors):
    spans = "".join(
        f'<span><a href="/Articles/SameAuthor/{n}" class="au-link " target="blank">{n}</a>&nbsp;'
        + (f"<sup>{s}</sup>" if s else "")
        + f'<a class="map fboxm" data-name="{n}" href="/Articles/MapAuthor/{n}"><i class="bi bi-diagram-3"></i></a></span>'
        for n, s in authors)
    return f'<div class="authors"><i class="bi bi-people"></i> {spans}</div>'


def _affs(items):
    return ('<div class="authors-dpt" style="display:flex;"><div class="dpt-title">作者单位</div></div>'
            '<div class="authors-dpt"><div class="items" id="audpt_OJx_2">' + "".join(items) + "</div></div>")


def _abstracts(cn=CN_ABS, en=EN_ABS):
    out = ""
    if cn is not None:
        out += ('<div class="abstract-cn"><div class="abstract-cn-tit"><i class="bi"></i> 摘要</div>'
                f'<div class="abstract-cn-con">{cn}<audio id="x_summaryAudio"><source src="/a.mp3"></audio>'
                '<a href="javascript:void(0);" title="点击语音播报本文摘要"><button type="button">语音播报</button></a>'
                '</div></div>')
    if en is not None:
        out += ('<div class="abstract-cn"><div class="abstract-cn-tit"><i class="bi"></i> Abstract</div>'
                f'<div class="abstract-cn-con">{en}</div></div>')
    return out


def _refs(entries):
    return ('<div class="con art-reference"><div class="con-tit"><i class="bi"></i> 参考文献</div><div class="con-text">'
            + "".join(entries) + "</div></div>")


def _ref(n, text, href=None):
    body = f"<span class='ref-number'>[{n}]</span> {text}"
    if href:
        body = f'<a href="{href}" target="_blank">{body}</a>'
    return f'<p id="Ref_{n}" style="margin-top: -120px;">{body}</p>'


def _page(body, og=URL, names=("韩子健", "袁祥岩")):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in names)
    return (f'<html><head><meta name="description" content="{CN_ABS}">'
            f'<link rel="canonical" href="{og}" /><meta property="og:url" content="{og}" />'
            f'<meta name="dc.description" content="{CN_ABS}" />{metas}'
            '<meta name="citation_title" content="光子灯笼技术及在天文中的应用" /></head><body>'
            f'<div class="ArticleContent"><div class="article">{body}</div></div></body></html>')


LINKED = _page(
    _byline([("韩子健", "1,2,*"), ("袁祥岩", "2")])
    + _affs(['<div class="item"><sup>1</sup>&nbsp;中国科学院国家天文台南京天文光学研究所，南京 210042</div>',
             '<div class="item uniten">Nanjing Institute of Astronomical Optics, Nanjing 210042, China</div>',
             '<div class="item"><sup>2</sup>&nbsp;中国科学院天文光学技术重点实验室，南京 210042</div>',
             '<div class="item uniten">Key Laboratory of Astronomical Optics, Nanjing 210042, China</div>'])
    + _abstracts()
    + _refs([_ref(1, "CUI X, ZHAO Y. The LAMOST telescope[J]<b>. Research in Astronomy, 2012, 12(9): 1197</b>.",
                  "http://dx.doi.org/10.1088/1674-4527/12/9/003"),
             _ref(2, "童雪, 林栋. 天文光子学研究现状[J]<b>. 天文学报, 2022, 63(5): 51</b>.",
                  "/Articles/OJ42adbe9113906ecf/Abstract"),
             '<p style="margin-top: -120px;">&nbsp;&nbsp;&nbsp;&nbsp;TONG Xue, LIN Dong. Research status of '
             'astrophotonics[J]<b>. Acta Astronomica Sinica, 2022, 63(5): 51</b>.</p>',
             _ref(3, "ZHOU Y. Infrared lasers[J]. Infrared and Laser Engineering, 2019, 48(1): 117001.",
                  "http://dx.doi.org/DOI: 10.3788/IRLA201948.0117001")]))


def _parsed(html):
    return OpticsJournal(BeautifulSoup(html, "lxml")).parse()


def test_affiliations_follow_the_byline_numbers_without_the_english_translations():
    authors = parse_page(LINKED.encode(), "doi", URL)["authors"]
    assert [a["name"] for a in authors] == ["韩子健", "袁祥岩"]
    assert [x["name"] for x in authors[0]["affiliations"]] == [
        "中国科学院国家天文台南京天文光学研究所，南京 210042", "中国科学院天文光学技术重点实验室，南京 210042"]
    assert [x["name"] for x in authors[1]["affiliations"]] == ["中国科学院天文光学技术重点实验室，南京 210042"]


def test_affiliation_number_with_a_dagger_still_links():
    html = _page(_byline([("马喆", "1†"), ("张明江", "2,*†")])
                 + _affs(['<div class="item"><sup>1</sup>&nbsp;太原理工大学电子信息与光学工程学院</div>',
                          '<div class="item"><sup>2</sup>&nbsp;太原理工大学物理学院</div>']), names=("马喆", "张明江"))
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [["太原理工大学电子信息与光学工程学院"],
                                                                         ["太原理工大学物理学院"]]


def test_unnumbered_affiliations_go_to_every_author_in_chinese_only():
    html = _page(_byline([("刘泽武", ""), ("陈洁", "*")])
                 + _affs(['<div class="item">浙江大学机械工程学院，浙江 杭州 310027</div>',
                          '<div class="item">School of Mechanical Engineering, Zhejiang University, Hangzhou 310027</div>'])
                 + _abstracts(), names=("刘泽武", "陈洁"))
    authors = parse_page(html.encode(), "doi", URL)["authors"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [["浙江大学机械工程学院，浙江 杭州 310027"]] * 2


def test_a_bare_star_without_a_legend_marks_no_corresponding_author():
    authors = parse_page(LINKED.encode(), "doi", URL)["authors"]
    assert not any(a["is_corresponding"] for a in authors)


def test_english_abstract_wins_over_the_chinese_meta_description():
    assert parse_page(LINKED.encode(), "doi", URL)["abstract"] == EN_ABS.strip()


def test_structured_english_abstract_keeps_its_labels_inline():
    en = ("<title>Objective</title>Lidar systems based on metasurfaces are popular. " * 3
          + "<title>Methods</title>We used Si<sub>3</sub>N<sub>4</sub> square posts. " * 3)
    abstract = _parsed(_page(_byline([("韩子健", "1")]) + _abstracts(en=en)))["abstract"]
    assert abstract.startswith("Objective Lidar systems based on metasurfaces are popular.")
    assert "Methods We used Si3N4 square posts." in abstract


def test_chinese_abstract_when_there_is_no_english_one_without_the_audio_button():
    abstract = _parsed(_page(_byline([("韩子健", "1")]) + _abstracts(en=None)))["abstract"]
    assert abstract == CN_ABS
    assert "语音播报" not in abstract


def test_reference_list_with_translations_and_dois():
    out = _parsed(LINKED)
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"] == "CUI X, ZHAO Y. The LAMOST telescope[J]. Research in Astronomy, 2012, 12(9): 1197."
    assert refs[0]["doi"] == "10.1088/1674-4527/12/9/003"
    assert refs[1]["doi"] is None
    assert refs[1]["raw"].startswith("童雪, 林栋. 天文光子学研究现状[J].")
    assert refs[1]["raw"].endswith("TONG Xue, LIN Dong. Research status of astrophotonics[J]. Acta Astronomica Sinica, "
                                   "2022, 63(5): 51.")
    assert refs[2]["doi"] == "10.3788/IRLA201948.0117001"
    assert out["references_complete"] is True


def test_reference_list_with_a_gap_is_not_complete():
    html = _page(_byline([("韩子健", "1")]) + _refs([_ref(1, "A reference one."), _ref(3, "A reference three.")]))
    out = _parsed(html)
    assert len(out["references"]) == 2
    assert out["references_complete"] is False


def test_no_reference_list_and_no_acknowledgments_or_funding_on_the_page():
    out = _parsed(_page(_byline([("韩子健", "1")]) + _refs([])))
    assert out["references"] is None and out["references_complete"] is False
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_same_markup_on_another_site_is_not_claimed():
    other = "https://www.researching.cn/articles/OJ4d385e2f9d67b25c"
    html = LINKED.replace(URL, other)
    parser = OpticsJournal(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    authors = parse_page(html.encode(), "doi", other)["authors"]
    assert not any(a["affiliations"] for a in authors)
