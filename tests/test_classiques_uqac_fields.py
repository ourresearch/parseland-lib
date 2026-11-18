"""Les Classiques des sciences sociales (classiques.uqac.ca) record pages: the byline and its affiliation line
(oxjob #2339).

Markup is cut down from stored record pages (10.1522/... DOIs, 17 Nov 2026). Each record page is hand-made HTML
(generator "WebExpert 6", meta author "Jean-Marie Tremblay", the library's founder): the author's name in a size-5
font under the collection's title, then a small-font line saying who the author is. That line is an affiliation when
it names an employer ("sociologue, departement de sociologie, UQAM"); a role, a biography, a former employer
("retraite de l'UQAM") or a degree is not. The Dublin Core creator is the site's maintainer, never the author.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.classiques_uqac import ClassiquesUQAC

URL = "https://doi.org/10.1522/cla.xyz.abc"
HEAD = ('<meta name="author" content="Jean-Marie Tremblay">'
        '<meta name="description" content="Une biblioth&egrave;que num&eacute;rique unique et originale.">'
        '<meta name="generator" content="WebExpert 6">'
        '<meta name="DC.Creator.PersonalName" content="Jean-Marie Tremblay">')


def _page(byline, head=HEAD, extra=""):
    return (f"<html><head><title>A title</title>{head}</head><body>"
            '<!-- Debut du contenu de la page -->'
            '<div class="titrecollection">Collection &laquo; Les sciences sociales contemporaines &raquo;</div>'
            '<div align="left"><font size=1><i><table border=0 width="100%"><tr><td><center>'
            f"{byline}</center></td></tr></table></i></font>"
            '<hr align="left" noshade size=2 width="100%">'
            '<p><font size=2>Une &eacute;dition &eacute;lectronique r&eacute;alis&eacute;e &agrave; partir du livre.'
            '<br><img border=0 height=20 src="../../../images/courrier/Boite_aux_lettres_clair.gif" width=20> '
            'Courriel: <a href="mailto:someone@example.ca">someone@example.ca</a></font></p>'
            f"{extra}</body></html>")


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"])
            for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_single_author_department_line():
    byline = ('<p><font color="red" size=5><a href="../dandurand_pierre_photo/x.html">Pierre Dandurand</a></font>'
              '<font size=5> (1932-1995)<br></font><font face="Times New Roman" size=2>sociologue, d&eacute;partement '
              "de sociologie de l'Universit&eacute; de Montr&eacute;al</font>")
    assert _authors(_page(byline)) == [
        ("Pierre Dandurand", ["département de sociologie de l'Université de Montréal"], False)]


def test_two_authors_share_the_line():
    byline = ('<p><font size=5><font color="#cc0000">Paul R. B&eacute;langer</font><font color="black"> et </font>'
              '<font color="#cc0000"><a href="x.html">Beno&icirc;t L&eacute;vesque</a></font><br></font>'
              '<font size=2>sociologues, D&eacute;partement de sociologie, Universit&eacute; du Qu&eacute;bec &agrave; '
              "Montr&eacute;al</font>")
    aff = ["Département de sociologie, Université du Québec à Montréal"]
    assert _authors(_page(byline)) == [("Paul R. Bélanger", aff, False), ("Benoît Lévesque", aff, False)]


def test_role_only_is_not_an_affiliation():
    byline = ('<p><font size=5><a href="x.html"><font color="#cc0000">Mona-Jos&eacute;e Gagnon</font></a>, '
              "(sociologue-historienne)</font>")
    assert _authors(_page(byline)) == [("Mona-Josée Gagnon", [], False)]


def test_former_employer_is_not_an_affiliation():
    byline = ('<p><font size=5><a href="x.html"><font color="#cc0000">Louis Gill</font></a><br></font>'
              "<font size=2>&eacute;conomiste qu&eacute;b&eacute;cois, retrait&eacute; de l'UQAM</font>")
    assert _authors(_page(byline)) == [("Louis Gill", [], False)]


def test_life_dates_and_honorific_are_not_the_name():
    byline = ('<p><font color="#cc0000" size=5><a href="x.html">Gustave Le Bon</a></font><font size=5>, '
              "1841-1931</font>")
    assert _authors(_page(byline)) == [("Gustave Le Bon", [], False)]
    byline = ('<p><font color="#cc0000" size=5><a href="x.html">Dr Jean Price-Mars</a></font><font size=5> '
              '[1876-1969]</font><font size=5><br></font><font size="2">Ethnologue, historien, diplomate</font>')
    assert _authors(_page(byline)) == [("Jean Price-Mars", [], False)]


def test_name_particles():
    byline = ('<p><font color="red" size=5><a href="x.html">Alexis de Tocqueville</a></font><font size=5> '
              "(1805-1859)</font>")
    assert _authors(_page(byline)) == [("Alexis de Tocqueville", [], False)]
    byline = '<p><font color="red" size=5>sous la direction de Jean Dupont</font>'
    assert _authors(_page(byline)) == []


def test_affiliation_continued_on_the_next_line():
    byline = ('<p><font size=5><a href="x.html">Jean Benoist</a>,<br></font><font size="2">M&eacute;decin et '
              "anthropologue, professeur &eacute;m&eacute;rite, Laboratoire d&rsquo;&Eacute;cologie humaine,<br> "
              "Universit&eacute; d&rsquo;Aix-Marseille</font>")
    assert _authors(_page(byline)) == [
        ("Jean Benoist", ["Laboratoire d’Écologie humaine, Université d’Aix-Marseille"], False)]


def test_degree_and_biography_lines_are_not_affiliations():
    byline = ('<p><font color="red" size=5><a href="x.html">Thierry Gaudin</a></font><font size=5><br></font>'
              "<font size=2>polytechnicien et ing&eacute;nieur des Mines<br> Pr&eacute;sident de l&rsquo;association "
              "Prospective 2100.<br> Docteur en Sciences de l'information (Universit&eacute; de Paris X Nanterre)</font>")
    assert _authors(_page(byline)) == [("Thierry Gaudin", [], False)]


def test_two_affiliation_lines():
    byline = ('<p><font size=5><a href="x.html"><font color="#cc0000">Christian Bromberger</font></a><br></font>'
              "<font size=2>professeur d'ethnologie &agrave; l'Universit&eacute; de Provence,<br> membre senior de "
              "l&rsquo;Institut universitaire de France</font>")
    assert _authors(_page(byline)) == [
        ("Christian Bromberger", ["Université de Provence", "Institut universitaire de France"], False)]


def test_brackets_and_windows_characters():
    byline = ('<p><font size=5><a href="x.html"><font color="#cc0000">Jacques Guilhaumou</font></a><br></font>'
              '<font size="2">Historien, Directeur de recherche au CNRS (langues, langages, discours)</font>')
    assert _authors(_page(byline)) == [("Jacques Guilhaumou", ["CNRS (langues, langages, discours)"], False)]
    byline = ('<p><font color="red" size=5><a href="x.html">Denis CHARTIER</a></font><font size=5><br></font>'
              '<font size="2">Institut de Recherche pour le D&eacute;veloppement &#151; IRD<br></font>')
    assert _authors(_page(byline)) == [("Denis CHARTIER", ["Institut de Recherche pour le Développement — IRD"], False)]
    byline = ('<p><font size=5><a href="x.html"><font color="#cc0000">Pierre Lemieux</font></a><br></font>'
              "[Professeur associ&eacute;, Universit&eacute; du Qu&eacute;bec en Outaouais]")
    assert _authors(_page(byline)) == [("Pierre Lemieux", ["Université du Québec en Outaouais"], False)]


def test_a_work_title_in_the_name_slot_is_not_an_author():
    byline = '<p><font color="#cc0000" size=5>Tchou-Tchou-Ki-Nien<br></font>'
    assert _authors(_page(byline)) == []


def test_new_fields_absent():
    byline = '<p><font color="red" size=5><a href="x.html">Pierre Dandurand</a></font>'
    out = ClassiquesUQAC(BeautifulSoup(_page(byline), "lxml")).parse()
    assert out["abstract"] is None
    assert not out.get("references") and not out.get("acknowledgments") and not out.get("funding_statement")


def test_other_sites_are_not_claimed():
    byline = ('<p><font color="red" size=5><a href="x.html">Pierre Dandurand</a></font><font size=5><br></font>'
              "<font size=2>sociologue, d&eacute;partement de sociologie, Universit&eacute; de Montr&eacute;al</font>")
    # same editor and the same hand-made layout on another site: not claimed
    other = _page(byline, head='<meta name="author" content="Marie Dupont"><meta name="generator" content="WebExpert 6">')
    assert not ClassiquesUQAC(BeautifulSoup(other, "lxml")).is_publisher_specific_parser()
    assert not ClassiquesUQAC(BeautifulSoup(other, "lxml")).authors_found()
    # the maintainer's other pages (no collection title, e.g. the usage policy) are claimed but hold no byline
    policy = f"<html><head>{HEAD}</head><body><p>Politique d'utilisation</p></body></html>"
    assert not ClassiquesUQAC(BeautifulSoup(policy, "lxml")).authors_found()
    # no <head> at all
    assert not ClassiquesUQAC(BeautifulSoup("<p>Jean-Marie Tremblay</p>", "lxml")).is_publisher_specific_parser()
