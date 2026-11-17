"""EM-Consulte (Elsevier Masson's French platform) article pages (oxjob #2339).

Markup is cut down from stored em-consulte.com article pages (17 Nov 2026). The pages carry Elsevier meta values
("Elsevier Masson" author tag, the Elsevier TDM policy), so ElsevierBV claims them, but its ScienceDirect byline readers
find nothing: the generic parser read no authors and the French abstract. The byline is div#article_auteurs: names
with role labels after a colon, superscript links to the affiliation list (#AFFnnnn), a starred link to a
"Auteur correspondant." note (#CORnnnn). The abstract pane prints the French version, then the English one under the
English title.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV

URL = "https://www.em-consulte.com/article/1689646/alertePM"
HEAD = ('<head><meta name="tdm-policy" content="https://www.elsevier.com/tdm/tdmrep-policy.json">'
        '<meta name="author" content="Elsevier Masson"><meta property="og:site_name" content="EM-Consulte">'
        '<meta property="og:url" content="https://www.em-consulte.com/article/1689646/alertePM"></head>')

LINKED_BYLINE = (
    '<b>Pierre Francès <sup><a class="liennormal" href="#AFF0005">a</a>, </sup>'
    '<a class="liennormal" href="#COR0005">⁎</a>, <sup><a class="liennormal" href="#AFF0010">b</a></sup> '
    '<a class="liennormal" href="mailto:p@example.fr"><img src="/mail.png"></a> : <span> Médecin généraliste, '
    'chef de service</span>, Tara Chalaye <sup><a class="liennormal" href="#AFF0010">b</a></sup> : '
    '<span> Interne en médecine générale</span><br>'
    '<a name="AFF0005"></a><div> <sup> a</sup> 1 rue Saint-Jean-Baptiste, 66650 Banyuls-sur-Mer, France </div>'
    '<a name="AFF0010"></a><div> <sup> b</sup> Faculté de médecine, 1<sup>er</sup> étage, 34000 Montpellier, '
    'France </div></b>')
UNLINKED_BYLINE = (
    '<b>Jean-Christophe&nbsp;Azorin&nbsp;: <span> Rédacteur en chef</span>, Valérie&nbsp;Lequien '
    '<a class="liennormal" href="#COR0005">⁎</a> <a class="liennormal" href="mailto:v@example.fr"><img></a>&nbsp;: '
    '<span> Journaliste</span><br><a name="AFF0005"></a><div> <sup> </sup>&nbsp;c/o La revue, 65 rue '
    'Camille-Desmoulins, 92442 Issy-les-Moulineaux, France&nbsp;</div></b>')
COR_NOTE = ('<br><a name="COR0005"></a><div align="left" class="textenormalSmallLeft"><b><i><sup>*</sup>'
            'Auteur correspondant.</i></b></div>')
FRENCH = ('<p class="textenormal">Le badminton est un des sports scolaires les plus répandus. Proposé en association '
          'sportive et en option, cette pratique fédère les élèves et renforce leur confiance en eux.</p>')
ENGLISH = ('<p class="textenormal">Badminton is one of the most popular school sports. Offered as part of a sports '
           'association and as an optional extra, the sport unites students and boosts their self-confidence.</p>')
KEYWORDS = ('<br><p align="left"><i><b><span class="textenormal">Mots clés : </span></b><span class="textenormal">'
            'badminton, sport</span></i></p><p align="left"><i><b><span class="textenormal">Keywords : </span></b>'
            '<span class="textenormal">badminton, sport</span></i></p><br><h2>Plan</h2>')


def _resume(*versions):
    titles = ["Résumé", "Badminton at school: from the pleasure of being together"]
    return '<div id="pane_resume">' + "".join(
        f'<table><tbody><tr><td><h2>{t}</h2></td></tr></tbody></table><span class="textenormal">{v}</span>'
        'Le texte complet de cet article est disponible en PDF.' for t, v in zip(titles, versions)) + KEYWORDS + "</div>"


def _page(byline, resume, head=HEAD, note=COR_NOTE):
    authors = (f'<div id="article_auteurs"><div align="left" class="textenormalSmallLeft"><b>'
               f'<div align="left" class="textenormalSmallLeft">{byline}</div>{note}</b></div></div>')
    return (f"<html>{head}<body><div id=\"page_article\"><article><div id=\"article_corps\"><header>"
            f"<h1>Badminton au collège</h1><div id=\"article_doi\">Doi : 10.1016/j.revssu.2024.07.008</div>"
            f"{authors}</header><div id=\"article_texte\">{resume}</div></div></article></div></body></html>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _emc(html):
    return ElsevierBV(BeautifulSoup(html, "lxml"))


def test_linked_affiliations_roles_dropped_and_star_mark_read():
    out = _parse(_page(LINKED_BYLINE, _resume(FRENCH, ENGLISH)))
    assert [a["name"] for a in out["authors"]] == ["Pierre Francès", "Tara Chalaye"]
    first, second = out["authors"]
    assert [x["name"] for x in first["affiliations"]] == [
        "1 rue Saint-Jean-Baptiste, 66650 Banyuls-sur-Mer, France",
        "Faculté de médecine, 1er étage, 34000 Montpellier, France"]
    assert [x["name"] for x in second["affiliations"]] == ["Faculté de médecine, 1er étage, 34000 Montpellier, France"]
    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_unmarked_affiliation_is_every_authors():
    out = _parse(_page(UNLINKED_BYLINE, _resume(FRENCH, ENGLISH)))
    assert [a["name"] for a in out["authors"]] == ["Jean-Christophe Azorin", "Valérie Lequien"]
    for author in out["authors"]:
        assert [x["name"] for x in author["affiliations"]] == [
            "c/o La revue, 65 rue Camille-Desmoulins, 92442 Issy-les-Moulineaux, France"]
    assert [a["is_corresponding"] for a in out["authors"]] == [False, True]


def test_star_without_its_note_is_not_a_mark():
    byline = UNLINKED_BYLINE.replace('<a class="liennormal" href="mailto:v@example.fr"><img></a>', "")
    out = _parse(_page(byline, _resume(FRENCH), note=""))
    assert [a["name"] for a in out["authors"]] == ["Jean-Christophe Azorin", "Valérie Lequien"]
    assert not any(a["is_corresponding"] for a in out["authors"])


def test_lone_mail_icon_marks_its_author():
    byline = ('<b>Jean-Étienne Bazin <a class="liennormal" href="mailto:j@example.fr"><img></a> : <span> Professeur'
              '</span><br><a name="AFF0005"></a><div> <sup> </sup> Université Clermont-Auvergne, France </div></b>')
    out = _parse(_page(byline, _resume(FRENCH), note=""))
    assert [(a["name"], a["is_corresponding"]) for a in out["authors"]] == [("Jean-Étienne Bazin", True)]


def test_english_version_of_the_abstract_is_given():
    out = _parse(_page(UNLINKED_BYLINE, _resume(FRENCH, ENGLISH)))
    assert out["abstract"].startswith("Badminton is one of the most popular school sports.")
    assert "Keywords" not in out["abstract"] and "PDF" not in out["abstract"]


def test_french_abstract_when_it_is_the_only_version():
    out = _parse(_page(UNLINKED_BYLINE, _resume(FRENCH)))
    assert out["abstract"].startswith("Le badminton est un des sports scolaires")
    assert "Mots clés" not in out["abstract"]


def test_page_without_a_byline_is_left_to_the_other_readers():
    # an editorial or news item: the byline block holds only the PDF notice
    html = (f"<html>{HEAD}<body><header><h1>Éditorial</h1><div id=\"article_auteurs\">Le texte complet de cet "
            "article est disponible en PDF.</div></header><div id=\"pane_resume\"></div></body></html>")
    assert not _emc(html).authors_found()
    assert _parse(html)["authors"] == []


def test_same_markup_on_another_site_is_not_read_as_em_consulte():
    head = '<head><meta name="author" content="Elsevier"><meta property="og:site_name" content="Some Journal"></head>'
    html = _page(LINKED_BYLINE, _resume(FRENCH, ENGLISH), head=head)
    assert not _emc(html).authors_found()
    assert not any(a["affiliations"] for a in _parse(html)["authors"])
