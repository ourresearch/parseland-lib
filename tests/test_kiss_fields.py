"""KISS (kiss.kstudy.com) article pages (oxjob #2338).

Markup is cut down from stored KISS pages (17 Nov 2026). The byline prints "Korean name ( Romanized name )"; the
abstract shows one block per language version, Korean first. The /Detail/Ar page comes with citation_* tags (the
generic parser read the Korean names and the Korean citation_abstract) or without any (Parseland read nothing); the
older /thesis/thesis-view.asp page puts the whole byline in one citation_author tag (read as one author).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.kiss import KISS

URL = "https://kiss.kstudy.com/Detail/Ar?key=3908275"
KOREAN = ("최근 청동기시대 연구는 사회변동에 초점을 맞추며 논의되는 것에 비해 영산강유역은 자료의 편중, 지표유물의 부재 등 "
          "상대적으로 주목받지 못하였다. 본고에서는 영산강유역에서 조사된 청동기시대 주거유적의 분포현황과 양상을 검토하였다.")
ENGLISH = ("The recent researches on the Bronze Age have been actively discussed focusing on social change while the "
           "Yeongsan River basin has not grabbed attention due to reasons like unequally-distributed data. As the "
           "dwelling data of the Bronze Age in the basin has been accumulated, this thesis aimed to examine the "
           "distributional aspect of the dwelling remains and the arrangement of their storage facilities.")

# the older render: no citation tags, head og:url is the site root, the article's own og tags sit in <main>
OLD_HEAD = """<head><meta charset="UTF-8"><title>지식을 담다. 지식을 나누다. 학술논문 전문 검색</title>
<meta property="og:title" content="학술논문검색사이트 KISS"><meta property="og:url" content="https://kiss.kstudy.com/">
<meta property="og:site_name" content="학술논문검색사이트 KISS"></head>"""

META_HEAD = """<head><meta charset="UTF-8"><title>A title - 호남고고학보 - 호남고고학회 - KISS</title>
<meta property="og:url" content="https://kiss.kstudy.com/Detail/Ar?key=4210706">
<meta name="citation_title" content="A title" />
<meta name="citation_author" content="최하진" /><meta name="citation_author" content="최재혁" />
<meta name="citation_abstract" content="{korean}" />
<link rel="canonical" href="https://kiss.kstudy.com/Detail/Ar?key=4210706" /></head>""".format(korean=KOREAN)


def _body(byline, paragraphs, heading="초록"):
    ps = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f"""<body><main><meta property="og:url" content="{URL}"/>
<div id="wrap_sub"><div class="wrap_sub_contents"><div class="container"><div class="wrap_journal">
<div class="wrap_journal_index"><div class="col-12 col-md-auto wrap_info"><div class="mb-1">
<div class="title" id="3908275">영산강유역 청동기시대 주거유적의 분포양상</div>
<div class="title_sub">Dwelling Distributional Aspect of Bronze Age in the Yeongsan River Basin</div>
<div class="author mb-1">
    {byline}
</div>
<div class="mb-1"><a href="javascript:movePublisher('Ks', '2241', '28232');"><span class="value">호남고고학회</span></a></div>
</div></div></div></div>
<div class="wrap_journal_info"><div id="journal_info" class="accordion nested-accordion w-icon" role="tablist">
<div class="wrap_info"><div role="tab" id="part1"><div class="accordion-title">
<a data-toggle="collapse" href="#collapse-part1" aria-expanded="true">{heading}<span class="pull-right"><i class="material-icons">expand_more</i></span></a>
</div></div><div id="collapse-part1" class="collapse show" role="tabpanel"><div class="wrap_part_body">{ps}</div></div></div>
<div class="wrap_info"><div role="tab" id="part2"><div class="accordion-title"><a href="#collapse-part2">키워드<span class="pull-right"><i class="material-icons">expand_more</i></span></a></div></div>
<div id="collapse-part2" class="collapse show"><div class="wrap_part_body"><a href="#">청동기시대</a><a href="#">Bronze Age</a></div></div></div>
<div class="wrap_info"><div role="tab" id="part4"><div class="accordion-title"><a href="#collapse-part4">참고문헌 ( 0 )<span class="pull-right"><i class="material-icons">expand_more</i></span></a></div></div>
<div id="collapse-part4" class="collapse show"><div class="wrap_part_body"></div></div></div>
</div></div></div></div></div></main></body>"""


def _page(head, byline, paragraphs, heading="초록"):
    return f"<!DOCTYPE html><html lang=\"ko\">{head}{_body(byline, paragraphs, heading)}</html>"


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _names(out):
    return [a["name"] for a in out["authors"]]


def test_old_render_without_citation_tags_is_read():
    out = _parse(_page(OLD_HEAD, "이재언 ( Lee Jae Earn )", [KOREAN, ENGLISH]))
    assert _names(out) == ["이재언 ( Lee Jae Earn )"]  # no tags: the byline as printed
    assert out["abstract"] == ENGLISH
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in out["authors"])


def test_names_match_citation_author_and_english_abstract_wins():
    out = _parse(_page(META_HEAD, "최하진 ( Ha Jin Choi ) , 최재혁 ( Jae Hyuk Choi )", [KOREAN, ENGLISH], "Abstract"))
    assert _names(out) == ["최하진", "최재혁"]  # one citation_author tag per byline entry: the tags' form
    assert out["abstract"] == ENGLISH  # citation_abstract holds the Korean version only


def test_romanized_only_name_and_parenthesis_inside_the_korean_name():
    out = _parse(_page(OLD_HEAD, "( Kassie Belay Addisu ) , 전양소(금원) ( Jeon Yang-so ) , 김성운 ( Kim¸ Sung Woon )",
                       [ENGLISH]))
    assert _names(out) == ["Kassie Belay Addisu", "전양소(금원) ( Jeon Yang-so )", "김성운 ( Kim¸ Sung Woon )"]


def test_single_version_is_kept_whatever_its_language():
    assert _parse(_page(OLD_HEAD, "이재언 ( Lee Jae Earn )", [KOREAN]))["abstract"] == KOREAN
    assert _parse(_page(OLD_HEAD, "이유정 ( Yu Jung Lee )", [ENGLISH]))["abstract"] == ENGLISH


def test_new_fields_are_absent():
    soup = BeautifulSoup(_page(OLD_HEAD, "이재언 ( Lee Jae Earn )", [KOREAN, ENGLISH]), "lxml")
    out = KISS(soup).parse()
    assert out["acknowledgments"] is None and out["funding_statement"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_look_alike_pages_are_not_claimed():
    # the same accordion and byline classes on another site's page
    other_head = OLD_HEAD.replace("https://kiss.kstudy.com/", "https://www.example-journal.kr/")
    soup = BeautifulSoup(_page(other_head, "이재언 ( Lee Jae Earn )", [KOREAN, ENGLISH]), "lxml")
    assert not KISS(soup).is_publisher_specific_parser() and not KISS(soup).authors_found()


ASP = """<html><head><meta charset="UTF-8"><title>A title &lt; 한국고객만족경영학회 &lt; KISS</title>
<meta property="og:url" content="https://kiss.kstudy.com/thesis/thesis-view.asp?key=3943762"/>
<meta name="citation_author" content="박유진 ( Yujin Park ) , 이상원 ( Sangwon Lee )"/>
<meta name="citation_abstract" content="{korean}"/></head>
<body><div id="contents"><div class="container"><section class="pub-info"><h3>A title</h3>
<div class="col2-container-is2 clearfix"><div class="left">
<div class="writers">박유진 ( Yujin Park ) , 이상원 ( Sangwon Lee )</div>
<ul class="dot-list"><li><label class="fc-k2">발행기관</label> : 한국고객만족경영학회 </li></ul></div>
<div class="right"><p class="author">최정우 ( Choi Jeongwoo )</p></div></div></section>
<section class="pad-25-10"><h4 class="row5">목차</h4><pre>1. 서 론
2. 결론</pre></section>
<section class="pad-25-10"><h4 class="row5">초록 보기</h4>
<!-- 초록 한글 --><div class='row20'><pre>{korean}</pre></div>
<!-- 초록 영문 --><div><pre>{english}</pre></div></section>
</div></div></body></html>""".format(korean=KOREAN, english=ENGLISH)


def test_thesis_view_page_splits_the_byline_and_gives_the_english_abstract():
    out = _parse(ASP)
    # the generic parser read one author "박유진 ( Yujin Park ) , 이상원 ( Sangwon Lee )" from the single tag
    assert _names(out) == ["박유진 ( Yujin Park )", "이상원 ( Sangwon Lee )"]
    assert out["abstract"] == ENGLISH


def test_paragraph_breaks_are_kept():
    two = ENGLISH + "\n   As a result, the dwelling remains show storage use rather than habitation in most of the sites."
    out = _parse(_page(OLD_HEAD, "이재언 ( Lee Jae Earn )", [KOREAN, two]))
    assert out["abstract"].split("\n") == [ENGLISH, "As a result, the dwelling remains show storage use rather than "
                                                     "habitation in most of the sites."]
    out = _parse(_page(OLD_HEAD, "이재언 ( Lee Jae Earn )", [KOREAN, ENGLISH + "<br>Second paragraph of the abstract text."]))
    assert out["abstract"] == ENGLISH + "\nSecond paragraph of the abstract text."
