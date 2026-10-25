"""Corresponding authors (and the affiliations beside them) on publishers' 2025-26 page templates (oxjob #1805).

Markup is cut down from fresh pages fetched 24 Oct 2026 (#1802's freshness pilot): ACS and RSC on Silverchair,
MDPI's Nuxt front end, Frontiers' ArticleDetailsV4. Before these fixes every new ACS and RSC page lost its
corresponding author, MDPI lost affiliations and most corresponding authors, Frontiers ~1 in 5.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import _mark_silverchair_corresponding, parse_page
from parseland_lib.publisher.parsers.frontiers import Frontiers
from parseland_lib.publisher.parsers.mdpi import MDPI
from parseland_lib.publisher.parsers.utils import NuxtPayload, same_person


def _silverchair_author(name, corresponding=False, ref="cor1"):
    note = (f'<span class="info-card-footnote"><a href="javascript:;" reveal-id="{ref}" data-open="{ref}" '
            f'class="link link-ref link-reveal js-reveal-distinct xref-corresp" '
            f'aria-label="Corresponding author note"></a></span>') if corresponding else ""
    block = (f'<div class="info-author-correspondence"><div content-id="{ref}"><span class="label title-label">*'
             f'</span>Email: <a href="/cdn-cgi/l/email-protection#a7c4"><span class="__cf_email__" '
             f'data-cfemail="2043">[email protected]</span></a>.</div></div>') if corresponding else ""
    return f"""
    <div class="al-author-name">
      <a class="linked-name js-linked-name stats-author-info-trigger" href="javascript:;">{name}</a> {note}
      <span class="al-author-delim">; </span>
      <div class="al-author-info-wrap arrow-up stats-author-info-panel" role="dialog">
        <div class="info-card-author authorInfo_ArticleTopInfo">
          <div class="name-role-wrap"><div class="info-card-name"> {name} {note} </div></div>
          <div class="info-card-affilitation"><div class="aff"><div class="institution">Shenzhen University</div>,
            <span class="city">Shenzhen</span> <div class="country">China</div></div></div>
          {block}
        </div>
      </div>
    </div>"""


def _silverchair_page(og_url, authors):
    metas = "".join(f'<meta name="citation_author" content="{family}, {given}">'
                    f'<meta name="citation_author_institution" content="Shenzhen University, Shenzhen 518060, China">'
                    for given, family, _ in authors)
    byline = "".join(_silverchair_author(f"{given} {family}", corr, f"cor{i}")
                     for i, (given, family, corr) in enumerate(authors, 1))
    return f"""<html><head><meta property="og:url" content="{og_url}">{metas}</head>
    <body><div class="wi-authors"><div class="al-authors-list">
    <input id="js-hdn-enable-corresponding-author-icon" type="hidden" value="False"/>{byline}</div></div></body></html>"""


def _corresponding(out):
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def test_acs_silverchair_page_keeps_its_corresponding_authors():
    # 10.1021/acs.analchem.3c05767: the stored pubs.acs.org/doi/ page marked Yu Chen and Danying Lin
    html = _silverchair_page(
        "https://pubs.acs.org/ancham/article/96/7/2754/85146/Label-Free",
        [("Junle", "Qu", False), ("Guoquan", "Luo", False), ("Yu", "Chen", True), ("Danying", "Lin", True)])
    out = parse_page(html.encode(), "doi", "https://pubs.acs.org/ancham/article-abstract/96/7/2754/85146/x")
    assert _corresponding(out) == ["Chen, Yu", "Lin, Danying"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, False, True, True]
    assert all(a["affiliations"] for a in out["authors"])


def test_rsc_silverchair_page_keeps_its_corresponding_authors():
    # 10.1039/d3ce00984j: the stored articlelanding page marked Rong Wang, Xiaodong Pi, Julong Yuan
    html = _silverchair_page(
        "https://pubs.rsc.org/ce/article/26/6/875/800120/Effect-of-subsurface",
        [("Guofeng", "Li", False), ("Rong", "Wang", True), ("Xiaodong", "Pi", True), ("Julong", "Yuan", True)])
    out = parse_page(html.encode(), "doi", "https://pubs.rsc.org/ce/article-abstract/26/6/875/800120/x")
    assert _corresponding(out) == ["Wang, Rong", "Pi, Xiaodong", "Yuan, Julong"]


def test_silverchair_card_name_footnote_label_is_not_part_of_the_name():
    # pubs.aip.org cards: "Nien-Hui Ge <span class=info-card-footnote><a ...>a)</a></span>"
    html = _silverchair_page("https://pubs.aip.org/aip/jcp/article/1/1/1/1/x", [("Ann", "Smith", False), ("Nien-Hui", "Ge", True)])
    html = html.replace('aria-label="Corresponding author note"></a>', 'aria-label="Corresponding author note">a)</a>')
    out = parse_page(html.encode(), "doi", None)
    assert _corresponding(out) == ["Ge, Nien-Hui"]


def test_silverchair_page_without_marks_sets_no_one():
    html = _silverchair_page("https://pubs.acs.org/jacs/article/1/1/1/1/x", [("Ann", "Smith", False), ("Bo", "Li", False)])
    out = parse_page(html.encode(), "doi", None)
    assert _corresponding(out) == []


def test_silverchair_marks_never_override_a_parser_that_found_one():
    # a page whose winning parser already marked a corresponding author keeps exactly its choice
    html = _silverchair_page("https://pubs.acs.org/jacs/article/1/1/1/1/x", [("Ann", "Smith", False), ("Bo", "Li", True)])
    authors = [{"name": "Ann Smith", "affiliations": [], "is_corresponding": True},
               {"name": "Bo Li", "affiliations": [], "is_corresponding": None}]
    _mark_silverchair_corresponding(BeautifulSoup(html, "lxml"), authors)
    assert [a["is_corresponding"] for a in authors] == [True, None]


def test_silverchair_name_that_matches_no_author_is_skipped():
    html = _silverchair_page("https://pubs.acs.org/jacs/article/1/1/1/1/x", [("Ann", "Smith", False), ("Bo", "Li", True)])
    html = html.replace('content="Li, Bo"', 'content="Wong, Carla"')
    out = parse_page(html.encode(), "doi", None)
    assert _corresponding(out) == []


# MDPI 2025-26 front end: byline with data-testid, full lists only in the Nuxt payload

def _mdpi_payload(authors, affiliations):
    """A devalue-format __NUXT_DATA__ array holding one article's authors and affiliations."""
    arr = [["ShallowReactive", 1], {"data": 2}, ["ShallowReactive", 3], {"article-2079-6382-14-5-482-guest": 4}, None]
    art = {}
    arr[4] = art

    def add(v):
        arr.append(v)
        return len(arr) - 1

    a_idx = []
    for name, sup in authors:
        a_idx.append(add({"name": add(name), "superscript": add(sup), "onBehalfOf": -1}))
    f_idx = []
    for ident, name in affiliations:
        f_idx.append(add({"name": add(name), "identifier": add(ident)}))
    art["authors"] = add(a_idx)
    art["affiliations"] = add(f_idx)
    return json.dumps(arr)


def _mdpi_page(authors, affiliations, payload=True):
    byline = "".join(
        f'<div class="inline-flex" data-testid="article-author"><button type="button"><span class="m-rich-text" '
        f'itemprop="author"><span class="underline" itemprop="name">{name}</span><sup> {sup}</sup></span>'
        f'</button></div>' for name, sup in authors)
    affs = "".join(
        f'<div class="flex gap-x-2.5" data-testid="article-affiliation"><span><sup>{ident}</sup></span>'
        f'<div class="m-rich-text">{name}</div></div>' for ident, name in affiliations[:4])  # the page shows four
    script = (f'<script type="application/json" data-nuxt-data="nuxt-app" id="__NUXT_DATA__">'
              f'{_mdpi_payload(authors, affiliations)}</script>') if payload else ""
    return f"""<html><head><meta property="og:url" content="https://www.mdpi.com/2079-6382/14/5/482"></head>
    <body><div data-testid="article-authors">{byline}</div>
    <div data-testid="article-affiliations-section">{affs}</div>{script}</body></html>"""


MDPI_AUTHORS = [("Filippos Georgios Nikolaou", "1"), ("Liora Mihaela Colobatiu", "2,*"),
                ("Laurentiu Mihai Ciupescu", "3"), ("Radu Tanasuica", "5,†")]
MDPI_AFFS = [("1", "Faculty of Veterinary Medicine, Cluj-Napoca, Romania"),
             ("2", "Faculty of Pharmacy, Iuliu Hatieganu University, Cluj-Napoca, Romania"),
             ("3", "Institute of Hygiene and Veterinary Public Health, Bucharest, Romania"),
             ("4", "National Institute for Isotopic and Molecular Technologies, Cluj-Napoca, Romania"),
             ("5", "Faculty of Veterinary Medicine, <i>University</i> of Agronomic Sciences, Bucharest, Romania"),
             ("*", "Author to whom correspondence should be addressed."),
             ("†", "These authors contributed equally to this work.")]


def test_mdpi_new_template_reads_the_full_payload():
    soup = BeautifulSoup(_mdpi_page(MDPI_AUTHORS, MDPI_AFFS), "lxml")
    parser = MDPI(soup)
    assert parser.authors_found() and parser.is_publisher_specific_parser()
    authors = parser.parse()["authors"]
    assert [a.name for a in authors] == [n for n, _ in MDPI_AUTHORS]
    assert [a.is_corresponding for a in authors] == [False, True, False, False]
    # affiliation 5 is only in the payload (the HTML shows four behind "Show more"); notes are not affiliations
    assert authors[3].affiliations == ["Faculty of Veterinary Medicine, University of Agronomic Sciences, Bucharest, Romania"]
    assert authors[1].affiliations == ["Faculty of Pharmacy, Iuliu Hatieganu University, Cluj-Napoca, Romania"]


def test_mdpi_new_template_falls_back_to_the_visible_byline():
    soup = BeautifulSoup(_mdpi_page(MDPI_AUTHORS, MDPI_AFFS, payload=False), "lxml")
    authors = MDPI(soup).parse()["authors"]
    assert [a.is_corresponding for a in authors] == [False, True, False, False]
    assert authors[0].affiliations == ["Faculty of Veterinary Medicine, Cluj-Napoca, Romania"]
    assert authors[3].affiliations == []  # affiliation 5 isn't in the visible list


def test_mdpi_new_template_sole_author_is_corresponding():
    soup = BeautifulSoup(_mdpi_page([("Mulugeta Wayu", "1")], [("1", "Kotebe University, Addis Ababa, Ethiopia")]),
                         "lxml")
    authors = MDPI(soup).parse()["authors"]
    assert authors[0].is_corresponding is True
    assert authors[0].affiliations == ["Kotebe University, Addis Ababa, Ethiopia"]


def test_mdpi_new_template_through_parse_page():
    out = parse_page(_mdpi_page(MDPI_AUTHORS, MDPI_AFFS).encode(), "doi", "https://www.mdpi.com/2079-6382/14/5/482")
    assert _corresponding(out) == ["Liora Mihaela Colobatiu"]
    assert all(a["affiliations"] for a in out["authors"])


# Frontiers ArticleDetailsV4

def _frontiers_person(name, sups, last=False):
    cls = "last-people" if last else "PeopleList__li"
    sup_html = "".join(f"<sup>{s}</sup>" for s in sups)
    return (f'<li class="{cls}"><a class="PeopleListItem" href="https://loop.frontiersin.org/people/1">'
            f'<div class="Avatar"><span class="notranslate">X</span></div>'
            f'<p class="PeopleListItem__name notranslate">{name} {sup_html}<!----></p></a></li>')


FRONTIERS_V4 = f"""<html><head>
<meta property="og:url" content="https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2024.1228846/full">
<meta name="citation_author" content="Schiemer, Robin "><meta name="citation_author_institution" content="Institute of Process Engineering in Life Sciences, Germany">
<meta name="citation_author" content="Rüdt, Matthias "><meta name="citation_author_institution" content="Institute of Life Technologies, Switzerland">
<meta name="citation_author" content="Hubbuch, Jürgen "><meta name="citation_author_institution" content="Institute of Process Engineering in Life Sciences, Germany">
</head><body>
<h1 class="ArticleDetailsV4__main__title">Generative data augmentation</h1>
<div class="PeopleList"><ul class="PeopleList__list PeopleList__list--hidden PeopleList__list--0">
{_frontiers_person("Robin Schiemer", ["1"])}{_frontiers_person("Matthias Rüdt", ["2"])}
{_frontiers_person("Jürgen Hubbuch", ["1", "*"], last=True)}
<li class="PeopleList__spacer" aria-hidden="true"></li></ul>
<div class="AffiliationList"><ul class="AffiliationList__list">
<li class="AffiliationList__item"><p class="AffiliationList__name notranslate"><span>1.</span> Institute of Process Engineering in Life Sciences, Section IV: Biomolecular Separation Engineering, Karlsruhe Institute of Technology (KIT), Karlsruhe, Germany</p></li>
<li class="AffiliationList__item"><p class="AffiliationList__name notranslate"><span>2.</span> Institute of Life Technologies, HES-SO Valais-Wallis, Sion, Switzerland</p></li>
</ul></div></div>
<h2>Edited by</h2><div class="PeopleList"><ul class="PeopleList__list">{_frontiers_person("Editor Person", ["3"])}</ul></div>
<p class="notranslate correspondence">*Correspondence: Jürgen Hubbuch, <a href="mailto:j@kit.edu">j@kit.edu</a></p>
</body></html>"""


def test_frontiers_v4_byline():
    parser = Frontiers(BeautifulSoup(FRONTIERS_V4, "lxml"))
    assert parser.authors_found() and parser.is_publisher_specific_parser()
    authors = parser.parse()["authors"]
    assert [a.name for a in authors] == ["Robin Schiemer", "Matthias Rüdt", "Jürgen Hubbuch"]  # no editors
    assert [a.is_corresponding for a in authors] == [False, False, True]
    assert authors[2].affiliations == ["Institute of Process Engineering in Life Sciences, Section IV: Biomolecular "
                                       "Separation Engineering, Karlsruhe Institute of Technology (KIT), Karlsruhe, Germany"]
    assert authors[1].affiliations == ["Institute of Life Technologies, HES-SO Valais-Wallis, Sion, Switzerland"]


def test_frontiers_v4_wins_over_meta_tags_in_parse_page():
    out = parse_page(FRONTIERS_V4.encode(), "doi", None)
    assert _corresponding(out) == ["Jürgen Hubbuch"]
    assert out["authors"][0]["affiliations"][0]["name"].endswith("Karlsruhe, Germany")


def test_frontiers_v4_reading_leaves_the_page_untouched():
    soup = BeautifulSoup(FRONTIERS_V4, "lxml")
    before = str(soup)
    Frontiers(soup).parse()
    assert str(soup) == before  # every parser shares one soup


# helpers

def test_same_person():
    assert same_person("Qu, Junle", "Junle Qu")
    assert same_person("Hubbuch, Jürgen ", "Jürgen Hubbuch")
    assert same_person("Yan-Yan Song", "Song, Yan Yan")
    assert same_person("Jurgen Hubbuch", "Jürgen Hubbuch")
    assert same_person("Mary O’Brien", "O'Brien, Mary")
    assert not same_person("Yu Chen", "Yu Cheng")
    assert not same_person("", "Yu Chen")


def test_nuxt_payload_lazy_reads_and_sentinels():
    arr = [["ShallowReactive", 1], {"data": 2, "missing": -1}, ["Ref", 3], {"x": 4}, [5, 6], "a", "b"]
    p = NuxtPayload(arr)
    assert p.node(0) == {"data": 2, "missing": -1}
    assert p.node(p.node(0)["data"]) == {"x": 4}
    assert p.node(4) == [5, 6] and p.dicts(4) == []
    assert NuxtPayload([[1], {"name": 2}, "Ann"]).dicts(0) == [{"name": 2}]
    assert p.node(-1) is None and p.node(99) is None
    assert NuxtPayload.from_soup(BeautifulSoup("<html><body></body></html>", "lxml")) is None
