"""
Who has which affiliation, where the page links an author to one outside the usual place (oxjob #2239, phase 2,
class affiliations-r3). Both cases were right in production and turned wrong with round 2's affiliation fix.

Springer Link: on older articles an author can be tied to an address only by an author note ("Present address: ...",
the byline marker points at it) while the "Authors and Affiliations" list names the co-authors alone. Round 2 stopped
giving an author the list does not name the co-authors' affiliation; that author then had none, though the page gives
one. They now get the address of the note that names them.

ScienceDirect: the page state can split a byline into several author groups and put an affiliation in another group
than the author whose marker points at it. The reader of that state looked a marker up in the author's own group only,
so the author lost the affiliation, or took the ones stored in their group.

Fragments mirror the dev pages; no network.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.sciencedirect import ScienceDirect
from parseland_lib.publisher.parsers.springer import Springer


# ---------------------------------------------------------------- Springer Link

def springer_page(byline, affiliations, notes=(), metas=()):
    """A Springer Link article page: the byline, the author notes (`notes`: (names, note <p> markup) pairs) and the
    "Authors and Affiliations" list (`affiliations`: (address, names) pairs)."""
    names = "".join(f'<li class="c-article-author-list__item"><a data-test="author-name">{n}</a></li>' for n in byline)
    note_items = "".join(
        f'<li class="c-article-author-information__item" id="nAff{i}">'
        f'<p class="c-article-author-information__authors-list">{who}</p>{note}</li>'
        for i, (who, note) in enumerate(notes, 1))
    affs = "".join(
        f'<li id="Aff{i}"><p class="c-article-author-affiliation__address">{address}</p>'
        f'<p class="c-article-author-affiliation__authors-list">{who}</p></li>'
        for i, (address, who) in enumerate(affiliations, 1))
    head = "".join(f'<meta name="{name}" content="{content}">' for name, content in metas)
    return (f'<html><head><link rel="canonical" href="https://link.springer.com/article/10.1007/BF00000000">{head}'
            f'</head><body><ul class="c-article-author-list c-article-author-list--short">{names}</ul>'
            f'<div id="author-information-content"><ol class="c-article-author-information__list">{note_items}</ol>'
            f'<ol class="c-article-author-affiliation__list">{affs}</ol></div></body></html>')


def present_address(address):
    return f'<p class="js-present-address">Present address: {address}</p>'


def springer_affiliations(html):
    return [(a["name"], a["affiliations"]) for a in Springer(BeautifulSoup(html, "lxml")).parse()["authors"]]


GOSH = "Hospital for Sick Children and Institute for Child Health, Great Ormond Street, WC1, London, UK"
BONN = "Botanisches Institut der Universität Bonn, Bundesrepublik Deutschland"
MADRID = "Centro de Investigaciones Biologicas, Instituto de Biologia Celular, Velazquez 144, Madrid-6, Spanien"


def test_author_tied_to_a_present_address_note_only_gets_that_address():
    # BF02018622: the list names Dhillon and Peters; Gordon's marker points at the note. He came out with nothing
    html = springer_page(["I. Gordon", "H. K. Dhillon", "A. M. Peters"],
                         [(GOSH, "H. K. Dhillon &amp; A. M. Peters")],
                         notes=[("I. Gordon", present_address(GOSH))])
    assert springer_affiliations(html) == [("I. Gordon", [GOSH]), ("H. K. Dhillon", [GOSH]), ("A. M. Peters", [GOSH])]


def test_one_note_for_two_authors_gives_both_the_address():
    # BF01279138: Schröter and Sievers share one note; the list names Rodriguez-Garcia alone
    html = springer_page(
        ["Klaus Schröter", "Maria Isabel Rodriguez-Garcia", "Andreas Sievers"],
        [(BONN, "Maria Isabel Rodriguez-Garcia")],
        notes=[("Maria Isabel Rodriguez-Garcia", present_address(MADRID)),
               ("Klaus Schröter &amp; Andreas Sievers", present_address(BONN))])
    assert springer_affiliations(html) == [
        ("Klaus Schröter", [BONN]), ("Maria Isabel Rodriguez-Garcia", [BONN]), ("Andreas Sievers", [BONN])]


def test_note_address_is_the_authors_own_not_the_co_authors():
    # the address comes from the note, not from the list: here they differ
    html = springer_page(["H. E. Musil", "M. Eide"], [("Universitätsklinik für Chirurgie, A-8036, Graz", "M. Eide")],
                         notes=[("H. E. Musil", present_address("Landeskrankenhaus, A-8700, Leoben"))])
    assert springer_affiliations(html) == [
        ("H. E. Musil", ["Landeskrankenhaus, A-8700, Leoben"]),
        ("M. Eide", ["Universitätsklinik für Chirurgie, A-8036, Graz"])]


def test_note_address_without_an_institution_loses_the_leading_comma():
    # BF02166383's note reads "Present address: , Felix-Dahn-Straße 62 B, 7, Stuttgart 70"
    html = springer_page(["Hermann Hoffmeister", "M. Eide"], [("Universitätsklinik, Graz", "M. Eide")],
                         notes=[("Hermann Hoffmeister", present_address(", Felix-Dahn-Straße 62 B, 7, Stuttgart 70"))])
    assert springer_affiliations(html)[0] == ("Hermann Hoffmeister", ["Felix-Dahn-Straße 62 B, 7, Stuttgart 70"])


def test_whole_page_keeps_the_note_address_through_parse_page():
    # as the service calls it: the citation_author tags name the same three people
    metas = [("citation_author", "Gordon, I."), ("citation_author_institution", "Hospital for Sick Children, London, UK"),
             ("citation_author", "Dhillon, H. K."), ("citation_author_institution", "Hospital for Sick Children, London, UK"),
             ("citation_author", "Peters, A. M."), ("citation_author_institution", "Hospital for Sick Children, London, UK")]
    html = springer_page(["I. Gordon", "H. K. Dhillon", "A. M. Peters"],
                         [(GOSH, "H. K. Dhillon &amp; A. M. Peters")],
                         notes=[("I. Gordon", present_address(GOSH))], metas=metas)
    out = parse_page(html.encode(), "doi", "https://link.springer.com/article/10.1007/BF00000000")
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]] == [
        ("I. Gordon", [GOSH]), ("H. K. Dhillon", [GOSH]), ("A. M. Peters", [GOSH])]


# look-alikes that must not change

def test_author_with_no_note_and_not_in_the_list_still_gets_none():
    # BF02109507 (round 2): the page gives Sakanoue no address anywhere
    kanazawa = "Radiochemical Laboratory, Faculty of Science, Kanazawa University, 920, Kanazawa, Japan"
    html = springer_page(["Toshio Imai", "Masanobu Sakanoue"], [(kanazawa, "Toshio Imai")])
    assert springer_affiliations(html) == [("Toshio Imai", [kanazawa]), ("Masanobu Sakanoue", [])]


def test_someone_elses_present_address_is_not_handed_round():
    # the note names Imai (who is in the list); Sakanoue, in neither, gets nothing
    kanazawa = "Radiochemical Laboratory, Faculty of Science, Kanazawa University, 920, Kanazawa, Japan"
    html = springer_page(["Toshio Imai", "Masanobu Sakanoue"], [(kanazawa, "Toshio Imai")],
                         notes=[("Toshio Imai", present_address("Institute of Physical Research, Wako, Japan"))])
    assert springer_affiliations(html) == [("Toshio Imai", [kanazawa]), ("Masanobu Sakanoue", [])]


def test_author_the_list_names_keeps_the_listed_affiliation_only():
    # BF01279138, 978-1-60327-259-9_62: an author with a listed affiliation and a present address keeps what the
    # list gives; the gold adds the present address on some such pages and not on others
    weizmann = "Department of Chemical Immunology, Weizmann Institute of Science, Rehovot, Israel"
    html = springer_page(["Dan S. Tawfik", "Ana Souza"], [(weizmann, "Dan S. Tawfik")],
                         notes=[("Dan S. Tawfik", present_address("Centre for Protein Engineering, Cambridge, UK")),
                                ("Ana Souza", present_address("Institute B, Porto, Portugal"))])
    assert springer_affiliations(html) == [("Dan S. Tawfik", [weizmann]), ("Ana Souza", ["Institute B, Porto, Portugal"])]


def test_a_note_that_is_not_an_address_gives_no_affiliation():
    # "contributed equally" notes use the same list and name authors the same way
    kanazawa = "Radiochemical Laboratory, Faculty of Science, Kanazawa University, 920, Kanazawa, Japan"
    html = springer_page(["Toshio Imai", "Masanobu Sakanoue"], [(kanazawa, "Toshio Imai")],
                         notes=[("Toshio Imai &amp; Masanobu Sakanoue", "<p>These authors contributed equally.</p>")])
    assert springer_affiliations(html) == [("Toshio Imai", [kanazawa]), ("Masanobu Sakanoue", [])]


# ---------------------------------------------------------------- ScienceDirect

def _author(given, surname, *refids):
    return {"#name": "author", "$$": [{"#name": "given-name", "_": given}, {"#name": "surname", "_": surname}] + [
        {"#name": "cross-ref", "$": {"refid": r}, "$$": [{"#name": "sup", "_": r[-1]}]} for r in refids]}


def _affiliation(aff_id, text, label=None):
    return {"#name": "affiliation", "$": {"id": aff_id},
            "$$": ([{"#name": "label", "_": label}] if label else []) + [{"#name": "textfn", "_": text}]}


def _state(groups):
    """The page state: `groups` is a list of author groups, each a list of author / affiliation nodes."""
    flat = {node["$"]["id"]: {"$$": [c for c in node["$$"] if c["#name"] == "textfn"]}
            for group in groups for node in group if node["#name"] == "affiliation"}
    return {"authors": {"content": [{"#name": "author-group", "$$": group} for group in groups], "affiliations": flat}}


def sciencedirect_page(groups):
    """A ScienceDirect article page with the byline's affiliation list collapsed, and the page-state JSON."""
    buttons = "".join(
        f'<button class="button-link" data-xocs-content-type="author"><span class="button-link-text">'
        f'<span class="react-xocs-alternative-link"><span class="given-name">{node["$$"][0]["_"]}</span> '
        f'<span class="text surname">{node["$$"][1]["_"]}</span></span></span></button>'
        for group in groups for node in group if node["#name"] == "author")
    return (f'<html><head><link rel="canonical" href="https://www.sciencedirect.com/science/article/pii/S1">'
            f'</head><body><div class="author-group" id="author-group">{buttons}</div>'
            f'<script>window.__PRELOADED_STATE__ = {json.dumps(_state(groups))};</script></body></html>')


def parsed_affiliations(html):
    """{name: [affiliation, ...]} as parse_page returns it (the parser that wins the page)."""
    out = parse_page(html.encode(), "doi", "https://www.sciencedirect.com/science/article/pii/S1")
    return {a["name"]: [x["name"] for x in a["affiliations"]] for a in out["authors"]}


def state_affiliations(groups):
    return {a["name"]: a["affiliations"] for a in ScienceDirect.page_state_authors(_state(groups))}


PADOVA = "Dipartimento di Fisica dell'Università, Padova, Italy"
INFN_PD = "Istituto Nazionale di Fisica Nucleare, Sezione di Padova, Italy"
ISAS = "International School for Advanced Studies (ISAS), Trieste, Italy"
TRIESTE = "Istituto di Fisica Teorica dell'Università, Trieste, Italy"
INFN_TS = "Istituto Nazionale di Fisica Nucleare, Sezione di Trieste, Italy"

# 0550-3213(85)90091-4: three groups, one author each; the affiliations d, e, f of the second author sit in the
# third author's group, whose own markers a, b, c point back into the first
NUCL_PHYS_B = [
    [_author("F.", "Feruglio", "AFF1", "AFF2", "AFF3"),
     _affiliation("AFF1", PADOVA, "a"), _affiliation("AFF2", INFN_PD, "b"), _affiliation("AFF3", ISAS, "c")],
    [_author("J.A.", "Helayël-Neto", "AFF4", "AFF5", "AFF6", "AFF7"), _affiliation("AFF7", ISAS, "g")],
    [_author("F.", "Legovini", "AFF1", "AFF2", "AFF3"),
     _affiliation("AFF4", TRIESTE, "d"), _affiliation("AFF5", INFN_TS, "e"), _affiliation("AFF6", ISAS, "f")]]


def test_marker_to_an_affiliation_stored_in_another_author_group_is_followed():
    # Helayël-Neto came out with ISAS alone and Legovini with the Trieste institutes
    assert parsed_affiliations(sciencedirect_page(NUCL_PHYS_B)) == {
        "F. Feruglio": [PADOVA, INFN_PD, ISAS],
        "J.A. Helayël-Neto": [TRIESTE, INFN_TS, ISAS, ISAS],  # f and g are both ISAS on the page
        "F. Legovini": [PADOVA, INFN_PD, ISAS]}


def test_page_state_reader_follows_the_marker_across_groups():
    # the ScienceDirect parser's own reader (the pages it wins read the same state)
    assert state_affiliations(NUCL_PHYS_B) == {
        "F. Feruglio": [PADOVA, INFN_PD, ISAS],
        "J.A. Helayël-Neto": [TRIESTE, INFN_TS, ISAS, ISAS],
        "F. Legovini": [PADOVA, INFN_PD, ISAS]}


# look-alikes that must not change

def test_groups_without_markers_still_share_their_own_affiliations():
    limerick, siegen = "Interaction Design Centre, University of Limerick, Ireland", "University of Siegen, Germany"
    groups = [[_author("Gabriela", "Avram"), _affiliation("id4", limerick)],
              [_author("Volker", "Wulf"), _affiliation("id6", siegen)]]
    assert state_affiliations(groups) == {"Gabriela Avram": [limerick], "Volker Wulf": [siegen]}


def test_marker_that_points_at_no_affiliation_is_not_a_link():
    # a footnote marker (fn1) names no affiliation in any group: the group's one affiliation is shared as before
    siegen = "University of Siegen, Germany"
    groups = [[_author("Gabriela", "Avram"), _affiliation("id4", "University of Limerick, Ireland")],
              [_author("Volker", "Wulf", "fn1"), _author("Ana", "Souza"), _affiliation("id6", siegen)]]
    assert state_affiliations(groups)["Volker Wulf"] == [siegen]
    assert state_affiliations(groups)["Ana Souza"] == [siegen]


def test_unmarked_author_beside_one_who_points_elsewhere_keeps_the_groups_affiliation():
    # only the author whose marker points into another group changes; the unmarked co-author is read as before
    limerick, siegen = "University of Limerick, Ireland", "University of Siegen, Germany"
    groups = [[_author("Gabriela", "Avram", "id4"), _affiliation("id4", limerick, "a")],
              [_author("Volker", "Wulf", "id4"), _author("Ana", "Souza"), _affiliation("id6", siegen)]]
    assert state_affiliations(groups) == {"Gabriela Avram": [limerick], "Volker Wulf": [limerick], "Ana Souza": [siegen]}


def test_markers_inside_the_group_are_read_as_before():
    # an author with no marker, in a group whose other authors are marked, gets none (as before)
    limerick, siegen = "University of Limerick, Ireland", "University of Siegen, Germany"
    groups = [[_author("Gabriela", "Avram", "id4"), _author("Volker", "Wulf", "id6"), _author("Ana", "Souza"),
               _affiliation("id4", limerick, "a"), _affiliation("id6", siegen, "b")]]
    assert state_affiliations(groups) == {"Gabriela Avram": [limerick], "Volker Wulf": [siegen], "Ana Souza": []}


def test_correspondence_marker_is_still_a_mark_not_an_affiliation():
    limerick = "University of Limerick, Ireland"
    groups = [[_author("Gabriela", "Avram", "id4", "cor1"), _affiliation("id4", limerick, "a"),
               {"#name": "correspondence", "$": {"id": "cor1"}, "$$": [{"#name": "text", "_": "Corresponding author."}]}],
              [_author("Volker", "Wulf", "id4")]]
    authors = ScienceDirect.page_state_authors(_state(groups))
    assert [(a["name"], a["affiliations"], a["is_corresponding"]) for a in authors] == [
        ("Gabriela Avram", [limerick], True), ("Volker Wulf", [limerick], False)]
