"""Morressier poster pages (oxjob #2338): the byline and abstract sit in the page's __NEXT_DATA__ JSON.

Markup cut down from stored morressier.com pages (17 Nov 2026). Two app versions: the current one keeps the poster in
props.pageProps.data.document, the older one in props.initialState.posters with authors as user ids. About half the
stored pages have "document": null (only the conference header shows): nothing is read there.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.morressier import Morressier

URL = "https://doi.org/10.26226/morressier.5f0c7d3058e581e69b05cf91"
HEAD = ('<meta name="twitter:card" content="summary_large_image"/><meta name="twitter:site" content="@Morressier"/>'
        '<meta name="twitter:creator" content="@Morressier"/>')
ABSTRACT = ("This study uses a unique dataset from listed German companies that helps identify a granular measure of "
            "board-level codetermination to examine whether board-level employee representation affects tax "
            "aggressiveness and audit committee decisions.")


def _page(next_data, head=HEAD):
    return (f'<html><head>{head}<title></title></head><body><div id="__next"><div class="event-header">'
            f'AAA 2020 Annual Meeting</div></div><script id="__NEXT_DATA__" type="application/json">'
            f'{json.dumps(next_data)}</script></body></html>')


def _current(document):
    return {"props": {"pageProps": {"data": {"article_id": "5f0c7d3058e581e69b05cf91",
                                             "event": {"name": "AAA 2020 Annual Meeting"}, "document": document},
                                    "metaTags": {"title": "", "description": ""}}},
            "page": "/event/[eventId]/article/[article_id]"}


def _user(uid, name=None, org=None, dept=None):
    u = {"_id": uid, "email": f"{uid}@example.org", "is_activated": bool(name)}
    if name is not None:
        u.update(full_name=name, organization=org, department=dept)
    return u


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_byline_affiliation_and_abstract_from_the_json():
    doc = {"title": "Codetermination", "paper_abstract": ABSTRACT,
           "authors": [_user("a1", "Miles A Romney", "Florida State University", "College of Business")],
           "_co_authors": ["Jane Q. Smith", "Lee, K."]}
    out = _parse(_page(_current(doc)))
    assert [a["name"] for a in out["authors"]] == ["Miles A Romney", "Jane Q. Smith", "Lee, K."]
    assert out["authors"][0]["affiliations"] == [{"name": "College of Business, Florida State University"}]
    assert out["authors"][1]["affiliations"] == []
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert out["abstract"] == ABSTRACT


def test_empty_document_is_not_read():
    out = _parse(_page(_current(None)))
    assert out["authors"] == []
    assert not out["abstract"]


def test_invited_authors_without_a_name_and_repeats_are_skipped():
    doc = {"title": "Nasal cannulae", "paper_abstract": ABSTRACT,
           "authors": [_user("a1", "Andrzej Piotrowski", "Children's Memorial Health Institute", "Anaesthesiology"),
                       _user("a2"), _user("a1", "Andrzej Piotrowski", "Children's Memorial Health Institute",
                                          "Anaesthesiology"),
                       _user("a3", "Tomasz Oleniacz", "", "Warsaw")],
           "_co_authors": ["A. Piotrowski", "Grochowski, T."]}
    out = _parse(_page(_current(doc)))
    assert [a["name"] for a in out["authors"]] == ["Andrzej Piotrowski", "Tomasz Oleniacz", "Grochowski, T."]
    # a department with no organization ("Warsaw") is not an affiliation
    assert out["authors"][1]["affiliations"] == []


def test_surname_and_initials_split_over_two_entries_are_joined():
    doc = {"title": "Salivary markers", "paper_abstract": ABSTRACT,
           "authors": [_user("a1", "Stephanie Bauduin", "Leiden University Medical Center", "Psychiatry")],
           "_co_authors": ["Bauduin", "S.", "Giltay", "E.", "van Noorden", "M.B."]}
    out = _parse(_page(_current(doc)))
    assert [a["name"] for a in out["authors"]] == ["Stephanie Bauduin", "Giltay, E.", "van Noorden, M.B."]


def test_two_names_in_one_co_author_entry_are_split():
    # 10.26226/morressier.5ac39997d462b8028d89a2e4: the uploader typed the last two co-authors as one entry
    doc = {"title": "Repurposing auranofin and ebselen", "paper_abstract": ABSTRACT,
           "authors": [_user("a1", "Ashok Kumar Chaturvedi", "The University of Texas at San Antonio", "Biology")],
           "_co_authors": ["Gina Wall", "Floyd L Wormley Jr. and Jose L Lopez-Ribot."]}
    out = _parse(_page(_current(doc)))
    assert [a["name"] for a in out["authors"]] == ["Ashok Kumar Chaturvedi", "Gina Wall", "Floyd L Wormley Jr.",
                                                  "Jose L Lopez-Ribot"]


def test_a_job_title_or_punctuation_in_the_department_is_not_the_affiliation():
    # 10.26226/morressier.5af985f5101067001b3aab07: "department": "Chief Technology Officer "
    doc = {"title": "Catheter securement", "paper_abstract": ABSTRACT,
           "authors": [_user("a1", "Spencer Jones", "Lineus Medical", "Chief Technology Officer "),
                       _user("a2", "Bartosz Bednarczyk", "TU Dresden & University of Wrocław", "."),
                       _user("a3", "Kate Brennan", "Imperial College London", "School of Public Health")]}
    out = _parse(_page(_current(doc)))
    assert [a["affiliations"] for a in out["authors"]] == [
        [{"name": "Lineus Medical"}], [{"name": "TU Dresden & University of Wrocław"}],
        [{"name": "School of Public Health, Imperial College London"}]]


def test_reference_list_inside_the_abstract_field_is_cut():
    doc = {"title": "Vitamin D", "authors": [_user("a1", "Ana Lopez", "University of London", "")],
           "paper_abstract": ABSTRACT + "\nReferences\nHart PH, Gorman S (2011) Nat Rev Immunol 11, 584-596"}
    out = _parse(_page(_current(doc)))
    assert out["abstract"] == ABSTRACT
    assert out["authors"][0]["affiliations"] == [{"name": "University of London"}]


def test_older_app_resolves_author_ids():
    state = {"posters": [{"id": "5e20352214799ab1e7e07a7d", "title": "Drug-adverse event pairs",
                          "authors": ["u1", "u2"], "_co_authors": [], "paper_abstract": ABSTRACT}],
             "users": [{"id": "u2", "full_name": "Tham Mun Yee", "organization": None, "department": None},
                       {"id": "u1", "full_name": "Sreemanee Dorajoo", "organization": "Health Sciences Authority",
                        "department": "Vigilance and Compliance Branch"}]}
    data = {"props": {"isServer": True, "initialState": state}, "page": "/article",
            "query": {"id": "5e20352214799ab1e7e07a7d"}}
    out = _parse(_page(data))
    assert [a["name"] for a in out["authors"]] == ["Sreemanee Dorajoo", "Tham Mun Yee"]
    assert out["authors"][0]["affiliations"] == [{"name": "Vigilance and Compliance Branch, Health Sciences Authority"}]
    assert out["abstract"] == ABSTRACT


def test_lookalike_next_page_from_another_site_is_not_claimed():
    doc = {"title": "Codetermination", "paper_abstract": ABSTRACT,
           "authors": [_user("a1", "Miles A Romney", "Florida State University", "College of Business")]}
    html = _page(_current(doc), head='<meta name="twitter:site" content="@SomeConferenceApp"/>')
    parser = Morressier(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["authors"] == []
