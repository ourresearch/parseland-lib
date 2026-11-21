"""Common Ground (cgscholar.com) article pages: only the article's own licenseType counts (oxjob #1168).

Common Ground article pages are Nuxt pages. The article, with its licenseType, is one object in the __NUXT_DATA__
array, its values indices into that array. The same array holds the site's label list for every licence on offer
("Gold Open Access (CC-BY)", "Open Access (CC-BY-NC-ND)"), on every page, so the whole-page search read cc-by-nc-nd on
paywalled articles ("all_rights_reserved", PDF for sale): tickets 27748 and 28098, 5 of 8 sampled cc-by-nc-nd works.
Shapes copied from live pages (21 Nov 2026); hand-crafted, no Taxicab, no network.
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.version_and_license import (
    cgscholar_article_license_text,
    license_search_text,
)

RESOLVED = "https://cgscholar.com/publishers/articles/mapping-research-on-museum-spatial-design-and-visitor-experience"


def cg_page(license_type, access_model: str = "hybrid") -> str:
    data = [
        ["ShallowReactive", 1],
        {"data": 2},
        ["ShallowReactive", 3],
        {"article": 4, "labels": 12},
        {"id": 5, "title": 6, "doi": 7, "copyrightStatement": 8, "licenseType": 9, "journalAccessModel": 10,
         "isJournalSubscribed": 11},
        28551,
        "Mapping Research on Museum Spatial Design and Visitor Experience",
        "https://doi.org/10.18848/1835-2014/CGP/A490",
        "© 2026 Common Ground Research Networks. All rights reserved.",
        license_type,
        access_model,
        False,
        {"journal": 13, "licenseType": 14, "goldCcBy": 15, "openCcByNcNd": 16},
        "Journal",
        "License type",
        "Gold Open Access (CC-BY)",
        "Open Access (CC-BY-NC-ND)",
    ]
    return (
        "<html><head><title>Mapping Research | Common Ground Research Networks</title>"
        f'<link rel="canonical" href="{RESOLVED}">'
        '<meta name="citation_doi" content="10.18848/1835-2014/CGP/A490"></head>'
        "<body><div id=\"__nuxt\"><h1>Mapping Research on Museum Spatial Design and Visitor Experience</h1></div>"
        '<script type="application/json" data-nuxt-data="nuxt-app" data-ssr="true" id="__NUXT_DATA__">'
        f"{json.dumps(data, ensure_ascii=False)}</script></body></html>"
    )


def licence(html: str):
    return parse_publisher_fulltext_location(BeautifulSoup(html, "lxml"), RESOLVED)["license"]


def test_all_rights_reserved_beats_the_label_list():
    html = cg_page("all_rights_reserved")
    assert cgscholar_article_license_text(html, RESOLVED) == ""
    assert licence(html) is None


def test_null_licence_type_is_no_licence():
    assert cgscholar_article_license_text(cg_page(None), RESOLVED) == ""


def test_open_article_gives_its_own_licence():
    html = cg_page("cc_by_nc_nd")
    assert cgscholar_article_license_text(html, RESOLVED) == "CC BY-NC-ND"
    assert licence(html) == "cc-by-nc-nd"


def test_gold_article_gives_cc_by_not_the_label_lists_by_nc_nd():
    html = cg_page("cc_by_4", access_model="open_access")
    assert cgscholar_article_license_text(html, RESOLVED) == "CC BY"
    assert licence(html) == "cc-by"


def test_other_pages_keep_the_whole_page_search():
    # A Nuxt page elsewhere with a licenseType key, and any page without one: unchanged.
    other = (
        '<html><body><script id="__NUXT_DATA__" type="application/json">'
        '[{"licenseType":1},"all_rights_reserved"]</script>'
        '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a></body></html>'
    )
    assert cgscholar_article_license_text(other, "https://example.org/a/1") is None
    assert "creativecommons.org/licenses/by/4.0" in license_search_text(other, "https://example.org/a/1")
    plain = '<html><body><a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a></body></html>'
    assert cgscholar_article_license_text(plain, RESOLVED) is None
