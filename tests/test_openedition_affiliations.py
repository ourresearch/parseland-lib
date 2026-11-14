"""Authors and affiliations on OpenEdition pages (journals. and books.openedition.org) (oxjob #2219).

Markup is cut down from stored OpenEdition pages (#2152 EXPLORE § 1, #2219 EXPLORE § 1). The item's "#authors" section
holds each author's note in one of three layouts; the parser read only one (a single p.description.directionltr), so
multi-author pages, older journal pages and book pages lost their affiliations and another parser emitted the section
heading ("Auteurs") as an author. Gold rubric label-v1: a note is an affiliation (employers, departments, institutes),
never a biography, and without e-mail addresses.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.openedition import OpenEdition

JOURNAL = "http://journals.openedition.org/edso/21807"
BOOK = "https://books.openedition.org/pur/189065"


def _page(og, authors_section):
    return (f'<html><head><meta property="og:url" content="{og}"/>'
            '<meta name="description" content="Un résumé de l’article qui décrit ce qu’il étudie et ce qu’il trouve : '
            'les difficultés des élèves et des enseignants relevées dans de nombreuses recherches, les dispositifs mis '
            'en place pour y répondre et ce que les observations de classe montrent de leurs effets."/></head><body>'
            '<div id="text">Texte</div>'
            f"{authors_section}</body></html>")


def _authors(html, url=JOURNAL):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in parse_page(html.encode(), "doi", url)["authors"]]


def _journal_new(*authors):
    """Multi-author Lodel journal page: each note in a span.directionltr wrapper."""
    body = "".join(f'<h3><a href="1">{n.split()[0]} <span class="familyName">{n.split()[1]}</span></a></h3>'
                   f'<span class="directionltr"><p class="description">{note}</p></span>' for n, note in authors)
    return (f'<div class="section authors" id="authors"><h2 class="section"><span class="text">Auteurs</span></h2>'
            f'{body}<a class="go-top" href="#article-1">Haut de page</a></div>')


def test_multi_author_journal_page_reads_every_note():
    html = _page(JOURNAL, _journal_new(("Laure Sochala", "Université de Lille, laboratoire CIREL-RECIFES"),
                                       ("Sylvain Broccolichi", "Université de Lille, laboratoire CIREL-RECIFES")))
    assert _authors(html) == [("Laure Sochala", ["Université de Lille, laboratoire CIREL-RECIFES"]),
                              ("Sylvain Broccolichi", ["Université de Lille, laboratoire CIREL-RECIFES"])]


def test_note_lines_each_count_and_emails_are_dropped():
    html = _page(JOURNAL, _journal_new(
        ("Jacques Castaing", "Directeur de recherche honoraire au CNRS<br/>(jacques.castaing[at]upmc.fr)"),
        ("Farid Bouchiba", "Université Nantes Angers Le Mans ; bouchiba@example.com"),
        ("Patrice Correa", "Université Gaston Berger de Saint-Louis (Sénégal). Courriel : patrice.correa@ugb.edu.sn")))
    assert _authors(html) == [("Jacques Castaing", ["Directeur de recherche honoraire au CNRS"]),
                              ("Farid Bouchiba", ["Université Nantes Angers Le Mans"]),
                              ("Patrice Correa", ["Université Gaston Berger de Saint-Louis (Sénégal)."])]


def test_several_paragraphs_in_one_wrapper():
    section = ('<div class="section authors" id="authors"><h2 class="section">Auteur</h2>'
               '<h3><a href="1">Olivier <span class="familyName">Bignon-Lau</span></a></h3>'
               '<span class="directionltr"><p class="description">Chercheur CRCN, CNRS</p> '
               '<p class="description">UMR 8068 TEMPS</p></span></div>')
    assert _authors(_page(JOURNAL, section)) == [("Olivier Bignon-Lau", ["Chercheur CRCN, CNRS", "UMR 8068 TEMPS"])]


def test_older_journal_section_without_the_authors_class():
    section = ('<div class="section" id="authors"><h2 class="section"><span class="text">Rédacteur</span></h2>'
               '<h3> <a href="65314">Sibylle <span class="familyName">Léonard</span></a></h3> '
               '<p class="description">Doctorante en théorie politique au CEVIPOF (Sciences Po).</p>'
               '<a class="go-top" href="#compterendu-65309">Haut de page</a></div>')
    assert _authors(_page(JOURNAL, section)) == [
        ("Sibylle Léonard", ["Doctorante en théorie politique au CEVIPOF (Sciences Po)."])]


def test_note_class_descriptionauteur():
    section = ('<div class="section authors" id="authors"><h2 class="section">Auteur</h2>'
               '<h3><a href="49">Frédérique <span class="familyName">Langue</span></a></h3>'
               '<span class="directionltr"><p class="descriptionauteur" dir="ltr">CNRS-Paris</p></span></div>')
    assert _authors(_page(JOURNAL, section)) == [("Frédérique Langue", ["CNRS-Paris"])]


def test_other_articles_by_the_author_are_not_a_note():
    section = ('<div class="section authors" id="authors"><h2 class="section">Auteur</h2>'
               '<h3><a href="206">M. <span class="familyName">Gast</span></a></h3><h4>Articles du même auteur</h4>'
               '<ul class="documents"><li><div class="title"><a href="606">Mil (Monde touareg)</a></div>'
               '<div class="description"><span class="docnumber">Article M116c</span></div></li></ul></div>')
    assert _authors(_page(JOURNAL, section)) == [("M. Gast", [])]


def test_book_page_reads_author_divs_and_skips_from_the_same_author():
    section = ('<div class="authors" id="authors"><h2 class="section">Auteurs</h2>'
               '<div class="author"><div class="name"><a href="/author?name=a" title="Jérôme Pelletier">'
               '<em>Jérôme Pelletier</em></a></div><div class="description">Docteur en Histoire, université Paris '
               'Ouest Nanterre La Défense, chercheur associé à l’IDHE (UMR 8533).</div>'
               '<div class="fromsameauthor"><h3 class="section">Du même auteur</h3><ul><li class="title">'
               '<a href="http://books.openedition.org/x/1">Un autre livre<span class="in">, PUR, 2019</span></a></li>'
               '</ul></div></div>'
               '<div class="author"><div class="name"><em>Karine Bennafla</em></div><div class="description">'
               '<p class="description">Professeure de géographie, Université Jean Moulin Lyon 3</p></div></div>'
               '<div class="author"><div class="name"><em>Florence Fabijanec</em> (Traducteur)</div></div></div>')
    assert _authors(_page(BOOK, section), BOOK) == [
        ("Jérôme Pelletier", ["Docteur en Histoire, université Paris Ouest Nanterre La Défense, chercheur associé à "
                              "l’IDHE (UMR 8533)."]),
        ("Karine Bennafla", ["Professeure de géographie, Université Jean Moulin Lyon 3"])]


def test_biographies_are_not_affiliations():
    html = _page(JOURNAL, _journal_new(
        ("Nathalie Sasseville", "Nathalie Sasseville est professeure à l’Unité d’enseignement en travail social. "
                                "Elle accompagne depuis plusieurs années la communauté de Mashteuiatsh."),
        ("Snježana Koren", "Née en 1965, enseigne au département d’histoire de la Faculté des Lettres de Zagreb.")))
    assert _authors(html) == [("Nathalie Sasseville", []), ("Snježana Koren", [])]


def test_affiliation_sentences_kept_up_to_the_biography():
    html = _page(JOURNAL, _journal_new(
        ("Pierre Rivas", "Maître de conférences honoraire de littérature comparée à l’université Paris 10. Il est "
                         "spécialiste des relations entre les littératures."),
        ("Arnaud Clere", "Agence Perles d’Histoire<br/>Diplômé de l’Essec en 2004, il a servi un an dans la Marine."
                         "<br/>Autres livres récents : Un titre, Paris, 2019.<br/>arnaud[at]example.fr"),
        ("Stéphane Magne", "Maître de conférences en marketing à l’université Paris 1 (laboratoire PRISM.) Ses "
                           "recherches portent sur les marques.")))
    assert _authors(html) == [
        ("Pierre Rivas", ["Maître de conférences honoraire de littérature comparée à l’université Paris 10."]),
        ("Arnaud Clere", ["Agence Perles d’Histoire"]),
        ("Stéphane Magne", ["Maître de conférences en marketing à l’université Paris 1 (laboratoire PRISM.)"])]


def test_translator_section_is_not_authors():
    section = ('<div class="section authors" id="authors"><h2 class="section"><span class="text">Traducteur</span>'
               '</h2><h3><a href="3990">Emilie <span class="familyName">Syssau</span></a></h3></div>')
    assert OpenEdition(BeautifulSoup(_page(JOURNAL, section), "lxml")).parse_authors() == []


def test_abstract_still_comes_from_the_meta_tags():
    html = _page(JOURNAL, _journal_new(("Laure Sochala", "Université de Lille")))
    assert parse_page(html.encode(), "doi", JOURNAL)["abstract"].startswith("Un résumé de l’article")


def test_lookalike_lodel_page_on_another_site_is_not_claimed():
    section = _journal_new(("Laure Sochala", "Université de Lille"), ("Sylvain Broccolichi", "Université de Lille"))
    soup = BeautifulSoup(_page("https://www.persee.fr/doc/x_1", section), "lxml")
    # not claimed as OpenEdition's page; main's parser also read a ".section.authors" block on any site, and still does
    assert not OpenEdition(soup).is_publisher_specific_parser()


def test_current_books_template_reads_persons_list():
    section = ('<div class="mb-3 scrollspy-target anchor--toc--section" id="anchor-persons"><h1 class="title--alt '
               'bottom"> Auteurs </h1><ul class="persons"><li><a href="/irmc/person/4106"><strong> Fadma Aït Mous '
               '</strong></a><div class="tab__values__value__person__value tab__values__value__person__value__description">'
               '<p>Professeure titulaire de sociologie, Université Hassan II de Casablanca, LADSIS.</p></div></li>'
               '<li><a href="/pufc/person/59032"><strong> Bruno Maes </strong></a><p class="tab__values__value__person__'
               'value"> IdRef : <a href="https://www.idref.fr/030808596">030808596</a></p></li></ul></div>')
    assert _authors(_page(BOOK, section), BOOK) == [
        ("Fadma Aït Mous", ["Professeure titulaire de sociologie, Université Hassan II de Casablanca, LADSIS."]),
        ("Bruno Maes", [])]


def test_long_cv_sentence_is_not_an_affiliation():
    html = _page(JOURNAL, _journal_new(("Christian Hoarau", (
        "Professeur de Sciences de Gestion du Conservatoire National des Arts et Métiers, titulaire de la chaire « "
        "Comptabilité Financière et Audit » et membre du comité exécutif du LABEX Régulation financière (ReFi)."))))
    assert _authors(html) == [("Christian Hoarau", [])]


def test_book_layout_on_another_site_is_not_read():
    section = ('<div class="authors" id="authors"><h2 class="section">Auteur</h2><div class="author"><div class="name">'
               '<em>Jérôme Pelletier</em></div><div class="description">Université de Lille</div></div></div>')
    assert not OpenEdition(BeautifulSoup(_page("https://www.example.org/livre/1", section), "lxml")).authors_found()
