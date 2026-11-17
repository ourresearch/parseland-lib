"""Korean JATS full-text sites (oxjob #2289, template korean-jats): the "view_article" JATS preview (jats-preview_main.css
sites: foodnlife.org, ejce.org, ekosfop.or.kr, ...) and Nurimedia's XML viewer (/_common/do.php sites: kpaj.or.kr,
jkros.org, ksae.org, ...). Markup cut down from stored pages."""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.korean_jats import KoreanJatsPreview, NurimediaXmlViewer

URL = "https://example.org/x"

PREVIEW_HEAD = """<html><head>
<meta name="citation_title" content="Comparison of Hams"/>
<meta name="citation_author" content="Bae, Su Min"/><meta name="citation_author" content="Yoo, Yeongmi"/>
<meta name="citation_author" content="Jeong, Jong Youn"/>
<meta name="citation_html_url" content="https://www.foodnlife.org/archive/view_article?pid=fl-26-e00015">
<meta name="citation_doi" content="10.5851/fl.2600015"/>
<script src="/include/js/js_common.js"></script></head><body>"""

PREVIEW = PREVIEW_HEAD + """
<div class="content_content view_article"><div class="article_wrapper"><div id="article-front" class="front">
<h1 class="metadata main-top-title citation_title">Comparison of Hams</h1>
<div class="contrib-group"><span class="citation_author">Su Min Bae</span><sup>1</sup>, <span class="citation_author">Yeongmi Yoo</span><sup>1</sup><sup>,</sup><sup>2</sup>, <span class="citation_author">Jong Youn Jeong</span><sup>1</sup><sup>,</sup><sup>2</sup><sup>,</sup><sup>*</sup></div>
<div class="author-aff">
<div class="affiliation"><a id="A1"><!-- named anchor --></a><sup>1</sup>Department of Food Science, Kyungsung University, Busan 48434, Korea.</div>
<div class="affiliation"><a id="A2"><!-- named anchor --></a><sup>2</sup>Brain Busan 21 Plus Project Team, Kyungsung University, Busan 48434, Korea.</div>
<div class="corresponding-author"><sup>*</sup>Corresponding Author: Jong Youn Jeong, Kyungsung University. E-mail: <a href="mailto:j@ks.ac.kr">j@ks.ac.kr</a>.</div>
<p>Copyright 2026.</p></div>
<h2 class="main-title">Abstract</h2><div class="abstract"><p>This study compared the physicochemical quality characteristics of eight commercially available ham products.</p></div>
<hr class="part-rule"/></div></div></div>
<link rel="stylesheet" type="text/css" href="/journal/jats-preview_main.css"/></body></html>"""

# Korean byline first, English second; Korean and English affiliations under the same numbers; "*" is the first
# author's note (제1저자), "**" the corresponding author's (교신저자).
PREVIEW_BILINGUAL = PREVIEW_HEAD + """
<div class="article_wrapper"><div id="article-front" class="front">
<div class="contrib-group"><span class="citation_author">조재민</span><sup>1</sup><sup>,</sup><sup>*</sup>, <span class="citation_author">민경석</span><sup>2</sup><sup>,</sup><sup>**</sup></div>
<div class="metadata main-top-title-trans">Consequential Validity</div>
<div class="contrib-group"><span class="citation_author">Jae-Min Cho</span><sup>1</sup><sup>,</sup><sup>*</sup>, <span class="citation_author">Kyung-Seok Min</span><sup>2</sup><sup>,</sup><sup>**</sup></div>
<div class="author-aff">
<div class="affiliation"><a id="i1"></a><sup>1</sup>서울남천초등학교 교사</div>
<div class="affiliation"><a id="i2"></a><sup>2</sup>세종대학교 부교수</div>
<div class="affiliation"><a id="A1"></a><sup>1</sup>Teacher, Seoul NamCheon Elementary School</div>
<div class="affiliation"><a id="A2"></a><sup>2</sup>Associate Professor, Sejong University</div>
<div class="corresponding-author"><sup>*</sup>제1저자, <a href="mailto:a@sen.go.kr">a@sen.go.kr</a></div>
<div class="corresponding-author"><sup>**</sup>교신저자, <a href="mailto:b@sejong.ac.kr">b@sejong.ac.kr</a></div>
</div></div></div></body></html>"""

# No numbers: the one affiliation, in Korean and English, belongs to every author; the bare "*" after the name and
# the note's "*" (an e-mail only) mark the corresponding author.
PREVIEW_UNLINKED = PREVIEW_HEAD + """
<div class="article_wrapper"><div id="article-front" class="front">
<div class="contrib-group"><span class="citation_author">Dae-Hoon Lee</span>, <span class="citation_author">Joo-Heon Hong</span>*</div>
<div class="author-aff">
<div class="affiliation"><a id="x"></a>대구가톨릭대학교 식품공학전공</div>
<div class="affiliation"><a id="y"></a>Department of Food Science and Technology, Daegu Catholic University, Gyeongsan 38430, Korea</div>
<div class="corresponding-author"><sup>*</sup><a href="mailto:h@cu.ac.kr">h@cu.ac.kr</a>82-53-850-3218</div>
</div></div></div></body></html>"""

NURI_HEAD = """<html><head><meta name="dc.identifier" content="10.7746/jkros.2022.17.3.245">
<link rel="stylesheet" href="/_common/default.css" type="text/css">
<script type="text/javascript" src="/_common/js/common.js"></script></head><body>"""

NURI = NURI_HEAD + """
<div class='NURIMEDIAXML'><div id="article-level-0-front" class="fm"><table width="100%" class="fm">
<tr><td colspan="2" valign="top"><span class="tl-document">자율주행을 위한 다중센서 데이터셋 구축</span></td></tr>
<tr><td valign="top" align="left"><div id="enNameColon"><span class="capture-id"><span class="gen">심성대</span><span class="xref"><sup><a href="#cor1">†</a></sup></span></span> ; <span class="capture-id"><span class="gen">민지홍</span><sup>1</sup></span> ; <span class="capture-id"><span class="gen">안성용</span><sup>2</sup></span>
</div></td></tr><tr><td valign="top" align="left"></td></tr>
<tr><td colspan="2" valign="top"><br><span class="tl-document">Build a Multi-Sensor Dataset</span></td></tr>
<tr><td valign="top" align="left"><div id="krNameColon"><span class="capture-id"><span class="gen">Sungdae Sim</span><span class="xref"><sup><a href="#cor1">†</a></sup></span></span> ; <span class="capture-id"><span class="gen">Jihong Min</span><sup>1</sup></span> ; <span class="capture-id"><span class="gen">Seongyong Ahn</span><sup>2</sup></span>
</div></td></tr><tr><td valign="top" align="left" id="J_A001"><span class="au-label">1</span>Principal Researcher, ADD, Daejeon, Korea <a href="mailto:m@add.re.kr">(m@add.re.kr)</a><br>
</td></tr><tr><td valign="top" align="left" id="J_A002"><span class="au-label">2</span>Senior Researcher, ADD, Daejeon, Korea <a href="mailto:s@add.re.kr">(s@add.re.kr)</a><br>
</td></tr>
<br><tr><td valign="top"><span class="capture-id"><span class="gen" id="cor1">Correspondence to : </span><sup>†</sup>Senior Researcher, Corresponding author: ADD, Daejeon, Korea (<a href="mailto:x@add.re.kr">x@add.re.kr</a>)<br>
</span><br></td></tr>
<tr><td colspan="2"><br>Copyright KROS</td></tr></table></div></div></body></html>"""

# Unlabelled affiliation rows under each language's byline; the note's marker is on nobody's name, and the page has
# one author, so that author is the one the note is for.
NURI_ONE_AUTHOR = NURI_HEAD + """
<div class='NURIMEDIAXML'><table class="fm">
<tr><td valign="top" align="left"><div id="enNameColon"><span class="capture-id"><span class="gen">김영재</span></span>
</div></td></tr><tr><td valign="top" align="left"></td></tr><tr><td valign="top" align="left">국립부경대학교 지구환경시스템과학부<br>
</td></tr>
<tr><td colspan="2" valign="top"><br><span class="tl-document">Preliminary study</span></td></tr>
<tr><td valign="top" align="left"><div id="krNameColon"><span class="capture-id"><span class="gen">YoungJae Kim</span></span>
</div></td></tr><tr><td valign="top" align="left">Major of Environmental Geosciences, Pukyong National University, Busan 48513, Republic of Korea<br>
</td></tr><tr><td valign="top" align="left"></td></tr>
<br><tr><td valign="top"><span class="capture-id"><span class="gen" id="cor1">Correspondence to : </span><sup>‡</sup>+82-51-629-6625 / E-mail: <a href="mailto:y@pknu.ac.kr">y@pknu.ac.kr</a><br>
</span><br></td></tr></table></div></body></html>"""

# A "*" explained only as the author's affiliation note, and no correspondence note: nobody is corresponding.
NURI_NO_NOTE = NURI_HEAD + """
<div class='NURIMEDIAXML'><table class="fm">
<tr><td valign="top" align="left"><div id="enNameColon"><span class="capture-id"><span class="gen">T. D. Nguyen</span></span><sup>*</sup>
</div></td></tr><tr><td valign="top" align="left" id="J_A001"><span class="au-label">*</span>PhD Student, Department of East Asian Languages and Cultures, Columbia University. <a href="mailto:d@columbia.edu">(d@columbia.edu)</a><br>
</td></tr>
<tr><td colspan="2" valign="top"><br><span class="tl-document"></span></td></tr>
<tr><td valign="top" align="left"><div id="krNameColon">
</div></td></tr>
<tr><td colspan="2"><br>Copyright</td></tr></table></div></body></html>"""


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _affs(author):
    return [a["name"] for a in author["affiliations"]]


def test_preview_numbered_affiliations_and_corresponding():
    authors = _authors(PREVIEW)
    assert [a["name"] for a in authors] == ["Su Min Bae", "Yeongmi Yoo", "Jong Youn Jeong"]
    assert _affs(authors[0]) == ["Department of Food Science, Kyungsung University, Busan 48434, Korea."]
    assert len(_affs(authors[1])) == 2 and len(_affs(authors[2])) == 2
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


def test_preview_keeps_the_generic_abstract():
    out = parse_page(PREVIEW.encode(), "doi", URL)
    assert out["abstract"].startswith("This study compared")


def test_preview_bilingual_takes_english_byline_and_english_affiliations():
    authors = _authors(PREVIEW_BILINGUAL)
    assert [a["name"] for a in authors] == ["Jae-Min Cho", "Kyung-Seok Min"]
    assert _affs(authors[0]) == ["Teacher, Seoul NamCheon Elementary School"]
    assert _affs(authors[1]) == ["Associate Professor, Sejong University"]
    # "*" is the first author's note (제1저자), "**" the corresponding author's (교신저자)
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_preview_unlinked_affiliations_go_to_every_author():
    authors = _authors(PREVIEW_UNLINKED)
    for a in authors:
        assert _affs(a) == ["대구가톨릭대학교 식품공학전공",
                            "Department of Food Science and Technology, Daegu Catholic University, Gyeongsan 38430, Korea"]
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_nurimedia_english_byline_numbered_affiliations_and_cor_link():
    authors = _authors(NURI)
    assert [a["name"] for a in authors] == ["Sungdae Sim", "Jihong Min", "Seongyong Ahn"]
    assert _affs(authors[0]) == []
    assert _affs(authors[1]) == ["Principal Researcher, ADD, Daejeon, Korea"]
    assert _affs(authors[2]) == ["Senior Researcher, ADD, Daejeon, Korea"]
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_nurimedia_one_author_unlabelled_affiliation_and_note():
    authors = _authors(NURI_ONE_AUTHOR)
    assert [a["name"] for a in authors] == ["YoungJae Kim"]
    assert _affs(authors[0]) == [
        "Major of Environmental Geosciences, Pukyong National University, Busan 48513, Republic of Korea"]
    assert authors[0]["is_corresponding"] is True


def test_nurimedia_unexplained_star_is_not_corresponding():
    authors = _authors(NURI_NO_NOTE)
    assert [a["name"] for a in authors] == ["T. D. Nguyen"]
    assert _affs(authors[0]) == [
        "PhD Student, Department of East Asian Languages and Cultures, Columbia University."]
    assert authors[0]["is_corresponding"] is False


def test_lookalikes_not_claimed():
    # KoreaMed Synapse's NLM viewer prints the same capture-id / author-aff vocabulary, but no Nurimedia container
    # or /_common/ assets, and no view_article JATS preview marks.
    synapse = """<html><head><link rel="stylesheet" href="/ViewNLM_m.css"></head><body><div class="abody">
<div id="enNameColon"><span class="capture-id"><span class="gen">Kim A</span></span></div>
<div class="contrib-group"><span class="citation_author">Kim A</span></div>
<div class="author-aff"><div class="affiliation"><sup>1</sup>Seoul National University</div></div></div></body></html>"""
    soup = BeautifulSoup(synapse, "lxml")
    assert not KoreanJatsPreview(soup).is_publisher_specific_parser()
    assert not NurimediaXmlViewer(soup).is_publisher_specific_parser()
    # the article.php?code= template (korean_article_php) uses /_script/ assets and div.fulltext-wrap
    article_php = """<html><head><script src="/_script/common.js"></script></head><body><div class="fulltext-wrap">
<div class="ft-author">Kim A</div><div class="ft-author-aff">Seoul National University</div></div></body></html>"""
    soup = BeautifulSoup(article_php, "lxml")
    assert not KoreanJatsPreview(soup).is_publisher_specific_parser()
    assert not NurimediaXmlViewer(soup).is_publisher_specific_parser()


# The cor link printed after the name's span (span.xref), a second marker inside a <sup>, a phone number on the
# affiliation line, and the dagger explained by an au-label note ("† Corresponding author: ...") with no span#cor1.
NURI_XREF_AFTER_NAME = NURI_HEAD + """
<div class='NURIMEDIAXML'><table class="fm">
<tr><td valign="top" align="left"><div id="enNameColon"><span class="capture-id"><span class="gen">Jeong Won Kim</span></span><sup>1</sup> ; <span class="capture-id"><span class="gen">Juwon Park</span></span><sup>2</sup><sup><span class="gen">, </span>3</sup> ; <span class="capture-id"><span class="gen">Sung Hwan Yoon</span></span><span class="xref"><sup><a href="#cor1">†</a></sup></span>
</div></td></tr><tr><td valign="top" align="left" id="J_A001"><span class="au-label">1</span>M. S. Candidate, National Korea Maritime &amp; Ocean University, Tel: +82-70-4121-0633 <a href="mailto:e@x.com">(e@x.com)</a><br>
</td></tr><tr><td valign="top" align="left" id="J_A002"><span class="au-label">2</span>Department of Marine System Engineering, National Korea Maritime &amp; Ocean University<br>
</td></tr><tr><td valign="top" align="left" id="J_A003"><span class="au-label">3</span>Interdisciplinary Major of Maritime AI Convergence, National Korea Maritime &amp; Ocean University<br>
</td></tr>
<tr><td colspan="2" valign="top"><br><span class="tl-document"></span></td></tr>
<br><tr><td valign="top"><span class="capture-id"><span class="au-label">†</span>Corresponding author: Korea Maritime &amp; Ocean University (<a href="mailto:s@kmou.ac.kr">s@kmou.ac.kr</a>)<br>
</span><br></td></tr></table></div></body></html>"""


def test_nurimedia_cor_link_after_name_and_au_label_note():
    authors = _authors(NURI_XREF_AFTER_NAME)
    assert [a["name"] for a in authors] == ["Jeong Won Kim", "Juwon Park", "Sung Hwan Yoon"]
    assert _affs(authors[0]) == ["M. S. Candidate, National Korea Maritime & Ocean University"]
    assert len(_affs(authors[1])) == 2
    assert [a["is_corresponding"] for a in authors] == [False, False, True]


PREVIEW_REFS = PREVIEW.replace("</div></div></div>\n<link", """</div></div></div>
<div class="back-section"><div class="section ref-list"><h2 class="main-title">REFERENCES</h2><div class="ref-list">
<div class="ref1"><a id="ref1"></a><div class="ref-label cell"><p class="ref-label"><span class="label"><span class="generated">1</span></span>. </p></div>
<div class="ref-content cell">Altintas O, Park S.  2016;  The role of insulin signaling. BMB Rep. 49:81-92<br/><a href="https://doi.org/10.5483/BMBRep.2016.49.2.261" class="ref_img"><img src="/images/icon/crossref_logo.gif"/></a><a href="https://www.google.com/search?q=x"><img src="/images/icon/google_logo.gif"/></a></div></div>
<div class="ref2"><a id="ref2"></a><div class="ref-label cell"><p class="ref-label"><span class="label"><span class="generated">2</span></span>. </p></div>
<div class="ref-content cell">Kim A.  2018;  Another paper. J Food. 3:1-9</div></div>
</div></div></div>
<link""")

NURI_BACK = NURI.replace("</table></div></div></body></html>", """
<tr><td><div class="funding" id="funding">Funding Information &#9660;</div><div id="funding_info" style="display: none;"><div><ul><li style="font-weight:bold;">National Research Foundation of Korea</li><li>NRF-2022S1A5C2A03093515</li></ul><ul><li style="font-weight:bold;">Incheon National University</li><li></ul></div></div></td></tr>
</table></div>
<div id="article-level-0-back" class="bm"><hr class="part-rule">
<div class="capture-id"><span class="tl-main-part">Acknowledgments</span>
<p>This work was supported by the Agency for Defense Development.</p>
<p>It is part of a master's thesis.</p>
</div><hr class="section-rule"><span class="tl-main-part">References</span>
<table width="100%" class="bm">
<tr><td left-margine="10" width="30px"></td><td></td></tr>
<tr><td id="J_B1" valign="top" align="right"><b><i>1. </i></b></td>
<td valign="top">Ahmad, R. (2003). Benefit segmentation. <i>International Journal of Market Research</i>, <i>45</i>(3), 1-13.<br><img src="/_common/images/crossref.gif" doi="https://doi.org/10.1177/147078530304500302" id="crossref"></td></tr>
<tr><td id="J_B2" valign="top" align="right"><b><i>2. </i></b></td>
<td valign="top">Ahn, I. S. (2013). Development of sustainable fashion product. <i>Journal of Illustration Research</i>, <i>37</i>, 155-164.</td></tr>
</table></div></div></body></html>""")


def test_preview_reference_list_whole_with_dois():
    out = KoreanJatsPreview(BeautifulSoup(PREVIEW_REFS, "lxml")).parse()
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2]
    assert refs[0]["raw"].startswith("Altintas O, Park S.") and refs[0]["raw"].endswith("49:81-92")
    assert refs[0]["doi"] == "10.5483/BMBRep.2016.49.2.261" and refs[1]["doi"] is None
    assert out["references_complete"] is True


def test_nurimedia_back_matter_and_funding_box():
    out = NurimediaXmlViewer(BeautifulSoup(NURI_BACK, "lxml")).parse()
    assert out["acknowledgments"] == ("This work was supported by the Agency for Defense Development.\n"
                                      "It is part of a master's thesis.")
    assert out["funding_statement"] == "National Research Foundation of Korea NRF-2022S1A5C2A03093515\n" \
                                       "Incheon National University"
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2]
    assert refs[0]["doi"] == "10.1177/147078530304500302" and refs[0]["raw"].startswith("Ahmad, R. (2003).")
    assert out["references_complete"] is True


def test_numbering_gap_is_not_whole():
    gap = PREVIEW_REFS.replace('<span class="generated">2</span>', '<span class="generated">3</span>')
    assert KoreanJatsPreview(BeautifulSoup(gap, "lxml")).parse()["references_complete"] is False


def test_bracketed_numbers_are_whole():
    bracketed = PREVIEW_REFS.replace('<span class="generated">1</span></span>. ', '<span class="generated">[1]</span></span>. ') \
        .replace('<span class="generated">2</span></span>. ', '<span class="generated">[2]</span></span>. ')
    assert KoreanJatsPreview(BeautifulSoup(bracketed, "lxml")).parse()["references_complete"] is True


# e-lca.org (2005): the English byline drops one of the Korean byline's six authors, so the Korean one is kept, with the
# Korean affiliation lines under its numbers.
PREVIEW_UNEVEN_BYLINES = PREVIEW_HEAD + """
<div class="article_wrapper"><div id="article-front" class="front">
<div class="contrib-group"><span class="citation_author">김영희</span><sup>1</sup>, <span class="citation_author">홍기정</span><sup>1</sup>, <span class="citation_author">이지용</span><sup>1</sup>, <span class="citation_author">허탁</span><sup>1</sup>, <span class="citation_author">이지원</span><sup>2</sup>, <span class="citation_author">문영준</span><sup>2</sup></div>
<div class="contrib-group"><span class="citation_author">Young Hee Kim</span><sup>1</sup>, <span class="citation_author">Ki-Jeong Hong</span><sup>1</sup>, <span class="citation_author">Tak Hur</span><sup>1</sup>, <span class="citation_author">Ji-Won Lee</span><sup>1</sup>, <span class="citation_author">Young-June Moon</span><sup>2</sup>, </div>
<div class="author-aff">
<div class="affiliation"><a id="i1"></a><sup>1</sup>건국대학교 화학생물공학부</div>
<div class="affiliation"><a id="i2"></a><sup>2</sup>(주)삼성전자</div>
<div class="affiliation"><a id="A1"></a><sup>1</sup>Dept. of Materials Chemistry &amp; Engineering</div>
<div class="affiliation"><a id="A2"></a><sup>2</sup>Konkuk University, Samsung Electronics</div>
</div></div></div></body></html>"""


def test_preview_keeps_the_byline_that_names_every_author():
    authors = _authors(PREVIEW_UNEVEN_BYLINES)
    assert [a["name"] for a in authors] == ["김영희", "홍기정", "이지용", "허탁", "이지원", "문영준"]
    assert _affs(authors[0]) == ["건국대학교 화학생물공학부"] and _affs(authors[5]) == ["(주)삼성전자"]


# jmis.org: each affiliation line ends with the author's e-mail link; ITMMA's with "E-mail : ..."; another site's with a
# phone number and a bare e-mail.
PREVIEW_CONTACT_ON_AFFILIATION = PREVIEW_HEAD + """
<div class="article_wrapper"><div id="article-front" class="front">
<div class="contrib-group"><span class="citation_author">Puja Das</span><sup>1</sup><sup>,</sup><sup>*</sup>, <span class="citation_author">Moutushi Singh</span><sup>2</sup>, <span class="citation_author">Du-Nan</span><sup>3</sup></div>
<div class="author-aff">
<div class="affiliation"><a id="A1"><!-- named anchor --></a><sup>1</sup>Department of CSE, Baba Farid College of Engineering Technology, India, <a href="mailto:p@gmail.com">p@gmail.com</a></div>
<div class="affiliation"><a id="A2"><!-- named anchor --></a><sup>2</sup>ITMMA – University of Antwerp, Keizerstraat 64, 2000 Antwerp, Belgium, E-mail : c@ua.ac.be</div>
<div class="affiliation"><a id="A3"><!-- named anchor --></a><sup>3</sup>Graduate School of Storytelling, Dong-eui University, Bus-an, Republic of Korea, +82-010-9583-1966, d@naver.com .</div>
<div class="corresponding-author"><sup>*</sup>Corresponding Author: Puja Das, +91-23952815, <a href="mailto:p@gmail.com">p@gmail.com</a></div>
</div></div></div></body></html>"""


def test_preview_affiliation_lines_lose_their_contact_details():
    authors = _authors(PREVIEW_CONTACT_ON_AFFILIATION)
    assert _affs(authors[0]) == ["Department of CSE, Baba Farid College of Engineering Technology, India"]
    assert _affs(authors[1]) == ["ITMMA – University of Antwerp, Keizerstraat 64, 2000 Antwerp, Belgium"]
    assert _affs(authors[2]) == ["Graduate School of Storytelling, Dong-eui University, Bus-an, Republic of Korea"]
    assert [a["is_corresponding"] for a in authors] == [True, False, False]
