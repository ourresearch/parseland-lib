"""eLife reviewed-preprint pages: corresponding authors (oxjob #2268, template "elife").

Markup is cut down from stored eLife pages (16 Nov 2026). The reviewed-preprint full-text tab (eLife's Next.js
"enhanced preprints" app, route /reviewed-preprints/[...path]) prints its byline as `ol.author-list`, and each
corresponding author's entry carries a "For correspondence:" e-mail line. The citation_author tags the generic parser
reads carry no correspondence flag, and the generic parser's byline star is eLife's "Lead contact" note, not a
correspondence mark. The Peer review tab of the same app prints no byline (its DOIs are review sub-articles) and the
eLife journal's own article pages (patterns `ol.author_list`) are a different template: neither is claimed.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.elife import ELifeReviewedPreprint

URL = "https://elifesciences.org/reviewed-preprints/105710v2"
NAMES = ["Chikayo Hemmi", "Kenichi Ishii", "Kazuo Emoto"]
ABSTRACT = ("Sleep-wakefulness regulation dynamically evolves along development in a wide range of organisms. " * 3).strip()
NEXT_DATA = ('<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}},'
             '"page":"/reviewed-preprints/[...path]","query":{"path":["105710v2"%s]}}</script>')


def _head(names=NAMES, publisher="eLife Sciences Publications Limited"):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f'<meta name="citation_title" content="A title"/><meta name="citation_publisher" content="{publisher}"/>'
            f'<meta name="citation_doi" content="10.7554/eLife.105710.2"/>{metas}'
            f'<meta name="citation_abstract" content="{ABSTRACT}"/>')


def _item(name, corr=False, star=False):
    sup = '<sup aria-hidden="true">*</sup>' if star else ""
    notes = ""
    if corr or star:
        notes = '<ul class="author-list__footnotes_list">'
        if corr:
            notes += ('<li class="author-list__footnote"><strong class="author-list__email--heading">For correspondence:'
                      '</strong> <!-- -->someone@example.org</li>')
        if star:
            notes += '<li class="author-list__footnote"><sup aria-hidden="true">*</sup>Lead contact</li>'
        notes += "</ul>"
    return (f'<li class="author-list__author"><h4 class="author-list__author_name" id="x1">{name}{sup}</h4>'
            f'<div class="author-list__affiliations">Department of Biological Sciences, The University of Tokyo, Tokyo, '
            f'Japan</div>{notes}</li>')


def _full_text_page(items, route_extra="", head=None):
    body = f'<ol class="author-list">{"".join(items)}</ol><section class="abstract"><p>{ABSTRACT}</p></section>'
    return (f"<html><head>{head or _head()}</head><body>{body}{NEXT_DATA % route_extra}</body></html>")


def _rp_page():
    return _full_text_page([_item(NAMES[0]), _item(NAMES[1], corr=True), _item(NAMES[2], corr=True, star=True)])


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _parser(html):
    return ELifeReviewedPreprint(BeautifulSoup(html, parser="lxml", features="lxml"))


def test_for_correspondence_marks_the_corresponding_authors():
    authors = _authors(_rp_page())
    assert [a["name"] for a in authors] == NAMES
    assert [a["is_corresponding"] for a in authors] == [False, True, True]


def test_lead_contact_star_alone_is_not_a_correspondence_mark():
    html = _full_text_page([_item(NAMES[0]), _item(NAMES[1], corr=True), _item(NAMES[2], star=True)])
    assert [a["name"] for a in _authors(html) if a["is_corresponding"]] == ["Kenichi Ishii"]


def test_byline_names_drop_the_footnote_star_and_keep_the_abstract():
    html = _rp_page()
    parsed = _parser(html).parse()
    assert [a["name"] for a in parsed["authors"]] == NAMES
    assert parse_page(html.encode(), "doi", URL)["abstract"].startswith("Sleep-wakefulness regulation")


def test_affiliations_are_left_to_the_works_side():
    # every eLife work with authors already carries its affiliations; this parser ships corresponding flags only
    assert all(a["affiliations"] == [] for a in _parser(_rp_page()).parse()["authors"])


def test_peer_review_tab_is_not_claimed():
    # the review tab prints no byline: its DOIs are review sub-articles (the citation tags are the parent's)
    html = (f'<html><head>{_head()}</head><body><h2>Reviewer #1 (Public review):</h2><p>Text.</p>'
            f'{NEXT_DATA % ",\"reviews\""}</body></html>')
    assert not _parser(html).authors_found()


def test_elife_journal_article_page_is_not_claimed():
    # eLife's journal (version of record) template: patterns markup, dc.contributor tags, no Next.js route
    html = ('<html><head><meta name="dc.publisher" content="eLife Sciences Publications Limited"/>'
            '<meta name="dc.contributor" content="Francois Lallemend"/>'
            '<meta property="og:url" content="https://elifesciences.org/articles/106803"/></head><body>'
            '<div class="authors" data-behaviour="Authors"><ol class="author_list"><li class="author_list_item">'
            '<span class="author"><a class="author_link" href="#x1">Francois Lallemend</a></span></li></ol></div>'
            '</body></html>')
    p = _parser(html)
    assert not p.is_publisher_specific_parser()
    assert not p.authors_found()


def test_other_nextjs_site_with_the_same_class_names_is_not_claimed():
    html = _full_text_page([_item(NAMES[0]), _item(NAMES[1], corr=True)],
                           head=_head(publisher="Some Other Press")).replace("/reviewed-preprints/[...path]",
                                                                             "/articles/[slug]")
    p = _parser(html)
    assert not p.is_publisher_specific_parser()
    assert not p.authors_found()
