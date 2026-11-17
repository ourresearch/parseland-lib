"""JoVE app pages (app.jove.com, DOI prefix 10.3791), oxjob #2338.

Markup is cut down from stored JoVE pages (17 Nov 2026). The app is a Next.js site: no publisher parser claimed it, so
the generic parser read only what the citation_* tags hold. Author Spotlight videos print a byline with no such tags,
the byline's envelope ("Corresponding author") is never read, Encyclopedia of Experiments videos keep their summary
only in the page's embedded data, and no reference list was read.
"""
import json

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.jove import JoVE

ABSTRACT = ("DNAzyme-based nanomachines for the detection of DNA and RNA sequences are multifunctional structures made "
            "of oligonucleotides. Their functions include tight analyte binding and highly selective recognition.")
VIDEO = ("This video demonstrates a method for obtaining Schwann cell-like cells from multipotent bone marrow stromal "
         "cells. Initially, the cells undergo hypoxia treatment, followed by directed differentiation.")


def _next_data(item_id, domain):
    data = {"props": {"pageProps": {"dehydratedState": {"queries": [
        {"queryKey": ["fetchArticleByDomainId", item_id, "en", 0], "state": {"data": {"domain": domain}}}]}}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


def _author(name, sups, corresponding=False):
    marks = "".join(f'<sup class="chakra-text">{s}</sup>' for s in sups)
    envelope = ('<span title="Corresponding author" class="css-1imvq7c"><svg></svg></span>'
                '<div class="chakra-popover__popper"><section><p>someone@example.org</p></section></div>'
                if corresponding else "")
    return (f'<span class="css-18biwo"><a rel="author" class="chakra-link" href="/author/1/x">'
            f'<span class="chakra-text" data-atm="author-name">{name}</span>{marks}</a>{envelope} , </span>')


def _institution(n, dept, inst):
    dept = f"{dept}, " if dept else ""
    return (f'<a class="chakra-link" href="/institutions/1/x"><sup>{n}</sup><span data-atm="institution-name">'
            f'{dept}<span class="chakra-text">{inst}</span></span>, </a>')


def _page(path, head="", body="", data=""):
    return (f'<html><head><title>JoVE</title><link rel="canonical" href="https://app.jove.com/{path}"/>{head}</head>'
            f'<body><div id="__next">{body}</div>{data}</body></html>')


SPOTLIGHT = _page(
    "v/66461/author-spotlight-advancements-dna-nanosensors",
    body=('<h1>DNAzyme 10-23 - Based Nanomachines for Nucleic Acid Recognition</h1>'
          '<div class="text-article-header-authors-wrapper"><div>'
          + _author("Pavel V. Filatov", ["1"]) + _author("Maria S. Rubel", ["1"], corresponding=True)
          + _author("Dmitry M. Kolpashchikov", ["2"]) + '</div><div>'
          + _institution(1, "", "ITMO University") + _institution(2, "Department of Chemistry", "University of Central Florida")
          + '</div></div><h2>Transcript</h2><p>Hi, my name is Maria.</p>'),
    data=_next_data(66461, {"id": 66461, "overviewContent": f"<p class='jove_content'>{ABSTRACT}</p>",
                            "acknowledgementsContent": "<p class='jove_content'>This work was supported by grant 1.</p>"}))

ENCYCLOPEDIA = _page(
    "v/31038/generating-schwann-cell-like-cells",
    head='<meta name="description" content="297 Views. Source: Tsui, Y., et al. Hypoxic Preconditioning. J. Vis. Exp. (2017)"/>',
    body='<h1>Generating Schwann Cell-Like Cells from Bone Marrow Stromal Cells</h1><h2>Transcript</h2>',
    data=_next_data(31038, {"id": 31038, "overviewContent": (
        "<p class='jove_content'>Source: Tsui, Y., <em>et al.</em> <a href='https://app.jove.com/v/55794'>Hypoxic "
        "Preconditioning of Marrow-derived Progenitor Cells.</a>&#160;<em>J. Vis. Exp. </em>(2017)</p>\n"
        f"<p class='jove_content'>{VIDEO}</p>")}))

REFS = "".join(f"<li>Author{i}, A. Title {i}. <em>J Biol</em>. <strong>{i}</strong> (2), 1-9 (2020).</li>"
               for i in range(1, 6))


def _article(overlay=""):
    metas = ('<meta name="citation_author" content="Shu-xiu Zhu"/>'
             '<meta name="citation_author_institution" content="School of Medicine, Jianghan University"/>'
             '<meta name="citation_author" content="Xue-Fei Hu"/>'
             '<meta name="citation_author_institution" content="School of Medicine, Jianghan University"/>'
             f'<meta name="citation_abstract" content="{ABSTRACT}"/>')
    return _page(
        "t/69340/visualizing-spatiotemporal-dynamics", head=metas,
        body=('<h1>Visualizing Spatiotemporal Dynamics</h1><div class="text-article-header-authors-wrapper"><div>'
              + _author("Shu-xiu Zhu", ["1"]) + _author("Xue-Fei Hu", ["1"], corresponding=True) + '</div><div>'
              + _institution(1, "School of Medicine", "Jianghan University") + '</div></div>'
              '<div class="css-79elbk"><h2 id="acknowledgements">Acknowledgements</h2><div><p>Thanks.</p></div></div>'
              '<div class="css-79elbk"><h2 id="references" data-atm="article-content-label-references">References</h2>'
              f'<div data-atm="article-content-text-references"><ol>{REFS}</ol></div>{overlay}</div>'),
        data=_next_data(69340, {"id": 69340, "overviewContent": f"<p>{ABSTRACT}</p>",
                                "acknowledgementsContent": "<p>This work was supported by grant 82405550.</p>"}))


URL = "https://app.jove.com/v/66461"


def _parse(html):
    return JoVE(BeautifulSoup(html, "lxml")).parse()


def test_spotlight_byline_affiliations_and_corresponding_author():
    out = parse_page(SPOTLIGHT.encode(), "doi", URL)
    assert [a["name"] for a in out["authors"]] == ["Pavel V. Filatov", "Maria S. Rubel", "Dmitry M. Kolpashchikov"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["ITMO University"], ["ITMO University"], ["Department of Chemistry, University of Central Florida"]]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True, False]


def test_spotlight_abstract_from_the_items_own_data():
    assert parse_page(SPOTLIGHT.encode(), "doi", URL)["abstract"] == ABSTRACT


def test_encyclopedia_abstract_drops_the_source_line():
    out = parse_page(ENCYCLOPEDIA.encode(), "doi", "https://app.jove.com/v/31038")
    assert out["abstract"] == VIDEO
    assert out["authors"] == []


def test_another_items_data_is_not_read():
    page = ENCYCLOPEDIA.replace('"id": 31038', '"id": 22973')  # the embedded data of a related video only
    assert _parse(page)["abstract"] is None


def test_article_keeps_meta_authors_and_reads_the_envelope_mark():
    out = parse_page(_article().encode(), "doi", "https://app.jove.com/t/69340")
    assert [a["name"] for a in out["authors"]] == ["Shu-xiu Zhu", "Xue-Fei Hu"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["School of Medicine, Jianghan University"]] * 2
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]
    assert out["abstract"] == ABSTRACT


def test_equal_contribution_star_is_not_a_corresponding_mark():
    page = _article().replace('data-atm="author-name">Shu-xiu Zhu</span>',
                              'data-atm="author-name">Shu-xiu Zhu</span><span class="chakra-text">*</span>')
    assert [a["is_corresponding"] for a in parse_page(page.encode(), "doi", URL)["authors"]] == [False, True]


def test_reference_list_whole():
    out = _parse(_article())
    assert [r["position"] for r in out["references"]] == [1, 2, 3, 4, 5]
    assert out["references"][0]["raw"].startswith("Author1, A. Title 1.")
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None  # left to parse_page's reader


def test_preview_reference_list_is_not_whole():
    overlay = ('<div class="css-ducv57"><div class="css-29y261"></div><p data-atm="article-protected-message-overlay">'
               'Access restricted. Please log in or start a trial to view this content.</p></div>')
    out = _parse(_article(overlay))
    assert len(out["references"]) == 5
    assert out["references_complete"] is False
    assert _parse(_article('<div class="css-ducv57"><div></div></div>'))["references_complete"] is False


def test_jove_wordpress_page_and_other_next_sites_are_not_claimed():
    wordpress = ('<html><head><link rel="canonical" href="https://www.jove.com/t/60939/laser-capture"/>'
                 '<meta name="citation_author" content="Andrea Comba"/></head><body><h1>Laser</h1></body></html>')
    other = SPOTLIGHT.replace("https://app.jove.com/", "https://app.example.com/")
    for page in (wordpress, other):
        parser = JoVE(BeautifulSoup(page, "lxml"))
        assert not parser.is_publisher_specific_parser()
        assert not parser.authors_found()


def test_empty_app_shell_is_not_read():
    shell = _page("v/67814/heat-tolerance", body='<div id="root"></div>')
    assert not JoVE(BeautifulSoup(shell, "lxml")).authors_found()
