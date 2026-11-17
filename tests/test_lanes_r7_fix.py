"""Pages that round 7's merged lane parsers (#2288, #2289, #2330) made worse on #2239's labelled dev sample (oxjob #2239).

Markup is cut down from the stored dev pages; names are the pages' own where the rubric's call rests on them. Each fix
has a look-alike that must not change.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.back_matter import plain_citation_tags
from parseland_lib.publisher.parsers.lippincott import Lippincott


def _parse(html, url):
    return parse_page(html.encode(), "doi", url)


def _corr(out):
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


# ---- LWW (#2288): a star that keys the author's own address with an e-mail is the corresponding mark ----

LWW_URL = "https://journals.lww.com/x"
LWW_SUP = '<sup xmlns:mrws="http://webservices.ovid.com/mrws/1.0">{}</sup>'


def _lww(byline, notes):
    paras = "".join(f'<p id="BT_ID_1">{n}</p>' for n in notes)
    return ('<html><head><meta property="og:url" content="https://journals.lww.com/cld/fulltext/2012/x.aspx"></head>'
            f'<body><section id="ejp-article-authors"><p id="P7">{byline}</p>'
            '<section><a href="#" id="ejp-article-authors-link"> Author Information </a></section></section>'
            f'<div class="ejp-article-authors-info-holder">{paras}</div></body></html>')


def test_lww_star_keying_the_authors_own_address_and_email_marks_him():
    # 10.1002/cld.420: one author, starred; the star's note is his name, postal address and e-mail, no label
    html = _lww("Volk, Michael L. MD, MSc" + LWW_SUP.format("1,*"),
                [LWW_SUP.format("1") + "Division of Gastroenterology and Hepatology, University of Michigan, Ann Arbor, MI",
                 LWW_SUP.format("*") + "Michael L. Volk, MD, MSc, Division of Gastroenterology and Hepatology, University "
                 "of Michigan Health System, 1500 E Medical Center Drive, Ann Arbor, MI 48109. E-mail: e-mail; x@y.edu.",
                 "Potential conflict of interest: Nothing to report."])
    assert [a.name for a in Lippincott(BeautifulSoup(html, "lxml")).get_authors() if a.is_corresponding] == [
        "Volk, Michael L. MD, MSc"]
    assert _corr(_parse(html, LWW_URL)) == ["Volk, Michael L. MD, MSc"]


def test_lww_star_keying_a_department_with_an_email_is_still_a_key():
    # the look-alike: the starred note names no author (an affiliation that happens to carry an e-mail)
    html = _lww("Volk, Michael L. MD" + LWW_SUP.format("*") + "; Kaplan, Amy BA" + LWW_SUP.format("*"),
                [LWW_SUP.format("*") + "Division of Gastroenterology, University of Michigan, Ann Arbor, MI. "
                 "E-mail: office@y.edu."])
    assert _corr(_parse(html, LWW_URL)) == []


# ---- SciRP (#2289): a star on one author only, unexplained, is the conventional corresponding mark ----

SCIRP_URL = "https://www.scirp.org/journal/paperinformation?paperid=75534"


def _scirp(authors, full_text=""):
    byline = ", ".join(f"<a href='articles?searchcode={n.replace(' ', '+')}&searchfield=authors&page=1'>{n}</a>"
                       f"<sup>{s}</sup>" for n, s in authors)
    return (f'<html><head><meta name="citation_publisher" content="Scientific Research Publishing" />'
            + "".join(f'<meta name="citation_author" content="{n}" />' for n, _ in authors)
            + '<meta name="citation_title" content="A title" /></head><body><div id="JournalInfor_div_paper">'
            f'<div>{byline}<br/><span id="JournalInfor_div_affs"><a href="articles?searchfield=affs">Zhanjiang Branch '
            f'of CNOOC, Zhanjiang, China</a>.<br/></span></div><div id="htmlContent">{full_text}</div></div></body></html>')


def test_scirp_star_on_one_author_marks_that_author():
    # 10.4236/ojms.2017.72019 ("Aiqun Liu*, Peiyuan Zhu, ...") and 10.4236/nr.2016.710047 ("1,2*"); a table's
    # "*Synthetic pesticides." note explains no byline mark
    html = _scirp([("Aiqun Liu", "*"), ("Peiyuan Zhu", ""), ("Guangchao Pan", "")],
                  '<p class="E-Title1">2. Methods</p><p>*Synthetic pesticides.</p>')
    assert _corr(_parse(html, SCIRP_URL)) == ["Aiqun Liu"]
    html = _scirp([("Moses Makonjio Okello", "1,2*"), ("John Warui Kiringe", "1")])
    assert _corr(_parse(html, SCIRP_URL)) == ["Moses Makonjio Okello"]


def test_scirp_star_the_notes_explain_otherwise_or_on_everyone_marks_no_one():
    notes = '<p class="E-Title1">NOTES</p><p>*Joint first author.</p>'
    assert _corr(_parse(_scirp([("Ana Example", "1*"), ("Ben Sample", "1")], notes), SCIRP_URL)) == []
    assert _corr(_parse(_scirp([("Ana Example", "1*"), ("Ben Sample", "1*")]), SCIRP_URL)) == []


# ---- RCNi (#2330): an opinion piece's second block is the body's first paragraph ----

RCNI_URL = "https://journals.rcni.com/doi/abs/10.7748/nm.10.3.10.s10"
STANDFIRST = ("David Benton discusses the results of the Scottish parliamentary elections and their likely effect on "
              "health care and nursing in Scotland")
OPENING = ("THE PEOPLE HAVE SPOKEN and the result is not quite what the press and commentators were expecting "
           "(<xref ref-type=\"table\" rid=\"T1\">Table 1</xref>).")


def _rcni(subject):
    return ('<html><head><meta name="dcterms.title" content="A title" /><meta name="dcterms.creator" content="" />'
            f'<meta name="dcterms:subject" content="{subject}" /><meta name="twitter:site" content="@rcni" />'
            '<meta name="dcterms.identifier" content="https://journals.rcni.com/doi/abs/10.7748/nm.10.3.10.s10"/>'
            '</head><body><div class="articleLeftBlock"><h1 class="mar-t5 mar-b25"> A title </h1>'
            f'<div class="borderBtmBlack"><abstract><p>{STANDFIRST}</p></abstract><abstract>'
            f'<p xmlns:mml="http://www.w3.org/1998/Math/MathML">{OPENING}</p></abstract></div></div>'
            '<h2 class="font1">Want to read more?</h2></body></html>')


def test_rcni_opinion_piece_keeps_the_standfirst_only():
    assert _parse(_rcni("Opinion"), RCNI_URL)["abstract"] == STANDFIRST


def test_rcni_news_item_keeps_both_blocks():
    # #2330's reading on news items stays (its labellers kept both blocks on 5 of 6 pages)
    assert _parse(_rcni("News"), RCNI_URL)["abstract"].startswith(STANDFIRST + "\nTHE PEOPLE HAVE SPOKEN")


# ---- IOS Press (#2330): the full text's structured abstract when the front-matter block has no Abstract row ----

IOS_URL = "https://content.iospress.com/articles/journal-of-alzheimers-disease-reports/adr230088"


def _ios(front):
    return ('<html><head><meta name="citation_publisher" content="IOS Press"/><meta name="citation_title" '
            'content="A title"/></head><body><div class="main col"><header class="article-header"><h1>A title</h1>'
            '<div class="front-meta-data" id="article1-front-metadata"><p class="metadata-entry"><span '
            'class="generated">Article type: </span>Research Article</p><p class="metadata-entry"><span '
            'class="generated">Authors: </span><a href="https://content.iospress.com:443/search?q=author%3A%28%22Roe'
            '%22%29">Roe, Catherine M.</a></p></div></header><div class="complete-article-html-placeholder"><div>'
            f'<section class="nlm-article"><div class="front" id="article1-front">{front}</div><div class="body">'
            '<div class="section"><h2 class="main-title">INTRODUCTION</h2><p>The ATN research framework.</p></div>'
            '</div></section></div></div></div></body></html>')


def _section(label, text):
    return (f'<div class="section"><h3 class="section-title"><span class="title-label"></span>{label}</h3>'
            f'<p id="d1">{text}</p></div>')


def test_ios_full_text_structured_abstract_is_read_whole():
    front = ('<h4 class="callout-title"><span class="generated">Abstract</span></h4>'
             + _section("Background:", "Declines in driving are hallmarks of AD.")
             + _section("Objective:", "This study assessed plasma A&#946;<sub>40</sub> biomarkers.")
             + _section("Conclusions:", "Different biomarkers offer complementary information."))
    assert _parse(_ios(front), IOS_URL)["abstract"] == (
        "Background: Declines in driving are hallmarks of AD.\n"
        "Objective: This study assessed plasma Aβ40 biomarkers.\n"
        "Conclusions: Different biomarkers offer complementary information.")


def test_ios_full_text_front_without_an_abstract_callout_gives_no_abstract():
    front = '<h4 class="callout-title"><span class="generated">Keywords</span></h4><p>driving, biomarkers</p>'
    out = _parse(_ios(front), IOS_URL)
    assert not out["abstract"] or "driving, biomarkers" not in out["abstract"]


# ---- Frontiers conference abstracts (#2289): the abstract ends at the keywords line ----

CTL = "ctl00_ctl00_MainContentPlaceHolder_ContentAreaMainContent_ucAbstractDetails"
FRONTIERS_URL = "https://doi.org/10.3389/conf.fmars.2019.08.00117"


def _conf(abstract):
    return ('<html><head><meta id="ctl00_ctl00_MetaImageUrl" name="url" property="og:url"/>'
            '<meta content="Frontiers" name="site_name" property="og:site_name"/></head><body>'
            '<div id="divFontAdjAreaLevel4" class="JournalAbstract"><h1>The blue crab in the Iberian Levantine coast'
            f'</h1><div class="authors"><a href="/people/X/1" id="{CTL}_rptAuthors_ctl00_aAuthor">Andres Izquierdo</a>'
            f'<sup>1</sup></div><ul class="notes"><li><span><sup>1</sup></span> University of Alicante, Spain</li></ul>'
            f'<p class="pb15"><span id="{CTL}_litAbstract" class="cont16 white-space-wrap">{abstract}</span></p>'
            '</div></body></html>')


def test_frontiers_conference_abstract_stops_at_the_keywords_line():
    text = ("Abstract \nIn the last five years C. sapidus has expanded dramatically. \n"
            "Key words: Callinectes sapidus, alien species\nIntroducción \nThe Atlantic blue crab was recorded in 2004.\n"
            "Material and methods\nThe study area is the Valencia region.")
    assert _parse(_conf(text), FRONTIERS_URL)["abstract"] == "In the last five years C. sapidus has expanded dramatically."


def test_frontiers_conference_abstract_without_keywords_or_with_them_first_is_kept():
    text = "Objective\nWe studied crabs.\nConclusion\nThe key words of this study are crabs and coasts."
    assert _parse(_conf(text), FRONTIERS_URL)["abstract"] == text
    first = "Keywords: crabs\nWe studied crabs on the coast of Valencia."
    assert _parse(_conf(first), FRONTIERS_URL)["abstract"] == first


# ---- Magtech (#2289): each printed row of a multi-part reference is one item ----

SIOC_URL = "https://doi.org/10.6023/cjoc202212033"


def _magtech(rows, badge):
    trs = "".join(f'<tr><td valign="top" align="right">{n}</td><td><div class="mag_xml_publish_ref">{raw}</div>'
                  + (f'<br/>doi: <a href="http://dx.doi.org/{doi}">{doi}</a>' if doi else "") + '</td></tr>'
                  for n, raw, doi in rows)
    return ('<html><head><META NAME="GENERATOR" CONTENT="Beijing Magtech Co., Ltd"><meta name="citation_language" '
            'content="en" /><meta name="citation_title" content="A title" /><meta name="citation_authors" '
            'content="WANG Huadong" /><script src="http://sioc-journal.cn/js/modelDialog1.js"></script></head><body>'
            '<div class="abs-con"><h3 class="abs-tit">A title</h3><p data-toggle="collapse" data-target="#divPanelEn">'
            '<span>WANG Huadong</span></p><div id="divPanelEn" class="collapse bs-callout"><address class="address">'
            '<ol class="list-unstyled"><li>Fudan University</li></ol></address></div>'
            '<div class="panel-heading" id="cankaowenxian"><h4 class="panel-title"><a id="reference">References '
            f'<span class="badge badge-info">{badge}</span></a></h4></div><div id="collapseThree"><div class="panel-body">'
            f'<table>{trs}</table></div></div></div></body></html>')


def test_magtech_sub_entries_are_items_of_their_own_and_the_list_is_whole():
    rows = [("[1]", "Greenwood, N. N.; Earnshaw, A. Chemistry of the Elements, Elsevier, 1997.", None),
            ("[2]", "Examples see: (a) Haubold, W.; Herdtle, J. J. Organomet. Chem. 1986, 315, 1.", "10.1016/0022-328X(86)80405-3"),
            ("", "(b) Sharp, M. J.; Cheng, W. Tetrahedron Lett. 1987, 28, 5093.", "10.1016/S0040-4039(00)95599-0"),
            ("[3]", "Pyykkö, P.; Atsumi, M. Chem.-Eur. J. 2009, 15, 186.", None)]
    out = _parse(_magtech(rows, 3), SIOC_URL)
    assert [r["raw"][:11] for r in out["references"]] == ["Greenwood, ", "Examples se", "(b) Sharp, ", "Pyykkö, P.;"]
    assert [r["doi"] for r in out["references"]][1:3] == ["10.1016/0022-328X(86)80405-3", "10.1016/S0040-4039(00)95599-0"]
    assert out["references_complete"] is True


def test_magtech_translation_row_stays_with_its_reference():
    rows = [("[1]", "Lu, X. Q.; Cao, S. F. Acta Chim. Sinica 2015, 73, 1.", None),
            ("", "(鲁效庆, 曹守福, 化学学报, 2015, 73, 1.)", None),
            ("[2]", "Pyykkö, P.; Atsumi, M. Chem.-Eur. J. 2009, 15, 186.", None)]
    out = _parse(_magtech(rows, 2), SIOC_URL)
    assert len(out["references"]) == 2 and "鲁效庆" in out["references"][0]["raw"]
    assert out["references_complete"] is True


# ---- citation_reference tags: two tags prove no whole list when the page prints its list elsewhere ----

TAGS = ('<meta name="citation_reference" content="CANBERRA Cooperate, InSpector 1000 Digital Hand-Held Multichannel '
        'Analyzer (Confirmed January 27, 2016).">'
        '<meta name="citation_reference" content="METI, First Secretariat meeting of the Team for Countermeasures, '
        'Material 4-5, December 26, 2013.">')


def test_two_tags_on_a_page_with_a_separate_references_tab_are_not_whole():
    # 10.1051/epjconf/201715308011 (EDP Sciences): the list is on the "References" tab, /ref/...
    html = (f'<html><head>{TAGS}</head><body><ul><li><a href="/articles/epjconf/ref/2017/22/x/x.html" '
            'title="References">References</a></li></ul></body></html>')
    found = plain_citation_tags(BeautifulSoup(html, "lxml"))
    assert len(found["references"]) == 2 and found["references_complete"] is False


def test_two_tags_with_the_list_on_this_page_stay_whole():
    html = f'<html><head>{TAGS}</head><body><a href="#pane-pcw-references">References</a></body></html>'
    assert plain_citation_tags(BeautifulSoup(html, "lxml"))["references_complete"] is True


def test_lww_star_on_two_authors_keying_one_address_marks_that_author_only():
    html = _lww("Volk, Michael L. MD" + LWW_SUP.format("*") + "; Kaplan, Amy BA" + LWW_SUP.format("*"),
                [LWW_SUP.format("*") + "Michael L. Volk, MD, Division of Gastroenterology, University of Michigan, "
                 "Ann Arbor, MI 48109. E-mail: x@y.edu."])
    assert _corr(_parse(html, LWW_URL)) == ["Volk, Michael L. MD"]
