"""
Page-template code that looks for a Creative Commons badge is not a licence statement (oxjob #1794).

SAGE's older article template (still in many stored pages) carries this script on every article page, paywalled or
open:
    if ($('.creative-commons-badge.cc-by').length){ console.debug('Hiding permissions button due to CC-BY type of
    article.'); ... }
The whole-page licence search read its `cc-by` tokens as the article's licence: a re-parse of old stored pages turned
755 closed works (Elsevier-prefix DOIs now hosted by SAGE) hybrid. Fragments mirror the stored pages; no network.
"""
from parseland_lib.parse import parse_page

SAGE_URL = "https://journals.sagepub.com/doi/10.1016/S0840-4704%2810%2960027-0"

TEMPLATE_SCRIPT = """<script>
// Here we keep the JS functions that use context sensitive parameters
$('.purchaseAccessDropZone').appendTo('.accessDenialWidget article');
if ($('.creative-commons-badge.cc-by').length){
\tconsole.debug('Hiding permissions button due to CC-BY type of article.');
\t$('a.permissionsTool').closest('div').css('display', 'none');
}
// show the full text tab if user has full access
if ($('.articleBadges .accessIcon.openAccess, .articleBadges .accessIcon.freeAccess').length>0){ }
</script>"""


def sage_page(body=""):
    return f"""<html><head><title>Leadership - Marion Suski, 1999</title>
<meta name="dc.Rights" content="&#169; 1999 The Canadian College of Health Leaders" /></head><body>
<article><h1>Leadership: The Winnipeg Community and Long Term Care Authority</h1>{body}
<div class="accessDenialWidget"><article>Purchase access</article></div></article>
{TEMPLATE_SCRIPT}
</body></html>"""


def test_paywalled_page_with_badge_script_has_no_licence():
    assert parse_page(sage_page(), "doi", SAGE_URL)["license"] is None


def test_paywalled_page_reached_through_doi_router_has_no_licence():
    assert parse_page(sage_page(), "doi", "https://doi.org/10.1016/s0840-4704(10)60027-0")["license"] is None


def test_open_access_page_still_reads_its_own_licence_statement():
    body = """<div class="creative-commons-badge cc-by"></div><p>This article is distributed under the terms of the
<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 License</a>.</p>"""
    assert parse_page(sage_page(body), "doi", SAGE_URL)["license"] == "cc-by"


def test_other_scripts_still_searched():
    # licences that only live in page data (eLife's __NEXT_DATA__) must still be found
    page = """<html><head><title>t</title></head><body><article><h1>t</h1></article>
<script id="__NEXT_DATA__" type="application/json">{"props":{"article":{"license":
"http://creativecommons.org/licenses/by/4.0/"}}}</script></body></html>"""
    assert parse_page(page, "doi", "https://elifesciences.org/reviewed-preprints/1")["license"] == "cc-by"
