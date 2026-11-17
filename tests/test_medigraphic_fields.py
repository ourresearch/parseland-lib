"""Corresponding authors on Medigraphic article pages, medigraphic.com (oxjob #2339).

Markup is cut down from stored medigraphic.com pages (17 Nov 2026). The generic reader already gets the byline and the
abstract from the citation_author tags and the page; Medigraphic's full-text pages name the corresponding author in a
"CORRESPONDENCIA" section at the end, which nothing read, and label-v1 marks that author. The visible text and the meta
tags each sometimes drop accented letters ("Dez-Ulloa" for "Díez-Ulloa"), and the meta tags may give the byline with
initials ("PS Vaca-Prez").
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.medigraphic import Medigraphic

URL = "https://www.medigraphic.com/cgi-bin/new/resumen.cgi?IDARTICULO=102903"
PUBLISHER = '<meta name="citation_publisher" content="Medigraphic">'
ABSTRACT = ("Las pruebas convencionales de coagulación evalúan el tiempo en que los factores de coagulación se activan "
            "en el plasma sanguíneo, el cual carece de componentes celulares, como enzimas y plaquetas que intervienen "
            "en el desarrollo de la hemostasia y su estudio en la cirugía general.")


def _page(names, correspondence, publisher=PUBLISHER):
    metas = "".join(f'<meta name="citation_author" content="{n}">' for n in names)
    corr = f"<BR><BR><p><strong>CORRESPONDENCIA</strong></p>{correspondence}<BR><BR><BR>" if correspondence else ""
    return (f'<html><head><meta name="citation_journal_title" content="Revista Mexicana de Anestesiología">'
            f'{publisher}{metas}<meta name="citation_title" content="Tromboelastografía para cirugía general">'
            f'<meta name="citation_pdf_url" content="https://www.medigraphic.com/pdfs/rma/cma-2022/cma221j.pdf">'
            f'</head><body><div class="blog-post-content"><h1><strong>Tromboelastografía para cirugía general</strong>'
            f'</h1><p><strong>RESUMEN</strong></p>{ABSTRACT}<br><br>'
            f'<BR><BR><p><strong>AFILIACIONES</strong></p><p class="afil_res1" id="afil_a1"><sup>1</sup> Centro Médico ABC.</p>'
            f'{corr}<em>Recibido:</em> 07-05-2020.</div></body></html>')


def _out(html):
    return parse_page(html.encode(), "doi", URL)


def _corr(html):
    return [a["name"] for a in _out(html)["authors"] if a["is_corresponding"]]


NAMES = ["Ana Luisa Hernández-Pérez", "Karina Ramírez-Morales", "Ana Gabriela Gallardo-Hernández"]


def test_correspondence_section_marks_its_author():
    html = _page(NAMES, "<strong>Dra. Ana Gabriela Gallardo-Hernández</strong>. E-mail: anagabygh@example.com")
    assert _corr(html) == ["Ana Gabriela Gallardo-Hernández"]
    assert [a["is_corresponding"] for a in _out(html)["authors"]] == [False, False, True]


def test_byline_and_abstract_stay_the_generic_readers():
    html = _page(NAMES, "<strong>Dra. Ana Gabriela Gallardo-Hernández</strong>. E-mail: anagabygh@example.com")
    out = _out(html)
    assert [a["name"] for a in out["authors"]] == NAMES
    assert out["abstract"] == _out(_page(NAMES, None))["abstract"]


def test_name_without_bold_and_comma_before_email():
    html = _page(["Araceli Martínez-Hernández", "Rodrigo Barrón-San Pedro"],
                 " Araceli Martínez-Hernández, ara@example.com")
    assert _corr(html) == ["Araceli Martínez-Hernández"]


def test_correo_label_and_name_dot_inside_bold():
    html = _page(["Francisco Xavier Cabrera-Mendoza", "Aurelio Barrera-González"],
                 "<strong>Francisco Xavier Cabrera-Mendoza. </strong>Correo electrónico: cab@example.com")
    assert _corr(html) == ["Francisco Xavier Cabrera-Mendoza"]


def test_dropped_accented_letters_and_hyphens_still_match():
    # the visible text lost "á", the meta tag kept it; a hyphen on one side, a space on the other
    html = _page(["Sal Ocampo Gonzlez", "Salvador Alejandro Ocampo Barro", "Jorge Elpidio Moreno Carranza"],
                 "<strong>Dr. Saul Ocampo Gonzlez</strong>. E-mail: s@example.com")
    assert _corr(html) == ["Sal Ocampo Gonzlez"]
    html = _page(["Jorge Elpidio Moreno Carranza", "Carlos Eduardo Medina Flores"],
                 "<strong>Dr. Jorge Elpidio Moreno-Carranza</strong>. E-mail: j@example.com")
    assert _corr(html) == ["Jorge Elpidio Moreno Carranza"]


def test_initials_in_either_name_match():
    html = _page(["PV Cornejo-Albn", "XA Ramos-Flores", "PS Vaca-Prez"],
                 "<strong>Paul Santiago Vaca-Prez</strong>. E-mail: p@example.com")
    assert _corr(html) == ["PS Vaca-Prez"]
    html = _page(["Nmesis Rodrguez Arizmendi", "Beatriz Catalina Aldape Barrios"],
                 "<strong>Beatriz C Aldape Barrios</strong>. E-mail: b@example.com")
    assert _corr(html) == ["Beatriz Catalina Aldape Barrios"]


def test_exact_name_wins_over_a_namesake():
    html = _page(["Luis Gerardo Domnguez Gasca", "Luis Gerardo Domnguez Carrillo"],
                 "<strong>Dr. Luis Gerardo Domnguez Carrillo</strong>. Correo electrnico: l@example.com")
    assert _corr(html) == ["Luis Gerardo Domnguez Carrillo"]


def test_no_correspondence_section_marks_no_one():
    # an e-mail meta tag alone is not a corresponding-author mark (label-v1)
    html = _page(NAMES, None).replace('content="Ana Luisa Hernández-Pérez">',
                                      'content="Ana Luisa Hernández-Pérez"><meta name="citation_author_email" content="a@example.com">')
    assert _corr(html) == []


def test_correspondent_not_in_byline_marks_no_one():
    html = _page(NAMES, "<strong>Dr. Pedro Páramo Ruiz</strong>. E-mail: p@example.com")
    assert _corr(html) == []


def test_other_site_with_a_correspondence_heading_is_not_claimed():
    html = _page(NAMES, "<strong>Dra. Ana Gabriela Gallardo-Hernández</strong>. E-mail: anagabygh@example.com",
                 publisher='<meta name="citation_publisher" content="Permanyer">')
    soup = BeautifulSoup(html, "lxml")
    assert not Medigraphic(soup).is_publisher_specific_parser()
    assert not Medigraphic(soup).authors_found()
    assert _corr(html) == []


def test_claimed_by_its_publisher_tag():
    soup = BeautifulSoup(_page(NAMES, None), "lxml")
    assert Medigraphic(soup).is_publisher_specific_parser()
    assert Medigraphic(soup).authors_found()
