"""OSTI.GOV record pages (www.osti.gov/biblio/<id>), the landing pages of DOE technical reports (oxjob #2210).

Markup is cut down from stored pages of the swarm pilot's osti.gov sample (13 Nov 2026). Before this parser the generic
one read these pages from the citation_* meta tags; it skips an abstract of 200 characters or less, and it reads
nothing of the record's funding rows ("Sponsoring Organization", "DOE Contract Number"), which name the work's funder.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.osti import OSTIBiblio

URL = "https://www.osti.gov/biblio/3020174"
TITLE = "Selection of LAW Glasses for FY 2016 SPFT Testing"
LONG_ABSTRACT = ("The primary objective of this work is to provide recommendations for glasses to be used for Single "
                 "Pass Flow Through (SPFT) testing in FY 2016. Since LAW glass formulation development is ongoing, it "
                 "is anticipated that this report will be revised on an annual basis.")
SHORT_ABSTRACT = ("Dielectric heating was explored as a means of calcining gypsum to produce stucco, the wallboard "
                  "precursor, with lower water demand and therefore lower drying energy.")
METADATA = """<section id="section-metadata" class="biblio-section"><div class="biblio-detail">
<dl class="dl-horizontal small clearfix"><dt>Research Organization:</dt>
<dd itemprop="sourceOrganization">Hanford Site (HNF)</dd></dl>
<dl class="dl-horizontal small clearfix"><dt>Sponsoring Organization:</dt>
<dd itemprop="sourceOrganization">USDOE Office of Environmental Management (EM)</dd></dl>
<dl class="dl-horizontal small clearfix"><dt>DOE Contract Number:</dt><dd>AC27-01RV14136</dd></dl>
<dl class="dl-horizontal small clearfix"><dt>OSTI ID:</dt><dd>3020174</dd></dl>
</div></section>"""
BYLINE = """<span class="author-link"><a href="#"><span class="author" itemprop="author">Muller, Isabelle S</span>
&nbsp;<sup class="text-muted">[1]</sup></a>; </span>
<span class="author-link"><a href="#"><span class="author" itemprop="author">Pegg, Ian L</span>
&nbsp;<sup class="text-muted">[1]</sup></a></span>
<ol class="affiliation_list affiliation_list_auth"><li>The Catholic Univ. of America, Washington, DC (United States)</li></ol>"""
AUTHOR_METAS = """<meta name="citation_author" content="Muller, Isabelle S" />
<meta name="citation_author_institution" content="The Catholic Univ. of America, Washington, DC (United States)" />
<meta name="citation_author" content="Pegg, Ian L" />
<meta name="citation_author_institution" content="The Catholic Univ. of America, Washington, DC (United States)" />"""


def _page(abstract=LONG_ABSTRACT, metadata=METADATA, byline=BYLINE, metas=AUTHOR_METAS,
          canonical="https://www.osti.gov/biblio/3020174"):
    return f"""<html><head><link rel="canonical" href="{canonical}" />
<meta name="citation_title" content="{TITLE}" />{metas}
<meta name="citation_doi" content="10.2172/3020174" /></head><body><div id="main-body">
<div itemprop="mainEntity" class="biblio-page" data-ostiid="3020174" data-doi="10.2172/3020174">
<section id="section-details" class="biblio-section"><h1><span itemprop="name headline">{TITLE}</span></h1>
{byline}
<div class="row"><div id="metadata-description" class="col-sm-12 mb-2">
<div class="description mb-0 mt-0 trunc trunc-4" id="citation-abstract" itemprop="description">
    {abstract}
</div></div></div></section>
{metadata}</div></div></body></html>"""


def _parse_page(html):
    return parse_page(html.encode(), "doi", URL)


def _parse(html):
    return OSTIBiblio(BeautifulSoup(html, "lxml")).parse()


def test_claims_osti_record_pages():
    assert OSTIBiblio(BeautifulSoup(_page(), "lxml")).is_publisher_specific_parser()


def test_authors_and_affiliations():
    authors = _parse_page(_page())["authors"]
    assert [a["name"] for a in authors] == ["Muller, Isabelle S", "Pegg, Ian L"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["The Catholic Univ. of America, Washington, DC (United States)"]] * 2
    assert not any(a["is_corresponding"] for a in authors)


def test_long_abstract_from_the_visible_block():
    assert _parse_page(_page())["abstract"] == LONG_ABSTRACT


def test_visible_abstract_keeps_ampersands_and_inline_marks():
    # the citation_abstract meta tag escapes '&' twice ("O&amp;M"); the visible block has the text as shown
    abstract = LONG_ABSTRACT + " Loose fasteners lead to increased O&amp;M costs at a luminance of L<sub>0</sub> = 3000 cd/m<sup>2</sup>."
    assert _parse_page(_page(abstract=abstract))["abstract"].endswith("increased O&M costs at a luminance of L0 = 3000 cd/m2.")


def test_short_one_sentence_abstract_is_read():
    assert _parse_page(_page(abstract=SHORT_ABSTRACT))["abstract"] == SHORT_ABSTRACT


def test_short_labels_and_title_repeats_are_not_abstracts():
    for text in ("presentation slides", "Final Technical Report", "Italian Summer Students Final Presentation 2022",
                 "Invited talk at SPIN2025 on the upcoming MOLLER experiment", TITLE):
        assert _parse_page(_page(abstract=text))["abstract"] is None, text


def test_cut_off_abstract_is_not_read():
    assert _parse_page(_page(abstract=LONG_ABSTRACT + " Although salt creep beneficially encapsulates the waste...")
                       )["abstract"] is None


def test_record_without_byline_keeps_its_abstract():
    out = _parse_page(_page(byline="", metas=""))
    assert out["authors"] == [] and out["abstract"] == LONG_ABSTRACT


def test_funding_statement_from_the_funding_rows():
    out = _parse(_page())
    assert out["funding_statement"] == ("Sponsoring Organization: USDOE Office of Environmental Management (EM)\n"
                                        "DOE Contract Number: AC27-01RV14136")
    assert out["acknowledgments"] is None
    assert out["references"] is None and out["references_complete"] is False


def test_funding_statement_on_the_older_full_record_tab():
    older = """<section id="biblio-full" class="tab-content active"><dl>
<dt>Authors: <span class="infotip-show-hidden d-none"></span></dt><dd>Solis-Lemus, Claudia</dd>
<dt>Research Org.: <span class="infotip-show-hidden d-none"></span></dt><dd>Univ. of Wisconsin, Madison, WI</dd>
<dt>Sponsoring Org.: <span class="infotip-show-hidden d-none"></span></dt><dd>USDOE Office of Science (SC)</dd>
<dt>DOE Contract Number: &nbsp;<span class="infotip-show-hidden d-none"></span></dt><dd>SC0021016</dd>
</dl></section>"""
    assert _parse(_page(metadata=older))["funding_statement"] == (
        "Sponsoring Org.: USDOE Office of Science (SC)\nDOE Contract Number: SC0021016")


def test_record_without_funding_rows_has_no_funding_statement():
    assert _parse(_page(metadata=""))["funding_statement"] is None


def test_other_site_with_similar_markup_is_not_claimed():
    html = _page(abstract=SHORT_ABSTRACT, canonical="https://repository.example.edu/biblio/3020174")
    assert not OSTIBiblio(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
    assert _parse_page(html)["abstract"] is None  # the generic parser skips abstracts this short
