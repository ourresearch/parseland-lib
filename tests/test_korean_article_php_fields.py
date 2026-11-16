"""Korean society journal sites on the shared article.php?code= template (oxjob #2268, template korean-article-php).

Markup is cut down from stored pages of the template (rjcc.or.kr, kosomes.or.kr, ksft.or.kr, joie.or.kr, jnfcwt.or.kr,
familywelfare.net, jiaptr.org). The pages carry no citation_* meta tags, so Parseland read no authors at all. The
byline sits in div.fulltext-wrap > #engInfo (English) and #korInfo (Korean): div.ft-author (names, comma separated,
each followed by superscript markers, a dagger or star, an empty mailto link and an ORCID link), div.ft-author-aff
(one affiliation per <br>, a leading <sup> marker when there are several) and div.ft-author-cor (the corresponding
author note). The reference list is div.ft-reference > ol > li.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.korean_article_php import KoreanArticlePhp

URL = "http://www.example.or.kr/journal/article.php?code=88599"


def _page(eng_author, eng_aff, cor="", kor_author="", kor_aff="", note="", back=""):
    return f"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<link rel="stylesheet" type="text/css" href="/_style/jats_layout.css"></head><body>
<meta name="dc.identifier" content="doi:10.29049/rjcc.2023.31.6.756">
<div class="article_box"><div class="fulltext-wrap">
<div class="ft-head"><div class="ft-issn">ISSN : 1226-0401(Print)</div>
<div class="ft-info"><strong>The Research Journal Vol.31 No.6 pp.756-775</strong></div></div>
<div id="engInfo"><h1>A title</h1>
<div class="ft-author">{eng_author}</div>
<div class="ft-author-aff">{eng_aff}</div>
<div class="ft-author-note">{note}</div>
<div class="ft-author-cor">{cor}</div></div>
<h2 class="ft-title-abstract">Abstract</h2>
<div class="ft-abstract"><p>This study was aimed at examining the characteristics of women's blue denim on the basis
of design elements to provide fundamental data for fashion majors and fashion designers.</p></div>
<div id="korInfo"><h1>한국어 제목</h1>
<div class="ft-author">{kor_author}</div>
<div class="ft-author-aff">{kor_aff}</div></div>
</div>{back}</div></body></html>"""


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return KoreanArticlePhp(BeautifulSoup(html, "lxml")).parse()


ORCID = '<a href="http://orcid.org/0000-0003-2978-5334" target="_blank"><img src="../_images/layout/icon_prof.gif"/></a>'


def test_authors_with_star_markers_and_dagger_corresponding():
    html = _page(
        "Hyo-Sang Choo<sup>&#x2A;</sup>&#x2020;<a href=\"mailto:choo@jnu.ac.kr\"></a>, Jin-Young Lee<sup>**</sup>, "
        "Kyeung-Ho Han<sup>***</sup>",
        "<sup>*</sup>Professor, Department of Ocean Integrated Science, Chonnam National University<br/>"
        "<sup>**</sup>Chief Executor, Sunjin Haeyang Co., Ltd.<br/>"
        "<sup>***</sup>Professor, Department of Aquaculture, Chonnam National University",
        cor="<sup>&#x2020;</sup> Corresponding Author : <a href=\"mailto:choo@jnu.ac.kr\">choo@jnu.ac.kr</a><br/>")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Hyo-Sang Choo", "Jin-Young Lee", "Kyeung-Ho Han"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Professor, Department of Ocean Integrated Science, Chonnam National University"],
        ["Chief Executor, Sunjin Haeyang Co., Ltd."],
        ["Professor, Department of Aquaculture, Chonnam National University"]]
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_unmarked_affiliation_goes_to_authors_without_a_matching_marker():
    # ksft.or.kr: the first affiliation has no marker; "*" is the corresponding mark, not an affiliation marker
    html = _page(
        f"Ki-Tak RYU<sup></sup>{ORCID}, Jong-Phil KIM<sup>1</sup>{ORCID}, Yun-Hyung LEE<sup>*</sup>{ORCID}<br/>",
        "Professor, Ocean Technology Training Team, Korea Institute of Maritime and Fisheries Technology<br/>"
        "<sup>1</sup>Professor, Ocean Polytech Maritime Team, Korea Institute of Maritime and Fisheries Technology",
        cor="<sup>*</sup>Corresponding author: <a href=\"mailto:x@daum.net\">x@daum.net</a>, Tel: +82-51-620-5823<br/>")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Ki-Tak RYU", "Jong-Phil KIM", "Yun-Hyung LEE"]
    first = "Professor, Ocean Technology Training Team, Korea Institute of Maritime and Fisheries Technology"
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        [first], ["Professor, Ocean Polytech Maritime Team, Korea Institute of Maritime and Fisheries Technology"],
        [first]]
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_numbered_markers_with_star_and_two_corresponding_authors():
    # joie.or.kr: "1*" is affiliation 1 plus the first corresponding mark, "3**" affiliation 3 plus the second
    html = _page(
        "NamJin Kim<sup>1*</sup>, HoSeung Chae<sup>1</sup>, SungTae Kim<sup>2</sup>, HungSoo Joo<sup>3**</sup>",
        "<sup>1</sup>Research Institute of Public Health and Environment<br/><sup>2</sup>E2M3 LTD<br/>"
        "<sup>3</sup>Department of Environmental Engineering, Anyang University",
        cor="<sup>*</sup> Corresponding Author: Tel: +82-2-570-3369<br/><sup>**</sup> Corresponding Author: Tel: "
            "+82-31-463-1291<br/>")
    authors = _parse(html)["authors"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Research Institute of Public Health and Environment"], ["Research Institute of Public Health and Environment"],
        ["E2M3 LTD"], ["Department of Environmental Engineering, Anyang University"]]
    assert [a["is_corresponding"] for a in authors] == [True, False, False, True]


def test_parenthesised_markers_link_several_affiliations():
    html = _page("Yeji Kim<sup>1,2)</sup>, Yongsu Yoon<sup>2,3)</sup>",
                 "<sup>1)</sup>Department of Radiological Science, Graduate School of Dongseo University<br/>"
                 "<sup>2)</sup>Center for Radiological Environment, Dongseo University<br/>"
                 "<sup>3)</sup>Department of Radiological Science, Dongseo University",
                 cor="Corresponding author: Yongsu Yoon, Department of Radiological Science, Dongseo University")
    authors = _parse(html)["authors"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Department of Radiological Science, Graduate School of Dongseo University",
         "Center for Radiological Environment, Dongseo University"],
        ["Center for Radiological Environment, Dongseo University", "Department of Radiological Science, Dongseo University"]]
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_one_unmarked_affiliation_is_shared_and_note_naming_the_author_marks_them():
    # kaomp.org / jnfcwt.or.kr: one affiliation for everyone; the note names the corresponding author
    html = _page("Kang Hyuk Kim, Jung Woo Cho, Chang Hyen Kim*<a href=\"mailto:k@catholic.ac.kr\"></a>",
                 "Department of Oral and Maxillofacial Surgery, The Catholic University of Korea",
                 cor="Corresponding author : Chang Hyen Kim, Department of Oral and Maxillofacial Surgery")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Kang Hyuk Kim", "Jung Woo Cho", "Chang Hyen Kim"]
    assert all([x["name"] for x in a["affiliations"]] == [
        "Department of Oral and Maxillofacial Surgery, The Catholic University of Korea"] for a in authors)
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_reversed_name_in_note_and_unmarked_affiliations_by_position():
    # familywelfare.net prints one unmarked line per author; ksotjournal.kr writes "Kim, Hwan" in the note
    html = _page("Eun Ra Baek, Yujin Oh, Hwan Kim",
                 "Graduate student, Chonnam National University<br/>Graduate student, Chonnam National University<br/>"
                 "Professor, Chonnam National University",
                 cor="Corresponding author: Kim, Hwan (<a href=\"mailto:h@daegu.ac.kr\">h@daegu.ac.kr</a>)")
    authors = _parse(html)["authors"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Graduate student, Chonnam National University"], ["Graduate student, Chonnam National University"],
        ["Professor, Chonnam National University"]]
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_unexplained_star_is_not_a_corresponding_mark():
    # ijfs.org: a starred byline with no note explaining it
    html = _page("Sang Kun Park<sup>*</sup><br/>", "Department of Floriculture, Korea National University of Agriculture")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Sang Kun Park"]
    assert not authors[0]["is_corresponding"]


def test_degrees_after_names_are_not_authors_and_line_wrapped_affiliation_is_joined():
    html = _page("Hojin Jeong, PT, PhD<sup>a</sup>, Sunghwan Park, PT, PhD<sup>a</sup>",
                 "<sup>a</sup>Goodbody Sling Exercise Center,<br/>Gwangju, Republic of Korea")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Hojin Jeong", "Sunghwan Park"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Goodbody Sling Exercise Center, Gwangju, Republic of Korea"]] * 2


def test_english_byline_preferred_and_email_dropped_from_affiliation():
    html = _page("Xuezhu Quan<sup>*</sup>, Sixuan Zhu<sup>**</sup>",
                 "<sup>*</sup>Ph.D. student, Seoul National University; Email: quanxuezhu@snu.ac.kr<br/>"
                 "<sup>**</sup>Ph.D. student, Seoul National University; Email: zhusixuan@snu.ac.kr",
                 kor_author="콴쉐주<sup>*</sup>, 주쓰쉬안<sup>**</sup>", kor_aff="<sup>*</sup>서울대학교<br/><sup>**</sup>서울대학교")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Xuezhu Quan", "Sixuan Zhu"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Ph.D. student, Seoul National University"], ["Ph.D. student, Seoul National University"]]


def test_korean_byline_when_english_is_empty():
    html = _page("", "", kor_author="백 경 진†<a href=\"mailto:m@hanmail.net\"></a>", kor_aff="정화예술대학교 미용예술학부 조교수",
                 cor="Corresponding author (<a href=\"mailto:m@hanmail.net\">m@hanmail.net</a>)<br/>")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["백 경 진"]
    assert [x["name"] for x in authors[0]["affiliations"]] == ["정화예술대학교 미용예술학부 조교수"]
    assert authors[0]["is_corresponding"]


BACK = """<div class="ft-content"><div id="article-body" class="body"><p>Body text.</p>
<div class="ack"><a id="ID0EYCAE"></a><h2 class="main-title">감사의 글</h2>
<p>이 연구는 한국연구재단의 지원을 받아 수행되었습니다.</p></div></div>
<h2 class="ft-title-reference">Reference</h2>
<div class="ft-reference"><ol>
<li><a id="b1"></a> Chang, Y. S. (2005), Time Series Analysis of the Subsurface Oceanic Data. Jour. Korean Earth Science
Society, Vol. 26, No. 7, pp. 706-713.</li>
<li><a id="b2"></a> Choo, H. S. and E. C. Yoon (2015), Temporal and spatial variations of sea surface temperature.
Journal of the Korean Society of Marine Environment &amp; Safety, Vol. 21, No. 4, pp. 315-326.<a
href="https://doi.org/10.7837/kosomes.2015.21.4.315" target="_blank"><img src="btn_crossref.gif"/></a></li>
</ol></div></div>"""


def test_reference_list_and_acknowledgments():
    html = _page("Hyo-Sang Choo<sup>*</sup>", "<sup>*</sup>Chonnam National University", back=BACK)
    out = _raw(html)
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2]
    assert refs[0]["raw"].startswith("Chang, Y. S. (2005), Time Series Analysis") and refs[0]["doi"] is None
    assert refs[1]["doi"] == "10.7837/kosomes.2015.21.4.315"
    assert out["references_complete"] is True
    assert out["acknowledgments"] == "이 연구는 한국연구재단의 지원을 받아 수행되었습니다."


def test_empty_reference_list_is_not_complete():
    html = _page("Sang Yong Nam, Chi Hoon Park", "<br/>",
                 back='<h3 class="ft-title-reference">Reference</h3><div class="ft-reference">\n</div>')
    out = _raw(html)
    assert out["references"] is None and out["references_complete"] is False
    assert [a["affiliations"] for a in out["authors"]] == [[], []]


def test_look_alike_nurimedia_page_is_not_claimed():
    # The nearest other template on the same Korean society sites (aodr.org, Nurimedia XML): no fulltext-wrap byline
    html = """<html><body><div class='NURIMEDIAXML'><div id="article-level-0-front" class="fm">
<div class="article_level_front">Design and Technology Transfer</div>
<div><ul><li><span class="athr_name">Rewat Suksikarn : </span><i>Walailak University, Thailand</i></li></ul></div>
</div></div><div class="ft-author">Not a byline</div></body></html>"""
    parser = KoreanArticlePhp(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_look_alike_view_asp_page_is_not_claimed():
    # The other Korean society template (past/view.asp?a_key=): its own classes, no ft-author-aff
    html = """<html><body><div class="contents"><div class="row20"><p class="j-doi">DOI 10.9786/kswm.2016.33.1.1</p>
<h3 class="title is2">A title</h3><div class="clearfix row10"><p class="fl">Kim Min-su, Lee Ji-won</p></div>
</div></div></body></html>"""
    parser = KoreanArticlePhp(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
