"""Duncker & Humblot eLibrary (elibrary.duncker-humblot.com): byline and author notes (oxjob #2338).

Markup is cut down from stored pages of the site (17 Nov 2026). The generic parser reads only the citation_author
tags: book reviews and chapters have none, edited volumes credit "Editors:" only, and every affiliation sits in the
"Author Details" notes ("Dr. Albrecht Hoppe, Domstiftsarchiv Brandenburg ...").
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.duncker_humblot import DunckerHumblot

URL = "https://elibrary.duncker-humblot.com/article/75981/x"
HEAD = ('<title>Duncker &amp; Humblot - Berlin: A title</title>'
        '<link rel="stylesheet" href="https://elibrary.duncker-humblot.com/assets_dh/bundle.css">')


def _page(byline, notes="", metas="", abstract="", head=HEAD):
    return (f"<html><head>{head}{metas}</head><body><div class=\"section__right\"><h2>A title</h2>{byline}"
            "<p><a href=\"https://elibrary.duncker-humblot.com/journal/35/x\">A journal</a>, Vol. 73(2025)</p></div>"
            f"<section class=\"additional-info\"><h4>Article Details</h4><dl class=\"metadata\"><dt>DOI</dt>"
            f"<dd>https://doi.org/10.3790/x</dd></dl>{notes}</section>{abstract}</body></html>")


def _byline(*names, label=""):
    links = " | ".join(f'<a href="https://elibrary.duncker-humblot.com/authors/{n.replace(" ", "%20")}">{n}</a>'
                       for n in names)
    return f"<p>{label}{links}</p>"


def _note(text, bio="", email=""):
    mail = f'<li><a href="mailto:{email}"><span class="fa fa-envelope"></span>Email</a></li>' if email else ""
    return (f'<p>{text}</p><ul class="list-none"><li>{bio}</li>{mail}'
            '<li><a href="https://scholar.google.com/scholar?q=x">Search in Google Scholar</a></li></ul>')


def _authors(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def _affs(html):
    return [[x["name"] for x in a["affiliations"]] for a in _authors(html)]


def test_book_review_byline_without_meta_tags():
    html = _page(_byline("Hoppe, Albrecht"))
    assert [a["name"] for a in _authors(html)] == ["Hoppe, Albrecht"]


def test_affiliation_after_name_with_degrees():
    note = _note("Dr. Albrecht Hoppe, Domstiftsarchiv Brandenburg Burghof 10 14776 Brandenburg an der Havel, Deutschland",
                 email="a@example.de")
    assert _affs(_page(_byline("Hoppe, Albrecht"), note)) == [
        ["Domstiftsarchiv Brandenburg Burghof 10 14776 Brandenburg an der Havel, Deutschland"]]


def test_affiliation_after_family_given_and_titles():
    note = _note("Sesselmeier, Prof. Dr. Werner, Universität Koblenz-Landau, Institut für Sozialwissenschaften, 76829 Landau")
    assert _affs(_page(_byline("Sesselmeier, Werner"), note)) == [
        ["Universität Koblenz-Landau, Institut für Sozialwissenschaften, 76829 Landau"]]


def test_footnote_marker_and_organisation_named_like_the_author():
    note = _note("1Hugues Höfer, Höfer AG, Ebnetrain 2, CH-6045 Meggen.")
    assert _affs(_page(_byline("Höfer, Hugues"), note)) == [["Höfer AG, Ebnetrain 2, CH-6045 Meggen."]]


def test_name_only_note_and_biography_give_no_affiliation():
    note = _note("Quinn, Regina Ammicht", bio="Professorin am Zentrum für Ethik der Universität Tübingen.")
    assert _affs(_page(_byline("Quinn, Regina Ammicht"), note)) == [[]]


def test_place_only_notes_are_not_affiliations():
    for text in ("Timo Bollen, 40468 Düsseldorf, Deutschland", "Jay H. Levin, Detroit/Michigan",
                 "Eyüp Ali Kılıçaslan, Ankara", "Misa Sanada, Hauptstraße 177, 69117 Heidelberg"):
        name = text.split(",")[0].split()
        byline = _byline(f"{name[-1]}, {' '.join(name[:-1])}")
        assert _affs(_page(byline, _note(text))) == [[]], text


def test_email_left_out_of_affiliation():
    notes = (_note("Mara Liebal, erlassjahr.de, E-Mail: m.liebal@example.de")
             + _note("Kristina Rehbein, erlassjahr.de, E-Mail: k.rehbein@example.de"))
    assert _affs(_page(_byline("Liebal, Mara", "Rehbein, Kristina"), notes)) == [["erlassjahr.de"], ["erlassjahr.de"]]


def test_unnamed_notes_go_to_authors_in_order():
    notes = (_note("Helmut-Schmidt-Universität Hamburg, Institut für Wirtschaftspolitik, 22043 Hamburg. "
                   "Internet: www.example.de/x.htm", email="a@example.de")
             + _note("University of Southern Denmark, Department of Business and Economics, 5230 Odense M, Dänemark; "
                     "Zentrum für Europäische Wirtschaftsforschung, Mannheim", email="b@example.dk"))
    assert _affs(_page(_byline("Dewenter, Ralf", "Kaiser, Ulrich"), notes)) == [
        ["Helmut-Schmidt-Universität Hamburg, Institut für Wirtschaftspolitik, 22043 Hamburg"],
        ["University of Southern Denmark, Department of Business and Economics, 5230 Odense M, Dänemark",
         "Zentrum für Europäische Wirtschaftsforschung, Mannheim"]]


def test_chapter_name_paragraph_then_note():
    notes = ('<p>Axel Gotthard</p>' + _note("Prof. Dr. Axel Gotthard, Department Geschichte, Friedrich-Alexander-"
                                           "Universität Erlangen – Nürnberg,"))
    byline = '<p><a href="https://elibrary.duncker-humblot.com/authors/Gotthard,%20Axel"><strong>Gotthard, Axel</strong></a></p>'
    assert _affs(_page(byline, notes)) == [["Department Geschichte, Friedrich-Alexander-Universität Erlangen – Nürnberg"]]


def test_birth_year_note_is_a_biography():
    note = _note("Bull, Prof. Dr. jur., geb. 1936, Universitätsprofessor (em.).")
    assert _affs(_page(_byline("Bull, Hans Peter"), note)) == [[]]


def test_editors_are_the_authors_of_an_edited_volume():
    html = _page(_byline("Niedersen, Uwe", "Pohlmann, Ludwig", label="Editors: "))
    assert [a["name"] for a in _authors(html)] == ["Niedersen, Uwe", "Pohlmann, Ludwig"]


def test_authors_win_over_editors():
    html = _page(_byline("Vieweg, Klaus") + _byline("Steiner, Udo", label="Editors: "))
    assert [a["name"] for a in _authors(html)] == ["Vieweg, Klaus"]


def test_email_link_is_not_a_corresponding_mark():
    note = _note("Thomas Gehrig, University of Vienna, Department of Finance", email="t@example.at")
    assert [a["is_corresponding"] for a in _authors(_page(_byline("Gehrig, Thomas"), note))] == [None]


def test_book_byline_keeps_the_tag_spelling():
    metas = '<meta name="citation_author" content="Klaus Ferdinand Gärditz"/>'
    assert [a["name"] for a in _authors(_page(_byline("Gärditz, Klaus Ferdinand"), metas=metas))] == [
        "Klaus Ferdinand Gärditz"]


def test_unnamed_positional_note_must_not_name_a_person():
    notes = _note("Prof. Dr. Hans Muster, Universität X") + _note("Universität Y, Institut Z")
    assert _affs(_page(_byline("Dewenter, Ralf", "Kaiser, Ulrich"), notes)) == [[], ["Universität Y, Institut Z"]]


def test_abstract_is_the_generic_readers():
    abstract = ("This paper deals with the potential of investor-side dialogue strategies for more quality and "
                "sustainability in corporate governance, and with the limits of such strategies in practice today.")
    metas = (f'<meta name="citation_author" content="Vögele, Gesa"/>'
             f'<meta name="citation_abstract" content="&lt;p&gt;{abstract}&lt;/p&gt;"/>')
    out = parse_page(_page(_byline("Vögele, Gesa"), metas=metas).encode(), "doi", URL)
    assert out["abstract"] == abstract
    assert [a["name"] for a in out["authors"]] == ["Vögele, Gesa"]


def test_look_alike_page_of_another_site_is_not_claimed():
    head = '<title>Brill: A title</title><link rel="stylesheet" href="https://brill.com/assets/x.css">'
    html = _page(_byline("Hoppe, Albrecht"), _note("Dr. Albrecht Hoppe, Some Archive, Berlin"), head=head)
    parser = DunckerHumblot(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_page_without_byline_is_left_to_the_generic_parser():
    html = _page("<p>No byline here</p>", metas='<meta name="citation_author" content="Jell, Florian"/>')
    assert not DunckerHumblot(BeautifulSoup(html, "lxml")).authors_found()
    assert [a["name"] for a in _authors(html)] == ["Jell, Florian"]
