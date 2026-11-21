"""UNSWorks item pages: only the item's own dc.rights / dc.rights.uri count (oxjob #1096, ZD 7949).

UNSWorks (unsworks.unsw.edu.au, DSpace 7) keeps the item's metadata in Angular TransferState JSON (`"` escaped as
`&q;`). Beside the item's own licence it carries dcterms.license by-nc-nd/3.0/au, also on items whose dc.rights says
CC BY or "No Licence"; read whole, the page gave cc-by-nc-nd for both. Shapes copied from item pages fetched 17 Nov
2026 (1959.4/107124, 53527, 100373, 103490, 105302); hand-crafted, no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import parse_repo_fulltext_location
from parseland_lib.legacy_parse_utils.version_and_license import license_search_text, unsworks_item_license_text

HANDLE = "http://hdl.handle.net/1959.4/107124"
ITEM = "https://unsworks.unsw.edu.au/server/api/core/items/c01be4e5-1847-4e69-a472-e982b1b9078a"
NC_ND_AU = "https://creativecommons.org/licenses/by-nc-nd/3.0/au/"


def field(name: str, *values: str) -> str:
    entries = ",".join(
        "{&q;uuid&q;:&q;5125d04f-a049-470f-a8a1-184d6446ad3f&q;,&q;language&q;:null,"
        f"&q;value&q;:&q;{v}&q;,&q;place&q;:{i},&q;authority&q;:null,&q;confidence&q;:-1}}"
        for i, v in enumerate(values)
    )
    return f"&q;{name}&q;:[{entries}]"


def unsworks_page(*fields: str, item: str = ITEM, body: str = "") -> str:
    state = (
        "{&q;" + item + "&q;:{&q;request&q;:{},&q;response&q;:{&q;payload&q;:{&q;metadata&q;:{"
        + ",".join(fields)
        + ",&q;dc.title&q;:[{&q;value&q;:&q;Architects Innovate&q;}]}}}}}"
    )
    return (
        '<html><head><base href="/"><title>Architects Innovate</title>'
        '<meta name="citation_title" content="Architects Innovate"></head>'
        f'<body><h1>Architects Innovate</h1>{body}'
        f'<script id="dspace-angular-state" type="application/json">{state}</script></body></html>'
    )


def licence(html: str, url: str | None = HANDLE):
    return parse_repo_fulltext_location(BeautifulSoup(html, "lxml"), url)["license"]


def test_cc_by_item_beats_the_default_dcterms_license():
    html = unsworks_page(field("dc.rights", "CC-BY"),
                         field("dc.rights.uri", "https://creativecommons.org/licenses/by/4.0/"),
                         field("dcterms.license", NC_ND_AU))
    assert licence(html) == "cc-by"


def test_no_licence_item_has_no_licence():
    # An ACS / IEEE accepted manuscript UNSWorks marks "No Licence": the default dcterms.license is not its licence.
    html = unsworks_page(field("dc.rights", "No Licence"), field("dcterms.license", NC_ND_AU))
    assert licence(html) is None
    assert unsworks_item_license_text(html) == "No Licence"


def test_cc_by_nc_nd_item_keeps_its_licence():
    html = unsworks_page(field("dc.rights", "CC BY-NC-ND 3.0"), field("dc.rights.uri", NC_ND_AU),
                         field("dcterms.license", NC_ND_AU))
    assert licence(html) == "cc-by-nc-nd"


def test_item_without_dcterms_license_unchanged():
    html = unsworks_page(field("dc.rights", "CC BY 4.0"),
                         field("dc.rights.uri", "https://creativecommons.org/licenses/by/4.0/"))
    assert licence(html) == "cc-by"


def test_page_text_outside_the_item_fields_is_not_read():
    # A licence named elsewhere on the page (a related item, the site's own terms) is not this item's.
    html = unsworks_page(field("dc.rights", "No Licence"),
                         body='<a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a>')
    assert licence(html) is None


def test_identified_by_address_or_by_item_state():
    html = unsworks_page(field("dc.rights", "CC-BY"), field("dcterms.license", NC_ND_AU))
    assert licence(html, None) == "cc-by"  # stored page without its address: the item state names UNSWorks
    other_state = html.replace("unsworks.unsw.edu.au", "repository.example.edu")
    assert unsworks_item_license_text(other_state) is None
    assert unsworks_item_license_text(other_state, "https://unsworks.unsw.edu.au/entities/publication/x") == "CC-BY"


def test_other_dspace7_pages_keep_the_whole_page_search():
    html = unsworks_page(field("dc.rights", "CC-BY"), field("dcterms.license", NC_ND_AU)).replace(
        "unsworks.unsw.edu.au", "repository.example.edu")
    assert unsworks_item_license_text(html, "https://repository.example.edu/items/1") is None
    assert "by-nc-nd/3.0/au" in license_search_text(html, "https://repository.example.edu/items/1")
    plain = '<html><body><a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a></body></html>'
    assert unsworks_item_license_text(plain) is None
