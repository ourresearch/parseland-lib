"""John Benjamins catalog pages (benjamins.com/catalog/...), oxjob #2210.

Markup is cut down from stored pages of the site (13 Nov 2026). A chapter of a monograph names its authors only in one
semicolon-separated `citation_authors` meta tag ("Family, Given; ..."), which no parser read, and that tag can also
carry the book's editors, translators or foreword writers. The visible byline under the book title in the title box
names the authors, so a meta name counts only when the byline shows it. Chapters of edited volumes carry
`citation_author` tags and a contributors block with affiliations; their reference list sits in a
"References (N)" tab.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.benjamins import Benjamins

URL = "https://benjamins.com/catalog/xyz.1.c1"


def _page(head, titlebox_byline, body="", og="https://benjamins.com/catalog/xyz.1.c1", variant="in"):
    if variant == "in":
        text = (f'<p><span class="in">In:</span><a class="catalog" href="catalog/xyz.1">A Book Title</a><br/>'
                f'{titlebox_byline}<br/><span class="titleboxinfo"> [<a class="series-link catalog" href="catalog/xyz">'
                f'A Series</a> 1] 2013<br/>► pp. 1–30</span></p>')
    else:
        text = (f'<div class="in">Part of</div><a class="catalog" href="catalog/xyz.1">A Book Title</a><br/>'
                f'{titlebox_byline}<br/><span class="titleboxinfo"> [<a class="series-link catalog" href="catalog/xyz">'
                f'A Series</a> 1] 2000<br/>► pp. 1–30</span>')
    return (f'<html><head><meta property="og:url" content="{og}"/>'
            f'<meta name="citation_publisher" content="John Benjamins Publishing Company"/>{head}</head><body>'
            f'<main id="main-page"><div class="article-main-container"><div class="titlebox"><div class="text">{text}'
            f'</div></div><div class="articleinfo"><div itemprop="name"><h1 class="bktitle">Chapter 1</h1></div>{body}'
            f'</div></div></main></body></html>')


def _authors(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"]]


def _parse(html):
    return Benjamins(BeautifulSoup(html, "lxml")).parse()


CA = '<meta name="citation_authors" content="{}"/>'


def test_monograph_chapter_author_from_citation_authors():
    assert _authors(_page(CA.format("Gironzetti, Elisa"), "Elisa Gironzetti")) == ["Elisa Gironzetti"]


def test_meta_names_the_byline_does_not_show_are_dropped():
    html = _page(CA.format("Casad, Eugene H.; Panther, Klaus-Uwe; Thornburg, Linda L."), "Eugene H. Casad")
    assert _authors(html) == ["Eugene H. Casad"]


def test_several_authors_keep_order_and_particles():
    html = _page(CA.format("Bekkum, Wout J. van; Houben, Jan; Sluiter, Ineke"),
                 "Wout J. van Bekkum, Jan Houben and Ineke Sluiter")
    assert _authors(html) == ["Wout J. van Bekkum", "Jan Houben", "Ineke Sluiter"]


def test_part_of_title_box_and_dagger():
    html = _page(CA.format("Dascal, Marcelo"), "Marcelo Dascal †", variant="part_of")
    assert _authors(html) == ["Marcelo Dascal"]


def test_edited_volume_byline_credits_no_author():
    html = _page(CA.format("Trosborg, Anna"), "Edited by Anna Trosborg")
    assert _authors(html) == []
    assert _authors(_page("", "Edited by Anna Trosborg")) == []


def test_edited_volume_chapter_contributors_with_affiliation_and_abstract():
    head = ('<meta name="citation_author" content="Moran, Pádraic"/>'
            '<meta name="citation_abstract" content="' + "This chapter examines the Latin language. " * 8 + '"/>')
    body = ('<div class="contributors xml"><div class="contribgroup"><div class="contribgroup_members">'
            '<div class="member"><span class="name"><b><a href="catalog/persons/1" itemprop="author">Pádraic Moran</a>'
            '</b></span><span class="pipe"> | </span><span class="affiliation"><a class="rorlink" href="catalog/ror/x">'
            'University of Galway</a></span></div></div></div></div>')
    out = parse_page(_page(head, "Edited by Francesco Stella", body).encode(), "doi", URL)
    assert [(a["name"], [f["name"] for f in a["affiliations"]]) for a in out["authors"]] == [
        ("Pádraic Moran", ["University of Galway"])]
    assert out["abstract"].startswith("This chapter examines the Latin language.")


def test_contributors_in_a_table_of_contents_are_not_authors():
    body = ('<div class="toc-entry"><span class="toc-title">Preface</span><div class="contributors xml">'
            '<div class="contribgroup"><div class="contribgroup_members"><div class="member"><span class="name">'
            'Mushira Eid</span></div></div></div></div></div>')
    assert _authors(_page("", "Edited by Mushira Eid", body)) == []


REF = ('<div class="reference" id="CIT{n}"><span class="refauth"><span class="string-name">Author{n}, A.</span>'
       '</span><span class="refline singleref"> (<span class="refyear">2014</span>). <span class="refsource">Book {n}'
       '</span>. Routledge. {doi}<a href="https://scholar.google.com/scholar_lookup?title=x" target="links">'
       '<span class="google-scholar-logo-container" title="Find on Google Scholar"><svg title="Google Scholar"><desc>'
       'Google Scholar logo with link to Google Scholar</desc></svg></span></a></span></div>')
DOI = ('<span class="doi"><a class="doilink" href="https://doi.org/10.4324%2F9781315759678" target="links" '
       'title="Permanent DOI link: 10.4324/9781315759678"><span class="doi-logo-container"></span></a></span>')


def _refs_tab(summary, n):
    refs = "".join(REF.format(n=i, doi=DOI if i == 2 else "") for i in range(1, n + 1))
    return (f'<details class="toc" name="tab"><summary class="tab">{summary}</summary>'
            f'<section class="ref-list" id="c1-ref-list1"><span class="toc-title">References</span>{refs}'
            f'</section></details>')


def test_reference_list_with_matching_stated_count_is_complete():
    html = _page(CA.format("Boucher, Paul"), "Paul Boucher").replace("</main>", _refs_tab("References (3)", 3) + "</main>")
    out = _parse(html)
    assert [r["position"] for r in out["references"]] == [1, 2, 3]
    assert out["references"][0]["raw"] == "Author1, A. (2014). Book 1. Routledge."
    assert [r["doi"] for r in out["references"]] == [None, "10.4324/9781315759678", None]
    assert out["references_complete"] is True
    assert out["acknowledgments"] is None and out["funding_statement"] is None


def test_reference_list_without_count_or_with_wrong_count_is_not_complete():
    for summary in ("References", "References (5)"):
        html = _page(CA.format("Boucher, Paul"), "Paul Boucher").replace("</main>", _refs_tab(summary, 3) + "</main>")
        out = _parse(html)
        assert len(out["references"]) == 3
        assert out["references_complete"] is False


def test_page_without_reference_list_has_none():
    out = _parse(_page(CA.format("Boucher, Paul"), "Paul Boucher"))
    assert out["references"] is None and out["references_complete"] is False


def test_other_site_with_similar_markup_is_not_claimed():
    for og in ("https://www.jbe-platform.com/content/books/9789027257857", "https://johnbenjamins.com/catalog/x.1"):
        html = _page(CA.format("Gironzetti, Elisa"), "Elisa Gironzetti", og=og)
        assert not Benjamins(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
        assert _authors(html) == []
