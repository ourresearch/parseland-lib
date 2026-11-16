"""KCI landing service pages (kci.go.kr/kciportal/landing, "Korea Open Access Journals"; oxjob #2268).

Markup is cut down from stored KCI pages (16 Nov 2026, #2268 template kci-portal). Korean DOIs of hundreds of small
society journals resolve to this one landing template. It prints the byline in div.articleInfo div.author with a
<sup>n</sup> after each name and the affiliations in div.attach as "<sup>n</sup>institution", an abstract box headed
초록, and the reference list as an <ol> under "참고문헌(N)" with its count. No publisher parser claimed it, and the
generic parser read no authors (the page has no citation_author tags), so no affiliation reached the works.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.kci_portal import KCIPortal

URL = "https://doi.org/10.21792/trijpn.2009..46.020"

HEAD = ('<head><title>Korea Open Access Journals</title>'
        '<meta property="og:url" content="http://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART001370139">'
        '<link rel="stylesheet" href="/kciportal/resources/landing/css/common.css" type="text/css">'
        '<link rel="stylesheet" href="/kciportal/resources/landing/css/sub.css" type="text/css"></head>')

ABSTRACT = ("이 연구에서는 객관적 신체활동 현장 검사도구의 타당도 증거를 제시하고 그동안 연구에서 이용된 타당화 검증절차를 "
            "체계적인 문헌분석을 통하여 요약하였다. 문헌분석 결과, 현재까지 사용빈도가 높은 가속도계는 Actigraph (USA) 이고, "
            "보행계수계는 상대적으로 정확한 것으로 밝혀졌다.")

REFS_3 = """
<div class="box">
  <h1>참고문헌<span>(3)</span><img src="/kciportal/resources/landing/img/arrow_down.png" alt="open"></h1>
  <ol class="innerBox" style="padding-left: 30px">
    <li><p>[기타]
       / 외무성 「文化外交の新発想」 2006年4月28日
    </p></li>
    <li><p>[단행본]
          홍길동
       / 1999
       / 戦後日本外交史
       / 有斐閣アルマ
         : 30
    </p></li>
    <li><p>[학술지] Adlof,S.M / 2006 / Should the simple view of reading include a fluency component / Reading and
      Writing: An Interdisciplinary Journal 19 : 933 ~ 958
      <a href="http://dx.doi.org/10.1007/s11145-006-9024-z" target="_blank"><img src="/kciportal/resources/landing/img/crossref.jpg"></a>
    </p></li>
  </ol>
</div>"""


def _page(author_html, attach_html, refs=REFS_3, abstract=ABSTRACT, head=HEAD):
    return f"""<html>{head}<body>
<div class="articleView">
 <div class="articleLeft">
  <div class="articleInfo">
    <p class="title">객관적 신체활동 검사도구의 타당도 증거와 검증 절차</p>
    <div class="journalInfo"><p class="jounal">한국체육측정평가학회지</p><p class="doi">DOI : 10.21797/ksme.2011.13.2.002</p></div>
    <div class="author">{author_html}</div>
    <div class="attach">{attach_html}</div>
    <div class="register"><img src="/kciportal/resources/landing/img/icon_kci2.png" alt="Korea Citation Index"></div>
  </div>
  <div class="articleBody">
    <div class="box neverClose"><h1>초록</h1><div class="innerBox"><p>{abstract}</p></div></div>
    <div class="box neverClose"><h1>키워드</h1><div class="innerBox"><p>신체활동, 타당도</p></div></div>
    {refs}
  </div>
 </div>
</div></body></html>"""


ONE = _page("\n 홍길동<sup>1</sup>\n", "<p><sup>1</sup>서울대학교</p>")
THREE = _page("김철수<sup>1</sup> , 이영희<sup>2</sup> , Boseuk Lee<sup>3</sup>",
              "<p><sup>1</sup>부산대학교</p> <p><sup>2</sup>고려대학교 대학원 산업디자인전공</p> <p><sup>3</sup>부산대학교</p>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return KCIPortal(BeautifulSoup(html, "lxml")).parse()


def test_single_author_gets_its_affiliation():
    authors = _parse(ONE)["authors"]
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in authors] == [("홍길동", ["서울대학교"])]
    assert not authors[0]["is_corresponding"]


def test_each_author_gets_the_affiliation_its_number_points_to():
    authors = _parse(THREE)["authors"]
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in authors] == [
        ("김철수", ["부산대학교"]), ("이영희", ["고려대학교 대학원 산업디자인전공"]), ("Boseuk Lee", ["부산대학교"])]
    assert not any(a["is_corresponding"] for a in authors)


def test_unexplained_asterisks_are_not_names_or_corresponding_marks():
    # the full-text XML variant prints "<span class="num">**</span>" after names, with no note and no affiliations
    html = _page('황 금숙 <span class="num">**</span> , 김 수경 <span class="num">***</span>', "")
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["황 금숙", "김 수경"]
    assert not any(a["affiliations"] or a["is_corresponding"] for a in authors)


def test_abstract_box_is_read():
    assert _parse(ONE)["abstract"].startswith("이 연구에서는 객관적 신체활동")


def test_english_title_alone_in_abstract_box_is_not_an_abstract():
    assert _parse(_page("홍길동<sup>1</sup>", "<p><sup>1</sup>군산대학교</p>",
                        abstract="Mission of Early Christianity"))["abstract"] is None


def test_reference_list_with_its_count_is_whole():
    parsed = _raw(ONE)
    refs = parsed["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[1]["raw"] == "[단행본] 홍길동 / 1999 / 戦後日本外交史 / 有斐閣アルマ : 30"
    assert refs[0]["doi"] is None and refs[2]["doi"] == "10.1007/s11145-006-9024-z"
    assert parsed["references_complete"] is True
    out = _parse(ONE)
    assert len(out["references"]) == 3 and out["references_complete"] is True


def test_count_that_does_not_match_the_entries_is_not_whole():
    refs = REFS_3.replace("<span>(3)</span>", "<span>(5)</span>")
    parsed = _raw(_page("홍길동<sup>1</sup>", "<p><sup>1</sup>서울대학교</p>", refs=refs))
    assert len(parsed["references"]) == 3 and parsed["references_complete"] is False


def test_empty_reference_box_gives_no_list():
    refs = '<div class="box"><h1 style="cursor:default;">참고문헌<span>(0)</span></h1></div>'
    parsed = _raw(_page("홍길동<sup>1</sup>", "<p><sup>1</sup>서울대학교</p>", refs=refs))
    assert not parsed.get("references") and not parsed.get("references_complete")


def test_full_text_xml_reference_items_are_left_alone():
    # the Full Text XML variant's items carry broken JATS markup ('01"&gt; <label>1</label> <element-citation ...')
    refs = ('<div class="box"><h1>참고문헌<span>(1)</span></h1><ol class="innerBox">'
            '<li class="ref" id="B001"><input type="hidden" id="refArtidoi" value=""/>[학위논문]'
            '<p class="author">고, 수진. </p> <p class="title">01"&gt; <label>1</label> <element-citation '
            'publication-type="thesis"><source>연구</source></element-citation></p><p class="year">1998</p></li></ol></div>')
    parsed = _raw(_page("홍길동<sup>1</sup>", "<p><sup>1</sup>서울대학교</p>", refs=refs))
    assert not parsed.get("references") and not parsed.get("references_complete")


def test_look_alike_byline_classes_on_another_site_are_not_claimed():
    # same div.articleInfo / div.author / div.attach class names, but not the KCI landing template
    head = '<head><title>A journal</title><link rel="stylesheet" href="/css/site.css"></head>'
    html = _page("홍길동<sup>1</sup>", "<p><sup>1</sup>서울대학교</p>", head=head)
    soup = BeautifulSoup(html, "lxml")
    assert not KCIPortal(soup).is_publisher_specific_parser()
    assert not KCIPortal(soup).authors_found()
    assert not _parse(html)["authors"]


def test_journal_site_that_links_to_kci_is_not_claimed():
    # a society journal's own site (JKSR) links to KCI's portal and carries citation_author tags: not this template
    html = ('<html><head><title>:: JKSR :: Journal of the Korean Society of Radiology</title>'
            '<meta name="citation_author" content="Kim, Moon Chul">'
            '<meta name="citation_author_institution" content="Department of Radiology, Chonnam National University">'
            '</head><body><div><span><a href="https://www.kci.go.kr/kciportal/po/search/poCitaView.kci?sereId=000499">'
            '<img src="https://www.kci.go.kr/kciportal/resources/newkci/image/kor/title/h1_logo.png"></a></span></div>'
            '<div class="author">Moon Chul Kim<sup>1</sup></div></body></html>')
    soup = BeautifulSoup(html, "lxml")
    assert not KCIPortal(soup).is_publisher_specific_parser()
    authors = _parse(html)["authors"]
    assert [a["name"] for a in authors] == ["Kim, Moon Chul"]


def test_comma_inside_a_marked_name_stays_one_author():
    html = _page("Kim, Pil-dong<sup>1</sup> , 이영희<sup>2</sup>", "<p><sup>1</sup>세명대학교</p><p><sup>2</sup>군산대학교</p>")
    authors = _parse(html)["authors"]
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in authors] == [
        ("Kim, Pil-dong", ["세명대학교"]), ("이영희", ["군산대학교"])]
