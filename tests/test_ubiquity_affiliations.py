"""Ubiquity Press platform: affiliations from the Next.js flight payload.

Since Ubiquity re-platformed (~mid-2024) its article pages carry
citation_author but no citation_author_institution, so every author parsed
with no affiliation (oxjob #833, ZD 23410: Journal of Long-Term Care
10.31389/jltc.481). The institutions are in the page's
``self.__next_f.push`` payload. Hand-crafted HTML, shaped like the stored
taxicab page (authors split across pushes, surname-first meta names).
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.ubiquity import Ubiquity

ASSETS = '<script src="https://journal-assets.ubiquity.press/2.21.1/_next/static/chunks/a.js" async=""></script>'


def _author(first, last, institution, country="GB", corresponding=False):
    return {"first_name": first, "last_name": last, "institution": institution,
            "country": country, "email": "", "bio": "", "corresponding": corresponding,
            "social": {"orcid": ""}, "fullName": f"{first} {last}"}


def _page(meta_names, authors, *, before="", meta_insts=None, assets=ASSETS, split=True):
    payload = (before + '8:["$","$L30",null,{"article":{"publication_id":480,'
               '"authors":' + json.dumps(authors, ensure_ascii=False) + '}}]\n')
    cut = len(payload) // 2 if split else len(payload)
    pushes = "".join(
        f"<script>self.__next_f.push({json.dumps([1, part])})</script>"
        for part in (payload[:cut], payload[cut:]) if part)
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in meta_names)
    metas += "".join(f'<meta name="citation_author_institution" content="{i}"/>'
                     for i in meta_insts or [])
    return (f"<html><head>{metas}{assets}</head><body><h1>Title</h1>"
            f"<script>(self.__next_f=self.__next_f||[]).push([0])</script>{pushes}</body></html>")


JLTC_META = ["Casal, Bruno", "Rodríguez-Míguez, Eva", "Towers, Ann-Marie", "Welch, Elizabeth"]
JLTC_AUTHORS = [
    _author("Bruno", "Casal", "University of A Coruña", "ES", corresponding=True),
    _author("Eva", "Rodríguez-Míguez", "University of Vigo", "ES"),
    _author("Ann-Marie", "Towers", "King’s College London"),
    _author("Elizabeth", "Welch", "University of Kent"),
]


def _authors(html):
    return parse_page(html, "doi", "https://journal.ilpnetwork.org/articles/10.31389/jltc.481")["authors"]


def test_jltc_481_each_author_gets_own_institution():
    got = _authors(_page(JLTC_META, JLTC_AUTHORS))
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in got] == [
        ("Casal, Bruno", ["University of A Coruña"]),
        ("Rodríguez-Míguez, Eva", ["University of Vigo"]),
        ("Towers, Ann-Marie", ["King’s College London"]),
        ("Welch, Elizabeth", ["University of Kent"]),
    ]
    assert [a["is_corresponding"] for a in got] == [True, False, False, False]


def test_institution_is_verbatim_no_country_appended_entities_decoded():
    # raw affiliation strings are exact-match keys downstream: the string must
    # equal what the old platform published ("Smart & Lean Hub Oy"), so decode
    # & but never append the country or normalise punctuation.
    authors = [_author("Juha", "Löytty", "Smart & Lean Hub Oy", "FI")]
    got = _authors(_page(["Löytty, Juha"], authors))
    assert got[0]["affiliations"] == [{"name": "Smart & Lean Hub Oy"}]


def test_empty_institution_gives_no_affiliation():
    authors = [_author("A", "Szczygiel", ""), _author("B", "Santana", "Universidade do Porto", "PT")]
    got = _authors(_page(["Szczygiel, A", "Santana, B"], authors))
    assert got[0]["affiliations"] == []
    assert got[1]["affiliations"] == [{"name": "Universidade do Porto"}]


def test_related_article_author_array_is_skipped():
    related = '5:{"related":[{"title":"Other","authors":' + json.dumps(
        [_author("Zed", "Other", "Wrong University")]) + '}]}\n'
    got = _authors(_page(JLTC_META, JLTC_AUTHORS, before=related))
    assert got[3]["affiliations"] == [{"name": "University of Kent"}]


def test_not_ubiquity_platform_is_not_publisher_specific():
    html = _page(JLTC_META, JLTC_AUTHORS, assets="")
    assert not Ubiquity(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_meta_institutions_kept_when_json_has_none():
    authors = [_author("Bruno", "Casal", "")]
    got = _authors(_page(["Casal, Bruno"], authors, meta_insts=["University of A Coruña"]))
    assert got[0]["affiliations"] == [{"name": "University of A Coruña"}]
