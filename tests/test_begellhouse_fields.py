"""Begell House Digital Library pages (oxjob #2338).

Markup cut down from stored pages of dl.begellhouse.com (journal articles; References & Proceedings papers) and
begellhouse.com's ebook platform (edited-volume chapters). The citation_* meta tags give authors and abstract, and
on journal pages each author's institution; proceedings and ebook pages print the affiliations only in the byline
(<i> under each name), and journal pages print their reference list in an <ol> under a REFERENCES title. A "CITED BY"
box in the same markup lists works citing the article and is never the reference list.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.begellhouse import BegellHouse

URL = "https://www.dl.begellhouse.com/references/587c7d3679ede81c,2ef0b2e331dc56a8,3968239b610e3ff7.html"
ABSTRACT = ("Compression ignition engines continue to exist in transport, agriculture, and power generation "
            "applications. While they efficiently convert heat into mechanical work, their thermal efficiency "
            "typically remains limited. This study designs and tests a latent heat storage system on a diesel engine.")


def _head(names, institutions=None, publisher="Begel House Inc.", abstract_tag=False):
    metas = ""
    for i, name in enumerate(names):
        metas += f'<meta name="citation_author" content="{name}">'
        if institutions and institutions[i]:
            metas += f'<meta name="citation_author_institution" content="{institutions[i]}">'
    if abstract_tag:
        metas += f'<meta name="citation_abstract" content="{ABSTRACT}">'
    pub = f'<meta name="citation_publisher" content="{publisher}">' if publisher else ""
    return (f'<html><head><title>A paper - Begell House Digital Library</title>'
            f'<meta name="citation_title" content="A paper">{metas}'
            f'<meta name="citation_doi" content="10.1615/IHMTC-2025.2320">{pub}</head>')


def _dl_byline(entries):
    divs = "".join(f'<div class="article-author"><b>{n}</b>' + (f"<br><i>{a}</i>" if a else "") + "</div>"
                   for n, a in entries)
    return f'<div class="article-authors">{divs}</div>'


def _dl_page(names, entries, institutions=None, refs=None, cited_by=None, publisher="Begel House Inc."):
    body = (f'<h2 class="article-title">A paper</h2>{_dl_byline(entries)}'
            f'<div class="article_abstract"><h3 class="article_abstract-title">ABSTRACT</h3><p>{ABSTRACT}</p></div>')
    if refs is not None:
        items = "".join(f"<li><p>{r}</p></li>" for r in refs)
        body += ('<div class="article-references article-references-hidden"><div class="article-references-title" '
                 f'title="REFERENCES">REFERENCES</div><ol class="article-references_list">{items}</ol></div>')
    if cited_by is not None:
        items = "".join(f"<li><p>{r}</p></li>" for r in cited_by)
        body += ('<div class="article-references article-references-hidden"><div class="article-references-title" '
                 'title="REFERENCES" id="citedby_crossref_citations">CITED BY</div>'
                 f'<ol class="article-references_list">{items}</ol></div>')
    return _head(names, institutions, publisher) + f"<body>{body}</body></html>"


def _ebook_page(meta_names, entries):
    items = "".join(f"<p><strong>{n}</strong><i>{a}</i></p>" for n, a in entries)
    body = (f'<h1 class="main-title">A chapter</h1><div class="common-text"><div class="article-authors-list">{items}'
            f'</div><h3 class="text-title">Abstract</h3><div class="common-text">{ABSTRACT}</div></div>')
    return _head(meta_names, publisher="Begell House", abstract_tag=True) + f"<body>{body}</body></html>"


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _parsed(html):
    return BegellHouse(BeautifulSoup(html, "lxml")).parse()


NAMES = ["Soumya Ranjan  Mohapatra", "Debi Prasad  Sahoo"]
AFF_1 = "Department of Mechanical Engineering, National Institute of Technology, Rourkela, Odisha, India"
AFF_2 = "Department of Mechanical Engineering, Government College of Engineering, Keonjhar, Odisha, India"
REFS = ["Ali, S., Habchi, C., and Harion, J.L., Heat Transfer and Mixing Enhancement by Free Elastic Flaps "
        "Oscillation, Int. J. Heat Mass Transf., vol. 85, pp. 250-264, 2015.",
        "ANSYS Inc., ANSYS Fluent Theory Guide, Release 18.2., USA, 2017.",
        "Barth, T. and Jespersen, D., The Design and Application of Upwind Schemes on Unstructured Meshes, in 27th "
        "Aerospace Sciences Meeting, p. 366, 1989."]


def test_proceedings_byline_gives_affiliations():
    html = _dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], f"{AFF_1}; {AFF_2}   ")])
    authors = _authors(html)
    assert [" ".join(a["name"].split()) for a in authors] == ["Soumya Ranjan Mohapatra", "Debi Prasad Sahoo"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [[AFF_1], [AFF_1, AFF_2]]
    assert parse_page(html.encode(), "doi", URL)["abstract"].startswith("Compression ignition")


def test_institution_tags_are_kept_when_present():
    html = _dl_page(NAMES, [(NAMES[0], None), (NAMES[1], None)], institutions=["Institute A", "Institute B"])
    assert [[x["name"] for x in a["affiliations"]] for a in _authors(html)] == [["Institute A"], ["Institute B"]]


def test_byline_fills_only_authors_without_an_institution_tag():
    html = _dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], AFF_2)], institutions=["Institute A", None])
    assert [[x["name"] for x in a["affiliations"]] for a in _authors(html)] == [["Institute A"], [AFF_2]]


def test_ebook_chapter_byline_matches_inverted_meta_names():
    html = _ebook_page(["Duran , Orlando ", "Batocchio, Antonio "],
                       [("Orlando  Duran ", "Universidade de Passo Fundo, Brazil"),
                        ("Antonio  Batocchio", "UNICAMP, Campinas, Brazil")])
    authors = _authors(html)
    assert len(authors) == 2
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Universidade de Passo Fundo, Brazil"], ["UNICAMP, Campinas, Brazil"]]


def test_corresponding_author_note_still_marks_the_author():
    entries = [(NAMES[0] + ' (Corresponding author <a href="mailto:x@example.edu">x@example.edu</a>)', AFF_1),
               (NAMES[1], AFF_2)]
    authors = _authors(_dl_page(NAMES, entries))
    assert [a["is_corresponding"] for a in authors] == [True, False]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [[AFF_1], [AFF_2]]


def test_reference_list_is_read_whole():
    parsed = _parsed(_dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], AFF_2)], refs=REFS))
    assert [r["raw"] for r in parsed["references"]] == REFS
    assert [r["position"] for r in parsed["references"]] == [1, 2, 3]
    assert parsed["references_complete"] is True
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None


def test_cited_by_box_is_not_the_reference_list():
    citing = ["Rees D.A.S., Comments on heat transfer in a square porous cavity, International Journal of "
              "Numerical Methods for Heat & Fluid Flow, 30, 2, 2020. <a href='http://dx.doi.org/10.1108/HFF-04-2019-0313'>"
              "Crossref</a>"]
    parsed = _parsed(_dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], AFF_2)], cited_by=citing))
    assert parsed["references"] is None and parsed["references_complete"] is False
    parsed = _parsed(_dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], AFF_2)], refs=REFS, cited_by=citing))
    assert len(parsed["references"]) == 3 and parsed["references_complete"] is True


def test_list_starting_past_one_is_not_whole():
    html = _dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], AFF_2)], refs=REFS).replace(
        '<ol class="article-references_list">', '<ol class="article-references_list" start="11">')
    assert _parsed(html)["references_complete"] is False


def test_other_publisher_with_the_same_markup_is_not_claimed():
    html = _dl_page(NAMES, [(NAMES[0], AFF_1), (NAMES[1], AFF_2)], refs=REFS, publisher="Some Other Press")
    parser = BegellHouse(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert all(not a["affiliations"] for a in _authors(html))
