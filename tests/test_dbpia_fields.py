"""DBpia and earticle (Korea) article pages (oxjob #2268, template "DBpia / KISS / KCI").

Markup is cut down from stored pages of the template's sites (16 Nov 2026). Both platforms carry citation_author tags
with names only, so the generic parser read every author and no affiliation. DBpia prints the byline as
"Name (Affiliation)" in one of three skins; earticle prints "Name [ Romanized | Affiliation ]" with a role tag that
names the corresponding author (교신저자). KISS (kiss.kstudy.com) pages print names only and stay with the generic
parser.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.dbpia import DBpia, Earticle

DBPIA_URL = "https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE11121044"
EARTICLE_URL = "https://www.earticle.net/Article/A417686"
KOREAN_ABSTRACT = "이 연구는 기혼 직장인 여성의 가사노동 스트레스가 삶의 만족도에 어떠한 영향을 주는지 분석하였다."


def _head(names, abstract=KOREAN_ABSTRACT):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f'<head><title>A title - DBpia</title><meta name="citation_title" content="A title"/>{metas}'
            f'<meta name="citation_abstract" content="{abstract}"/></head>')


def _page(names, body):
    return f"<html>{_head(names)}<body>{body}</body></html>"


def _authors(html, url=DBPIA_URL):
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"])
            for a in parse_page(html.encode(), "doi", url)["authors"]]


def _soup(html):
    return BeautifulSoup(html, "lxml")


# ---- DBpia: three skins of one byline

SKIN_LIST = """<main class="dpMain"><section class="thesisDetail"><section class="thesisDetail__info">
<section class="thesisDetail__author"><h2 class="info__h2">저자정보</h2><ul class="authorList">
<li class="authorList__item"><a class="authorList__author" href="/author/authorDetail?ancId=5120990"> 강은진 </a>
<span class="authorList__agency"> (고려대학교) </span></li>
<li class="authorList__item"><span>박제용</span><span class="authorList__agency"> ((주)엠쓰리시스템즈) </span></li>
<li class="authorList__item"><a class="authorList__author" href="/author/authorDetail?ancId=1"> 김수암 </a></li>
</ul></section></section></section></main>"""

SKIN_WRAP = """<section class="thesisDetail"><dl><dd class="dd thesisDetail__authorList">
<div id="authorWrap" class="author-list">
<span class="author"><a class="authorName" href="/author/authorDetail?ancId=995007348"> 김성옥 </a>
(<span class="authorAffiliation">충남대학교</span>) </span>
<span class="author"><span class="authorName">이유신</span> (<span class="authorAffiliation">강원대학교</span>) </span>
</div></dd></dl></section>"""

SKIN_LINKS = """<div class="section"><div class="thesisInfoArea"><div class="quoteWrap"><div class="author-wrap">
<p class="author"><a href="/author/authorDetail?ancId=2254402" target="_blank"> 박현수 (한국해양대학교) </a> ,
<a href="/author/authorDetail?ancId=500182" target="_blank"> 高靜(中國 廣西科技大學)</a> ,
<a href="/author/authorDetail?ancId=1434764" target="_blank"> 김창락 </a> , 이덕주 (감리교신학대학교)
<!-- <a href="/author/authorDetail?ancId=2254402"> 박현수 (한국해양대학교)</a> --></p>
</div></div></div></div>"""


def test_dbpia_author_list_skin():
    html = _page(["강은진", "박제용", "김수암"], SKIN_LIST)
    assert _authors(html) == [("강은진", ["고려대학교"], None), ("박제용", ["(주)엠쓰리시스템즈"], None),
                              ("김수암", [], None)]


def test_dbpia_author_wrap_skin():
    html = _page(["김성옥", "이유신"], SKIN_WRAP)
    assert _authors(html) == [("김성옥", ["충남대학교"], None), ("이유신", ["강원대학교"], None)]


def test_dbpia_linked_byline_skin_reads_unlinked_author_and_skips_comment():
    html = _page(["박현수", "高靜", "김창락", "이덕주"], SKIN_LINKS)
    assert _authors(html) == [("박현수", ["한국해양대학교"], None), ("高靜", ["中國 廣西科技大學"], None),
                              ("김창락", [], None), ("이덕주", ["감리교신학대학교"], None)]


def test_dbpia_full_author_dialog_wins_over_a_shorter_byline():
    dialog = ('<dialog class="dpAuthorInfo" id="authorLayer"><section class="dpAuthorInfo__cont"><ul class="authorList">'
              '<li class="authorList__item"><a class="authorList__author" href="/author/authorDetail?ancId=1"> 김성옥 </a>'
              '<span class="authorList__agency"> (충남대학교) </span></li>'
              '<li class="authorList__item"><a class="authorList__author" href="/author/authorDetail?ancId=2"> 이유신 </a>'
              '<span class="authorList__agency"> (강원대학교) </span></li>'
              '<li class="authorList__item"><a class="authorList__author" href="/author/authorDetail?ancId=3"> 최연선 </a>'
              '<span class="authorList__agency"> (성균관대학교) </span></li></ul></section></dialog>')
    html = _page(["김성옥", "이유신", "최연선"], SKIN_WRAP + dialog)
    assert [a[0] for a in _authors(html)] == ["김성옥", "이유신", "최연선"]


def test_dbpia_keeps_the_abstract_the_generic_parser_reads():
    html = _page(["김성옥", "이유신"], SKIN_WRAP + '<div class="abstractTxt">한국어 <br><br> English text.</div>')
    assert parse_page(html.encode(), "doi", DBPIA_URL)["abstract"] == KOREAN_ABSTRACT


def test_dbpia_reference_preview_is_never_complete():
    refs = ('<section class="thesisDetail__reference"><h2 class="thesisDetail__h2">참고문헌 '
            '<span class="dbpiaCount">(32)</span></h2><div class="referList">'
            '<a class="referenceLink" href="https://scholar.google.com/x"> Aguiar, Luis / 2016 / Digital Music '
            'Consumption / Information Economics and Policy 34:27~43 </a>'
            '<a class="referenceLink" href="https://scholar.google.com/y"> Kim, S. / 2019 / A study / J 10.1234/abc.5 </a>'
            '</div><button class="loginBtn">로그인하시고 참고문헌 전체를 확인해 보세요.</button></section>')
    out = DBpia(_soup(_page(["김성옥", "이유신"], SKIN_WRAP + refs))).parse()
    assert [r["position"] for r in out["references"]] == [1, 2]
    assert out["references"][0]["raw"].startswith("Aguiar, Luis / 2016")
    assert out["references"][1]["doi"] == "10.1234/abc.5"
    assert out["references_complete"] is False
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_dbpia_empty_reference_section_gives_none():
    refs = ('<section class="thesisDetail__reference"><h2>참고문헌 <span class="dbpiaCount">(0)</span></h2>'
            '<div class="referList"><p>등록된 정보가 없습니다.</p></div></section>')
    out = DBpia(_soup(_page(["김성옥", "이유신"], SKIN_WRAP + refs))).parse()
    assert out["references"] is None and out["references_complete"] is False


# ---- earticle

def _earticle(items):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return ('<div class="page_content art-detail"><div class="otherInfo"><div class="detail-info"><h3>원문정보</h3>'
            '<div class="section"><h4>초록</h4><dl class="abs"><dt> 영어 </dt><dd id="abs_cnt">English.</dd></dl></div>'
            f'<div class="section"><h4>저자</h4><ul class="authors">{lis}</ul></div></div></div></div>')


def test_earticle_affiliations_and_corresponding_role():
    html = _page(["박경련", "김하나"], _earticle([
        '박경련 [ Park, Kyung-Ryun | 차의과학대학교 상담심리학과 강사 ] <span class="write_type">제1저자</span>',
        '김하나 [ Kim, Ha-Na | 차의과학대학교 상담심리학과 교수 ] <span class="write_type">교신저자</span>']))
    assert _authors(html, EARTICLE_URL) == [("박경련", ["차의과학대학교 상담심리학과 강사"], False),
                                            ("김하나", ["차의과학대학교 상담심리학과 교수"], True)]


def test_earticle_without_role_tags_marks_no_one():
    html = _page(["성세훈", "이지치 노리코"], _earticle([
        "성세훈 [ Sung, Se-Hoon | 계명대학교, 석사 ]", "이지치 노리코 [ Noriko Ijichi | 오사카시립대학 ]"]))
    assert _authors(html, EARTICLE_URL) == [("성세훈", ["계명대학교, 석사"], None),
                                            ("이지치 노리코", ["오사카시립대학"], None)]


def test_earticle_keeps_the_abstract_the_generic_parser_reads():
    html = _page(["권혁래"], _earticle(["권혁래 [ Kwon, Hyeok-rae | 용인대학교 용오름대학 부교수 ]"]))
    assert parse_page(html.encode(), "doi", EARTICLE_URL)["abstract"] == KOREAN_ABSTRACT


# ---- look-alikes are not claimed

def test_kiss_page_is_not_claimed():
    """KISS (kiss.kstudy.com), the template's third site, prints names only: it stays with the generic parser."""
    body = ('<div class="title">한국 스포츠 선수</div><div class="author mb-1"> 김아연 ( Kim A-yeon ) , '
            '이연재 ( Lee Yeon-jae ) </div>')
    soup = _soup(_page(["김아연", "이연재"], body))
    assert not DBpia(soup).is_publisher_specific_parser() and not DBpia(soup).authors_found()
    assert not Earticle(soup).is_publisher_specific_parser() and not Earticle(soup).authors_found()


def test_ojs_author_list_is_not_claimed():
    body = ('<section class="item authors"><h2>Authors</h2><ul class="authors"><li><span class="name">Ann Lee</span>'
            '<span class="affiliation">Universitas X</span></li></ul></section>'
            '<p class="author"><a href="/author/1">Ann Lee (Universitas X)</a></p>')
    soup = _soup(_page(["Ann Lee"], body))
    assert not DBpia(soup).is_publisher_specific_parser() and not DBpia(soup).authors_found()
    assert not Earticle(soup).is_publisher_specific_parser() and not Earticle(soup).authors_found()
