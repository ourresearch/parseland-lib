"""Open Monograph Press (PKP's book platform) book and chapter pages (oxjob #2289).

Markup cut down from stored OMP pages (17 Nov 2026, #2289 template sample: OMP 3.1 to 3.5, 139 sites). Every page carries
<meta name="generator" content="Open Monograph Press 3.x"> and citation_author tags, usually without
citation_author_institution, so the meta-tag parser reads the byline and no affiliations. The page prints each author's
affiliation in its "item authors" block, two ways: OMP 3.1 / 3.4 themes give each author a sub_item with a div.label
(name) and div.value (affiliation); OMP 3.3 prints inline "<span class="label">Name</span>, <span
class="value">Affiliation</span>;". The block may write a name differently from the tag (family name first, or a
shorter public name), and may list only the volume editors or a chapter's authors.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.omp import OpenMonographPress

URL = "https://press.example.edu/index.php/press/catalog/book/352"
GENERATOR = '<meta name="generator" content="Open Monograph Press 3.3.0.13">'
ABSTRACT = "Este libro reúne experiencias de investigación en educación superior y su relación con el currículo. " * 4


def _page(names, block, generator=GENERATOR, institutions=None):
    metas = ""
    for i, n in enumerate(names):
        metas += f'<meta name="citation_author" content="{n}"/>'
        if institutions:
            metas += f'<meta name="citation_author_institution" content="{institutions[i]}"/>'
    return (f'<html><head>{generator}<meta name="citation_title" content="Un libro"/>{metas}'
            f'<meta name="citation_abstract" content="{ABSTRACT}"/></head><body><div class="page page_book">'
            f'<div class="obj_monograph_full"><h1 class="title">Un libro</h1><div class="row"><div class="main_entry">'
            f'{block}<div class="item abstract"><h2 class="label">Synopsis</h2><div class="value"><p>{ABSTRACT}</p>'
            f'</div></div></div></div></div></div></body></html>')


def _sub_items(entries):
    """OMP 3.1 / 3.4: one sub_item per author, the affiliation in div.value."""
    items = ""
    for name, aff in entries:
        value = f'<div class="value">{aff}</div>' if aff else ""
        items += (f'<div class="sub_item"><div class="label">{name}</div>{value}<span class="orcid">'
                  f'<a href="https://orcid.org/0000-0002-9163-3991">https://orcid.org/0000-0002-9163-3991</a></span></div>')
    return f'<div class="item authors"><h2 class="pkp_screen_reader">Authors</h2>{items}</div>'


def _inline(entries):
    """OMP 3.3: "<span class="label">Name</span>, <span class="value">Affiliation</span>; ..."."""
    parts = [f'<span class="label">{n}</span>' + (f', <span class="value">{a}</span>' if a else "") for n, a in entries]
    return f'<div class="item authors"><h2 class="pkp_screen_reader">Autores/as</h2>{"; ".join(parts)}</div>'


def _parsed(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_sub_item_affiliation_is_read():
    html = _page(["Jale Akgol"], _sub_items([("Jale Akgol", "Afyonkarahisar Health Sciences University / Türkiye")]))
    assert _parsed(html) == [("Jale Akgol", ["Afyonkarahisar Health Sciences University / Türkiye"])]


def test_inline_spans_shorter_public_names_and_an_author_without_one():
    names = ["Marta Ruiz de la Vega", "Iván Gómez", "Lucía Pardo Ortiz"]
    block = _inline([("Marta Ruiz", "Unicatólica-Cali"), ("Iván Gómez", "Universidad del Valle"), ("Lucía Pardo", "")])
    assert _parsed(_page(names, block)) == [("Marta Ruiz de la Vega", ["Unicatólica-Cali"]),
                                            ("Iván Gómez", ["Universidad del Valle"]), ("Lucía Pardo Ortiz", [])]


def test_family_name_first_in_the_block():
    names = ["Alexandra Álvarez", "Juan Carlos Lazo-Galán", "Diego Larriva-Calle"]
    block = _sub_items([("Álvarez Alexandra", "Universidad del Azuay, Ecuador"),
                        ("Lazo-Galán Juan Carlos", "Universidad del Azuay, Ecuador"), ("Larriva-Calle Diego", "")])
    assert _parsed(_page(names, block)) == [("Alexandra Álvarez", ["Universidad del Azuay, Ecuador"]),
                                            ("Juan Carlos Lazo-Galán", ["Universidad del Azuay, Ecuador"]),
                                            ("Diego Larriva-Calle", [])]


def test_role_values_are_not_affiliations():
    block = ('<div class="item authors"><div class="sub_item"><div class="label">Laura P. Z. Izarra</div>'
             '<div class="value">(Author)</div><div class="value">Universidade de São Paulo</div></div>'
             '<div class="sub_item"><div class="value"><div class="role">Volume editor</div>'
             '<div class="label">Denis Yuni</div></div></div></div>')
    assert _parsed(_page(["Laura P. Z. Izarra", "Denis Yuni"], block)) == [
        ("Laura P. Z. Izarra", ["Universidade de São Paulo"]), ("Denis Yuni", [])]


def test_chapter_block_adds_affiliations_and_never_authors():
    # a chapter page whose tags list the whole book's authors, and a block listing the chapter's two
    names = ["Alla Cherep", "Iryna Dashko", "Olga Zborovska", "Oksana Hamova"]
    block = _sub_items([("Iryna Dashko", "Zaporizhzhia National University, Ukraine"),
                        ("Oksana Hamova", "Zaporizhzhia National University, Ukraine")])
    assert _parsed(_page(names, block)) == [("Alla Cherep", []), ("Iryna Dashko", ["Zaporizhzhia National University, Ukraine"]),
                                            ("Olga Zborovska", []), ("Oksana Hamova", ["Zaporizhzhia National University, Ukraine"])]
    # an editor the tags do not list is not added
    block = _sub_items([("Andrej Novak (ed)", "Univerza v Mariboru")])
    assert _parsed(_page([], block)) == []


def test_ambiguous_name_is_left_alone():
    names = ["Ana Silva", "Ana Silva Costa"]
    block = _sub_items([("Ana Silva", "Universidade Federal do Piauí")])
    page = _page(names, block)
    assert _parsed(page) == [("Ana Silva", ["Universidade Federal do Piauí"]), ("Ana Silva Costa", [])]
    block = _sub_items([("Silva", "Universidade Federal do Piauí")])  # one word names no one
    assert _parsed(_page(names, block)) == [("Ana Silva", []), ("Ana Silva Costa", [])]


def test_institution_tags_win():
    block = _sub_items([("Jale Akgol", "Block University")])
    html = _page(["Jale Akgol"], block, institutions=["Tag University"])
    assert _parsed(html) == [("Jale Akgol", ["Tag University"])]
    assert not OpenMonographPress(BeautifulSoup(html, "lxml")).authors_found()


def test_abstract_is_the_meta_tag_readers():
    html = _page(["Jale Akgol"], _sub_items([("Jale Akgol", "Afyonkarahisar Health Sciences University")]))
    assert parse_page(html.encode(), "doi", URL)["abstract"].startswith("Este libro reúne")


def test_ojs_page_with_the_same_markup_is_not_claimed():
    # Open Journal Systems, PKP's journal platform, prints a look-alike "item authors" block
    block = _sub_items([("Jale Akgol", "Afyonkarahisar Health Sciences University")])
    html = _page(["Jale Akgol"], block, generator='<meta name="generator" content="Open Journal Systems 3.3.0.10">')
    parser = OpenMonographPress(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
