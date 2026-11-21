"""
A DSpace-CRIS config's licence lookup table is not the record's licence (oxjob #1165, ticket 21970).

EPFL Infoscience (infoscience.epfl.ch, DSpace-CRIS) serves every record page with the Angular app's config in the
TransferState JSON (<script id="dspace-angular-state">, `"` escaped as `&q;`). The config holds the lookup table of
EPFL's Unpaywall widget, every licence label in it:
    &q;epflUnpaywallMetadata&q;:{&q;oaire_licenseCondition&q;:{&q;cc_by&q;:&q;CC BY&q;,...,&q;cc_by_nc_nd&q;:
    &q;CC BY-NC-ND&q;,&q;cc_0&q;:&q;CC0&q;,&q;pdm&q;:&q;PDM&q;},&q;oaire_version&q;:{...},&q;polling&q;:{...}}
The whole-page search read the most specific label, so every Infoscience record came out cc-by-nc-nd, metadata-only
records included (208,789 pages), and Walden counts a page's CC licence as an open copy. Fragments below mirror the
real pages (handles 20.500.14299/206952 metadata-only, 20.500.14299/231448 open, fetched 20 Nov 2026); no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import drop_dspace_cris_licence_vocabulary
from parseland_lib.parse import parse_page

HANDLE_URL = "https://infoscience.epfl.ch/handle/20.500.14299/{}"

CONFIG = ("&q;epflUnpaywallMetadata&q;:{&q;oaire_licenseCondition&q;:{&q;cc_by&q;:&q;CC BY&q;,&q;cc_by_sa&q;:"
          "&q;CC BY-SA&q;,&q;cc_by_nd&q;:&q;CC BY-ND&q;,&q;cc_by_nc&q;:&q;CC BY-NC&q;,&q;cc_by_nc_sa&q;:&q;CC BY-NC-SA&q;,"
          "&q;cc_by_nc_nd&q;:&q;CC BY-NC-ND&q;,&q;cc_0&q;:&q;CC0&q;,&q;pdm&q;:&q;PDM&q;},&q;oaire_version&q;:"
          "{&q;submittedVersion&q;:&q;http://purl.org/coar/version/c_71e4c1898caa6e32&q;,&q;acceptedVersion&q;:"
          "&q;http://purl.org/coar/version/c_ab4af688f83e57aa&q;,&q;publishedVersion&q;:"
          "&q;http://purl.org/coar/version/c_970fb48d4fbd8a85&q;},&q;polling&q;:{&q;initialIntervalMs&q;:10000,"
          "&q;initialMaxRetries&q;:3}},&q;mirador&q;:{&q;enableDownloadPlugin&q;:true}")

# the layout's field list and the i18n labels name the field too; neither is a value
LAYOUT = ("{&q;name&q;:&q;datacite.rights&q;,&q;type&q;:&q;metadata&q;,&q;truncatable&q;:false},{&q;name&q;:"
          "&q;oaire.licenseCondition&q;,&q;type&q;:&q;metadata&q;,&q;truncatable&q;:false},"
          "&q;cris-layout.advanced-attachment.oaire.licenseCondition&q;:&q;License Condition&q;,"
          "&q;search.filters.applied.f.original_bundle_oaire_licenseCondition&q;:&q;File License&q;")


def item_metadata(rights, licence=None):
    fields = [f"&q;datacite.rights&q;:[{{&q;uuid&q;:&q;1e1f7726&q;,&q;language&q;:null,&q;value&q;:&q;{rights}&q;,"
              "&q;place&q;:0,&q;authority&q;:null,&q;confidence&q;:-1}]"]
    if licence:
        fields.append(f"&q;oaire.licenseCondition&q;:[{{&q;uuid&q;:&q;5a1c&q;,&q;language&q;:null,&q;value&q;:"
                      f"&q;{licence}&q;,&q;place&q;:0,&q;authority&q;:null,&q;confidence&q;:-1}}]")
    return ",".join(fields)


def infoscience_page(handle, rights, pdf_uuid=None, licence=None, config=CONFIG):
    pdf_meta = (f'<meta name="citation_pdf_url" property="citation_pdf_url" '
                f'content="https://infoscience.epfl.ch/bitstreams/{pdf_uuid}/download">') if pdf_uuid else ""
    return f"""<!DOCTYPE html><html lang="en"><head><title>A record</title>
<meta name="citation_title" content="A record">
<meta name="citation_author" content="Wang, Bowen">
<meta name="citation_publication_date" content="2024-03-07">
<meta name="citation_abstract_html_url" content="{HANDLE_URL.format(handle)}">{pdf_meta}
<meta name="citation_doi" content="10.1109/TCSI.2024.3365862">
</head><body><ds-app><h1>A record</h1><p>Infoscience</p></ds-app>
<script id="dspace-angular-state" type="application/json">{{&q;APP_CONFIG_STATE&q;:{{{config},&q;layout&q;:[{LAYOUT}]}},
&q;item&q;:{{&q;handle&q;:&q;20.500.14299/{handle}&q;,&q;metadata&q;:{{{item_metadata(rights, licence)}}}}}}}</script>
</body></html>"""


@pytest.mark.parametrize("namespace", ["pmh", "doi"])
def test_metadata_only_record_has_no_licence(namespace):
    parsed = parse_page(infoscience_page(206952, "metadata-only"), namespace, HANDLE_URL.format(206952))
    assert parsed["license"] is None
    assert not [u for u in parsed["urls"] if u["content_type"] == "pdf"]


def test_open_record_keeps_its_file_and_gets_no_licence_from_the_table():
    page = infoscience_page(231448, "openaccess", pdf_uuid="40f33ab1-8e00-4004-a851-001542b98dd0")
    parsed = parse_page(page, "pmh", HANDLE_URL.format(231448))
    assert parsed["license"] is None
    assert {"url": "https://infoscience.epfl.ch/bitstreams/40f33ab1-8e00-4004-a851-001542b98dd0/download",
            "content_type": "pdf"} in parsed["urls"]


@pytest.mark.parametrize("label, licence", [("CC BY", "cc-by"), ("CC BY-SA", "cc-by-sa")])
def test_the_records_own_licence_field_stays(label, licence):
    page = infoscience_page(231448, "openaccess", pdf_uuid="40f33ab1", licence=label)
    assert parse_page(page, "pmh", HANDLE_URL.format(231448))["license"] == licence


def test_before_the_fix_the_table_read_as_cc_by_nc_nd():
    # the table alone, with nothing else on the page, is what read as the licence
    from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
    assert find_normalized_license(CONFIG) == "cc-by-nc-nd"
    assert find_normalized_license(drop_dspace_cris_licence_vocabulary(CONFIG)) is None


def test_only_the_lookup_table_goes():
    kept = drop_dspace_cris_licence_vocabulary(CONFIG + "," + LAYOUT + "," + item_metadata("openaccess", "CC BY"))
    assert "oaire_licenseCondition&q;:{" not in kept
    assert "&q;oaire_version&q;:{" in kept  # the version table names no licence
    assert "&q;oaire.licenseCondition&q;:[" in kept and "&q;CC BY&q;" in kept
    assert "original_bundle_oaire_licenseCondition&q;:&q;File License&q;" in kept


def test_unescaped_json_too():
    table = '"oaire_licenseCondition":{"cc_by":"CC BY","cc_by_nc_nd":"CC BY-NC-ND"}'
    assert drop_dspace_cris_licence_vocabulary('{"x":1,' + table + '}') == '{"x":1,}'


def test_pages_without_the_table_are_untouched():
    page = '<html><body><a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a></body></html>'
    assert drop_dspace_cris_licence_vocabulary(page) is page
    assert drop_dspace_cris_licence_vocabulary(None) is None
