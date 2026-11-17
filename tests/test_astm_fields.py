"""astm.org product pages: the abstract a symposia paper or book chapter prints with no heading (oxjob #2330).

Markup is cut down from stored astm.org pages (17 Nov 2026, the #2330 sample). ASTM's Magento store prints a symposia
paper's or chapter's abstract in the lead block between the title and "Author Information", with no "Abstract"
heading; journal articles head theirs "Abstract", which the parser already read. The asm_international parser claims
the pages by og:url (astm.org) and reads the byline from "Author Information".
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.asm_international import ASMInternational

URL = "https://www.astm.org/stp49373s.html"
OG = '<meta property="og:url" content="https://www.astm.org/stp49373s.html" />'

ABSTRACT_1 = ("Energy use in the United States is heavily reliant on imported fossil fuels. Finding a way to produce "
              "renewable fuels that can replace these fossil fuels will address national security threats.")
ABSTRACT_2 = ("This paper discusses both the near-neutral extraction process and a thermochemical process that can be "
              "utilized in a Kraft pulp mill based biorefinery to produce ethanol and acetic acid.")

AUTHORS = ('<div class="border-top"><h1 class="astm-type-heading--h5 astm-type-heading--h5-bold mb-1">Author Information'
           '</h1><div class="astm-type-body--lead mb-3"><div>Dickerson, Catherine</div><div> <i>Univ. of Maine, Orono, '
           'ME</i> </div></div><div class="astm-type-body--lead mb-3"><div>Rubin, Jonathan</div><div> <i>Univ. of '
           'Maine, Orono, ME</i> </div></div></div>')


def _lead(paragraphs):
    return ('<div class="astm-type-body--lead border-top mt-3 pt-3"><div>' + "".join(f"<p>{p}</p>" for p in paragraphs)
            + "</div></div>")


def _page(middle, authors=AUTHORS, og=OG, badge="SYMPOSIA PAPER"):
    return (f'<html><head>{og}<meta name="citation_publisher" content="ASTM International"/></head><body>'
            f'<div class="col-md-8"><div class="d-flex align-items-center"><span class="badge astm-badge bg-secondary">'
            f'{badge}</span></div><div class="mt-1"><h3 class="astm-type-heading--h3"><b>Bioproducts Process '
            f'Pathways for Kraft Paper Mills</b></h3><a href="https://www.astm.org/stp1477-eb.html">Source</a></div>'
            f'{middle}{authors}</div></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_symposia_paper_abstract_without_heading_is_read():
    out = _parse(_page(_lead([ABSTRACT_1])))
    assert out["abstract"] == ABSTRACT_1
    assert [a["name"] for a in out["authors"]] == ["Dickerson, Catherine", "Rubin, Jonathan"]
    assert out["authors"][0]["affiliations"] == [{"name": "Univ. of Maine, Orono, ME"}]


def test_paragraphs_are_kept_apart():
    out = _parse(_page(_lead([ABSTRACT_1, ABSTRACT_2])))
    assert out["abstract"].split("\n") == [ABSTRACT_1, ABSTRACT_2]


def test_inline_markup_adds_no_spaces():
    html = _page(_lead(["Chemical permeation test methods follow ASTM F739-12e1, <i>Standard Test Method for "
                        "Permeation of Liquids and Gases through Protective Clothing Materials</i>, which "
                        "establishes the test procedure for the resistance of protective equipment to permeation."]))
    assert "Materials, which establishes" in _parse(html)["abstract"]


def test_journal_article_abstract_heading_still_wins():
    headed = ('<div class="mt-4 border-top"><h1 class="astm-type-heading--h5 astm-type-heading--h5-bold mb-0">'
              f'Abstract</h1><div class="row p-1 astm-type-body--lead"><p>{ABSTRACT_2}</p></div></div>')
    assert _parse(_page(headed, badge="Journal"))["abstract"] == ABSTRACT_2


def test_empty_lead_block_gives_no_abstract():
    assert _parse(_page('<div class="astm-type-body--lead border-top mt-3 pt-3"><div></div></div>'))["abstract"] is None


def test_standard_preamble_is_not_an_abstract():
    preamble = ("This Standard of the American Society for Testing and Materials is issued under the fixed "
                "designation D 1159; the number immediately following the designation indicates the year of "
                "original adoption or, in the case of revision, the year of last revision.")
    assert _parse(_page(_lead([preamble])))["abstract"] is None


def test_look_alike_page_from_another_site_is_not_claimed():
    other = '<meta property="og:url" content="https://journals.example.org/article/123" />'
    soup = BeautifulSoup(_page(_lead([ABSTRACT_1]), og=other), "lxml")
    parser = ASMInternational(soup)
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(_page(_lead([ABSTRACT_1]), og=other))["abstract"] != ABSTRACT_1
