"""
Who has which affiliation on ScienceDirect and Springer Link pages (oxjob #2239, phase 2, class affiliations-r2).

ScienceDirect: with the byline's affiliation list collapsed, the Elsevier BV parser took each author's affiliations
from the page-state JSON by the last word of the name, keyed by surname. "Rodrigo M. de Carvalho" (surname
"de Carvalho") matched nobody and got nothing; of two authors named Ahmed the first got the second's; an affiliation
whose text is nested (CO<inf>2</inf>) was not read, so the one affiliation left went to authors it isn't linked to.
The parser now takes them from the ScienceDirect parser's reader of the same JSON, by full name.

Springer Link: a chapter author who also edits the book was dropped as an editor and put back from the byline
without affiliations, or with a co-author's; and a byline author the affiliation block does not list got the
co-author's affiliation.

Fragments mirror the dev pages; no network.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV
from parseland_lib.publisher.parsers.springer import Springer


# ---------------------------------------------------------------- ScienceDirect

def _author(given, surname, *refids):
    return {"#name": "author", "$$": [{"#name": "given-name", "_": given}, {"#name": "surname", "_": surname}] + [
        {"#name": "cross-ref", "$": {"refid": r}, "$$": [{"#name": "sup", "_": r[-1]}]} for r in refids]}


def _affiliation(aff_id, text, label=None):
    textfn = text if isinstance(text, dict) else {"#name": "textfn", "_": text}
    return {"#name": "affiliation", "$": {"id": aff_id},
            "$$": ([{"#name": "label", "_": label}] if label else []) + [textfn]}


def _flat(groups):
    """The page state's second copy of the affiliations: one dict for the page, keyed by id."""
    return {node["$"]["id"]: {"$$": [c for c in node["$$"] if c["#name"] == "textfn"]}
            for group in groups for node in group if node["#name"] == "affiliation"}


def sciencedirect_page(groups, byline=None, banner="", script=None):
    """A ScienceDirect article page: the byline buttons (affiliation list collapsed unless `banner` gives one) and
    the page-state JSON. `groups` is a list of author groups, each a list of author / affiliation nodes."""
    state = {"authors": {"content": [{"#name": "author-group", "$$": group} for group in groups],
                         "affiliations": _flat(groups)}}
    if byline is None:
        byline = [(node["$$"][0]["_"], node["$$"][1]["_"]) for group in groups for node in group
                  if node["#name"] == "author"]
    buttons = "".join(
        f'<button class="button-link" data-xocs-content-type="author"><span class="button-link-text">'
        f'<span class="react-xocs-alternative-link"><span class="given-name">{given}</span> '
        f'<span class="text surname">{surname}</span></span></span></button>' for given, surname in byline)
    if script is None:
        script = f"<script>window.__PRELOADED_STATE__ = {json.dumps(state)};</script>"
    return (f'<html><head><link rel="canonical" href="https://www.sciencedirect.com/science/article/pii/S1">'
            f'</head><body><div class="author-group" id="author-group">{buttons}</div>{banner}{script}'
            f'</body></html>')


def parsed_affiliations(html):
    """{name: [affiliation, ...]} as parse_page returns it (the parser that wins the page)."""
    out = parse_page(html.encode(), "doi", "https://www.sciencedirect.com/science/article/pii/S1")
    return {a["name"]: [x["name"] for x in a["affiliations"]] for a in out["authors"]}


NRC_A = "Electrochemistry and Corrosion Lab, National Research Centre, Dokki, Giza 12622, Egypt"
NRC_B = "Material Engineering Lab, National Research Centre, Dokki, Giza 12622, Egypt"
NRC_C = "Photochemistry Department, National Research Centre, Dokki, Giza 12622, Egypt"


def test_surname_of_two_words_keeps_its_affiliations():
    # j.colsurfa.2023.133089: "Al Kiey" came out with no affiliation, his co-authors with theirs
    html = sciencedirect_page([[
        _author("Sherief A.", "Al Kiey", "aff0005", "aff0010"), _author("Ahmed A.", "El-Sayed", "aff0015"),
        _author("Ahmed M.", "Khalil", "aff0015"),
        _affiliation("aff0005", NRC_A, "a"), _affiliation("aff0010", NRC_B, "b"), _affiliation("aff0015", NRC_C, "c")]])
    assert parsed_affiliations(html) == {
        "Sherief A. Al Kiey": [NRC_A, NRC_B], "Ahmed A. El-Sayed": [NRC_C], "Ahmed M. Khalil": [NRC_C]}


def test_unlinked_single_affiliation_reaches_the_author_with_a_surname_prefix():
    # j.mineng.2024.108914: one group, one affiliation, no markers; "de Carvalho" got nothing
    ufrj = "Department of Metallurgical and Materials Engineering, Universidade Federal do Rio de Janeiro, Brazil"
    html = sciencedirect_page([[_author("Rodrigo M.", "de Carvalho"), _author("Luís Marcelo", "Tavares"),
                                _affiliation("af005", ufrj)]])
    assert parsed_affiliations(html) == {"Rodrigo M. de Carvalho": [ufrj], "Luís Marcelo Tavares": [ufrj]}


def test_two_authors_with_one_surname_each_keep_their_own():
    # j.molcel.2025.05.010: Syed Moiz Ahmed (2) got Zamal Ahmed's affiliation (1)
    mda, csi = "UT MD Anderson Cancer Center, Houston, TX 77030, USA", "The Cancer Science Institute of Singapore"
    html = sciencedirect_page([[
        _author("Michael A.", "Longo", "aff1"), _author("Syed Moiz", "Ahmed", "aff2"),
        _author("Zamal", "Ahmed", "aff1"), _affiliation("aff1", mda, "1"), _affiliation("aff2", csi, "2")]])
    assert parsed_affiliations(html) == {
        "Michael A. Longo": [mda], "Syed Moiz Ahmed": [csi], "Zamal Ahmed": [mda]}


def test_affiliation_with_nested_text_is_read_and_the_other_one_is_not_handed_round():
    # j.molliq.2024.125347: affiliation a holds CO<inf>2</inf>; Fu (a, b) and Wu (a) both came out with b alone
    imut = {"#name": "textfn", "$$": [
        {"#name": "__text__", "_": "Inner Mongolia Engineering Research Center for CO"},
        {"#name": "inf", "_": "2"},
        {"#name": "__text__", "_": " Capture and Utilization, Inner Mongolia University of Technology, Hohhot, China"}]}
    imut_text = ("Inner Mongolia Engineering Research Center for CO2 Capture and Utilization, Inner Mongolia University "
                 "of Technology, Hohhot, China")
    hebut = "School of Chemical Engineering and Technology, Hebei University of Technology, Tianjin, 300130, China"
    html = sciencedirect_page([[
        _author("Xupeng", "Fu", "af005", "af010"), _author("Yuting", "Wang", "af010"),
        _author("Zhaojun", "Wu", "af005"), _affiliation("af005", imut, "a"), _affiliation("af010", hebut, "b")]])
    assert parsed_affiliations(html) == {
        "Xupeng Fu": [imut_text, hebut], "Yuting Wang": [hebut], "Zhaojun Wu": [imut_text]}


def test_each_author_group_keeps_its_own_affiliation():
    # j.intcom.2011.07.002: two groups, each one author and one affiliation, no markers; the second affiliation's
    # text is nested, so the second author got the first group's
    limerick = "Interaction Design Centre, University of Limerick, Limerick, Ireland"
    siegen = {"#name": "textfn", "$$": [
        {"#name": "__text__", "_": "Information Systems and New Media, University of Siegen, H"},
        {"#name": "italic", "_": "-"}, {"#name": "__text__", "_": "B 8420, 57076 Siegen, Germany"}]}
    html = sciencedirect_page([[_author("Gabriela", "Avram"), _affiliation("id4", limerick)],
                               [_author("Volker", "Wulf"), _affiliation("id6", siegen)]])
    assert parsed_affiliations(html) == {
        "Gabriela Avram": [limerick],
        "Volker Wulf": ["Information Systems and New Media, University of Siegen, H-B 8420, 57076 Siegen, Germany"]}


def test_author_the_page_links_to_no_affiliation_does_not_get_a_namesakes():
    # G.M. Martin carries no marker; before, both Martins got the affiliation of whichever came last in the state
    monash = "Department of Econometrics, Monash University, Clayton, Victoria 3800, Australia"
    html = sciencedirect_page([[_author("G.C.", "Lim", "aff1"), _author("G.M.", "Martin"),
                                _author("V.L.", "Martin", "aff1"), _affiliation("aff1", monash, "a")]])
    assert parsed_affiliations(html) == {"G.C. Lim": [monash], "G.M. Martin": [], "V.L. Martin": [monash]}


def test_corresponding_marks_are_untouched():
    # the page-state fill changes affiliations only: the mark still comes from the cor* cross-ref as before
    html = sciencedirect_page([[
        _author("Sherief A.", "Al Kiey", "aff0005"), _author("Ahmed M.", "Khalil", "aff0015", "cor1"),
        _affiliation("aff0005", NRC_A, "a"), _affiliation("aff0015", NRC_C, "c")]])
    out = parse_page(html.encode(), "doi", "https://www.sciencedirect.com/science/article/pii/S1")
    assert [(a["name"], a["is_corresponding"]) for a in out["authors"]] == [
        ("Sherief A. Al Kiey", False), ("Ahmed M. Khalil", True)]


# look-alikes that must not change

def test_affiliations_printed_in_the_open_banner_are_kept():
    # an expanded byline prints who has which; the page state is not consulted for those authors
    banner = ('<dl class="affiliation"><dt><sup>a</sup></dt><dd>Printed affiliation A</dd></dl>'
              '<dl class="affiliation"><dt><sup>b</sup></dt><dd>Printed affiliation B</dd></dl>')
    html = sciencedirect_page([[_author("Ana", "De Souza", "aff1"), _author("Bo", "Li", "aff2"),
                                _affiliation("aff1", "State affiliation A", "a"),
                                _affiliation("aff2", "State affiliation B", "b")]], banner=banner)
    html = html.replace('<span class="text surname">De Souza</span>',
                        '<span class="text surname">De Souza</span><span class="author-ref"><sup>a</sup></span>')
    html = html.replace('<span class="text surname">Li</span>',
                        '<span class="text surname">Li</span><span class="author-ref"><sup>b</sup></span>')
    assert parsed_affiliations(html) == {"Ana De Souza": ["Printed affiliation A"], "Bo Li": ["Printed affiliation B"]}


def test_page_where_elsevier_bv_finds_no_affiliation_still_goes_to_the_sciencedirect_parser():
    # A lone author whose surname has two words: the Elsevier BV parser found no affiliation before and must find
    # none now, so the page is still returned from the ScienceDirect parser (authors, abstract and marks alike).
    html = sciencedirect_page([[_author("Yves", "De Smet"), _affiliation("aff1", "Université libre de Bruxelles")]])
    own = ElsevierBV(BeautifulSoup(html, "lxml")).parse()["authors"]
    assert [(a.name, a.affiliations) for a in own] == [("Yves De Smet", [])]
    assert parsed_affiliations(html) == {"Yves De Smet": ["Université libre de Bruxelles"]}


def test_byline_author_the_page_state_does_not_name_is_left_as_before():
    # the state lists the first authors only on long bylines: an author it doesn't name gets nothing from it
    html = sciencedirect_page(
        [[_author("Ana", "De Souza", "aff1"), _author("Bo", "Li", "aff1"), _affiliation("aff1", "Institute A", "a"),
          _affiliation("aff2", "Institute B", "b")]],
        byline=[("Ana", "De Souza"), ("Bo", "Li"), ("Carla", "Du Pont")])
    assert parsed_affiliations(html) == {"Ana De Souza": ["Institute A"], "Bo Li": ["Institute A"], "Carla Du Pont": []}


def test_page_is_never_left_with_no_affiliation_at_all():
    # The byline shows one of the state's two Martins, the one the state links to nothing. Taking the state's word
    # would leave the page without any affiliation and hand it to another parser, so the earlier fill stands.
    html = sciencedirect_page(
        [[_author("G.M.", "Martin"), _author("V.L.", "Martin", "aff1"), _affiliation("aff1", "Monash University", "a")]],
        byline=[("G.M.", "Martin")])
    own = ElsevierBV(BeautifulSoup(html, "lxml")).parse()["authors"]
    assert [(a.name, a.affiliations) for a in own] == [("G.M. Martin", ["Monash University"])]


def test_application_json_state_still_fills_no_affiliation_in_elsevier_bv():
    # only the __PRELOADED_STATE__ form is read by the Elsevier BV parser (as before); the other form's pages are
    # the ScienceDirect parser's
    groups = [[_author("Ana", "De Souza", "aff1"), _author("Bo", "Li", "aff1"), _affiliation("aff1", "Institute A", "a")]]
    state = {"authors": {"content": [{"#name": "author-group", "$$": g} for g in groups], "affiliations": _flat(groups)}}
    html = sciencedirect_page(groups, script=f'<script type="application/json">{json.dumps(state)}</script>')
    own = ElsevierBV(BeautifulSoup(html, "lxml")).parse()["authors"]
    assert [a.affiliations for a in own] == [[], []]


# ---------------------------------------------------------------- Springer Link

def springer_page(byline, affiliations, editors=(), kind="chapter"):
    """A Springer Link page: the byline, the "Authors and Affiliations" block (address, names) and, on a chapter,
    the book's "Editors and Affiliations" block."""
    names = "".join(f'<li class="c-article-author-list__item"><a data-test="author-name">{n}</a></li>' for n in byline)
    affs = "".join(
        f'<li id="Aff{i}"><p class="c-article-author-affiliation__address">{address}</p>'
        f'<p class="c-article-author-affiliation__authors-list">{who}</p></li>'
        for i, (address, who) in enumerate(affiliations, 1))
    eds = ""
    if editors:
        eds = ('<section data-title="Editor information"><div id="editor-information-section">'
               '<h3>Editors and Affiliations</h3><ol class="c-article-author-affiliation__list">' + "".join(
                   f'<li id="Aff{i}"><p class="c-article-author-affiliation__address">{address}</p>'
                   f'<p class="c-article-author-affiliation__authors-list">{who}</p></li>'
                   for i, (address, who) in enumerate(editors, 7)) + '</ol></div></section>')
    return (f'<html><head><link rel="canonical" href="https://link.springer.com/{kind}/10.1007/example"></head><body>'
            f'<ul class="c-article-author-list c-article-author-list--short">{names}</ul>'
            f'<ol class="c-article-author-affiliation__list">{affs}</ol>{eds}</body></html>')


def springer_affiliations(html):
    return [(a["name"], a["affiliations"]) for a in Springer(BeautifulSoup(html, "lxml")).parse()["authors"]]


def test_chapter_author_who_also_edits_the_book_keeps_own_affiliations():
    # 978-3-031-67099-2_7: Debbie Jones and Mark Jones (the volume's editors, and this chapter's authors) came out
    # with Planter's affiliation
    html = springer_page(
        ["Clayton Planter", "Debbie Jones", "Mark Jones"],
        [("Street2Boardroom, Bristol, UK", "Clayton Planter"),
         ("Department of Criminology, Swansea University, Swansea, UK", "Debbie Jones"),
         ("Higher Plain Research & Education, Swansea, UK", "Mark Jones"),
         ("Centre for Criminology, University South Wales, Newport, UK", "Mark Jones")],
        editors=[("Higher Plain, Swansea, UK", "Mark Jones"), ("Criminology, Swansea University, Swansea, UK", "Debbie Jones")])
    assert springer_affiliations(html) == [
        ("Clayton Planter", ["Street2Boardroom, Bristol, UK"]),
        ("Debbie Jones", ["Department of Criminology, Swansea University, Swansea, UK"]),
        ("Mark Jones", ["Higher Plain Research & Education, Swansea, UK",
                        "Centre for Criminology, University South Wales, Newport, UK"])]


def test_editor_author_keeps_own_affiliation_among_several():
    # 978-3-658-44037-4_53: with two affiliations on the page the editor-author (Maier) came out with none
    fau, siemens = "Friedrich-Alexander-Universität Erlangen-Nürnberg, Erlangen, Deutschland", "Siemens Healthineers AG, Forchheim, Deutschland"
    html = springer_page(
        ["Maryam Parvin", "Andreas Maier", "Holger Kunze"],
        [(fau, "Maryam Parvin &amp; Andreas Maier"), (siemens, "Holger Kunze")],
        editors=[("Lehrstuhl für Mustererkennung, Erlangen, Deutschland", "Andreas Maier")])
    assert springer_affiliations(html) == [
        ("Maryam Parvin", [fau]), ("Andreas Maier", [fau]), ("Holger Kunze", [siemens])]


def test_byline_author_the_affiliation_block_does_not_list_gets_none():
    # BF02109507: the block ties the one affiliation to Imai; Sakanoue came out with it too
    kanazawa = "Radiochemical Laboratory, Faculty of Science, Kanazawa University, 920, Kanazawa, Japan"
    html = springer_page(["Toshio Imai", "Masanobu Sakanoue"], [(kanazawa, "Toshio Imai")], kind="article")
    assert springer_affiliations(html) == [("Toshio Imai", [kanazawa]), ("Masanobu Sakanoue", [])]


# look-alikes that must not change

def test_book_editor_who_is_not_in_the_byline_stays_out():
    html = springer_page(
        ["Clayton Planter"],
        [("Street2Boardroom, Bristol, UK", "Clayton Planter"), ("Higher Plain, Swansea, UK", "Mark Jones")],
        editors=[("Higher Plain, Swansea, UK", "Mark Jones")])
    assert springer_affiliations(html) == [("Clayton Planter", ["Street2Boardroom, Bristol, UK"])]


def test_authors_the_block_lists_keep_what_it_gives_them():
    html = springer_page(
        ["Ana Souza", "Bo Li"], [("Institute A, Lisbon, Portugal", "Ana Souza &amp; Bo Li"),
                                 ("Institute B, Porto, Portugal", "Bo Li")], kind="article")
    assert springer_affiliations(html) == [
        ("Ana Souza", ["Institute A, Lisbon, Portugal"]),
        ("Bo Li", ["Institute A, Lisbon, Portugal", "Institute B, Porto, Portugal"])]
