"""RCIN (rcin.org.pl, the Digital Repository of Scientific Institutes, a dLibra repository) record pages (oxjob #2339).

Markup is cut down from stored rcin.org.pl pages (17 Nov 2026). The generic parser already reads the byline
(citation_author) and the abstract (DC.description) the page shows; the record's "References:" field, a list of the
work's references separated by <br>, was read by nothing. The RCIN parser keeps the generic parser's authors and
abstract and adds that list.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rcin import RCIN

URL = "https://rcin.org.pl/ibl/dlibra/publication/edition/12345"
OG_URL = '<meta property="og:url" content="https://rcin.org.pl/ibl/dlibra/publication/edition/12345?id=12345"/>'
ABSTRACT = ("A population dynamic model for a vole species is developed and analyzed. The model incorporates the fact "
            "that a high number of territorial and mature females inhibits sexual maturation of young females. Density "
            "dependence in litter size and in the interval between litters is assumed.")


def _page(refs_block, og=OG_URL, header='<h3 class="object__subheader">References:</h3>',
          creators=("Kowalska, Anna",), description=ABSTRACT):
    metas = "".join(f'<meta name="citation_author" content="{c}"/>' for c in creators)
    metas += f'<meta name="DC.description" content="{description}"/>' if description else ""
    return (f'<html><head><meta name="Description" content="x"/>{og}{metas}'
            '<meta name="citation_title" content="A title"/></head><body>'
            '<h3 class="object__subheader">Title:</h3><p class="object__desc"><a href="#">A title</a></p>'
            f'{header}<p class="object__desc">{refs_block}</p>'
            '<h3 class="object__subheader">Issue:</h3><p class="object__desc"><a href="#">3</a></p>'
            '</body></html>')


def _span(text, doi=None):
    link = (f'<a href="https://doi.org/{doi}" target="_blank"><img src="/doi-icon.png" alt="DOI"/></a>'
            if doi else "")
    return f"<span>{text}</span>{link}"


NUMBERED = "<br>".join([
    _span("1. A. Y. Aikhenvald, Perspectivism Through Language, Walter de Gruyter, Berlin 2022, s. 425-442.",
          "10.1515/9783110726626-015"),
    _span("2. B. Alberti, Archeologies of Ontology, Annual Review of Anthropology 2016 nr 16, s. 163-179."),
    _span("3. P. Descola, Beyond Nature and Culture, University of Chicago Press, Chicago 2013."),
])


def _parse(html):
    return RCIN(BeautifulSoup(html, "lxml")).parse()


def test_claims_rcin_pages_by_og_url():
    assert RCIN(BeautifulSoup(_page(NUMBERED), "lxml")).is_publisher_specific_parser()


def test_does_not_claim_another_dlibra_library():
    # another dLibra library prints the same metadata markup and fields
    other = '<meta property="og:url" content="https://pbc.gda.pl/dlibra/publication/edition/12345"/>'
    parser = RCIN(BeautifulSoup(_page(NUMBERED, og=other), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_does_not_claim_a_page_naming_rcin_elsewhere():
    page = _page(NUMBERED, og='<meta property="og:url" content="https://example.org/?ref=rcin.org.pl/"/>')
    assert not RCIN(BeautifulSoup(page, "lxml")).is_publisher_specific_parser()


def test_numbered_list_is_read_whole_with_dois():
    out = _parse(_page(NUMBERED))
    refs = out["references"]
    assert [r["position"] for r in refs] == [1, 2, 3]
    assert refs[0]["raw"].startswith("1. A. Y. Aikhenvald, Perspectivism")
    assert refs[0]["doi"] == "10.1515/9783110726626-015"
    assert refs[1]["doi"] is None
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_doi_in_the_entry_text_wins_over_the_icon_link():
    block = "<br>".join([
        _span("1. P. Descola, Perspectivisme et animisme, FMSH, Paris 2009. https://doi.org/10.60527/f1nn-ja24 (22.08.2024)",
              "10.7208/chicago/9780226145006.001.0001"),
        _span("2. Ph. Descola, Beyond Nature and Culture, Chicago 2013."),
    ])
    assert _parse(_page(block))["references"][0]["doi"] == "10.60527/f1nn-ja24"


def test_search_link_entries_and_doi_lines_join_the_entry_before():
    # IGiPZ journals print each entry as a metadata-search link, and a DOI on its own line after the entry
    link = '<a href="https://rcin.org.pl/igipz//dlibra/metadatasearch?val1=References:x">{}</a>'
    block = "<br>".join([
        link.format("1. Aring J., 2009. Europäische Metropolregionen. Hannover: Verlag der ARL, pp. 10-21."),
        link.format("2. Bański J., 2011. Development of peripheral regions. Geographia Polonica, vol. 84, pp. 5-17."),
        link.format("http://dx.doi.org/10.7163/GPol.2011.2.1 -"),
        link.format("3. Batty M., 2008. Fifty years of urban modeling. Heidelberg: Physica-Verlag, pp. 1-20."),
    ])
    out = _parse(_page(block))
    refs = out["references"]
    assert len(refs) == 3
    assert refs[1]["raw"].endswith("http://dx.doi.org/10.7163/GPol.2011.2.1")
    assert refs[1]["doi"] == "10.7163/GPol.2011.2.1"
    assert out["references_complete"] is True


def test_numbering_gap_or_unnumbered_list_is_not_whole():
    gap = "<br>".join([_span("1. A. Author, A book, Warszawa 2001."), _span("3. B. Author, Another book, Kraków 2002.")])
    assert _parse(_page(gap))["references_complete"] is False
    apa = "<br>".join([_span("Benkő, M. (2015). The lifespan of housing estates. Periodica, 59(4), 1-8."),
                       _span("Bolt, G. (2018). Who is to blame? Urban Studies, 56(5), 1-17.")])
    out = _parse(_page(apa))
    assert len(out["references"]) == 2 and out["references_complete"] is False


def test_dash_lines_and_sub_headings_are_not_entries():
    block = "<br>".join([_span("Bibliografia podmiotowa"), _span("1. J. Kotik, Moje wspomnienia, Warszawa 2019."),
                         _span("-"), _span("Bibliografia przedmiotowa"),
                         _span("1. T. W. Adorno, Minima moralia, Kraków 1999.")])
    out = _parse(_page(block))
    assert [r["raw"][:5] for r in out["references"]] == ["1. J.", "1. T."]
    assert out["references_complete"] is False


def test_content_viewer_details_panel():
    header = '<span class="details__header">References:</span>'
    page = _page(NUMBERED, header=header).replace('class="object__desc">' + NUMBERED,
                                                  'class="details__text ">' + NUMBERED)
    assert len(_parse(page)["references"]) == 3


def test_record_without_references_field():
    page = _page(NUMBERED, header='<h3 class="object__subheader">Description:</h3>')
    out = _parse(page)
    assert out["references"] == [] and out["references_complete"] is False


def test_authors_and_abstract_are_the_generic_readers():
    out = parse_page(_page(NUMBERED, creators=("Buchalczyk, A.", "Korybska, Z.")).encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Buchalczyk, A.", "Korybska, Z."]
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in out["authors"])
    assert out["abstract"] == ABSTRACT
    assert len(out["references"]) == 3 and out["references_complete"] is True


def test_record_with_no_creator_and_no_abstract_is_left_to_the_generic_parser():
    parser = RCIN(BeautifulSoup(_page(NUMBERED, creators=(), description=None), "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
