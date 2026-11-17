"""Australian Centre for Geomechanics paper pages, papers.acg.uwa.edu.au (oxjob #2339).

Markup cut down from stored pages of the site (17 Nov 2026). The parser adds the page's reference list; authors and
abstract stay what the generic parser read before it.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.acg_papers import ACGPapers

URL = "https://doi.org/10.36487/ACG_rep/1915_64_Murphy"
OG = '<meta property="og:url" content="https://papers.acg.uwa.edu.au/p/1915_64_Murphy/" />'
ABSTRACT = ("In response to the challenges of population growth and associated economic sustainability, Australian "
            "governments are moving towards more structured and coordinated approaches to regional development, and "
            "this paper presents the proposed repurposing framework and the process of stakeholder engagement.")
ICON = '<span class="glyphicon glyphicon-share" style="margin-left: 20px"></span>'


def _page(reflines, og=OG, publisher="Australian Centre for Geomechanics"):
    lines = "".join(f'\n\t\t  \t\n\t\t\t  <div class="refline">{line}</div>' for line in reflines)
    return (f'<html><head><meta name="citation_authors" content="Murphy, DP; Fromm, J" />'
            f'<meta name="citation_title" content="A repurposing framework" />'
            f'<meta name="citation_abstract" content="{ABSTRACT}" />'
            f'<meta name="citation_publisher" content="{publisher}" />{og}</head><body>'
            f'<h3 class="page-header">A repurposing framework</h3>'
            f'Authors: <a href="/a/10004271">Murphy, DP</a>; <a href="/a/10029859">Fromm, J</a><br/>'
            f'<b>Abstract:</b><br/>{ABSTRACT}<br/><br/><b>References:</b><br/>{lines}<br/><br/></body></html>')


WHOLE = [
    'Bocking, KA &amp; Fitzgerald, P 2012, &lsquo;Management of post-closure liabilities&rsquo;, in AB Fourie &amp; '
    'M Tibbett (eds), Mine Closure 2012, Australian Centre for Geomechanics, Perth, pp. 49&ndash;56.',
    'Commander, LE 2020, &lsquo;Seedling recruitment&rsquo;, Plant and Soil, vol. 457, pp. 113&ndash;129, '
    f'<a href="https://doi.org/10.1007/s11104-019-04081-2" target="_blank">{ICON}</a>',
    f'Department of Water 2013, Strategic Policy 2.09, Perth, viewed 24 August 2018, '
    f'<a href="https://www.water.wa.gov.au/policy.pdf" target="_blank">{ICON}</a>',
    'van Gool, D, Tille, P &amp; Moore, G 2005, Land Evaluation Standards, Department of Agriculture, Perth.',
]


def _refs(html):
    return ACGPapers(BeautifulSoup(html, "lxml")).parse()


def test_reference_list_is_read_whole_in_page_order():
    parsed = _refs(_page(WHOLE))
    assert [r["position"] for r in parsed["references"]] == [1, 2, 3, 4]
    assert parsed["references"][0]["raw"].startswith("Bocking, KA & Fitzgerald, P 2012, ‘Management")
    assert parsed["references"][3]["raw"].startswith("van Gool, D")
    assert parsed["references_complete"] is True


def test_doi_comes_from_the_entrys_doi_link_only():
    refs = _refs(_page(WHOLE))["references"]
    assert [r["doi"] for r in refs] == [None, "10.1007/s11104-019-04081-2", None, None]


def test_lines_that_cannot_open_a_reference_join_the_one_before():
    lines = [WHOLE[0],
             'Coulon, C, White, JT &amp; Lemieux, J 2024a, &lsquo;Pumping optimization&rsquo;, Hydrology and Earth '
             'System Sciences, vol. 28, no. 1,',
             f'pp. 303&ndash;319, <a href="https://doi.org/10.5194/hess-28-303-2024" target="_blank">{ICON}</a>',
             'Mäkitaavola, K &amp; Dudley, J 2016, &lsquo;Application of InSAR&rsquo;, in HS Mitri (ed.)',
             '(eds), Proceedings of the 3rd International Symposium on Mine Safety, Montreal, pp. 133&ndash;139.',
             f'<a href="https://www.example.org/report.pdf" target="_blank">{ICON}</a>',
             WHOLE[3]]
    parsed = _refs(_page(lines))
    raws = [r["raw"] for r in parsed["references"]]
    assert len(raws) == 4
    assert raws[1].endswith("vol. 28, no. 1, pp. 303–319,")
    assert parsed["references"][1]["doi"] == "10.5194/hess-28-303-2024"
    assert raws[2].endswith("(ed.) (eds), Proceedings of the 3rd International Symposium on Mine Safety, Montreal, "
                            "pp. 133–139.")
    assert parsed["references_complete"] is True


def test_an_entry_broken_without_a_sign_makes_the_list_not_whole():
    # "Booklet, January 2006, ..." carries a year and a capital, so it reads as an entry: only the list's order
    # (D before B) shows it is the rest of the entry before it
    lines = ['Department of Industry (2006) Overview, Leading Practice Sustainable Development Program.',
             'Booklet, January 2006, Australian Government, Canberra.', WHOLE[3]]
    assert _refs(_page(lines))["references_complete"] is False


def test_an_entry_with_no_year_or_left_open_makes_the_list_not_whole():
    assert _refs(_page([WHOLE[0], "Framework for Mine Closure.", WHOLE[3]]))["references_complete"] is False
    left_open = ['Slatter, PT &amp; Wasp, EJ (2000) The laminar/turbulent transition in large pipes, 10th '
                 'International Conference on Transport and']
    assert _refs(_page(left_open))["references_complete"] is False


def test_parse_page_keeps_authors_and_abstract_and_adds_the_list():
    out = parse_page(_page(WHOLE).encode(), "doi", URL)
    before = parse_page(_page([]).encode(), "doi", URL)  # no reference list: the parser does not take the page
    assert out["authors"] == before["authors"]
    assert out["abstract"] == before["abstract"] == ABSTRACT
    assert len(out["references"]) == 4
    assert out["references_complete"] is True


def test_proceedings_of_other_publishers_on_the_site_are_read():
    parsed = _refs(_page(WHOLE, publisher="Gecamin Publications"))
    assert len(parsed["references"]) == 4


def test_a_page_of_another_site_with_the_same_markup_is_not_claimed():
    other = '<meta property="og:url" content="https://www.example-geomechanics.org/p/1915_64_Murphy/" />'
    parser = ACGPapers(BeautifulSoup(_page(WHOLE, og=other), "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    out = parse_page(_page(WHOLE, og=other).encode(), "doi", URL)
    assert not out["references"]
