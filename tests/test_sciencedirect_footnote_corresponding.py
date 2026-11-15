"""
ScienceDirect corresponding authors marked by a footnote the parsers did not reach (oxjob #2246).

Shape: utils.cross_ref_footnotes (footnote nested in the author's cross-ref, DOIs 10.1006 and 10.1054). Neither
the ScienceDirect nor the Elsevier BV parser read its "To whom correspondence should be addressed" note. One older book
chapter also gave a sibling footnote's note text nested with a mailto link. Fragments mirror stored state; no network.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV
from parseland_lib.publisher.parsers.sciencedirect import ScienceDirect

URL = "https://www.sciencedirect.com/science/article/abs/pii/S0012160699995875"


def author(given, surname, *cross_refs):
    return {"#name": "author", "$": {"id": f"aep-{surname}"},
            "$$": [{"#name": "given-name", "_": given}, {"#name": "surname", "_": surname}, *cross_refs]}


def nested_footnote(fn_id, label, text):
    return {"#name": "cross-ref", "$": {"refid": fn_id}, "$$": [
        {"#name": "sup", "$": {"loc": "post"}, "_": label},
        {"#name": "footnote", "$": {"id": fn_id}, "$$": [{"#name": "label", "_": label}, {"#name": "note-para", "_": text}]}]}


def aff_ref(aff_id):
    return {"#name": "cross-ref", "$": {"refid": aff_id}, "$$": [{"#name": "sup", "$": {"loc": "post"}, "_": aff_id[-1]}]}


def affiliation(aff_id, text):
    return {"#name": "affiliation", "$": {"id": aff_id}, "$$": [{"#name": "textfn", "_": text}]}


def html(groups):
    state = {"authors": {"content": [{"#name": "author-group", "$$": g} for g in groups]}}
    return (f'<html><head><link rel="canonical" href="{URL}"><meta name="citation_publisher" content="Academic Press"/>'
            f'<meta name="citation_title" content="Limb bud cells"/></head>'
            f'<body><div class="author-group" id="author-group"></div>'
            f'<script>window.__PRELOADED_STATE__ = {json.dumps(state)};</script></body></html>')


def sd_corr(groups):
    out = ScienceDirect(BeautifulSoup(html(groups), "lxml")).parse()
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


def page_corr(groups):
    return [a["name"] for a in parse_page(html(groups).encode(), "doi", URL)["authors"] if a["is_corresponding"]]


TAMURA = [
    author("Hitoshi", "Yokoyama", aff_ref("A1")),
    author("Sayuri", "Yonei-Tamura", aff_ref("A2"), nested_footnote("FN1", "1", "Present address: Tohoku University, Sendai, Japan.")),
    author("Koji", "Tamura", aff_ref("A2"), nested_footnote("FN3", "3", "To whom correspondence should be addressed. Fax: +81-22-217-3489.")),
    affiliation("A1", "Department of Biology, Tohoku University, Sendai, Japan"),
    affiliation("A2", "The Salk Institute for Biological Studies, La Jolla, California"),
]


def test_nested_correspondence_footnote_marks_its_author():
    assert sd_corr([TAMURA]) == ["Koji Tamura"]


def test_nested_correspondence_footnote_through_parse_page():
    assert page_corr([TAMURA]) == ["Koji Tamura"]


def test_correspondence_to_note_with_shared_affiliation():
    # Churchill Livingstone (10.1054): one unlabelled affiliation for every author, note on the last author only.
    group = [author("J.", "Weirich"), author("L.", "Seiler"),
             author("G.", "Fleckenstein-Grün", nested_footnote("FNUN", "f1", "Correspondence to: Prof. Dr. med. G. Fleckenstein-Grün, Freiburg, Germany.")),
             affiliation("aep-affiliation-id5", "Physiologisches Institut, Universität Freiburg, Germany")]
    assert sd_corr([group]) == ["G. Fleckenstein-Grün"]
    assert page_corr([group]) == ["G. Fleckenstein-Grün"]


def test_correspondence_and_present_address_note_marks_its_author():
    group = [author("Yolanda M.", "van Heezik", nested_footnote("FN1", "f1", "Correspondence and present address: Y. M. van Heezik, Taif, Saudi Arabia.")),
             author("Philip J.", "Seddon", nested_footnote("FN2", "f2", "P. J. Seddon is at the Percy FitzPatrick Institute, Cape Town.")),
             affiliation("aep-affiliation-id3", "Percy FitzPatrick Institute of African Ornithology, University of Cape Town")]
    assert page_corr([group]) == ["Yolanda M. van Heezik"]


def test_nested_footnote_without_correspondence_marks_no_one():
    group = [author("Hitoshi", "Yokoyama", aff_ref("A1"), nested_footnote("FN1", "1", "Present address: Hiroshima, Japan.")),
             author("Hiroyuki", "Ide", aff_ref("A1")),
             affiliation("A1", "Department of Biology, Tohoku University, Sendai, Japan")]
    assert sd_corr([group]) == []
    assert page_corr([group]) == []


def test_sibling_footnote_with_nested_note_text_marks_its_author():
    # Older book chapter: the footnote sits beside the authors, but its note text is nested with a mailto link.
    group = [author("J.", "Bernsdorf"),
             author("G.", "Brenner", {"#name": "cross-ref", "$": {"refid": "fn1"}, "$$": [{"#name": "sup", "_": "*"}]}),
             {"#name": "footnote", "$": {"id": "fn1"}, "$$": [{"#name": "label", "_": "*"}, {"#name": "note-para", "$$": [
                 {"#name": "__text__", "_": "corresponding author ("},
                 {"#name": "inter-ref", "$": {"href": "mailto:brenner@example.de"}, "_": "brenner@example.de"},
                 {"#name": "__text__", "_": ")"}]}]}]
    assert sd_corr([group]) == ["G. Brenner"]


def test_sibling_footnote_with_plain_note_text_still_marks_its_author():
    group = [author("A.", "One", {"#name": "cross-ref", "$": {"refid": "fn1"}, "$$": [{"#name": "sup", "_": "*"}]}),
             author("B.", "Two"),
             {"#name": "footnote", "$": {"id": "fn1"}, "$$": [{"#name": "label", "_": "*"},
                                                             {"#name": "note-para", "_": "Corresponding author. Tel.: +1 555 0100."}]}]
    assert sd_corr([group]) == ["A. One"]


def test_elsevier_bv_reads_nested_correspondence_footnote_as_a_cor_ref():
    assert ElsevierBV._json_author_entry_has_cor_ref(TAMURA[2]) is True
    assert ElsevierBV._json_author_entry_has_cor_ref(TAMURA[1]) is False
    assert ElsevierBV._json_author_entry_has_cor_ref(TAMURA[0]) is False


def test_shared_surname_marks_only_the_footnoted_author():
    # ElsevierBV matched JSON marks by surname too, so a same-surname coauthor was flagged as well (jmla.2001.2825).
    group = [author("Jenn-Yeu", "Chen", aff_ref("A1"), nested_footnote("FNUN2", "f2", "Address correspondence to Jenn-Yeu Chen.")),
             author("Train-Min", "Chen", aff_ref("A1")),
             author("Gary S", "Dell", aff_ref("A2")),
             affiliation("A1", "National Cheng Kung University, Tainan, Taiwan"),
             affiliation("A2", "University of Illinois at Urbana-Champaign")]
    mapping = ElsevierBV(BeautifulSoup(html([group]), "lxml"))._author_json_corresponding_map()
    assert mapping == {"Jenn-Yeu Chen": True}
    assert sd_corr([group]) == ["Jenn-Yeu Chen"]
