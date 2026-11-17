"""Classic SciELO sites other than scielo.br (oxjob #2289, template scielo-intl).

scielo.cl, scielo.isciii.es, scielo.org.za, scielo.pt, pepsic.bvsalud.org and ~30 more sites still run SciELO's classic
platform (article pages at /scielo.php?script=sci_arttext&pid=...). No publisher parser claimed them, so the
citation_author meta tags won and marked no corresponding author, though the page names one in a note ("Correspondencia:
Dr. X", "Dirección para correspondencia: X", "Correspondence : X", "Autor correspondiente: X"). Pages built from the
article's XML also print the whole citation_author list twice. Markup is cut down from the template's stored pages
(sample of 17 Nov 2026).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.scielo import SciELOClassic

URL = "https://doi.org/10.4067/s0034-98872013000200013"
CANONICAL = ('<link rel="canonical" href="http://www.scielo.cl/scielo.php?script=sci_arttext&amp;'
             'pid=S0034-98872013000200013">')
FULLTEXT = ('<meta name="citation_fulltext_html_url" content="http://scielo.isciii.es/scielo.php?script=sci_arttext&amp;'
            'pid=S0376-78922011000400007&amp;lng=en&amp;nrm=iso&amp;tlng=en">')


def _metas(authors):
    out = ""
    for name, *affs in authors:
        out += f'<meta name="citation_author" content="{name}">'
        out += "".join(f'<meta name="citation_author_institution" content="{a}">' for a in affs)
    return out


def _page(authors, body, head=CANONICAL):
    return (f'<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">{head}'
            f'<meta name="citation_title" content="A title">{_metas(authors)}</head><body><div class="content">'
            f'<div id="toolBox"><h2 id="toolsSection">Services on Demand</h2></div><h4 id="doi">10.4067/x</h4>'
            f'<div class="index,es"><!--version=html-->{body}</div></div></body></html>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _corr(html):
    return [a["name"] for a in _authors(html) if a["is_corresponding"]]


CHILE = [("Cuello F, Mauricio", "Pontificia Universidad Católica de Chile, Santiago, Chile"),
         ("Kato C, Sumie", "Pontificia Universidad Católica de Chile, Santiago, Chile")]
CHILE_BYLINE = ('<p><b>Mauricio Cuello F.<sup>1</sup>, Sumie Kato C.<sup>1a</sup></b></p>'
                '<p><sup>1</sup>Unidad de Oncología, Facultad de Medicina, Pontificia Universidad Católica de Chile.</p>'
                '<p><a href="#back">Correspondencia a:</a></p><hr><p><b>ABSTRACT</b></p><p><i>This review explores the '
                'evidence supporting a potential benefit of statins in cancer.</i></p>')


def test_correspondence_note_at_the_end_marks_that_author():
    body = CHILE_BYLINE + ('<p>Recibido el 4 de abril de 2012. Fuente de financiamiento: FONDECYT 1080163.</p>'
                           '<p><a name="back"></a>Correspondencia: Dr. Mauricio Cuello División de Obstetricia y '
                           'Ginecología Facultad de Medicina. Lira 85 5° piso, Santiago, Chile.</p>')
    authors = _authors(_page(CHILE, body))
    assert [(a["name"], a["is_corresponding"]) for a in authors] == [
        ("Cuello F, Mauricio", True), ("Kato C, Sumie", False)]


def test_direccion_para_correspondencia_on_a_page_stored_as_mojibake():
    # scielo.isciii.es pages stored with their UTF-8 read as Latin-1: names and notes both read 'Ã³' for 'ó'
    authors = [("CenturiÃ³n, P.",), ("Cuba, J.L.",), ("Noriega, A.",)]
    body = ('<p><b>CenturiÃ³n, P.*, Cuba, J.L.**, Noriega, A.***</b></p><p>* Cirujano PlÃ¡stico.<br>** MÃ©dico '
            'Cirujano.<br>*** Interno de Medicina.<br>PrÃ¡ctica Privada. ClÃ­nica Montesur. Lima. PerÃº.</p>'
            '<p>Una fibra de 600 μm.</p>'
            '<p><a href="#back">DirecciÃ³n para correspondencia</a></p><p>RESUMEN La disponibilidad ...</p>'
            '<p><a name="back"></a>DirecciÃ³n para correspondencia: Dr. Patricio CenturiÃ³n Av. El Polo 505, '
            'Santiago de Surco - Lima, PerÃº e-mail: pc@example.com</p>')
    assert _corr(_page(authors, body, FULLTEXT)) == ["CenturiÃ³n, P."]


def test_spanish_autor_correspondiente_note():
    authors = [("Cabral, Dennis",), ("Ramírez, Marcelo",), ("Martinez, Edith",)]
    body = ('<p>Recibido: 12 de Septiembre de 2019; Aprobado: 10 de Enero de 2020</p><p>Autor correspondiente: Dr. '
            'Marcelo Sebastián Ramírez Romero. Email: m@example.com</p>')
    assert _corr(_page(authors, body)) == ["Ramírez, Marcelo"]


def test_english_correspondence_note():
    authors = [("Teffo, M",), ("Earl, A",), ("Zuidgeest, M H P",)]
    body = ('<p>M Teffo; A Earl; M H P Zuidgeest</p><p><a href="#back">Correspondence</a></p><p>ABSTRACT ...</p>'
            '<p><a name="back"></a>Correspondence : M Teffo Transnet Group Capital 9 Country Estate Drive Midrand</p>')
    assert _corr(_page(authors, body)) == ["Teffo, M"]


def test_note_with_only_an_address_or_an_email_marks_no_one():
    authors = [("Casariego, Z. J.",), ("Baudo, J. E.",)]
    body = '<p>CORRESPONDENCIA Bartolomé Mitre Nº 1371 c/ Talcahuano (1036) Capital Federal. email: d@example.com</p>'
    assert _corr(_page(authors, body)) == []
    assert all(a["is_corresponding"] is None for a in _authors(_page(authors, body)))


def test_page_without_a_note_keeps_the_meta_tag_reading():
    html = _page(CHILE, CHILE_BYLINE.replace("Correspondencia a:", ""))
    authors = _authors(html)
    assert [a["name"] for a in authors] == ["Cuello F, Mauricio", "Kato C, Sumie"]
    assert [a["is_corresponding"] for a in authors] == [None, None]
    assert [a["affiliations"] for a in authors] == [[{"name": CHILE[0][1]}], [{"name": CHILE[1][1]}]]


def test_whole_author_list_printed_twice_is_read_once():
    # pages built from the article's XML repeat every citation_author tag, each with its institution twice
    one = ("Alvarado Burbano, Maria Ximena", "Universidad del Valle, Colombia", "Universidad del Valle, Colombia")
    body = ('<!--version=xml-file--><div class="front" id="article-front"><div class="autores"><p class="author">'
            '<span class="author-name">Maria Ximena Alvarado Burbano</span><sup><a href="#aff1">1</a></sup></p></div>'
            '<p class="aff"><a name="aff1"></a><sup>1</sup>Escuela de Música de la Universidad del Valle, Colombia</p>'
            '</div>')
    authors = _authors(_page([one, one], body))
    assert [(a["name"], a["affiliations"]) for a in authors] == [
        ("Alvarado Burbano, Maria Ximena", [{"name": "Universidad del Valle, Colombia"}])]


def test_two_different_authors_are_never_folded():
    authors = [("Lima, Ana",), ("Costa, Bruno",), ("Lima, Ana",)]
    assert [a["name"] for a in _authors(_page(authors, "<p>Text</p>"))] == ["Lima, Ana", "Costa, Bruno", "Lima, Ana"]


def test_abstract_is_the_meta_tag_parsers():
    html = _page(CHILE, CHILE_BYLINE).replace(
        "</head>", '<meta name="citation_abstract" content="This review explores the evidence supporting a potential '
                   'benefit of statins in cancer, and what it would mean for prevention and therapy.">' + "</head>")
    assert parse_page(html.encode(), "doi", URL)["abstract"].startswith("This review explores the evidence")


def test_classic_scielo_br_page_is_not_claimed():
    head = '<link rel="canonical" href="http://www.scielo.br/scielo.php?script=sci_arttext&amp;pid=S0100-1">'
    body = CHILE_BYLINE + '<p><a name="back"></a>Correspondencia: Dr. Mauricio Cuello Lira 85.</p>'
    html = _page(CHILE, body, head)
    # (parse_page reads scielo.br's notes through #2149's own path, as before)
    assert not SciELOClassic(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_current_scielo_template_page_is_not_claimed():
    # the nearest other template: SciELO's current article page (scielo.br and journals on the same software)
    html = ('<html><head><meta property="og:url" content="https://www.scielo.br/j/rbz/a/AbC/?lang=en">'
            '<meta name="citation_author" content="Lima, Ana"></head><body><div class="contribGroup"><span '
            'class="dropdown"><a>Ana Lima</a><ul>Universidade Federal</ul></span></div><div class="articleSection">'
            '<p>Correspondence to: Ana Lima</p></div></body></html>')
    assert not SciELOClassic(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()


def test_other_site_linking_to_a_scielo_page_is_not_claimed():
    # an Open Journal Systems page that links a SciELO copy in its body: the claim reads only the page's own head
    html = ('<html><head><meta name="generator" content="Open Journal Systems 3.3.0.10"><link rel="canonical" '
            'href="https://revista.example.edu/index.php/r/article/view/12"><meta name="citation_author" '
            'content="Lima, Ana"></head><body><a href="http://www.scielo.cl/scielo.php?script=sci_arttext&amp;pid=S1">'
            'SciELO</a><p>Correspondencia: Ana Lima</p></body></html>')
    assert not SciELOClassic(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
