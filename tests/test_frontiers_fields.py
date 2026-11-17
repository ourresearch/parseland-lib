"""Frontiers conference abstracts and the parser's cheap claim (oxjob #2289).

Markup is cut down from stored 10.3389/conf.* pages (2009-2019, the Frontiers Events abstract pages): og:url is left
empty, so the Frontiers parser never claimed them, no meta tags name the authors, and nothing read their affiliations
or corresponding marks. The claim now reads <head> only before any tree search (#2239: every parser's claim runs on
every DOI page).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.frontiers import Frontiers

URL = "https://doi.org/10.3389/conf.fnins.2019.96.00003"
CTL = "ctl00_ctl00_MainContentPlaceHolder_ContentAreaMainContent_ucAbstractDetails"
EVENTS_BLURB = ("Frontiers Events is a rapidly growing calendar management system dedicated to the scheduling of "
                "academic events.")


def _author(i, given, family, sup):
    return (f'<a href="/people/X/{i}" id="{CTL}_rptAuthors_ctl{i:02d}_aAuthor">\n {given}\n\n {family}</a>'
            f'<sup>{sup}</sup>')


BYLINE = (_author(0, "Lien", "Naert", "1*") + ", \n" + _author(2, "Wim", "Fias", "1") + " and \n"
          + _author(4, "Mario", "Bonato", "2"))
NOTE = (f'<p id="{CTL}_pCorrespondence"><span>* Correspondence:</span> Ms. Lien Naert, Ghent University, Ghent, '
        f'Belgium, l.naert@example.org<br/></p>')


def _conf_page(byline=BYLINE, note=NOTE, site="Frontiers"):
    return f"""<html><head><title>Frontiers | Dividing attention across space and tasks</title>
<meta content="Frontiers | " id="ctl00_ctl00_MetaTitle" name="Title" property="og:title"/>
<meta content="{EVENTS_BLURB}" name="Description" property="og:description"/>
<meta id="ctl00_ctl00_MetaImageUrl" name="url" property="og:url"/>
<meta content="{site}" name="site_name" property="og:site_name"/>
</head><body><div class="print"><div id="divFontAdjAreaLevel4" class="JournalAbstract">
<h1>Dividing attention across space and tasks: a study in acute stroke patients</h1>
<div class="authors">{byline}</div>
<ul class="notes">
<li id="{CTL}_rptAffiliation_ctl00_liAffilliation"><span><sup>\n 1</sup></span>\n Ghent University, Belgium\n</li>
<li id="{CTL}_rptAffiliation_ctl01_liAffilliation"><span><sup>\n 2</sup></span>\n University of Padova, Italy\n</li>
</ul>
<p class="pb15"><span id="{CTL}_litAbstract" class="cont16 white-space-wrap">Objective

After a unilateral stroke the processing of contralesional hemispace can be affected by a number of factors.

Conclusion
The divided-attention procedure we adopted here has a number of methodological strengths. </span></p>
</div>
<div class="References"><p class="ReferencesCopy1">Bonato, M. (2010). Neuropsychologia, 48, 3934-3940.</p></div>
<div class="AbstractSummary"><p id="{CTL}_pCitation"><span>Citation:</span> Naert L, Fias W and Bonato M (2019).
doi: 10.3389/conf.fnins.2019.96.00003</p>{note}</div></div></body></html>"""


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def test_conference_abstract_byline_and_affiliations():
    authors = _parse(_conf_page())["authors"]
    assert [a["name"] for a in authors] == ["Lien Naert", "Wim Fias", "Mario Bonato"]
    assert [[x["name"] for x in a["affiliations"]] for a in authors] == [
        ["Ghent University, Belgium"], ["Ghent University, Belgium"], ["University of Padova, Italy"]]


def test_conference_abstract_corresponding_star_explained_by_note():
    assert [a["is_corresponding"] for a in _parse(_conf_page())["authors"]] == [True, False, False]


def test_conference_abstract_star_without_note_marks_no_one():
    assert not any(a["is_corresponding"] for a in _parse(_conf_page(note=""))["authors"])


def test_conference_abstract_text_not_the_events_blurb():
    abstract = _parse(_conf_page())["abstract"]
    assert abstract.startswith("Objective\nAfter a unilateral stroke the processing")
    assert abstract.endswith("has a number of methodological strengths.")
    assert "Frontiers Events" not in abstract


def test_conference_byline_with_an_unlinked_name_is_not_claimed():
    byline = BYLINE.replace(" and \n", ", Ann Plain<sup>2</sup> and \n")
    assert not Frontiers(BeautifulSoup(_conf_page(byline=byline), "lxml")).authors_found()


def test_lookalike_markup_on_another_site_is_not_claimed():
    parser = Frontiers(BeautifulSoup(_conf_page(site="Events Calendar"), "lxml"))
    assert not parser.authors_found() and not parser.is_publisher_specific_parser()


# The old claim took every page with a div.authors (Open Monograph Press, Scholastica, Ubiquity, OJS themes)

OMP_LIKE = """<html><head><meta name="generator" content="Open Monograph Press 3.3.0.8"/>
<meta property="og:url" content="https://press.example.org/catalog/book/12"/></head><body>
<div class="authors"><span class="name">Ann Author</span>, <span class="name">Bo Writer</span></div>
<ul class="notes"><li><sup>1</sup> Some University</li></ul></body></html>"""


def test_nearest_other_template_with_div_authors_is_not_claimed():
    parser = Frontiers(BeautifulSoup(OMP_LIKE, "lxml"))
    assert not parser.authors_found() and not parser.is_publisher_specific_parser()


def _journal_page(og_url):
    img = '<img class="pr5" src="https://loop.frontiersin.org/images/profile/1/24"/>'
    return (f'<html><head><meta property="og:url" content="{og_url}"/></head><body><div class="authors">'
            f'<a href="#">{img}Kati Sarnola</a><sup>1*</sup>, <a href="#">{img}Heini Kari</a><sup>2</sup></div>'
            f'<ul class="notes"><li><sup>1</sup> Kela, Helsinki, Finland</li><li><sup>2</sup> University of Turku, '
            f'Turku, Finland</li></ul></body></html>')


def test_journal_page_still_claimed_and_read():
    parser = Frontiers(BeautifulSoup(_journal_page(
        "https://www.frontiersin.org/articles/10.3389/fphar.2022.943249/full"), "lxml"))
    assert parser.authors_found() and parser.is_publisher_specific_parser()
    authors = parser.parse()["authors"]
    assert [(a.name, a.is_corresponding) for a in authors] == [("Kati Sarnola", True), ("Heini Kari", False)]


def test_partner_page_read_but_not_claimed_as_before():
    parser = Frontiers(BeautifulSoup(_journal_page(
        "https://www.ssph-journal.org/articles/10.3389/ijph.2023.1605840/full"), "lxml"))
    assert parser.authors_found() and not parser.is_publisher_specific_parser()


def test_journal_markup_without_a_frontiers_og_url_is_not_claimed():
    parser = Frontiers(BeautifulSoup(_journal_page("https://journal.example.org/article/1"), "lxml"))
    assert not parser.authors_found()
