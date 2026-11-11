"""Chapter and article openings that publishers mark on the page are not abstracts (oxjob #2162).

T&F (taylorfrancis.com) labels the text it shows for a chapter in its product data: textType "abstract" or
"enriched" (written about the chapter) or "first-paragraph" (the chapter's opening, shown when it has no abstract);
the JSON-LD description repeats it. Cambridge Core marks its stand-in the same way: a chapter's "Summary" holds
div.abstract with data-abstract-type="extract", an article's section is headed "Extract", and citation_abstract
repeats the text. Gold v1.3 labels these pages "no abstract" (T&F 11 of 12 dev pages; the 12th opens "This chapter
discusses...", kept below). Hand-crafted HTML, no network.
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.cup import CUP
from parseland_lib.publisher.parsers.taylor import Taylor

OPENING = (
    "Valley is, of course, the chief and the most remarkable. But the State is full of wonderful natural phenomena; "
    "and when the tourist has seen the Yosemite, the Calaveras Big Tree Grove, the Geysers and Mount Shasta, he has "
    "left unseen still Mono Lake."
)
ABSTRACT = (
    "The fourth chapter positions Information Security Management Systems as the institutional core of logistics "
    "cybersecurity. By contextualising international governance frameworks within logistics operations, it shows "
    "how cybersecurity governance becomes an organisational discipline."
)
STATEMENT = (
    "This chapter discusses the Chain Rule for functions of several variables. As a consequence of this result, "
    "differentiation of functions defined implicitly is presented."
)


def _tf_escape(value: str) -> str:
    return value.replace("&", "&a;").replace('"', "&q;").replace("<", "&l;").replace(">", "&g;")


def _tf_page(text: str, text_type: str) -> str:
    state = json.dumps({"product": {"title": "A chapter", "abstracts": [
        {"type": "xml", "position": 0, "textType": text_type, "value": f"<p>{text}</p>"}]}})
    jsonld = json.dumps({"@context": "https://schema.org", "@type": "Chapter", "name": "A chapter",
                         "url": "https://www.taylorfrancis.com/chapters/mono/10.4324/x-1/a-chapter",
                         "description": text[:150], "publisher": {"name": "Taylor & Francis"}})
    return (
        '<html><head><meta property="og:url" content="https://www.taylorfrancis.com/chapters/mono/10.4324/x-1/a" />'
        '<meta name="citation_title" content="A chapter" />'
        f'<script type="application/ld+json">{jsonld}</script></head><body>'
        f'<script type="application/json" id="serverApp-state">{_tf_escape(state)}</script></body></html>'
    )


def _tf_abstract(text: str, text_type: str):
    return Taylor(BeautifulSoup(_tf_page(text, text_type), features="lxml")).parse()["abstract"]


def test_tf_first_paragraph_is_not_an_abstract():
    assert not _tf_abstract(OPENING, "first-paragraph")


def test_tf_first_paragraph_does_not_fall_back_to_jsonld_description():
    page = _tf_page(OPENING, "first-paragraph")
    parser = Taylor(BeautifulSoup(page, features="lxml"))
    assert parser._taylorfrancis_jsonld_chapter()["description"]
    assert not parser.parse()["abstract"]


def test_tf_first_paragraph_that_states_what_the_chapter_does_is_kept():
    assert _tf_abstract(STATEMENT, "first-paragraph").startswith("This chapter discusses")


def test_tf_abstract_and_enriched_are_kept():
    assert _tf_abstract(ABSTRACT, "abstract").startswith("The fourth chapter")
    assert _tf_abstract(ABSTRACT, "enriched").startswith("The fourth chapter")


CUP_OG = '<meta property="og:url" content="https://www.cambridge.org/core/books/x/y/ABC" />'
AUTHOR = '<div class="author"><dt>Jane Doe</dt><div class="d-sm-flex">Example University</div></div>'


def _cup(head: str, body: str):
    html = f"<html><head>{CUP_OG}{head}</head><body>{AUTHOR}{body}</body></html>"
    return CUP(BeautifulSoup(html, features="lxml")).parse()["abstract"]


def _summary(text: str, abstract_type: str, heading: str = "Summary") -> str:
    return (f'<div id="sec0" class="col sec summary"><h2>{heading}</h2> <div>'
            f'<div class="abstract" data-abstract-type="{abstract_type}"><p>{text}</p></div></div></div>')


def _article(text: str, abstract_type: str, heading: str) -> str:
    return ('<div id="sec0" class="col article-abstract sec"><div class="abstract-text-container"><div lang="en">'
            f'<h2>{heading}</h2> <div class="abstract-content"><div class="abstract" data-abstract-type="{abstract_type}">'
            f'<p>{text}</p></div></div></div></div></div>')


def test_cup_chapter_extract_is_not_an_abstract():
    assert not _cup("", _summary(OPENING, "extract"))


def test_cup_chapter_normal_summary_is_kept():
    assert _cup("", _summary(ABSTRACT, "normal")).startswith("The fourth chapter")


def test_cup_article_extract_heading_drops_meta_and_visible_text():
    meta = f'<meta name="citation_abstract" content="{OPENING}" />'
    assert not _cup(meta, _article(OPENING, "text-abstract", "Extract"))


def test_cup_article_abstract_heading_is_kept():
    meta = f'<meta name="citation_abstract" content="{ABSTRACT}" />'
    assert _cup(meta, _article(ABSTRACT, "normal", "Abstract")).startswith("The fourth chapter")


def test_keep_rule_reads_past_the_first_sentence_and_literal_newline_escapes():
    text = ("In 1996, Congress passed the Telecommunications Act to promote local telephone entry. Through late 1998, "
            "no operator had satisfied the conditions set out in Section 271.\\nWe propose instead to permit entry.")
    assert _tf_abstract(text, "first-paragraph").startswith("In 1996")


def test_cup_extract_that_describes_the_work_is_kept():
    text = ("This is a two-year survey of bibliographical work completed in the Republic of South Africa. Recent "
            "developments in current and retrospective national bibliography are outlined.")
    assert _cup("", _article(text, "text-abstract", "Extract")).startswith("This is a two-year survey")
