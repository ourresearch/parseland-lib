"""Abstracts on Lexxion journal article pages (lexxion.eu, oxjob #2339).

Markup is cut down from stored Lexxion pages (17 Nov 2026). The site prints the abstract in the "Abstract" tab of its
tab strip (div#abstract_de, whatever the language) with a "Keywords:" line at its end, and the authors only in
citation_author tags and a plain byline. On older articles the same tab holds a first-page preview instead: an image,
or the opening of the body cut off mid-word, which is not an abstract.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.lexxion import Lexxion

URL = "https://core.lexxion.eu/article/core/2026/2/5"


def _page(tab, publisher="Lexxion Publisher", authors=("Alex Wanninger",), info=""):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in authors)
    tabs = f'<div id="abstract_de" class="tab-pane active">{tab}</div>' if tab is not None else ""
    info_tab = f'<div id="author_info" class="tab-pane"><p>{info}</p></div>' if info else ""
    return (f'<html><head><meta name="citation_title" content="A title"><meta name="citation_publisher" '
            f'content="{publisher}"><meta name="citation_doi" content="10.21552/core/2026/2/5">{metas}'
            f'<link href="https://core.lexxion.eu/bundles/quotus/css/core.css" rel="stylesheet"></head><body>'
            f'<div class="article article-contents"><h1 class="title">A title</h1>'
            f'<section class="authors">{", ".join(authors)}</section></div>'
            f'<section class="data tabbable"><ul class="nav nav-tabs"><li class="active"><a href="#abstract_de" '
            f'data-toggle="tab">Abstract</a></li></ul><div class="tab-content">{tabs}{info_tab}</div></section>'
            f'</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


ABSTRACT = ("The EU’s competition and regulatory acquis is increasingly characterised by layering: Article 102 TFEU "
            "applies alongside dense sector regulation. This article argues that regulatory compliance can be "
            "relevant but cannot become a shield.")


def test_reads_the_abstract_tab_without_its_keyword_line():
    out = _parse(_page(f"<p>{ABSTRACT}<br />\nKeywords: sector regulation; regulatory compliance; Bronner</p>"))
    assert out["abstract"] == ABSTRACT
    assert [a["name"] for a in out["authors"]] == ["Alex Wanninger"]


def test_drops_footnote_markers():
    tab = (f'<p>{ABSTRACT} <xref ref-type="fn" rid="fn2">1</xref><br/> Keywords: defence supply markets</p>')
    assert _parse(_page(tab))["abstract"] == ABSTRACT


def test_reads_a_bare_text_abstract():
    text = ("In recent years, climate change adaptation has emerged as an important issue in the policymaking "
            "process. This paper seeks to provide an overview of the governance framework within ASEAN.")
    assert _parse(_page(f"\n\t\t\t\t{text}\n\t\t\t"))["abstract"] == text


def test_keeps_annotation_line_and_text_as_two_paragraphs():
    tab = ("<p>Annotation on the Judgment of the Court of Justice (Fourth Chamber) of 15 September 2022 in Case "
           "C-416/21 <italic>Landkreis v J Sch</italic><br/> On 15 September 2022, the Court delivered its judgment "
           "concerning the interpretation of Article 57 of Directive 2014/24. The case concerns the exclusion of two "
           "tenders.</p>")
    out = Lexxion(BeautifulSoup(_page(tab), "lxml")).parse()
    assert out["abstract"].split("\n") == [
        "Annotation on the Judgment of the Court of Justice (Fourth Chamber) of 15 September 2022 in Case C-416/21 "
        "Landkreis v J Sch",
        "On 15 September 2022, the Court delivered its judgment concerning the interpretation of Article 57 of "
        "Directive 2014/24. The case concerns the exclusion of two tenders."]


def test_a_lone_annotation_line_is_not_an_abstract():
    tab = ("<p>Annotation on the Judgment of the Court (Ninth Chamber) of 21 September 2023 in Case C-510/22 "
           "<italic>Romaqua Group SA v Societatea Națională a Apelor Minerale SA e.a.</italic></p>")
    assert _parse(_page(tab))["abstract"] is None


def test_body_opening_cut_mid_word_is_not_an_abstract():
    tab = ("\n\t\tI. Introduction There is no standard definition of infrastructure across EU legislation or in the "
           "jurisprudence. In the context of the application of the EU rules on competition, the Commission until "
           "recently was of the view that infrastructure projects financed by the public sector represent a general "
           "measure of economic policy, in so far as it is aimed at meeting planning needs or implem\n\t")
    assert _parse(_page(tab))["abstract"] is None


def test_cut_preview_in_a_paragraph_is_not_an_abstract():
    tab = ("<p>On 5 June 2012, the Court of Justice handed down its long-awaited judgment in the dispute between "
           "France and the European Commission regarding alleged State aid. By rejecting the Commission’s appeal, "
           "the Court draws to a close a case that has occupied </p>")
    assert _parse(_page(tab))["abstract"] is None


def test_scanned_front_matter_is_not_an_abstract():
    tab = ("© Lexxion Verlagsgesellschaft mbH · Berlin · Germany i Editorial Advocate General Léger and the Market "
           "Economy Investor Test: Still a long Way to go 1 Andreas Bartosch Articles.")
    assert _parse(_page(tab))["abstract"] is None


def test_preview_image_gives_no_abstract_but_keeps_the_authors():
    tab = ('<div class="col-sm-8 col-xs-12 thumbnail"><img class="img-responsive" '
           'src="/data/article_preview/12175/medium.jpg" alt=""></div>')
    out = _parse(_page(tab))
    assert out["abstract"] is None
    assert [a["name"] for a in out["authors"]] == ["Alex Wanninger"]


def test_claims_lexxion_pages_by_publisher_and_abstract_tab():
    assert Lexxion(BeautifulSoup(_page(f"<p>{ABSTRACT}</p>"), "lxml")).is_publisher_specific_parser()
    assert Lexxion(BeautifulSoup(_page(f"<p>{ABSTRACT}</p>", publisher="Lexxion Verlag"),
                                 "lxml")).is_publisher_specific_parser()


def test_look_alike_page_of_another_publisher_is_not_claimed():
    html = _page(f"<p>{ABSTRACT}</p>", publisher="Quotus Example Press")
    parser = Lexxion(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["abstract"] is None


def test_lexxion_page_without_the_tab_strip_is_not_claimed():
    parser = Lexxion(BeautifulSoup(_page(None), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_drops_a_keyword_line_run_on_after_the_last_sentence():
    tab = f"<p>{ABSTRACT}  Keywords: AI/ML; SaMD; approval processes; design choices; case studies</p>"
    assert _parse(_page(tab))["abstract"] == ABSTRACT
