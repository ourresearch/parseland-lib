"""
A DSpace 7 site's translation labels are not the record's licence (oxjob #1165, ticket 22598).

DSpace 7 pages (Angular SSR) embed the site's translation dictionary in <script id="dspace-angular-state">, a label
per dotted key, among them every licence the item page, the submission form or the journal-policy widget can name:
    &q;item.page.rights.CCBYNCND40&q;:&q;CC BY-NC-ND 4.0&q;               (ruj.uj.edu.pl, `"` escaped as `&q;`)
    "licence.cc-by-nc-nd":"CC-BY-NC-ND"                                  (repozytorium.uw.edu.pl, plain JSON)
    "controlledVocabulary.dc.rights.httpscreativecommonsorglicensesby-nc-nd10":"CC BY-NC-ND 1.0: ..."  (ZHAW)
    "submission.agreement.content.text":"... licencji Creative Commons Public Domain Dedication (CC0) ..."  (UW)
The whole-page search read them, so every record of such a site came out cc-by-nc-nd: metadata-only records ("Dodaję
tylko opis bibliograficzny", RUJ), closed ones ("ClosedAccess", UW) and records with their own CC BY alike. The
record's own fields are lists of value objects and stay. Fragments below mirror pages fetched 20 Nov 2026; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import drop_dspace_cris_licence_vocabulary
from parseland_lib.parse import parse_page

RUJ_URL = "https://ruj.uj.edu.pl/entities/publication/5202a9be-4f83-4139-840d-e9c4aa96501f"
UW_URL = "https://repozytorium.uw.edu.pl/entities/publication/06a2dea7-e87d-40c2-be3e-a2987f226f27"

ESCAPED_LABELS = ("&q;item.page.rights.CCBYNC40&q;:&q;CC BY-NC 4.0&q;,&q;item.page.rights.CCBYNCND30&q;:&q;CC BY-NC-ND "
                  "3.0&q;,&q;item.page.rights.cc-by-nc-nd&q;:&q;Except as otherwise noted, this item is licensed under "
                  "the Attribution-NonCommercial-NoDerivatives 4.0 International&q;,&q;journal.page.oapermission.license"
                  ".cc-by-nc-4.0,-publisher&s;s-bespoke-license&q;:&q;CC BY-NC 4.0, publisher&s;s bespoke license&q;,"
                  "&q;journal.page.oapermission.license.cc-by-nc-nd&q;:&q;CC BY-NC-ND&q;")
PLAIN_LABELS = ('"item.page.rights.CCBYNCND30":"CC BY-NC-ND 3.0","licence.cc-by-nc-nd":"CC-BY-NC-ND",'
                '"controlledVocabulary.dc.rights.httpscreativecommonsorglicensesby-nc-nd10":"CC BY-NC-ND 1.0: '
                'Namensnennung - Nicht kommerziell - Keine Bearbeitungen 1.0 Generic",'
                '"submission.agreement.content.text":"\\u003Cli>Udzielam Uniwersytetowi Warszawskiemu licencji Creative '
                'Commons Public Domain Dedication (CC0) na udost\\u0119pnianie metadanych\\u003C/li>"')


def escaped_value(field, value):
    return (f"&q;{field}&q;:[{{&q;uuid&q;:&q;43bd&q;,&q;language&q;:null,&q;value&q;:&q;{value}&q;,&q;place&q;:0,"
            "&q;authority&q;:null,&q;confidence&q;:-1}]")


def plain_value(field, value):
    return (f'"{field}":[{{"uuid":"43bd","language":null,"value":"{value}","place":0,"authority":null,'
            '"confidence":-1}]')


def dspace7_page(state, pdf_url=None):
    pdf_meta = f'<meta name="citation_pdf_url" content="{pdf_url}">' if pdf_url else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><base href="/"><title>A record</title>
<meta name="citation_title" content="A record"><meta name="citation_author" content="Kowalska, Anna">{pdf_meta}
</head><body><ds-app><h1>A record</h1></ds-app>
<script id="dspace-angular-state" type="application/json">{{{state}}}</script></body></html>"""


def test_metadata_only_record_with_escaped_labels_has_no_licence():
    state = ESCAPED_LABELS + "," + escaped_value("dc.rights", "Dodaję tylko opis bibliograficzny") + "," + \
        escaped_value("dc.rights.uri", "")
    assert parse_page(dspace7_page(state), "pmh", RUJ_URL)["license"] is None


@pytest.mark.parametrize("uri, licence", [
    ("http://creativecommons.org/licenses/by/3.0/legalcode", "cc-by"),
    ("http://creativecommons.org/licenses/by-nc/4.0/legalcode.pl", "cc-by-nc"),
])
def test_record_keeps_its_own_licence_among_escaped_labels(uri, licence):
    state = ESCAPED_LABELS + "," + escaped_value("dc.rights.uri", uri)
    page = dspace7_page(state, pdf_url="https://ruj.uj.edu.pl/bitstreams/1/download")
    assert parse_page(page, "pmh", RUJ_URL)["license"] == licence


def test_closed_record_with_plain_labels_has_no_licence():
    state = PLAIN_LABELS + "," + plain_value("dc.rights", "ClosedAccess")
    page = dspace7_page(state, pdf_url="https://repozytorium.uw.edu.pl/bitstreams/2/download")
    assert parse_page(page, "pmh", UW_URL)["license"] is None


def test_record_keeps_its_own_licence_among_plain_labels():
    state = PLAIN_LABELS + "," + plain_value("dc.rights.uri", "https://creativecommons.org/licenses/by-sa/4.0/")
    assert parse_page(dspace7_page(state), "pmh", UW_URL)["license"] == "cc-by-sa"


def test_labels_alone_read_as_a_licence_before_the_fix():
    from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
    assert find_normalized_license(ESCAPED_LABELS) == "cc-by-nc-nd"
    assert find_normalized_license(PLAIN_LABELS) == "cc-by-nc-nd"


def test_only_the_labels_go():
    page = dspace7_page(ESCAPED_LABELS + "," + escaped_value("dc.rights.uri", "x") + "," + PLAIN_LABELS + "," +
                        plain_value("dc.rights.uri", "y"))
    kept = drop_dspace_cris_licence_vocabulary(page)
    assert "CC BY-NC-ND" not in kept and "CC-BY-NC-ND" not in kept and "CC0" not in kept
    assert escaped_value("dc.rights.uri", "x") in kept and plain_value("dc.rights.uri", "y") in kept


def test_labels_on_a_page_that_is_not_dspace_7_are_untouched():
    page = '<html><body><script>var t = {"item.page.rights.CCBYNCND30":"CC BY-NC-ND 3.0"};</script></body></html>'
    assert drop_dspace_cris_licence_vocabulary(page) is page
