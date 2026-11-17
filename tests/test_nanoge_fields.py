"""nanoGe conference abstract pages (nanoge.org proceedings; oxjob #2339).

Markup cut down from stored nanoge.org pages (17 Nov 2026). The page prints the whole abstract in
<div id="abst-content">; its og:description is cut ("...") and no tag holds the whole text, so no reader took it
(0 of 80 sampled pages; about 4,900 of the site's 6,320 works lack an abstract). The parser adds the abstract only:
authors stay what the citation_author tags give (the works already have authors and affiliations), and a reference
list printed at the end of the block is not abstract text.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.nanoge import NanoGe

URL = "https://www.nanoge.org/proceedings/NIPHO19/5bd9c58dd2067c18770eeaba"
P1 = ("Perovskites have emerged as low-cost, high efficiency photovoltaics with certified efficiencies of 22.1% "
      "approaching already established technologies. The perovskites used for solar cells have an ABX<sub>3</sub> "
      "structure where the cation A is methylammonium (MA).")
P2 = ("Recently, double-cation perovskites were shown to have a stable black phase at room temperature.(1,2) Here, we "
      "take the mixing approach further to investigate triple cation perovskites resulting in improved stability.(3)")


def _page(content, og_url=URL, citation_authors=("Saliba, Michael",)):
    metas = "".join(f'<meta property="citation_author" content="{n}"/>' for n in citation_authors)
    og = f'<meta property="og:url" content="{og_url}"/>' if og_url else ""
    return (f'<html><head><meta name="author" content="nanoGe"/>{og}'
            '<meta property="og:description" content="Perovskites have emerged as low-cost, high efficiency su..."/>'
            f'<meta property="citation_title" content="The Versatility of Polyelemental Perovskite Compositions"/>{metas}'
            '<title>nanoGe - NIPHO19 - The Versatility of Polyelemental Perovskite Compositions</title></head><body>'
            '<section id="content"><div id="abstract"><div class="row"><div class="col-xs-12 col-sm-8">'
            '<div id="abst-title">The Versatility of Polyelemental Perovskite Compositions</div>'
            '<div id="abst-authors"><span>Michael Saliba<sup>&nbsp;a</sup></span></div>'
            '<div id="abst-entities"><div><sup>a </sup><span>University of Fribourg, Adolphe Merkle Institute, '
            'Fribourg, Switzerland</span></div></div>'
            '<div id="abst-details">Invited Speaker,<span> Michael Saliba,</span> presentation 001<br/>DOI: '
            '<a href="https://doi.org/10.29363/nanoge.nipho.2019.001">https://doi.org/10.29363/nanoge.nipho.2019.001</a>'
            f'</div><div id="abst-content">{content}</div><div>© Fundació Scito</div></div></div></div></section>'
            '</body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_abstract_is_the_printed_block():
    out = _parse(_page(f"<p>{P1}</p>\n<p>{P2}</p>"))
    assert out["abstract"].startswith("Perovskites have emerged as low-cost")
    assert "ABX3 structure" in out["abstract"]  # a subscript joins its word, as the page reads
    assert out["abstract"].endswith("improved stability.(3)")


def test_numbered_reference_paragraphs_are_cut():
    refs = ("<p>(1) Jeon et al. Nature (2015)</p><p>(2) Lee et al. Advanced Energy Materials (2015)</p>"
            "<p>(3) Saliba et al., Cesium-containing triple cation perovskite solar cells. Energy &amp; Environmental "
            "Science (2016)</p>")
    abstract = _parse(_page(f"<p>{P1}</p><p>{P2}</p>{refs}"))["abstract"]
    assert abstract.endswith("improved stability.(3)")
    assert "Jeon et al" not in abstract


def test_headed_reference_list_is_cut():
    refs = ("<p>&nbsp;</p><p>References:</p><p>[1] B. B. Yu, Z. Chen, Adv. Mater. 2021, 33, 2102055.</p>"
            "<p>[2] S. Shahbazi and E. W.-G. Diau, ACS Energy Lett. 2020, 5, 2508-2511.</p>")
    abstract = _parse(_page(f"<p>{P1}</p><p>{P2}</p>{refs}"))["abstract"]
    assert abstract.endswith("improved stability.(3)")
    assert "References" not in abstract and "Shahbazi" not in abstract


def test_reference_lines_in_one_paragraph_are_cut():
    refs = ("<p>1 Li, Z., et.al. Chem. Mater. 28, 284-292 (2016)<br/>\n2 Lee, J.-W., et.al. Adv. Energy Mater. 5, "
            "1501310 (2015)<br/>\n3 Z, Yuan., et.al. In revision.</p>")
    abstract = _parse(_page(f"<p>{P1}<br/>\n{P2}</p>\n{refs}"))["abstract"]
    assert abstract.endswith("improved stability.(3)")
    assert "Chem. Mater" not in abstract


def test_numbered_points_in_the_abstract_stay():
    text = ("<p>In this talk I will discuss our investigations of 1) the effect of pH and 2) the effect of cation "
            "identity for CO2 reduction on Au, Ag, and Cu electrodes, and what they mean for catalyst design and for "
            "electrolyte engineering.</p><p>&nbsp;</p><p> </p>")
    abstract = _parse(_page(text))["abstract"]
    assert abstract.startswith("In this talk") and abstract.endswith("electrolyte engineering.")


def test_authors_stay_the_citation_tags():
    out = _parse(_page(f"<p>{P1}</p><p>{P2}</p>"))
    assert [a["name"] for a in out["authors"]] == ["Saliba, Michael"]
    assert out["authors"][0]["affiliations"] == []


def test_older_page_without_citation_tags_gets_the_abstract_only():
    out = _parse(_page(f"<p>{P1}</p><p>{P2}</p>", citation_authors=()))
    assert out["authors"] == []
    assert out["abstract"].startswith("Perovskites have emerged")


def test_empty_block_is_not_claimed():
    html = _page("")
    parser = NanoGe(BeautifulSoup(html, "lxml"))
    assert not parser.authors_found()


def test_look_alike_page_from_another_site_is_not_claimed():
    # same block ids on another conference site: not nanoGe's
    html = _page(f"<p>{P1}</p><p>{P2}</p>", og_url="https://www.example-conference.org/proceedings/X/1")
    parser = NanoGe(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["abstract"] is None


def test_new_fields_are_not_returned():
    parsed = NanoGe(BeautifulSoup(_page(f"<p>{P1}</p>"), "lxml")).parse()
    assert not parsed.get("references") and not parsed.get("acknowledgments")
