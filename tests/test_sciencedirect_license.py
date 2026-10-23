"""
ScienceDirect licences come from the article's own licence statement (oxjob #1794).

ScienceDirect's page state says once per page what the article's licence is:
    "access":{"openAccess":<bool>,"openArchive":<bool>[,"license":"<url>"]}
The same state also carries the journal's self-archiving policy ("sa-user-license", the licence an accepted
manuscript may carry after an embargo) and open-research agreements ("or-agreement-license"). Before this fix
Parseland read those as the article's licence, so paywalled articles came out cc-by-nc-nd (12 of 12 such pages
in the gold dev set) and read as open access downstream. Fragments below mirror the real page state; no network.
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import sciencedirect_article_license_text
from parseland_lib.parse import parse_page

SD_URL = "https://www.sciencedirect.com/science/article/abs/pii/S2352152X26044919"

SELF_ARCHIVING = ('"self-archiving":{"#name":"self-archiving","$":{"xmlns:xocs":true},"$$":['
                  '{"#name":"sa-start-date","_":"2028-09-30T00:00:00.000Z"},'
                  '{"#name":"sa-user-license","_":"http://creativecommons.org/licenses/by-nc-nd/4.0/"}]}')
OPEN_RESEARCH = ('"open-research":{"#name":"open-research","$":{"xmlns:xocs":true},"$$":['
                 '{"#name":"or-agreements","$$":[{"#name":"or-agreement","$$":[{"#name":"or-agreement-name","_":"X"},'
                 '{"#name":"or-agreement-terms","_":"publishAcceptedManuscriptIndexable"}]}]},'
                 '{"#name":"or-agreement-license","_":"http://www.elsevier.com/open-access/userlicense/1.0/"}]}')


def sd_page(access, extra_state="", body=""):
    return f"""<html><head><title>An article</title>
<link rel="canonical" href="{SD_URL}"></head><body>
<article><h1>An article</h1>{body}</article>
<script>window.__PRELOADED_STATE__ = {{"article":{{"access":{access},"pii":"S2352152X26044919",
"accessTypeLabel":null,{extra_state}"srctitle":"Journal of Energy Storage"}}}};</script>
</body></html>"""


PAYWALLED = '{"openAccess":false,"openArchive":false}'
OA_CC_BY = '{"openAccess":true,"openArchive":false,"license":"http://creativecommons.org/licenses/by/4.0/"}'
OA_CC_BY_NC_ND = '{"openAccess":true,"openArchive":false,"license":"http://creativecommons.org/licenses/by-nc-nd/4.0/"}'
OPEN_ARCHIVE = '{"openAccess":true,"openArchive":true,"license":"http://www.elsevier.com/open-access/userlicense/1.0/"}'


@pytest.mark.parametrize("extra", [SELF_ARCHIVING + ",", OPEN_RESEARCH + ",", SELF_ARCHIVING + "," + OPEN_RESEARCH + ","])
def test_paywalled_article_has_no_licence_despite_policy_licences(extra):
    assert parse_page(sd_page(PAYWALLED, extra), "doi", SD_URL)["license"] is None


def test_paywalled_article_reached_through_doi_router_has_no_licence():
    # older stored pages were fetched via doi.org; the state is the same
    page = sd_page(PAYWALLED, SELF_ARCHIVING + ",")
    assert parse_page(page, "doi", "https://doi.org/10.1016/j.est.2026.124827")["license"] is None


def test_paywalled_article_has_no_licence_without_a_resolved_url():
    assert parse_page(sd_page(PAYWALLED, SELF_ARCHIVING + ","), "doi", None)["license"] is None


@pytest.mark.parametrize("access,expected", [
    (OA_CC_BY, "cc-by"),
    (OA_CC_BY_NC_ND, "cc-by-nc-nd"),
    (OPEN_ARCHIVE, "publisher-specific-oa"),
])
def test_article_licence_still_read(access, expected):
    # the policy blocks must not override, or be needed for, the article's own licence
    assert parse_page(sd_page(access, SELF_ARCHIVING + ","), "doi", SD_URL)["license"] == expected


def test_open_access_article_with_cc_by_beats_self_archiving_cc_by_nc_nd():
    page = sd_page(OA_CC_BY, SELF_ARCHIVING + ",")
    assert parse_page(page, "doi", SD_URL)["license"] == "cc-by"


def test_open_access_label_without_licence_url_stays_unspecified_oa():
    body = '<div class="OpenAccessLabel">open access</div>'
    page = sd_page('{"openAccess":true,"openArchive":false}', SELF_ARCHIVING + ",", body)
    assert parse_page(page, "doi", SD_URL)["license"] == "unspecified-oa"


def test_article_licence_text_helper():
    assert sciencedirect_article_license_text(sd_page(PAYWALLED, SELF_ARCHIVING + ",")) == ""
    assert sciencedirect_article_license_text(sd_page(OA_CC_BY)) == "http://creativecommons.org/licenses/by/4.0/"
    assert sciencedirect_article_license_text("<html><body>no state</body></html>") is None
    assert sciencedirect_article_license_text("") is None
    assert sciencedirect_article_license_text(None) is None


def test_pages_without_sciencedirect_state_keep_the_whole_page_search():
    page = """<html><head><title>t</title></head><body><article><p>This is an open access article under the
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a> licence.</p></article></body></html>"""
    assert parse_page(page, "doi", "https://journals.plos.org/plosone/article?id=10.1371/x")["license"] == "cc-by"
