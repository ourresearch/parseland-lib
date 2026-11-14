"""Authors on APA's supplemental-material pages (supp.apa.org, DOIs ending ".supp") (oxjob #2213).

Markup is cut down from stored supp.apa.org pages (13 Nov 2026, #2213 EXPLORE § 1). The page has no meta tags, so no
parser read its byline and ~22K supplementary-materials works showed no authors. The byline is one
<span class="author">: names joined by commas and a final "and", sometimes each followed by an ORCID icon link. Two
markup variants: an older one (<h1>, <p class="disclaimer">) and a newer one (<div class="title1">,
<div class="disclaimer">).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.apa_supplemental import APASupplementalMaterial

URL = "https://supp.apa.org/psycarticles/supplemental/tep0000103/tep0000103_supp.html"
LOGO = '<img alt="APA\'s header logo" class="logo-content" src="../apa-logo.png"/>'
OLD_NOTE = ('<p class="disclaimer">This content was submitted by the author as supplemental \n material for an article '
            'published in APA&#8217;s PsycARTICLES. The content is presented as the author submitted it.</p>')
NEW_NOTE = ('<div class="disclaimer">This content was submitted by the author as supplemental \n material for an '
            'article published in APA PsycArticles. The content is presented as the author submitted it.</div>')
ORCID = ('<a href="http://orcid.org/0000-0002-3307-5637" target="_blank"><img src="../orcid.png" alt="ORCID Icon" '
         'title="ORCID Icon"/></a>')


def _old(byline, logo=LOGO, note=OLD_NOTE):
    return (f"<html><head><title>Supplemental Material for A title</title></head><body>{logo}"
            '<div class="jrnname">Training and Education in Professional Psychology</div>'
            '<div><h1>Supplemental Material for </h1><h2>A title</h2>'
            f'<p><span class="author">{byline}</span></p>'
            '<p><span class="journal">Training and Education in Professional Psychology</span>, Vol. 10</p>'
            '<p>View article:<br/><a href="https://doi.org/10.1037/tep0000103">https://doi.org/10.1037/tep0000103</a></p>'
            f"{note}</div></body></html>")


def _new(byline):
    return (f"<html><head><title>Supplemental Material for A title</title></head><body>{LOGO}"
            '<div><div class="title1">Supplemental Material for </div><div class="title2">A title</div>'
            f'<div><span class="author">{byline}</span></div>'
            '<div><span class="journal">Journal of Experimental Psychology</span>, Vol. 35</div>'
            f"{NEW_NOTE}</div></body></html>")


def _names(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"]]


def test_old_template_byline_with_final_and_across_a_line_break():
    byline = "Elizabeth Possis, Beret Skroch, Michael Mallen, and \nDouglas Olson"
    assert _names(_old(byline)) == ["Elizabeth Possis", "Beret Skroch", "Michael Mallen", "Douglas Olson"]


def test_new_template_byline():
    byline = "Derek A. Hamilton, Katherine G. Akers, and \nEdward S. Redhead"
    assert _names(_new(byline)) == ["Derek A. Hamilton", "Katherine G. Akers", "Edward S. Redhead"]


def test_orcid_icons_and_spaces_before_commas_are_dropped():
    byline = (f"Marya T. Schulte {ORCID}, Lisa Armistead {ORCID}, Mark S. Allen , and \nWilliam Marelich\n {ORCID}")
    assert _names(_old(byline)) == ["Marya T. Schulte", "Lisa Armistead", "Mark S. Allen", "William Marelich"]


def test_two_authors_joined_by_and_and_a_single_author():
    assert _names(_old("Sung won Kim and Nancy E. Hill")) == ["Sung won Kim", "Nancy E. Hill"]
    assert _names(_old("Hanna Marno")) == ["Hanna Marno"]


def test_entities_and_name_particles_survive():
    byline = "Agust&#237;n Perez Santangelo , Didrika S. van de Wouw, Lauren O&#8217;Reilly, and Nicole St. Jean"
    assert _names(_old(byline)) == ["Agustín Perez Santangelo", "Didrika S. van de Wouw", "Lauren O’Reilly",
                                    "Nicole St. Jean"]


def test_byline_cut_off_after_its_final_and():
    # 1 of 60 sampled pages ends the byline at "and" (the page drops the last name): keep the names it shows
    byline = f"Jennifer E. Lansford {ORCID}, Jennifer Godwin, Anna Rybi&#324;ska, and "
    assert _names(_old(byline)) == ["Jennifer E. Lansford", "Jennifer Godwin", "Anna Rybińska"]


def test_suffix_stays_with_its_name():
    # joined with a space, not the page's comma: a comma in a name reads downstream as "Family, Given"
    assert _names(_old("John Smith, Jr., Ann Lee, and Bo Chen III")) == ["John Smith Jr.", "Ann Lee", "Bo Chen III"]


def test_no_abstract_no_affiliations_no_corresponding_mark():
    out = parse_page(_old("Elizabeth Possis and Douglas Olson").encode(), "doi", URL)
    assert out["abstract"] is None
    assert all(a["affiliations"] == [] and not a["is_corresponding"] for a in out["authors"])


def test_other_pages_are_not_claimed():
    # a page with a span.author byline and a supplemental note, but no APA header logo
    other = _old("Ann Lee and Bo Chen", logo='<img alt="Header logo" src="../logo.png"/>')
    assert not APASupplementalMaterial(BeautifulSoup(other, "lxml")).is_publisher_specific_parser()
    # an APA page without the supplemental-material note (e.g. a PsycNet shell)
    shell = _old("Ann Lee and Bo Chen", note='<p class="disclaimer">Copyright APA.</p>')
    assert not APASupplementalMaterial(BeautifulSoup(shell, "lxml")).is_publisher_specific_parser()
    assert APASupplementalMaterial(BeautifulSoup(_old("Ann Lee"), "lxml")).is_publisher_specific_parser()
    assert APASupplementalMaterial(BeautifulSoup(_new("Ann Lee"), "lxml")).is_publisher_specific_parser()


def test_parse_returns_no_new_fields_the_page_does_not_show():
    out = APASupplementalMaterial(BeautifulSoup(_old("Ann Lee and Bo Chen"), "lxml")).parse()
    assert set(out) == {"authors", "abstract"}
