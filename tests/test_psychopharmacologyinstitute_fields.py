"""Psychopharmacology Institute lesson and publication pages (psychopharmacologyinstitute.com, DOI prefix 10.64239;
oxjob #2339).

Markup is cut down from stored pages of the site (17 Nov 2026). The site is WordPress with no citation_* meta tags; a
lesson or publication page prints its byline in <section class="author-details">: one card per author, the name with
degrees in h2.author-name and "<job title> - <institution>" under it, the institution in its own
span.author-affiliation-name. The home page shows author cards too (div.author-details, in publication listings), but
it presents no one work and must not be read.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.psychopharmacologyinstitute import PsychopharmacologyInstitute

URL = "https://psychopharmacologyinstitute.com/section/a-lesson-2658-5232/"
HEAD = ('<meta property="og:type" content="article" />'
        '<meta property="og:url" content="https://psychopharmacologyinstitute.com/section/a-lesson-2658-5232/" />'
        '<meta property="og:site_name" content="Psychopharmacology Institute" />')


def _card(name, job=None, aff=None):
    affiliation = ""
    if job or aff:
        affiliation = ('<div class="author-affiliation">'
                       + (f'<span class="author-job-title">{job}</span>' if job else "")
                       + ('<span class="author-separator">-</span>' if job and aff else "")
                       + (f'<span class="author-affiliation-name">{aff}</span>' if aff else "")
                       + "</div>")
    return (f'<div class="details-container"><div class="author-avatar"><img src="a.jpg" /></div>'
            f'<div class="author-info"><a href="/author/x/" aria-label="Author Profile">'
            f'<h2 class="author-name"> {name} </h2></a>{affiliation}</div></div>')


def _page(cards, head=HEAD, extra_head="", body_before=""):
    return (f"<html><head><title>A lesson | Psychopharmacology Institute</title>{head}{extra_head}</head><body>"
            f'<h1 class="entry-title">01. A Lesson</h1>{body_before}'
            f'<section class="author-details" aria-label="Author Details">{"".join(cards)}</section>'
            f'<div class="post-content"><h2 class="content-title">Text version</h2><p>Hi! Text here.</p></div>'
            f"</body></html>")


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]], a["is_corresponding"])
            for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_author_card_gives_name_without_degrees_and_institution():
    html = _page([_card("James Phelps, M.D.", "Research Editor", "Psychopharmacology Institute")])
    assert _authors(html) == [("James Phelps", ["Psychopharmacology Institute"], False)]


def test_job_title_is_not_an_affiliation():
    html = _page([_card("Paul S. Links, M.D., F.R.C.P.C.",
                        "Professor Emeritus in the Department of Psychiatry and Behavioural Neurosciences",
                        "McMaster University in Hamilton, Ontario, Canada")])
    assert _authors(html) == [("Paul S. Links", ["McMaster University in Hamilton, Ontario, Canada"], False)]


def test_card_with_job_title_only_gives_no_affiliation():
    html = _page([_card("Oliver Freudenreich, M.D.", "Co-Director of the MGH Psychosis Clinical and Research Program")])
    assert _authors(html) == [("Oliver Freudenreich", [], False)]


def test_two_cards_give_two_authors_in_order():
    html = _page([_card("Ken Gillman, M.D."), _card("Helen Tellegen, P.M.H.N.P.")])
    assert _authors(html) == [("Ken Gillman", [], False), ("Helen Tellegen", [], False)]


def test_printed_byline_wins_over_stale_json_ld_author():
    ld = ('<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"ScholarlyArticle",'
          '"name":"A Lesson","author":{"@type":"Person","name":"David A. Gorelick"}}]}</script>')
    html = _page([_card("Scott R. Beach, M.D.", "Associate Professor of Psychiatry", "Harvard Medical School")],
                 extra_head=ld)
    assert _authors(html) == [("Scott R. Beach", ["Harvard Medical School"], False)]


def test_home_page_listing_cards_are_not_read():
    html = ('<html><head><meta property="og:type" content="website" />'
            '<meta property="og:url" content="https://psychopharmacologyinstitute.com/" />'
            '<meta property="og:site_name" content="Psychopharmacology Institute" /></head><body>'
            '<a href="/publication/x/"><div class="publication-card"><h3 class="publication-title">A guide</h3>'
            '<div class="author-details"><div class="author-name"> James K. Rustad, M.D. </div>'
            '<div class="author-job"> Geisel School of Medicine at Dartmouth </div></div></div></a></body></html>')
    soup = BeautifulSoup(html, "lxml")
    assert not PsychopharmacologyInstitute(soup).authors_found()
    assert _authors(html) == []


def test_look_alike_page_of_another_site_is_not_claimed():
    other = ('<meta property="og:type" content="article" />'
             '<meta property="og:url" content="https://example-cme.org/section/a-lesson/" />'
             '<meta property="og:site_name" content="Example CME Academy" />')
    html = _page([_card("Jane Doe, M.D.", "Professor", "Example University")], head=other)
    parser = PsychopharmacologyInstitute(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_new_fields_are_empty():
    html = _page([_card("James Phelps, M.D.", "Research Editor", "Psychopharmacology Institute")])
    parsed = PsychopharmacologyInstitute(BeautifulSoup(html, "lxml")).parse()
    assert parsed["abstract"] is None
    assert parsed["acknowledgments"] is None and parsed["funding_statement"] is None
    assert parsed["references"] is None and parsed["references_complete"] is False
