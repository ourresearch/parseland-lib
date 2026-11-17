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


def test_a_signatory_missing_from_the_byline_is_a_co_author_with_their_own_address():
    # "In Reply" letters: the byline carries the first author; the address paragraphs name every signatory
    body = ('<p class="Anschrift_der_Verfasser">On behalf of the authors</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. med. Hartmut H.-J. Schmidt</span></p>'
            '<p class="Anschrift_der_Verfasser">Klinik für Transplantationsmedizin, Universitätsklinikum Münster</p>'
            '<p class="Anschrift_der_Verfasser">hepar@example.de</p>'
            '<p class="Anschrift_der_Verfasser">Prof. Dr. jur. Thomas Gutmann</p>'
            '<p class="Anschrift_der_Verfasser">Lehrstuhl für Bürgerliches Recht, Rechtsphilosophie und Medizinrecht</p>'
            '<p class="Anschrift_der_Verfasser">Westfälische Wilhelms-Universität Münster</p>')
    assert _affs(_page(["Schmidt, H H"], body)) == {
        "H H Schmidt": ["Klinik für Transplantationsmedizin, Universitätsklinikum Münster"],
        "Thomas Gutmann": ["Lehrstuhl für Bürgerliches Recht, Rechtsphilosophie und Medizinrecht, "
                           "Westfälische Wilhelms-Universität Münster"]}


def test_a_family_name_alone_takes_its_given_name_from_the_article_replied_to():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">PD Dr. med. Marc Regier</span></p>'
            '<p class="Anschrift_der_Verfasser">Universitätsklinikum Hamburg-Eppendorf</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. med. Chun</span></p>'
            '<p class="Anschrift_der_Verfasser">Martini-Klinik am UKE</p>')
    html = _page(["Regier, M"], body).replace(
        '<h4>', '<div class="bezug"><a href="/archiv/1">Thermal Ablation of Renal Tumors by PD Dr. med. Marc Regier, '
        'Prof. Dr. med. Felix Chun in issue 24/2015</a></div><h4>', 1)
    assert _affs(html) == {"M Regier": ["Universitätsklinikum Hamburg-Eppendorf"],
                           "Felix Chun": ["Martini-Klinik am UKE"]}


def test_no_co_author_from_the_address_when_a_byline_name_is_not_found_there():
    # a byline name spelled otherwise in the address ("Loellgen") must not come back as a second author
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. med. Dieter Leyk</span></p>'
            '<p class="Anschrift_der_Verfasser">Deutsche Sporthochschule Köln</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. med. Herbert Loellgen</span></p>'
            '<p class="Anschrift_der_Verfasser">Sana-Klinikum Remscheid</p>')
    assert [a["name"] for a in _authors(_page(["Leyk, D", "Löllgen, H"], body))] == ["D Leyk", "H Löllgen"]


def test_short_lines_under_the_institution_stay_in_the_affiliation():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Dr. med. Claas Ulrich</span></p>'
            '<p class="Anschrift_der_Verfasser">Hauttumorcentrum der Charité</p>'
            '<p class="Anschrift_der_Verfasser">Dermatologischer Konsiliarbereich</p>'
            '<p class="Anschrift_der_Verfasser">und Nachsorgeambulanz für Immunsupprimierte</p>'
            '<p class="Anschrift_der_Verfasser">Berlin</p>'
            '<p class="Anschrift_der_Verfasser">Claas.Ulrich@example.de<br/></p>')
    assert _affs(_page(["Ulrich, C"], body)) == {"C Ulrich": [
        "Hauttumorcentrum der Charité, Dermatologischer Konsiliarbereich, und Nachsorgeambulanz für Immunsupprimierte, "
        "Berlin"]}


def test_a_postal_address_is_an_affiliation():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">PD Dr. med. Ernst Eising</span></p>'
            '<p class="Anschrift_der_Verfasser">Elper Weg 66<br/>45657 Recklinghausen</p>')
    assert _affs(_page(["Eising, E"], body)) == {"E Eising": ["Elper Weg 66, 45657 Recklinghausen"]}


def test_plain_br_address_after_the_doi_line_on_2008_2010_letters():
    citation = '<div class="citation">Dtsch Arztebl Int 2008; 105: 900. DOI: 10.3238/arztebl.2008.0900b</div>'
    body = ('The authors are of the opinion that it is incumbent on insurers to act now.\tDOI: '
            '10.3238/arztebl.2008.0900b<BR>\n<BR>\n<BR>\nProf. Dr. med. Dr. Sportwiss. Dieter Leyk<BR>\n'
            'Institut für Physiologie und Anatomie<BR>\nDeutsche Sporthochschule Köln, Carl-Diem-Weg 6<BR>\n'
            '50933 Köln, Germany<BR>\nleyk@example.de<BR>\n<BR>\nProf. Dr. med. Herbert Löllgen<BR>\n'
            'Präsident der Deutschen Gesellschaft für Sportmedizin und Prävention<BR>\nBermesgasse 32b<BR>\n'
            '42897 Remscheid, Germany<BR>\nloellgen@example.de or<BR>\nh.l@example.de<BR>\n<BR>\n'
            'Conflict of interest statement<BR>\nThe authors declare that no conflict of interest exists.'
            '<iframe id="civey" src="about:blank"></iframe><script>console.log("x");</script>')
    html = _page(["Leyk, D", "Löllgen, H"], body).replace(
        '<div class="citation">Dtsch Arztebl Int 2020; 117: 737-44. DOI: 10.3238/arztebl.2020.0737</div>', citation)
    assert _affs(html) == {
        "D Leyk": ["Institut für Physiologie und Anatomie, Deutsche Sporthochschule Köln, Carl-Diem-Weg 6, "
                   "50933 Köln, Germany"],
        "H Löllgen": ["Präsident der Deutschen Gesellschaft für Sportmedizin und Prävention, Bermesgasse 32b, "
                      "42897 Remscheid, Germany"]}


def test_supplement_author_paragraphs():
    body = ('<p class="Grundschrift_ohne_Einzug"><span class="DOI">DOI: 10.3238/PersOnko.2022.12.02.03</span></p>'
            '<p class="Autor_nach_Artikel">Prof. Dr. med. Dr. rer. nat. Rebekka Schneider-Kramann</p>'
            '<p class="Autor_nach_Artikel_Taetigkeit">Institut für Zell- und Tumorbiologie<br/>Universitätsklinikum RWTH '
            'Aachen</p><p class="Fussnote"><span class="fett">Interessenkonflikt:</span> keiner.</p>')
    assert _affs(_page(["Schneider-Kramann, Rebekka"], body)) == {
        "Rebekka Schneider-Kramann": ["Institut für Zell- und Tumorbiologie, Universitätsklinikum RWTH Aachen"]}


def test_authors_sharing_a_family_name_are_told_apart_by_the_given_name():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. Ing. Dr. h. c. mult. Siegfried Hünig'
            '</span></p><p class="Anschrift_der_Verfasser">Institut für Organische Chemie, Würzburg</p>'
            '<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Dr. med. Georg Hünig</span></p>'
            '<p class="Anschrift_der_Verfasser">Hefnersplatz 10, 90402 Nürnberg, Germany</p>')
    assert _affs(_page(["Hünig, S", "Hünig, G"], body)) == {
        "S Hünig": ["Institut für Organische Chemie, Würzburg"],
        "G Hünig": ["Hefnersplatz 10, 90402 Nürnberg, Germany"]}


def test_stray_windows_1252_dash_is_read_as_a_dash():
    body = ('<p class="Anschrift_der_Verfasser"><span class="Autor_fett">Prof. Dr. med. Maike de Wit</span></p>'
            '<p class="Anschrift_der_Verfasser">Klinik für Innere Medizin \x96 Hämatologie, Vivantes Klinikum Neukölln</p>')
    assert _affs(_page(["de Wit, Maike"], body)) == {
        "Maike de Wit": ["Klinik für Innere Medizin – Hämatologie, Vivantes Klinikum Neukölln"]}


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
