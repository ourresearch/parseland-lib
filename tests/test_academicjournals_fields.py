"""Academic Journals (academicjournals.org, DOI prefix 10.5897): affiliations and the starred author (oxjob #2338).

Markup cut down from the site's stored abstract pages (sample of 17 Nov 2026). Two byline templates: the current one
(a div.user card per author: li.authorname, then one li with that author's affiliation) and the older one (an h5.black
line of names with plain markers glued on, "Mashaly1, 2*", then span.black with one affiliation per line and an
"Email:" line). The citation_author tags carry names only, so the generic parser read no affiliation on either.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.academicjournals import AcademicJournals

URL = "https://doi.org/10.5897/AJB12.2905"
SITE = ('<meta name="citation_publisher" content="Academic Journals" />'
        '<meta name="citation_pdf_url" content="https://academicjournals.org/journal/AJB/article-full-text-pdf/1F.pdf" />')
ABSTRACT = ("Improvement of seed performance by static magnetic field constitutes a safe ecological way to substitute "
            "chemicals use. In laboratory conditions, we studied the effects of presowing seeds of two varieties by "
            "moderate fields on growth and oxidative status, using different intensities and exposure times.")
EMAIL = ('<span><span class=\'black\'>Email</span>: <a href="/cdn-cgi/l/email-protection#6c01"><span class="__cf_email__"'
         ' data-cfemail="b8d5">[email&#160;protected]</span></a><br></span>')


def _page(names, byline, head=SITE):
    metas = "".join(f'<meta name="citation_author" content="{n}" />' for n in names)
    return (f"<html><head>{head}{metas}<meta name=\"citation_title\" content=\"A title\" /></head><body>"
            f"<div class=\"abstract_title\"><h2>A title</h2><p>{byline}</p>"
            f"<div class=\"abstract_stats\"><ul><li>Article Number - 1FE8CD323683</li></ul></div></div>"
            f"<div class=\"articles abstract_details\"><p class=\"heading\">Abstract</p><p>{ABSTRACT}</p></div>"
            f"</body></html>")


def _older(names_line, affs_line, email=EMAIL):
    return f"<h5 class='black'>\n&nbsp;\n{names_line}\n&nbsp;\n</h5>\n<span class='black'>\n&nbsp;\n{affs_line}\n</span><br />\n{email}"


def _card(name, aff):
    return (f'<div class="user"><h5>{name}</h5><ul><li class="authorname">{name}</li><li>{aff}</li>'
            f'<li class="sep search">Search for this author on:</li><li><a href="https://scholar.google.com/'
            f'scholar?q=x" target="_blank">Google Scholar</a></li></ul></div>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)["authors"]


def test_older_template_numbered_affiliations_and_star():
    names = ["Fahd Abdu Al-Mekhlafi", "Ashraf Mohamed Ali Mashaly", "", "Mohamed Ahmed Wadaan", "Nazar M. Al-Mallah"]
    byline = _older("Fahd Abdu Al-Mekhlafi1, Ashraf Mohamed Ali Mashaly1, 2*,Mohamed Ahmed Wadaan1&nbsp;and "
                    "Nazar M. Al-Mallah3",
                    "1Department of Zoology, King Saud University, Riyadh 11451, Kingdom of Saudi Arabia.\n"
                    "2Department of Zoology, Minia University, El-Minia, Egypt.\n"
                    "3Plant Protection Department, Mosul University, Mosul, Iraq.")
    authors = _parse(_page(names, byline))
    assert [a["name"] for a in authors] == ["Fahd Abdu Al-Mekhlafi", "Ashraf Mohamed Ali Mashaly",
                                            "Mohamed Ahmed Wadaan", "Nazar M. Al-Mallah"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Department of Zoology, King Saud University, Riyadh 11451, Kingdom of Saudi Arabia."],
        ["Department of Zoology, King Saud University, Riyadh 11451, Kingdom of Saudi Arabia.",
         "Department of Zoology, Minia University, El-Minia, Egypt."],
        ["Department of Zoology, King Saud University, Riyadh 11451, Kingdom of Saudi Arabia."],
        ["Plant Protection Department, Mosul University, Mosul, Iraq."]]
    assert [a["is_corresponding"] for a in authors] == [False, True, False, False]


def test_older_template_byline_spelling_and_no_star_marks_no_one():
    names = ["Maroua Akacha Touati", "Neziha Ghanem Boughanmi", "Rabiaa Haouala"]
    byline = _older("Maroua Akacha Touati1, N&eacute;ziha Ghanem Boughanmi1&nbsp;and\nRabiaa Haouala2",
                    "1Faculty of Sciences of Bizerta, University of Carthage,&nbsp;7021 Zarzouna, Tunisia.\n"
                    "2Higher Institute of Agronomy, University of Sousse,&nbsp;4042&nbsp;Chott Meriem, Tunisia.")
    authors = _parse(_page(names, byline))
    assert [a["name"] for a in authors] == ["Maroua Akacha Touati", "Néziha Ghanem Boughanmi", "Rabiaa Haouala"]
    assert authors[2]["affiliations"] == [{"name": "Higher Institute of Agronomy, University of Sousse, 4042 Chott "
                                                   "Meriem, Tunisia."}]
    assert not any(a["is_corresponding"] for a in authors)


def test_older_template_one_unnumbered_affiliation_goes_to_everyone():
    names = ["Abraham Bairu", "Yirgale G/her", "Gebrehiwot G/her"]
    byline = _older("Abraham Bairu*, Yirgale G/her and Gebrehiwot G/her",
                    "Tigray Water Resources Bureau, Mekelle, Tigray, Ethiopia.")
    authors = _parse(_page(names, byline))
    assert [a["affiliations"] for a in authors] == [[{"name": "Tigray Water Resources Bureau, Mekelle, Tigray, "
                                                              "Ethiopia."}]] * 3
    assert [a["is_corresponding"] for a in authors] == [True, False, False]


def test_older_template_star_without_the_email_legend_is_not_read():
    names = ["Abraham Bairu", "Yirgale G/her"]
    byline = _older("Abraham Bairu1*&nbsp;and Yirgale G/her2", "1Bureau A, Mekelle, Ethiopia.\n2Bureau B, Ethiopia.",
                    email="")
    authors = _parse(_page(names, byline))
    assert [a["affiliations"] for a in authors] == [[{"name": "Bureau A, Mekelle, Ethiopia."}],
                                                    [{"name": "Bureau B, Ethiopia."}]]
    assert not any(a["is_corresponding"] for a in authors)


def test_current_template_cards_names_from_the_byline():
    # the site's citation_author tags drop accented letters ("J&essica"); the cards print the names whole
    names = ["J&amp;essica Naiara dos Santos", "Charles Owach*"]
    cards = _card("Jéssica Naiara dos Santos", "Federal University of Jequitinhonha and Mucuri Valleys, Diamantina, "
                  "Brasil.") + _card("Charles Owach*", "Food and Agriculture Organization, Kampala, Uganda.")
    authors = _parse(_page(names, cards))
    assert [a["name"] for a in authors] == ["Jéssica Naiara dos Santos", "Charles Owach"]
    assert [a["affiliations"] for a in authors] == [
        [{"name": "Federal University of Jequitinhonha and Mucuri Valleys, Diamantina, Brasil."}],
        [{"name": "Food and Agriculture Organization, Kampala, Uganda."}]]
    assert [a["is_corresponding"] for a in authors] == [False, True]


def test_abstract_unchanged_from_the_generic_reader():
    html = _page(["Solomon Chollom"], _card("Solomon Chollom", "Federal University, Lafia, Nigeria."))
    assert parse_page(html.encode(), "doi", URL)["abstract"] == ABSTRACT


def test_byline_that_does_not_match_the_tags_is_left_to_the_generic_parser():
    names = ["Ana Lima", "Rui Costa", "Joao Silva"]
    byline = _older("Lima, Ana1 and Costa, Rui1", "1Universidade X, Lisboa, Portugal.")  # 4 parts for 3 tags
    soup = BeautifulSoup(_page(names, byline), "lxml")
    assert not AcademicJournals(soup).authors_found()
    assert [a["name"] for a in _parse(_page(names, byline))] == names


def test_look_alike_page_of_another_publisher_is_not_claimed():
    other = ('<meta name="citation_publisher" content="Academic Journals Inc." />'
             '<meta name="citation_pdf_url" content="https://example.org/a.pdf" />')
    html = _page(["Solomon Chollom"], _card("Solomon Chollom", "Federal University, Lafia, Nigeria."), head=other)
    soup = BeautifulSoup(html, "lxml")
    assert not AcademicJournals(soup).is_publisher_specific_parser()
    assert not AcademicJournals(soup).authors_found()
    assert _parse(html)[0]["affiliations"] == []


def test_site_page_without_a_byline_is_not_claimed():
    html = f"<html><head>{SITE}</head><body><p>You need to be signed in to view this page.</p></body></html>"
    assert not AcademicJournals(BeautifulSoup(html, "lxml")).authors_found()


def test_older_byline_wins_over_tags_split_at_and():
    # the site's citation_author tags split "Luis Fernando" at "and"; the byline is read as printed
    names = ["Emilio Exaire-Murad", "Luis Fern", "o Paredes-Fernandez", "Noemi Santos-Caballero"]
    byline = _older("Emilio Exaire-Murad1, Luis Fernando Paredes-Fern&aacute;ndez1&nbsp;and Noem&iacute; "
                    "Santos-Caballero2*", "1Hospital General, Mexico City, Mexico.\n2Landsteiner Scientific, Mexico.")
    authors = _parse(_page(names, byline))
    assert [a["name"] for a in authors] == ["Emilio Exaire-Murad", "Luis Fernando Paredes-Fernández",
                                            "Noemí Santos-Caballero"]
    assert [a["is_corresponding"] for a in authors] == [False, False, True]
