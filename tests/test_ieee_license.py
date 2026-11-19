"""
IEEE Xplore licences come from the article's own access state (oxjob #2417).

Every IEEE Xplore document page holds the article's access in its metadata object:
    xplGlobal.document.metadata={..."isOpenAccess":<bool>,...,"openAccessFlag":"T"|"F",...};
An open-access article also names its licence in a "ccby-indicator" line linking the licence. The page template's
stylesheet, inlined on pages fetched whole, styles that banner on every page, open or not:
    .document-header-metrics-banner.ccby-document[_ngcontent-ng-c2640185558]{padding-bottom:0}
and the class name read as "cc by": 147,579 of the 148,479 IEEE pages parsed in the week of 2 Nov 2026 came out cc-by,
paywalled articles served as hybrid open access. Fragments below mirror the real pages; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import ieee_article_page
from parseland_lib.parse import parse_page

IEEE_URL = "https://ieeexplore.ieee.org/document/11587018"

STYLESHEET = ("<style>.document-header-metrics-banner[_ngcontent-ng-c2640185558]{padding:.4rem 1rem .8rem;width:100%}"
              ".document-header-metrics-banner.ccby-document[_ngcontent-ng-c2640185558]{padding-bottom:0}</style>")


def ieee_page(is_open, licence_url=None, stylesheet=STYLESHEET):
    flag = "T" if is_open else "F"
    indicator = (f'<div class="ccby-indicator u-pl-2 pb-2"> Under a <a target="_blank" href="{licence_url}">'
                 'Creative Commons License</a></div>') if licence_url else ""
    banner_class = "document-header-metrics-banner d-flex flex-wrap" + (" ccby-document" if is_open else "")
    return f"""<html><head><title>A paper | IEEE Conference Publication | IEEE Xplore</title>{stylesheet}</head><body>
<div class="{banner_class}">{indicator}</div>
<h1>A paper</h1>
<script type="text/javascript">
xplGlobal.document.metadata={{"userInfo":{{"institute":false}},"title":"A paper","isFreeDocument":{str(is_open).lower()},
"isOpenAccess":{str(is_open).lower()},"openAccessFlag":"{flag}","pdfUrl":"/stamp/stamp.jsp?tp=&arnumber=11587018"}};
</script></body></html>"""


def test_paywalled_page_with_the_banner_stylesheet_has_no_licence():
    assert parse_page(ieee_page(False), "doi", IEEE_URL)["license"] is None


def test_paywalled_page_reached_as_a_repository_record_has_no_licence():
    assert parse_page(ieee_page(False), "pmh", IEEE_URL)["license"] is None
    assert parse_page(ieee_page(False), "doi", "https://doi.org/10.1109/icc59461.2026.11587018")["license"] is None


@pytest.mark.parametrize("url, licence", [
    ("https://creativecommons.org/licenses/by/4.0/", "cc-by"),
    ("https://creativecommons.org/licenses/by-nc-nd/4.0/", "cc-by-nc-nd"),
])
def test_open_access_page_keeps_the_licence_it_names(url, licence):
    assert parse_page(ieee_page(True, url), "doi", IEEE_URL)["license"] == licence


def test_access_flag_read_from_the_metadata_object_only():
    assert ieee_article_page(ieee_page(False)) is False
    assert ieee_article_page(ieee_page(True)) is True
    assert ieee_article_page("<html><body>no metadata here \"isOpenAccess\":false</body></html>") is None

