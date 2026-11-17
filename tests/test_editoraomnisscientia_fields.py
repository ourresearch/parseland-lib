"""Editora Omnis Scientia (editoraomnisscientia.com.br) chapter and conference-paper pages (oxjob #2339).

Markup is cut down from stored pages of the site (17 Nov 2026). The WordPress theme prints a chapter's authors in its
"Autores" tab (one <li><p> per author) while every citation_author tag repeats one name, and prints the abstract twice:
the Portuguese one unlabelled under the title, the English one after "ABSTRACT:" in the "Descrição" tab. The labels
give the English one. A book's own page ("Autor" tab, "Artigos" tab, catalogue post) is not read by this parser.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.editoraomnisscientia import EditoraOmnisScientia

URL = "https://editoraomnisscientia.com.br/post-artigo/?artigo=6059"
PT = ("Este capítulo apresenta o relato de uma prática pedagógica interdisciplinar desenvolvida no Ensino Médio, que "
      "integrou o Ensino de Química à literatura de cordel como estratégia didático-pedagógica.")
EN = ("This chapter presents an experience report of an interdisciplinary pedagogical practice developed in a public "
      "high school in the state of Paraíba, Brazil, which integrated Chemistry teaching with cordel literature as a "
      "didactic-pedagogical strategy. The results demonstrated significant improvements in academic performance.")
NAMES = ["Marcos Roberto Gomes da Silva", "Patrícia Edióne da Silva"]


def _head(publisher="Editora Omnis Scientia"):
    metas = "".join(f'<meta name="citation_author" content="{NAMES[1]}">' for _ in NAMES)
    return (f'<head><meta name="citation_title" content="67 - CORDEL COMO CAMINHO">{metas}'
            f'<meta name="citation_doi" content="10.47094/978-65-284-0357-8/598-604" />'
            f'<meta name="citation_publisher" content="{publisher}"/>'
            f'<meta name="generator" content="{publisher}"></head>')


def _chapter(abstract=EN, names=NAMES, publisher="Editora Omnis Scientia", tab="Autores"):
    items = "".join(f"<li><p>{n}</p></li>" for n in names)
    return (f"<html>{_head(publisher)}<body class=\"page-template-templatePostArtigo\"><div class=\"pagina\">"
            f"<div class=\"ebook_topo\"><ul><li><img src=\"c.png\"></li><li><h2>67 - CORDEL COMO CAMINHO</h2>"
            f"<span class=\"heading-line\"></span><p>{PT}</p></li></ul></div>"
            f"<div class=\"ebook_footer\"><div class=\"tab-wrap\">"
            f"<label for=\"tab4\">Descrição</label><label for=\"tab5\">{tab}</label>"
            f"<div class=\"tab__content\"><h3>67 - CORDEL COMO CAMINHO</h3>"
            f"<p><strong>Doi:</strong> 10.47094/978-65-284-0357-8/598-604</p>"
            f"<p><strong>PALAVRAS CHAVE:</strong> Ensino de Química. Literatura de Cordel.</p>"
            f"<p><strong>KEYWORDS:</strong> Chemistry Teaching. Cordel Literature.</p>"
            f"<p><strong>ABSTRACT:</strong><br>{abstract}</p></div>"
            f"<div class=\"tab__content\"><h3>{tab}</h3><ul class=\"ul-padrao\">{items}</ul></div>"
            f"</div></div></div></body></html>")


def _book():
    items = "".join(f"<li><p>{n}</p></li>" for n in NAMES + ["Adriana Gradela"])
    return (f"<html>{_head()}<body class=\"single-post\"><div class=\"pagina\"><div class=\"ebook_detalhes\">"
            f"<div class=\"ebook_topo\"><ul><li><img src=\"c.png\"></li><li><div class=\"conteudo-catalogo\">"
            f"<h1>EPIDEMIOLOGIA, VOL 2</h1><div class=\"conteudo-post\"><p>{PT}</p></div></div></li></ul></div>"
            f"<div class=\"ebook_footer\"><div class=\"tab-wrap\"><label>Descrição</label><label>Autor</label>"
            f"<label>Artigos</label><div class=\"tab__content\"><h3>EPIDEMIOLOGIA, VOL 2</h3>"
            f"<p><strong>ISBN:</strong> 978-65-6036-107-2</p></div>"
            f"<div class=\"tab__content\"><h3>Autor</h3><ul class=\"ul-padrao\">{items}</ul></div>"
            f"</div></div></div></div></body></html>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _parser(html):
    return EditoraOmnisScientia(BeautifulSoup(html, "lxml"))


def test_authors_come_from_the_autores_tab_not_the_repeated_meta_tag():
    authors = _parse(_chapter())["authors"]
    assert [a["name"] for a in authors] == NAMES
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in authors)


def test_author_names_have_their_spaces_collapsed():
    authors = _parse(_chapter(names=["Mauricio  Claudio Horta ", "Ana Lima"]))["authors"]
    assert [a["name"] for a in authors] == ["Mauricio Claudio Horta", "Ana Lima"]


def test_abstract_is_the_english_abstract():
    assert _parse(_chapter())["abstract"] == EN


def test_short_english_abstract_is_kept():
    short = "This study had as objective evaluate the use of the CRISPR/Cas9 technique in the context of the COVID-19 pandemic."
    assert _parser(_chapter(abstract=short)).parse()["abstract"] == short


def test_empty_english_abstract_falls_back_to_the_portuguese_one():
    assert _parser(_chapter(abstract="")).parse()["abstract"] == PT


def test_chapter_opening_in_the_abstract_slot_is_not_an_abstract():
    # cut down from a stored chapter page: both copies are the chapter's numbered first section
    pt_body = "1.INTRODUÇÃO<br>A saúde pública brasileira passou por um longo processo histórico de transformações."
    en_body = ("1. INTRODUCTION<br>Brazilian public health underwent a long historical process of transformations until "
               "the formulation and consolidation of the Unified Health System (SUS).")
    html = _chapter(abstract=en_body).replace(PT, pt_body)
    assert _parser(html).parse()["abstract"] is None
    assert _parse(html)["abstract"] is None


def test_structured_abstract_opening_with_a_label_is_kept():
    text = "INTRODUCTION: Accidents involving venomous animals are considered a serious public health problem in Brazil."
    assert _parser(_chapter(abstract=text)).parse()["abstract"] == text


def test_page_shows_no_new_fields():
    out = _parser(_chapter()).parse()
    assert not out.get("acknowledgments") and not out.get("funding_statement") and not out.get("references")


def test_book_page_is_not_read():
    parser = _parser(_book())
    assert parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_same_theme_on_another_publisher_is_not_claimed():
    parser = _parser(_chapter(publisher="Editora Científica Digital"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
