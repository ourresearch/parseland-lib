"""EAI's European Union Digital Library (eudl.eu) paper pages: byline affiliations, the starred contact author and the
whole abstract (oxjob #2338).

Markup is cut down from stored eudl.eu pages (#2338, 17 Nov 2026). One template serves the proceedings and the journal
articles: <section id="authors"> holds the byline (<span class="author-list">, each name followed by <sup>N</sup> or
<sup>N,M</sup> and, for the contact author, <sup>,*</sup>), the numbered affiliation list ("1: University ...") and a
"*Contact email: ..." line that explains the star. The citation_author tags give first and last names only ("Sukma
Yunianti" for "Sukma Shinta Yunianti"), there are no institution tags, and the Description tag is the abstract cut at
300 characters, often mid-word; the abstract is printed whole in <section class="full-abstract">. No references,
acknowledgments or funding sections.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.eudl import EUDL

URL = "https://eudl.eu/doi/10.4108/eai.2-12-2022.2328707"
ABSTRACT = ("The regression model is established by using the panel data of 30 provinces in China from 2011 to 2020 "
            "using STATA statistical software. The empirical results show that: the application of information "
            "technology and big data technology in the financial sector have significantly reduced the asset-liability "
            "ratio of enterprises; at the same time, the use of computer technology in finance plays a more remarkable "
            "effect on the asset-liability ratio of enterprises in the eastern region.")
CUT = ABSTRACT[:296]


def _page(byline, affs, contact="*Contact email: first@example.org", metas=("Linying Song", "Heying Song"),
          paragraphs=(ABSTRACT,), title="Digital Finance's Influence on the Asset-Liability Ratio - EUDL"):
    meta_tags = "".join(f'<meta name="citation_author" content="{m}">' for m in metas)
    aff_html = "".join(f"<li>{a}</li>" for a in affs)
    contact_html = f'<section class="corresponding-email">{contact}</section>' if contact else ""
    abstract_html = "".join(f"<p>{p}</p>" for p in paragraphs)
    return (f'<html><head><title>{title}</title><link rel="stylesheet" type="text/css" href="/css/screen.css">'
            f'<meta name="Description" content="{CUT}">'
            f'<meta name="citation_title" content="Digital Finance&#39;s Influence on the Asset-Liability Ratio">'
            f'{meta_tags}<meta name="citation_pdf_url" content="http://eudl.eu/pdf/10.4108/eai.2-12-2022.2328707">'
            f'</head><body><div id="eudl-page"><section id="content"><section id="article">'
            f'<section class="info-and-search"><h1>Digital Finance&#39;s Influence on the Asset-Liability Ratio</h1>'
            f'<section id="authors"><span class="author-list">{byline}</span>'
            f'<ul class="affiliation-list">{aff_html}</ul>{contact_html}</section>'
            f'<section class="full-abstract"><h2>Abstract</h2><div>{abstract_html}</div></section>'
            f'<section class="metas-section"><section class="meta-section"><dl class="main-metadata">'
            f'<dt class="title">Keywords</dt> <dd class="value">digital finance; asset liability ratio</dd></dl>'
            f'</section></section><div class="copyright-block">Copyright © 2022–2025 EAI</div>'
            f'</section></section></section></div></body></html>')


TWO = "Linying  Song<sup>1</sup><sup>,*</sup>, Heying  Song<sup>2</sup>"
TWO_AFFS = ["1: Tianjin University of Technology", "2: Tianjin Normal University"]


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _affs(out):
    return [[a["name"] for a in au["affiliations"]] for au in out["authors"]]


def test_numbered_affiliations_link_per_author():
    out = _parse(_page(TWO, TWO_AFFS))
    assert [a["name"] for a in out["authors"]] == ["Linying Song", "Heying Song"]
    assert _affs(out) == [["Tianjin University of Technology"], ["Tianjin Normal University"]]


def test_starred_author_is_the_contact_author():
    out = _parse(_page(TWO, TWO_AFFS))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_byline_name_wins_over_the_shortened_meta_tag():
    byline = "Sukma Shinta Yunianti<sup>1</sup><sup>,*</sup>"
    out = _parse(_page(byline, ["1: Universitas Tidar, Magelang, Indonesia"], metas=("Sukma Yunianti",)))
    assert [a["name"] for a in out["authors"]] == ["Sukma Shinta Yunianti"]
    assert _affs(out) == [["Universitas Tidar, Magelang, Indonesia"]]
    assert out["authors"][0]["is_corresponding"] is True


def test_several_numbers_and_several_stars():
    byline = ("S. Hiyama<sup>1</sup><sup>,*</sup>, Y. Moritani<sup>1</sup>, T. Suda<sup>1,2</sup><sup>,*</sup>, "
              "T. Shima<sup>3</sup>")
    affs = ["1: Research Laboratories, NTT DoCoMo, Inc.", "2: Information and Computer Science, University of "
            "California, Irvine, CA 92697-3425, USA", "3: Department of Life Sciences, The University of Tokyo"]
    out = _parse(_page(byline, affs, contact="*Contact email: a@example.org, b@example.org",
                       metas=("S. Hiyama", "Y. Moritani", "T. Suda", "T. Shima")))
    assert [a["name"] for a in out["authors"]] == ["S. Hiyama", "Y. Moritani", "T. Suda", "T. Shima"]
    assert _affs(out) == [["Research Laboratories, NTT DoCoMo, Inc."],
                          ["Research Laboratories, NTT DoCoMo, Inc."],
                          ["Research Laboratories, NTT DoCoMo, Inc.",
                           "Information and Computer Science, University of California, Irvine, CA 92697-3425, USA"],
                          ["Department of Life Sciences, The University of Tokyo"]]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, True, False]


def test_author_with_an_empty_number_gets_no_affiliation():
    byline = "Fouad  Aytouna<sup></sup><sup>,*</sup>, Chakkor  Otman<sup>1</sup>, Latrach  Mohamed<sup>2</sup>"
    out = _parse(_page(byline, ["1: ENSATe", "2: ESEO"], metas=("Fouad Aytouna", "Chakkor Otman", "Latrach Mohamed")))
    assert _affs(out) == [[], ["ENSATe"], ["ESEO"]]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_star_without_the_contact_line_marks_no_one():
    out = EUDL(BeautifulSoup(_page(TWO, TWO_AFFS, contact=None), "lxml")).parse()
    assert [a["is_corresponding"] for a in out["authors"]] == [None, None]


def test_whole_abstract_replaces_the_cut_description_tag():
    out = _parse(_page(TWO, TWO_AFFS))
    assert out["abstract"] == ABSTRACT


def test_abstract_paragraphs_join_with_a_space():
    out = EUDL(BeautifulSoup(_page(TWO, TWO_AFFS, paragraphs=("First part.", "Second part.")), "lxml")).parse()
    assert out["abstract"] == "First part. Second part."


def test_empty_abstract_block_gives_none():
    out = EUDL(BeautifulSoup(_page(TWO, TWO_AFFS, paragraphs=()), "lxml")).parse()
    assert out["abstract"] is None


def test_no_back_matter_keys():
    out = EUDL(BeautifulSoup(_page(TWO, TWO_AFFS), "lxml")).parse()
    assert not out.get("references") and not out.get("acknowledgments") and not out.get("funding_statement")


def test_look_alike_page_is_not_claimed():
    # Same byline markup on another site's page (its <title> names that site, not EUDL)
    html = _page(TWO, TWO_AFFS, title="Digital Finance's Influence on the Asset-Liability Ratio | Some Press")
    parser = EUDL(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_eudl_page_without_a_byline_is_not_read():
    html = ('<html><head><title>Proceedings of the 3rd International Conference on Big Data Economy - EUDL</title>'
            '</head><body><section id="content"><h1>Proceedings</h1></section></body></html>')
    parser = EUDL(BeautifulSoup(html, "lxml"))
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()
