"""IntechOpen book chapters (www.intechopen.com/chapters/N): authors, affiliations, corresponding author, abstract
(oxjob #2330).

Markup is cut down from stored chapter pages (17 Nov 2026). The chapter's "Author Information" block
(`#section-chapter-and-author`) lists each author as `li.authorsItem` with the name in `h4.author`, a trailing
`<span>*</span>` for the author the "*Address all correspondence to:" note is about, and the affiliations in
`span.position li`. The meta tags carry names only, so before this parser no affiliation was read.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.intechopen import IntechOpen

URL = "https://doi.org/10.5772/intechopen.74136"
OG = '<meta data-vue-meta="ssr" property="og:url" content="https://www.intechopen.com/chapters/60131">'
# a chapter page served without its meta tags still loads the site's own fonts in the head
NO_META_HEAD = ("<style>@font-face{font-family:'Relative Faux';"
                "src:url(//cdnintech.com/web/frontend/www/assets/fonts/relative-faux.eot)}</style>")


def _item(name, affs=(), star=False):
    mark = '<span data-v-7ab7a970>*</span>' if star else "<!---->"
    position = "".join(f"<li>{a}</li>" for a in affs)
    return (f'<li class="authorsItem" data-v-7ab7a970><h4 class="author" data-v-7ab7a970>{name}{mark}</h4> '
            f'<span class="position" data-v-7ab7a970><ul class="list">{position}</ul></span></li>')


def _page(items, note="*Address all correspondence to: grt2@hw.ac.uk", head=OG, names=None, intro=""):
    metas = "".join(f'<meta data-vue-meta="ssr" name="citation_author" content="{n}">' for n in (names or []))
    return (f"<html><head><title>A chapter | IntechOpen</title>{head}{metas}</head><body>{intro}"
            '<div id="section-chapter-and-author" class="info collapsed" data-v-7ab7a970>'
            '<div class="toggle-header"><h2 class="title">Author Information</h2> <a class="title">Show +</a></div>'
            f'<div class="wrap"><ul>{"".join(items)}</ul> <p class="title">{note}</p></div></div>'
            '<div class="reader-body"><div class="section" id="sec_1"><h2 class="heading main-title">1. Introduction'
            "</h2><p>Energy harvesting is a process of converting energy.</p></div></div>"
            '<script>window.__INITIAL_STATE__={"authors":[{"fullName":"Someone Else","institution":'
            '{"name":"Another University"}}]}</script></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


THREE = [_item("Gordon Thomson", ["IMPEE, Heriot-Watt University, UK"], star=True),
         _item("Daniil Yurchenko", ["IMPEE, Heriot-Watt University, UK"]),
         _item("Dimitri V. Val", ["EGIS, Heriot-Watt University, UK"])]


def test_authors_and_affiliations_from_author_information():
    out = _parse(_page(THREE, names=["Gordon Thomson", "Daniil Yurchenko", "Dimitri V. Val"]))
    assert [a["name"] for a in out["authors"]] == ["Gordon Thomson", "Daniil Yurchenko", "Dimitri V. Val"]
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["IMPEE, Heriot-Watt University, UK"], ["IMPEE, Heriot-Watt University, UK"], ["EGIS, Heriot-Watt University, UK"]]


def test_starred_author_is_corresponding():
    out = _parse(_page(THREE))
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_two_affiliations_kept_in_order_and_blank_ones_dropped():
    items = [_item("Christophe Casteleyn", ["Ghent University, Belgium", "University of Antwerp, Belgium"], star=True),
             _item("Jaco Bakker", ["", "Biomedical Primate Research Centre, The Netherlands"])]
    out = _parse(_page(items))
    assert [[x["name"] for x in a["affiliations"]] for a in out["authors"]] == [
        ["Ghent University, Belgium", "University of Antwerp, Belgium"], ["Biomedical Primate Research Centre, The Netherlands"]]


def test_no_star_and_empty_note_marks_no_one():
    # the template prints "*Address all correspondence to:" on every chapter; with no starred name it names nobody
    items = [_item("Miao Qiguang"), _item("Shi Cheng"), _item("Li Weisheng")]
    out = _parse(_page(items, note="*Address all correspondence to:"))
    assert [a["name"] for a in out["authors"]] == ["Miao Qiguang", "Shi Cheng", "Li Weisheng"]
    assert not any(a["is_corresponding"] for a in out["authors"])
    assert not any(a["affiliations"] for a in out["authors"])


def test_starred_author_with_empty_note_is_corresponding():
    # the note explains the star even when the address after it is missing
    items = [_item("N Begum", ["Department of Physics, COMSATS, Pakistan"], star=True),
             _item("F Jabeen", ["Laboratorio Nazionale TASC INFM-CNR, Italy"])]
    out = _parse(_page(items, note="*Address all correspondence to:", head=NO_META_HEAD))
    assert [(a["name"], a["is_corresponding"]) for a in out["authors"]] == [("N Begum", True), ("F Jabeen", False)]
    assert out["authors"][0]["affiliations"] == [{"name": "Department of Physics, COMSATS, Pakistan"}]


def test_a_star_without_the_note_is_not_corresponding():
    out = _parse(_page(THREE, note=""))
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_a_name_listed_twice_is_one_author():
    aff = ["Laboratorio de Toxicología, Universidad Autónoma de San Luis, México"]
    items = [_item("Iván Pérez Maldonado", aff), _item("Fernando Díaz-Barriga", aff), _item("Fernando Díaz-Barriga", aff),
             _item("Lilia Batres Esquivel", aff)]
    out = _parse(_page(items, note="*Address all correspondence to:"))
    assert [a["name"] for a in out["authors"]] == ["Iván Pérez Maldonado", "Fernando Díaz-Barriga", "Lilia Batres Esquivel"]


def test_abstract_is_the_block_headed_abstract():
    intro = ('<div class="intro" data-v-46823712><h2 class="title">Abstract</h2> <div class="body"><p>Dielectric '
             'elastomers are a type of electroactive polymers that can be used as sensors, actuators or energy '
             'harvesters, and the latter is the focus of this review of their mechanical and electrical properties.'
             '</p></div></div>')
    out = _parse(_page(THREE, intro=intro))
    assert out["abstract"].startswith("Dielectric elastomers are a type of electroactive polymers")


def test_book_description_in_the_intro_block_is_not_the_abstract():
    # an introductory chapter's page shows the book's description where other chapters show their abstract
    intro = ('<div class="intro"><h2 class="title">Biogas</h2> <div class="body"><p>This book covers biogas '
             'production from many feedstocks, the process and its upgrading, and the industrial scale-up of plants '
             'in many countries, written by experts in the field.</p></div></div>')
    soup = BeautifulSoup(_page(THREE, intro=intro), "lxml")
    assert IntechOpen(soup).parse()["abstract"] is None


def test_claimed_by_og_url_or_the_sites_assets():
    assert IntechOpen(BeautifulSoup(_page(THREE), "lxml")).is_publisher_specific_parser()
    assert IntechOpen(BeautifulSoup(_page(THREE, head=NO_META_HEAD), "lxml")).is_publisher_specific_parser()


def test_look_alike_page_from_another_site_is_not_claimed():
    other = _page(THREE, head='<meta property="og:url" content="https://www.example-press.org/chapters/60131">')
    parser = IntechOpen(BeautifulSoup(other, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    bare = _page(THREE, head="<style>body{color:red}</style>")
    assert not IntechOpen(BeautifulSoup(bare, "lxml")).authors_found()


def test_book_page_and_old_pdf_chapter_page_are_not_claimed():
    # IntechOpen pages without the chapter's Author Information block (a book's page, an old chapter shown as a PDF)
    book = ('<html><head><meta property="og:url" content="https://www.intechopen.com/books/10783"></head><body>'
            '<div class="authors"><p class="authors__title">Edited by</p><span>Natalia Szejko</span></div></body></html>')
    assert not IntechOpen(BeautifulSoup(book, "lxml")).authors_found()
