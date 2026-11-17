"""Gramota Publishing article pages: the gramota.net archive and philology-journal.ru (oxjob #2339).

Markup is cut down from stored pages of 10.30853 DOIs (17 Nov 2026). Two platforms: the old gramota.net archive page
(a table layout styled by gramota.css: an <h2> title, the byline in <b> with the affiliations after it, "Аннотация.",
"Список литературы:" and one <ol>) and the new journal site (meta publisher "Gramota Publishing, LLC": h2#abst,
h2#ref with ol.a-ref-items, div.a-author cards).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.gramota import Gramota

URL = "https://doi.org/10.30853/phil201007"

OLD_HEAD = ('<head><title>Заголовок</title><meta name="author" content="Web developer"/>'
            '<link rel="stylesheet" type="text/css" href="{css}"/></head>')


def _old(byline, abstract=True, refs="<OL><li>Ахманова О. С. Статья // Журнал. 1977. № 3.<li>Виноградов В. В. "
         "Книга. М., 1936.</OL>", css="/gramota.css"):
    abst = ("<tr valign=top><td><DIV align=justify><B>Аннотация.</B> В статье изучаются лингвостилистические основы "
            "построения кинематографической прозы.</DIV></td></tr>") if abstract else ""
    return ("<html>" + OLD_HEAD.format(css=css) + "<body><table><tr><td class=maintext><H1>Архив научных статей</H1>"
            "</td></tr><tr><td class=maintext2><table><tr><td colspan=2><H2 align=center>Заголовок статьи</H2></td></tr>"
            f"<tr valign=top><td align=center width=50%>{byline}</td></tr>{abst}"
            "<tr valign=top><td><B>Ключевые слова и фразы:</B> проза, film scripts.</td></tr>"
            f"<tr><td colspan=2><B>Список литературы:</B> {refs}<BR></td></tr></table></td></tr></table></body></html>")


NEW_HEAD = ('<head><link rel="icon" href="/_assets/icons/phil/favicon.ico"/><title>T</title>'
            '<meta name="author" content="Gramota Publishing, LLC"/>'
            '<meta name="publisher" content="{publisher}"/>'
            '<meta property="og:url" content="https://philology-journal.ru/en/article/phil20240656/fulltext"/></head>')


def _new(publisher="Gramota Publishing, LLC", refs=None, mat=""):
    refs = refs if refs is not None else ("".join(
        f'<li class="a-ref-item" refnum="{i}.">Автор {i}. Работа // Журнал. 2015. № {i}.</li>' for i in (1, 2, 3)))
    return ("<html>" + NEW_HEAD.format(publisher=publisher) + "<body><main><article><header><h1 class=\"a-title-h\">"
            "Texts as a source</h1><ul class=\"a-content-authors\"><li><a href=\"#a1\">M. V. Voronets</a></li>"
            "<li><a href=\"#a2\">I. I. Ivanov</a></li></ul></header><div class=\"a-content\">"
            "<h2 id=\"abst\">Abstract</h2><p class=\"mt-md\">The article examines the problem of sources of formation of "
            "the conceptual sphere.</p>" + mat +
            f"<h2 id=\"ref\">References</h2><ol class=\"a-ref-items mt-md\">{refs}</ol>"
            "<h2 id=\"auth\">Author information</h2>"
            "<div id=\"a1\" class=\"a-author mt-md\"><p class=\"a-author-name\">Maria Vladimirovna Voronets</p>"
            "<p class=\"a-author-affil mt-0\">Altai State Pedagogical University, Barnaul</p></div>"
            "<div id=\"a2\" class=\"a-author mt-md\"><p class=\"a-author-name\">Ivan Ivanovich Ivanov</p>"
            "<p class=\"a-author-sci mt-0\">Dr</p><p class=\"a-author-affil mt-0\">Lomonosov Moscow State University; "
            "Moscow Pedagogical State University</p></div>"
            "<h2 id=\"info\">About this article</h2></div></article></main></body></html>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _raw(html):
    return Gramota(BeautifulSoup(html, parser="lxml", features="lxml")).parse()


# ---- the old gramota.net archive page

def test_old_single_author_and_affiliation():
    out = _parse(_old("<B>Кондратьева&nbsp;Светлана&nbsp;Борисовна</B><BR> Московский педагогический государственный "
                      "университет<br><br><BR>", css="/css/gramota.css"))
    assert [a["name"] for a in out["authors"]] == ["Кондратьева Светлана Борисовна"]
    assert [x["name"] for x in out["authors"][0]["affiliations"]] == ["Московский педагогический государственный университет"]
    assert not out["authors"][0]["is_corresponding"]


def test_old_unlinked_affiliations_go_to_every_author():
    out = _parse(_old("<B>Канарёва&nbsp;Татьяна&nbsp;Николаевна, Уранчимэг&nbsp;Доржсурэн</B><BR>Алтайский "
                      "государственный технический университет<br><br>Монгольский государственный университет; "
                      "Институт философии<br><br><BR>"))
    assert [a["name"] for a in out["authors"]] == ["Канарёва Татьяна Николаевна", "Уранчимэг Доржсурэн"]
    for a in out["authors"]:
        assert [x["name"] for x in a["affiliations"]] == ["Алтайский государственный технический университет",
                                                          "Монгольский государственный университет",
                                                          "Институт философии"]


def test_old_abstract_is_the_annotation_without_its_label():
    out = _parse(_old("<B>Жаркова&nbsp;Ульяна</B><BR>Челябинский государственный университет<br>"))
    assert out["abstract"] == "В статье изучаются лингвостилистические основы построения кинематографической прозы."


def test_old_reference_list_is_whole():
    raw = _raw(_old("<B>Жаркова&nbsp;Ульяна</B><BR>Челябинский государственный университет<br>"))
    assert [r["position"] for r in raw["references"]] == [1, 2]
    assert raw["references"][0]["raw"] == "Ахманова О. С. Статья // Журнал. 1977. № 3."
    assert raw["references_complete"] is True


def test_old_list_with_start_above_one_is_not_whole():
    raw = _raw(_old("<B>Жаркова&nbsp;Ульяна</B><BR>Челябинский государственный университет<br>",
                    refs='<OL start="5"><li>Пятая работа. М., 2001.</OL>'))
    assert raw["references"] and raw["references_complete"] is False


def test_old_page_without_byline_is_not_read():
    html = _old("").replace("<H2 align=center>Заголовок статьи</H2>", "")
    assert not Gramota(BeautifulSoup(html, parser="lxml", features="lxml")).authors_found()


# ---- the new journal site

def test_new_authors_from_author_cards():
    out = _parse(_new())
    assert [a["name"] for a in out["authors"]] == ["Maria Vladimirovna Voronets", "Ivan Ivanovich Ivanov"]
    assert [x["name"] for x in out["authors"][0]["affiliations"]] == ["Altai State Pedagogical University, Barnaul"]
    assert [x["name"] for x in out["authors"][1]["affiliations"]] == ["Lomonosov Moscow State University",
                                                                      "Moscow Pedagogical State University"]


def test_new_abstract():
    assert _parse(_new())["abstract"] == ("The article examines the problem of sources of formation of the "
                                         "conceptual sphere.")


def test_new_references_whole_and_research_materials_left_out():
    mat = ('<h2 id="mat">Research materials</h2><ol class="a-ref-items mt-md">'
           '<li class="a-ref-item" refnum="1.">Источник. Газета. 2000.</li></ol>')
    raw = _raw(_new(mat=mat))
    assert [r["raw"] for r in raw["references"]] == ["Автор 1. Работа // Журнал. 2015. № 1.",
                                                     "Автор 2. Работа // Журнал. 2015. № 2.",
                                                     "Автор 3. Работа // Журнал. 2015. № 3."]
    assert raw["references_complete"] is True


def test_new_references_with_a_gap_are_not_whole():
    refs = "".join(f'<li class="a-ref-item" refnum="{i}.">Работа {i}.</li>' for i in (1, 2, 4))
    raw = _raw(_new(refs=refs))
    assert len(raw["references"]) == 3 and raw["references_complete"] is False


# ---- look-alikes

def test_other_publisher_on_a_similar_platform_is_not_claimed():
    html = _new(publisher="Another Publishing House")
    assert not Gramota(BeautifulSoup(html, parser="lxml", features="lxml")).is_publisher_specific_parser()


def test_page_with_a_gramota_css_in_body_only_is_not_claimed():
    html = ('<html><head><title>x</title><link rel="stylesheet" href="/css/site.css"/></head><body>'
            '<link rel="stylesheet" href="/gramota.css"/><h2>Title</h2><b>Name</b><br>Univ</body></html>')
    p = Gramota(BeautifulSoup(html, parser="lxml", features="lxml"))
    assert not p.is_publisher_specific_parser() and not p.authors_found()
