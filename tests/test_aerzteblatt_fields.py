"""Deutsches Ärzteblatt archive pages (aerzteblatt.de, DOI prefix 10.3238) (oxjob #2339).

Markup cut down from stored pages of the archive's article layout: the byline under the citation line
("Family, Initial"), the "Autoren" block of reviews and original articles ("Affiliation: names"), the address
paragraphs of letters and research letters, the author lines after a supplement article ("Perspektiven"), and the
"Corresponding author" address block.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.aerzteblatt import Aerzteblatt

URL = "https://www.aerzteblatt.de/int/archive/article?id=216402"
HEAD = ('<head><meta name="author" content="Deutscher &Auml;rzteverlag GmbH, Redaktion Deutsches &Auml;rzteblatt" />'
        '<meta property="og:site_name" content="Deutsches Ärzteblatt" />'
        '<meta property="og:url" content="https://www.aerzteblatt.de/int/archive/article?id=216402" /></head>')


def _byline(names):
    spans = "; ".join(f'<span class="author"><a href="/suche?archivAutor=x">{n}</a></span>' for n in names)
    return (f'<div class="citation">Dtsch Arztebl Int 2020; 117: 737-44. DOI: 10.3238/arztebl.2020.0737</div>'
            f'<h4>{spans}</h4>')


def _page(names, body, head=HEAD):
    return (f'<html>{head}<body><div class="archiveArticle"><h1>A title</h1>{_byline(names)}</div>'
            f'<div id="artikel"><div class="tango medizin">{body}</div></div></body></html>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _affs(html):
    return {a["name"]: [x["name"] for x in a["affiliations"]] for a in _authors(html)}


REVIEW_NAMES = ["Güsgen, C", "Willms, A", "Prior, M"]
AUTOREN = ('<div id="autoren">Department of General, Visceral and Thoracic Surgery, German Armed Forces Central Hospital,'
           '<br />German Society for General and Visceral Surgery (DGAV), Koblenz, Germany: Dr. med. Christoph Güsgen, '
           'Oberstarzt<br />PD Dr. med. Arnulf Willms, Oberfeldarzt<br />Klinik für Anästhesie, Städtisches Klinikum '
           'Solingen gGmbH: Prof. Dr. med. Prior<br /></div>')
CORR = ('<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Corresponding author</span><br/>Oberstarzt '
        'Dr. med. Christoph Güsgen <br/>Klinik für Allgemein-, Viszeral- und Thoraxchirurgie<br/>Bundeswehrzentralkrankenhaus '
        'Koblenz<br/>christophguesgen@bundeswehr.org<br/></p>')


def test_byline_names_in_order():
    assert [a["name"] for a in _authors(_page(REVIEW_NAMES, AUTOREN))] == ["C Güsgen", "A Willms", "M Prior"]


def test_autoren_block_gives_each_author_their_group():
    affs = _affs(_page(REVIEW_NAMES, AUTOREN + CORR))
    koblenz = ("Department of General, Visceral and Thoracic Surgery, German Armed Forces Central Hospital, "
               "German Society for General and Visceral Surgery (DGAV), Koblenz, Germany")
    assert affs["C Güsgen"] == [koblenz]
    assert affs["A Willms"] == [koblenz]
    assert affs["M Prior"] == ["Klinik für Anästhesie, Städtisches Klinikum Solingen gGmbH"]


def test_autoren_block_on_one_line():
    names = ["Michelson, G", "Hornegger, J"]
    body = ('<div id="autoren">Augenklinik mit Poliklinik, Universität Erlangen-Nürnberg: Prof. Dr. med. Michelson '
            'Lehrstuhl für Mustererkennung, Technische Fakultät, Universität Erlangen-Nürnberg: Prof. Dr.-Ing. Hornegger'
            '</div>')
    affs = _affs(_page(names, body))
    assert affs["G Michelson"] == ["Augenklinik mit Poliklinik, Universität Erlangen-Nürnberg"]
    assert affs["J Hornegger"] == ["Lehrstuhl für Mustererkennung, Technische Fakultät, Universität Erlangen-Nürnberg"]


def test_corresponding_author_block_marks_that_author():
    authors = _authors(_page(REVIEW_NAMES, AUTOREN + CORR))
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["C Güsgen"]


def test_plain_corresponding_author_lines_on_old_pages():
    body = AUTOREN + ('<p>Translated from the original German.<BR>\n<BR>\nCorresponding author<BR>\n Prof. Dr. med. '
                      'Arnulf Willms<BR>\nKlinik für Augenheilkunde<BR>\nwillms@example.de<BR>\n</p>')
    authors = _authors(_page(REVIEW_NAMES, body))
    assert [a["name"] for a in authors if a["is_corresponding"]] == ["A Willms"]


def test_letter_address_block_without_corresponding_label():
    names = ["Reck, M", "Vogel-Claussen, J"]
    body = ('<p class="Anschrift_der_Verfasser">On behalf of the authors:</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Prof. Dr. med. Martin Reck</span></p>'
            '<p class="Anschrift_der_Verfasser">LungenClinic Grosshansdorf</p>'
            '<p class="Anschrift_der_Verfasser">Airway Research Center North (ARCN)</p>'
            '<p class="Anschrift_der_Verfasser">reck@example.de</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Prof. Dr. med. Jens Vogel-Claussen</span></p>'
            '<p class="Anschrift_der_Verfasser">Medizinische Hochschule Hannover</p>')
    authors = _authors(_page(names, body))
    assert {a["name"]: [x["name"] for x in a["affiliations"]] for a in authors} == {
        "M Reck": ["LungenClinic Grosshansdorf, Airway Research Center North (ARCN)"],
        "J Vogel-Claussen": ["Medizinische Hochschule Hannover"]}
    assert not any(a["is_corresponding"] for a in authors)


def test_shared_address_after_several_names_and_email_dropped():
    names = ["Rupp, M", "Heiß, C"]
    body = ('<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Dr. med. Markus Rupp, Prof. Dr. med. '
            'Christian Heiß</span> <br/>Fachbereich Medizin, Justus-Liebig-Universität Gießen, rupp@example.de</p>')
    assert _affs(_page(names, body)) == {"M Rupp": ["Fachbereich Medizin, Justus-Liebig-Universität Gießen"],
                                         "C Heiß": ["Fachbereich Medizin, Justus-Liebig-Universität Gießen"]}


def test_a_bare_town_is_not_an_affiliation():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Dr. med. Hans-Joachim Ritz</span></p>'
            '<p class="Anschrift_der_Verfasser">Hannover, ritz@example.de</p>')
    assert _affs(_page(["Ritz, H"], body)) == {"H Ritz": []}


def test_research_letter_names_in_parentheses():
    names = ["Choudhury, K", "Haugk, R", "Claass, J"]
    body = ('<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Kohelia Choudhury, René Haugk, '
            'Johanna Claass</span></p><p class="Anschrift_der_Verfasser">Division of Hygiene, Institute for Hygiene '
            'and Environment, Hamburg, Germany (Choudhury, Haugk), Robert Koch Institute (RKI), Berlin, Germany '
            '(Claass)</p>')
    assert _affs(_page(names, body)) == {
        "K Choudhury": ["Division of Hygiene, Institute for Hygiene and Environment, Hamburg, Germany"],
        "R Haugk": ["Division of Hygiene, Institute for Hygiene and Environment, Hamburg, Germany"],
        "J Claass": ["Robert Koch Institute (RKI), Berlin, Germany"]}


def test_supplement_author_lines():
    names = ["Kleinwechter, Helmut", "Heinemann, Lutz"]
    body = ('<p class="Grundschrift_mit_Einzug"><span class="Autor_nach_Artikel">Dr. med. Helmut Kleinwechter</span></p>'
            '<p class="Grundschrift_mit_Einzug"><span class="Autor_Taetigkeit">diabetologikum kiel, '
            'Diabetesschwerpunktpraxis, Schulungszentrum</span></p>'
            '<p class="Grundschrift_mit_Einzug"><span class="Autor_nach_Artikel">Prof. Dr. Lutz Heinemann</span></p>'
            '<p class="Grundschrift_mit_Einzug"><span class="Autor_Taetigkeit">Science &amp; Co GmbH, Düsseldorf</span></p>')
    assert _affs(_page(names, body)) == {
        "Helmut Kleinwechter": ["diabetologikum kiel, Diabetesschwerpunktpraxis, Schulungszentrum"],
        "Lutz Heinemann": ["Science & Co GmbH, Düsseldorf"]}


def test_other_site_with_a_similar_byline_is_not_claimed():
    head = '<head><meta property="og:site_name" content="Zahnärztliche Mitteilungen" /></head>'
    soup = BeautifulSoup(_page(REVIEW_NAMES, AUTOREN, head=head), "lxml")
    assert not Aerzteblatt(soup).is_publisher_specific_parser()
    assert not Aerzteblatt(soup).authors_found()


def test_new_layout_without_the_archive_byline_is_not_claimed():
    html = f'<html>{HEAD}<body><main><h1>Dermatoonkologie</h1><p>Willen, Christine</p></main></body></html>'
    soup = BeautifulSoup(html, "lxml")
    assert not Aerzteblatt(soup).authors_found()


def test_utf8_bytes_under_a_windows_1252_declaration():
    html = _page(["Güsgen, C"], CORR).replace("<head>", '<head><meta charset="windows-1252" />', 1)
    authors = parse_page(html.encode("utf-8"), "doi", URL)["authors"]
    assert authors[0]["name"] == "C Güsgen" and authors[0]["is_corresponding"]


def test_a_name_missing_from_the_byline_does_not_join_the_address_before_it():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">PD Dr. med. Marc Regier</span></p>'
            '<p class="Anschrift_der_Verfasser">Universitätsklinikum Hamburg-Eppendorf</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. med. Chun</span></p>'
            '<p class="Anschrift_der_Verfasser">Martini-Klinik am UKE</p>')
    assert _affs(_page(["Regier, M"], body)) == {"M Regier": ["Universitätsklinikum Hamburg-Eppendorf"]}


def test_representation_lines_are_not_affiliations():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Anschrift_fett">Prof. Dr. med. Hans-Jörg Busch<br/></span>'
            'Uniklinik Freiburg, Freiburg, Germany,<br/>for the German Society of Medical Intensive Care Medicine and '
            '<br/>Emergency Medicine (DGIIN)</p>')
    assert _affs(_page(["Busch, HJ"], body)) == {"HJ Busch": ["Uniklinik Freiburg, Freiburg, Germany"]}


def test_colon_inside_an_affiliation():
    body = ('<div id="autoren">Internal Medicine VI: Psychosomatic Medicine and Psychotherapy, University Hospital '
            'Tübingen, Tübingen: Prof. Paul Enck<br /></div>')
    assert _affs(_page(["Enck, P"], body)) == {"P Enck": [
        "Internal Medicine VI: Psychosomatic Medicine and Psychotherapy, University Hospital Tübingen, Tübingen"]}
