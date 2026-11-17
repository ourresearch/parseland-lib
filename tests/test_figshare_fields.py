"""Figshare item pages (figshare.com and the portals built on it: aacr.figshare.com, Optica Open, university
repositories) (oxjob #2289).

Markup cut down from stored figshare pages (17 Nov 2026, #2289 template sample). Every page carries
<meta name="application-name" content="figshare"> in its <head>. The item's creators are DataCite.contributor tags
(and, on some items, citation_author tags too); the page prints them after "authored by". Under its own "Funding"
heading an item lists each funder as an <h3> in its own block: the generic heading reader stops at the first nested
heading, so it read none of them. No item page shows affiliations or a corresponding author.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.figshare import Figshare

URL = "https://doi.org/10.1158/1078-0432.22467267"
APP = '<meta data-rh="true" content="figshare" name="application-name"/>'
NAMES = ["van Vlodrop, Iris J.H.", "Joosten, Sophie C.", "De Meyer, Tim"]
TITLE = "Supplementary Figure S2 from A Four-Gene Promoter Methylation Marker Panel"
LEGEND = ("Supplementary Figure S2. Validation of up-regulation of gene expression after demethylation with DAC by "
          "qRT-PCR for 22 genes in ccRCC cell lines treated with either mock or DAC for 96 hours.")
ARTICLE_ABSTRACT = ("Purpose: The currently used prognostic models for patients with nonmetastatic clear cell renal "
                    "cell carcinoma are based on clinicopathologic features and might be improved by adding molecular "
                    "markers. " * 3)


def _funding(*funders):
    blocks = "".join(f'<div class="_7P-Hc"><h3 class="jSqDa" dir="ltr">{f}</h3></div>' for f in funders)
    return f'<div class="BMOMY"><h2 class="EbFsx">Funding</h2>{blocks}</div>'


def _page(funding="", app=APP, citation_authors=False, names=NAMES):
    metas = "".join(f'<meta data-rh="true" content="{n}" name="DataCite.contributor"/>' for n in names)
    if citation_authors:
        metas += "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
        metas += f'<meta name="citation_title" content="{TITLE}"/>'
    byline = "".join(f'<span>, <span dir="ltr">{n}</span></span>' for n in names)
    return (f'<html><head><title>Item - {TITLE} - figshare</title>{app}{metas}'
            f'<meta data-rh="true" content="{TITLE}" name="DataCite.title"/>'
            f'<meta data-rh="true" content="{LEGEND}" name="abstract"/>'
            f'<meta data-rh="true" content="{LEGEND}" property="og:description"/>'
            '<meta data-rh="true" content="figshare" property="og:site_name"/></head><body>'
            f'<h2>{TITLE}</h2><span>authored by<span>{byline}</span></span>'
            f'<div class="BMOMY _1xhaQ" dir="ltr"><p>{LEGEND}</p></div>{funding}'
            '<div class="BMOMY"><h2 class="suPDM">History</h2></div>'
            f'<div><div class="Bpari"><h2 class="fNQzp">ARTICLE ABSTRACT</h2><span dir="ltr">{ARTICLE_ABSTRACT}'
            '</span></div></div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return Figshare(BeautifulSoup(html, "lxml")).parse()


def test_funding_section_lists_each_funder_on_its_own_line():
    html = _page(_funding("Skin Diseases Research Center", "VA Merit Award", "NIH"))
    assert _raw(html)["funding_statement"] == "Skin Diseases Research Center\nVA Merit Award\nNIH"
    assert _parse(html)["funding_statement"] == "Skin Diseases Research Center\nVA Merit Award\nNIH"


def test_grant_block_keeps_its_funding_body_and_drops_the_link():
    grant = ('<div class="_7P-Hc"><h3 class="jSqDa" dir="ltr">National Institute of Neurological Disorders and Stroke '
             '(NINDS)</h3><p class="VMRyn" dir="ltr">United States Department of Health and Human Services</p>'
             '<a aria-label="Learn more about the name of the funding" class="lPlX1" '
             'href="https://app.dimensions.ai/details/grant/grant.7582160" target="_blank">Find out more...</a></div>')
    html = _page(_funding("The Schnuck Family Fund").replace('<h2 class="EbFsx">Funding</h2>',
                                                             '<h2 class="EbFsx">Funding</h2>' + grant))
    assert _parse(html)["funding_statement"] == (
        "National Institute of Neurological Disorders and Stroke (NINDS), United States Department of Health and Human "
        "Services\nThe Schnuck Family Fund")


def test_one_short_funder_is_still_a_funding_statement():
    assert _parse(_page(_funding("NIH")))["funding_statement"] == "NIH"


def test_no_funding_section_no_statement():
    out = _parse(_page())
    assert out["funding_statement"] is None
    assert out["acknowledgments"] is None


def test_byline_from_datacite_tags_when_no_citation_author_tags():
    out = _parse(_page(_funding("NIH")))
    assert [a["name"] for a in out["authors"]] == NAMES
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in out["authors"])


def test_citation_author_byline_kept_as_the_generic_reader_gives_it():
    out = _parse(_page(_funding("NCI", "NIH"), citation_authors=True))
    assert [a["name"] for a in out["authors"]] == NAMES
    assert out["funding_statement"] == "NCI\nNIH"


def test_parent_articles_abstract_is_never_the_items():
    # "ARTICLE ABSTRACT" under Related Materials belongs to the article this item supplements
    out = _parse(_page(_funding("NIH")))
    assert "prognostic models" not in (out["abstract"] or "")


def test_figshare_mark_only_in_the_body_is_not_claimed():
    # a journal article page (Silverchair, Springer Nature) that links to its supplementary data on figshare
    html = ('<html><head><meta name="citation_title" content="An article"/>'
            '<meta name="citation_author" content="Doe, Jane"/></head><body>'
            '<a href="https://aacr.figshare.com/collections/Data_from_X/6548656">Data from figshare</a>'
            '<meta content="figshare" name="application-name"/>'
            + _funding("National Cancer Institute") + '</body></html>')
    parser = Figshare(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_other_platform_application_name_is_not_claimed():
    html = _page(_funding("NIH"), app='<meta name="application-name" content="Nature"/>')
    parser = Figshare(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_with_no_creators_is_not_read():
    parser = Figshare(BeautifulSoup(_page(_funding("NIH"), names=[]), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
