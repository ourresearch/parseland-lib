"""
IOP's Accepted Manuscript notice on a subscription article is not the article's licence (oxjob #1860).

Before IOP publishes the Version of Record, iopscience.iop.org shows an "ACCEPTED MANUSCRIPT" page. For a
subscription article its licence block says the manuscript "is fully protected by copyright" during a 12-month
embargo and "will be available for reuse under a CC BY-NC-ND 4.0 licence after the 12 month embargo period", with a
cc-by-nc-nd.png badge. Parseland read that as the article's licence, so paywalled IOP articles came out cc-by-nc-nd
and read as hybrid open access downstream (249 of 250 sampled IOP pages whose licence was cc-by-nc-nd while Crossref
deposits IOP's standard licence). The gold-OA notice and the published article's own licence block must still count.
Fragments below are copied from stored production pages; no network.
"""
import pytest

from parseland_lib.parse import parse_page

AM_URL = "https://iopscience.iop.org/article/10.1088/2053-1583/ae4811"

# 10.1088/2053-1583/ae4811 (2D Materials), stored 2026-02 (ticket 23390's example W7130545508)
SUBSCRIPTION_NOTICE_2026 = """<div class="media">
<img alt="" class="pull-left" src="https://static.iopscience.com/4.12.0/img/cc-by-nc-nd.png" style="width: 59px"/>
<div class="media-body">
<p>
      During the embargo period (the 12 month period from the publication of the Version of Record of this article),
      the Accepted Manuscript is fully protected by copyright and cannot be reused or reposted elsewhere.
    </p>
<p>
      As the Version of Record of this article is going to be / has been published on a subscription basis, this
      Accepted Manuscript will be available for reuse under a CC BY-NC-ND 4.0 licence after the 12 month embargo period.
    </p>
<p>
      After the embargo period, everyone is permitted to use copy and redistribute this article for non-commercial
      purposes only, provided that they adhere to all the terms of the licence
      <a href="https://creativecommons.org/licences/by-nc-nd/4.0">https://creativecommons.org/licences/by-nc-nd/4.0</a>
</p>
<p>
      Although reasonable endeavours have been taken to obtain all necessary permissions from third parties to include
      their copyrighted content within this article, their full citation and copyright line may not be present in this
      Accepted Manuscript version.
    </p>
</div>
</div>"""

# 10.1088/1361-6439/acb958, older template (2023): one paragraph, CC BY-NC-ND 3.0, "after a 12 month embargo period"
SUBSCRIPTION_NOTICE_2023 = """<div class="col-no-break wd-jnl-art-license media">
            <img alt="" SRC="https://static.iopscience.com/2.99.0/img/cc-by-nc-nd.png" style="width: 59px" class="pull-left" />
            <div class="media-body">
              <p>As the Version of Record of this article is going to be/has been published on a subscription basis,
              this Accepted Manuscript will be available for reuse under a CC BY-NC-ND 3.0 licence after a 12 month
              embargo period.</p>
              <p>Although reasonable endeavours have been taken to obtain all necessary permissions from third parties
              to include their copyrighted content within this article, their full citation and copyright line may not
              be present in this Accepted Manuscript version.</p>
            </div>
        </div>"""

# 10.1088/1741-4326/ad0981: gold OA article, Accepted Manuscript page
GOLD_OA_NOTICE = """<div class="media">
  <img alt="" src="https://static.iopscience.com/3.29.1/img/cc-by.png" class="pull-left" style="width: 59px" />
  <div class="media-body">
    <p>
      As the Version of Record of this article is going to be / has been published on a gold open access basis under a
      CC BY 4.0 licence, this Accepted Manuscript is available for reuse under a CC BY 4.0 licence immediately.
    </p>
    <p>
      Everyone is permitted to use all or part of the original content in this article, provided that they adhere to all
      the terms of the licence <a href="https://creativecommons.org/licences/by/4.0">https://creativecommons.org/licences/by/4.0</a>
    </p>
  </div>
</div>"""

# 10.1088/1742-6596/2764/1/012005: the published article's own licence block
VOR_CC_BY_BLOCK = """<div class="col-no-break wd-jnl-art-license media"><img SRC="https://content.cld.iop.org/journals/1742-6596/2764/1/012005/revision3/ccby.gif" alt="" class="pull-left"></img><div class="media-body"><p>
  Content from this work may be used under the terms of the <a class="webref" target="_blank" href="https://creativecommons.org/licenses/by/4.0">Creative Commons Attribution 4.0 licence</a>. Any further distribution of this work must maintain attribution to the author(s) and the title of the work, journal citation and DOI.</p></div></div>"""


def iop_page(licence_block, surtitle="ACCEPTED MANUSCRIPT"):
    return f"""<html><head><title>An article - IOPscience</title>
<link rel="canonical" href="{AM_URL}">
<meta name="citation_title" content="An article">
<meta name="citation_author" content="Ray, A">
<link rel="stylesheet" href="https://static.iopscience.com/4.12.0/css/main.css"></head><body>
<div class="da1 ta1 article-head"><div class="eyebrow"><span class="wd-jnl-art-sur-title">{surtitle}</span></div>
<h1 itemprop="headline" class="wd-jnl-art-title">An article</h1>
<p class="small"><span class="wd-jnl-art-pub-date">Accepted Manuscript online 19 February 2026</span>
<span itemprop="copyrightHolder" class="wd-jnl-art-copyright"> &copy; 2026 IOP Publishing Ltd.</span></p></div>
<div class="article-content"><div class="wd-jnl-art-abstract"><p>We study excitons in monolayer WSe2.</p></div>
{licence_block}</div>
<footer><a href="https://publishingsupport.iopscience.iop.org/open_access/">IOP Publishing open access policy</a></footer>
</body></html>"""


@pytest.mark.parametrize("notice", [SUBSCRIPTION_NOTICE_2026, SUBSCRIPTION_NOTICE_2023])
@pytest.mark.parametrize("resolved_url", [AM_URL, AM_URL + "/pdf", "https://doi.org/10.1088/2053-1583/ae4811", None])
def test_subscription_accepted_manuscript_notice_is_not_a_licence(notice, resolved_url):
    assert parse_page(iop_page(notice), "doi", resolved_url)["license"] is None


def test_repository_path_gets_the_same_rule():
    # repository records can resolve to the IOP page; the repository path shares the licence search
    assert parse_page(iop_page(SUBSCRIPTION_NOTICE_2026), "pmh", AM_URL)["license"] is None


def test_gold_open_access_accepted_manuscript_keeps_cc_by():
    assert parse_page(iop_page(GOLD_OA_NOTICE), "doi", AM_URL)["license"] == "cc-by"


def test_published_article_licence_block_still_read():
    page = iop_page(VOR_CC_BY_BLOCK, surtitle="PAPER")
    assert parse_page(page, "doi", AM_URL)["license"] == "cc-by"


def test_article_licence_wins_when_both_blocks_are_on_the_page():
    # a page carrying the subscription notice and the article's own CC BY block reads cc-by, not cc-by-nc-nd
    page = iop_page(SUBSCRIPTION_NOTICE_2026 + VOR_CC_BY_BLOCK)
    assert parse_page(page, "doi", AM_URL)["license"] == "cc-by"


def test_other_fields_unchanged_by_the_rule():
    with_notice = parse_page(iop_page(SUBSCRIPTION_NOTICE_2026), "doi", AM_URL)
    without = parse_page(iop_page(""), "doi", AM_URL)
    for field in ("authors", "abstract", "pdf_url", "version"):
        assert with_notice.get(field) == without.get(field)
