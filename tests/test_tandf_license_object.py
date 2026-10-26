"""Taylor & Francis book pages: only the product's own licence object counts (oxjob #1809).

T&F chapter pages keep the product in Angular TransferState JSON (`"` escaped as `&q;`). Read whole, that JSON's
subject keywords ("Creative Commons Attribution ShareAlike") and chapter text ("... into the public domain") became
the licence; the product's `license` object (null, or an open-access object with a creativecommons.org location) is
the page's statement. Shapes copied from stored pilot pages; hand-crafted, no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_publisher_fulltext_location
from parseland_lib.legacy_parse_utils.version_and_license import (
    license_search_text,
    taylorfrancis_product_license_text,
)

RESOLVED = "https://www.taylorfrancis.com/chapters/edit/10.4324/9781315228815-9/marital-marginalia"


def tf_page(license_json: str, extra_json: str = "") -> str:
    state = (
        "{&q;product&q;:{&q;doi&q;:&q;10.4324/9781315228815-9&q;,"
        + extra_json
        + "&q;license&q;:" + license_json + ",&q;fundingGroups&q;:[]}}"
    )
    return (
        '<html><head><title>Marital Marginalia | 9 | Taylor &amp; Francis eBooks</title>'
        '<link rel="canonical" href="https://www.taylorfrancis.com/chapters/edit/10.4324/9781315228815-9"></head>'
        '<body><h1>Marital Marginalia</h1>'
        f'<script id="serverApp-state" type="application/json">{state}</script></body></html>'
    )


KEYWORD = (
    "&q;keywords&q;:[{&q;type&q;:&q;concept&q;,&q;name&q;:&q;Armorial Bookplate&q;},"
    "{&q;type&q;:&q;concept&q;,&q;name&q;:&q;Creative Commons Attribution ShareAlike&q;}],"
)
TEXT = "&q;excerpt&q;:&q;all bring aspects of university culture into the public domain.&q;,"
OA = (
    "{&q;type&q;:&q;open-access&q;,&q;description&q;:null,"
    "&q;location&q;:&q;http://creativecommons.org/licenses/by-nc-nd/4.0&q;}"
)


def licence(html: str):
    return parse_publisher_fulltext_location(BeautifulSoup(html, "lxml"), RESOLVED)["license"]


def test_null_licence_object_beats_a_keyword():
    assert licence(tf_page("null", KEYWORD)) is None


def test_null_licence_object_beats_chapter_text():
    assert licence(tf_page("null", TEXT)) is None


def test_open_access_object_gives_its_licence():
    html = tf_page(OA, KEYWORD)
    assert licence(html) == "cc-by-nc-nd"
    assert parse_publisher_fulltext_location(BeautifulSoup(html, "lxml"), RESOLVED)["oa_status"] == "hybrid"


def test_object_text_is_decoded():
    assert taylorfrancis_product_license_text(tf_page(OA)).startswith('{"type":"open-access"')
    assert taylorfrancis_product_license_text(tf_page("null")) == ""


def test_other_pages_keep_the_whole_page_search():
    # An Angular page elsewhere with a licence key, and any page without one: unchanged.
    other = '<html><body><script>{&q;license&q;:null}</script><p>CC BY 4.0</p></body></html>'
    assert taylorfrancis_product_license_text(other) is None
    plain = '<html><body><a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a></body></html>'
    assert taylorfrancis_product_license_text(plain) is None
    assert "creativecommons.org/licenses/by/4.0" in license_search_text(plain)
