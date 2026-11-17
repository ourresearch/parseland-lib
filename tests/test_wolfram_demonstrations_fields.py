"""Wolfram Demonstrations Project item pages (demonstrations.wolfram.com, DOI prefix 10.3840) (oxjob #2339).

Markup is cut down from stored pages of the site (17 Nov 2026). The pages carry no citation_* tags, so before this
parser Parseland read no author from them, and an abstract only when the description meta tag (cut at 400 characters)
was long enough. The byline is "Contributed by: <a>Name</a> and <a>Name</a> (Month Year)", the abstract the
description section's paragraphs (the part after "[more]" is in the page, hidden).
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.wolfram_demonstrations import WolframDemonstrations

URL = "https://doi.org/10.3840/07001806"
HEAD = ('<head><meta charset="utf-8"><title>{title} - Wolfram Demonstrations Project</title>'
        '<meta name="description" content="{meta}">'
        '<meta property="og:url" content="/RotationalSymmetriesOfPlatonicSolids/">'
        '<link rel="stylesheet" href="/common/framework/css/framework.en.css">'
        '<link rel="stylesheet" href="/app-files/assets/css/demonstration.css"></head>')
DESCRIPTION = ('<div id="section-description" class="description"><p id="descriptionSectionParagraph">A symmetry of a '
               'figure moves a copy of the figure to coincide with its original position. If <span class="InlineFormula">'
               '<img src="img/desc1.png" align="absmiddle"></span> and <span class="InlineFormula"><img src="img/desc2.png">'
               '</span> are symmetries, so is their product.</p></div>')
MORE = ('<div id="section-description" class="description"><p></p><p id="descriptionSectionParagraph">The qualifications '
        'of an incoming academic class depend on admission and matriculation.</p> <a href="#more" class="more">[more]</a>'
        '<p></p><div class="details hide"><p id="descriptionSectionParagraph">The grayish curve is the probability of '
        'being offered admission.</p><p id="descriptionSectionParagraph">Change the curves by dragging the locators.</p>'
        ' <a href="#less" class="less">[less]</a></div></div>')


def _link(name):
    return f'<a href="http://demonstrations.wolfram.com/author.html?author={name.replace(" ", "+")}">{name}</a>'


def _byline(inner):
    return (f'<div id="contributed-section"><p class="contributed-by">Contributed by: {inner}'
            '<span class="contentTerms" id="publishdate"><br>Open content licensed under '
            '<a href="http://www.wolfram.com/legal/terms/wolfram-demonstrations-project.html">CC BY-NC-SA</a></span>'
            '</p></div>')


DATE = '&#xA0;<span id="publishdate">(September 2007)</span>'


def _page(byline, description=DESCRIPTION, title="Rotational Symmetries of Platonic Solids", meta="A symmetry."):
    citation = ('<div id="section-permanent-citation" class="permanent-citation"><h2>Permanent Citation</h2>'
                f'<p class="citation"><span class="citation-author">{_link("George Beck")}</span></p></div>')
    related = ('<div class="related-demonstrations"><a href="/CombiningTwo3DRotations/">Combining Two 3D Rotations</a>'
               '<span>George Beck and Jeff Bryant</span></div>')
    return (f'<!DOCTYPE html><script>window.public_embed_src = "prd"</script><html lang="en">'
            f'{HEAD.format(title=title, meta=meta)}<body class="demonstration"><main class="main"><section>'
            f'<h1 id="demoTitle">{title}</h1>{description}{byline}<hr>{citation}{related}</section></main></body></html>')


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _names(html):
    return [a["name"] for a in _parse(html)["authors"]]


def test_single_contributor_is_the_author():
    out = _parse(_page(_byline(_link("George Beck") + DATE)))
    assert out["authors"] == [{"name": "George Beck", "affiliations": [], "is_corresponding": False}]


def test_two_contributors_in_byline_order():
    assert _names(_page(_byline(_link("Jean Buck") + " and " + _link("Mike Pilat") + DATE))) == \
        ["Jean Buck", "Mike Pilat"]


def test_based_on_a_program_by_is_not_an_author():
    inner = _link("Jeff Bryant") + DATE + "<br>Based on a program by: " + _link("Michael Trott")
    assert _names(_page(_byline(inner))) == ["Jeff Bryant"]


def test_additional_contributions_are_not_authors():
    inner = ('<a href="http://demonstrations.wolfram.com/search.html?query=Frederick+Wu">Frederick Wu</a>' + DATE +
             '<br>Additional contributions by: <a href="http://demonstrations.wolfram.com/search.html?query=Bing+Ye">'
             'Bing Ye</a>')
    assert _names(_page(_byline(inner))) == ["Frederick Wu"]


def test_book_credit_after_the_date_is_not_a_second_author():
    inner = (_link("Michael Trott") + " with permission of Springer" + DATE + "<br>From: <em>The Mathematica "
             "GuideBook for Programming</em>, second edition by " + _link("Michael Trott") + " (&#xA9; Springer, 2008).")
    assert _names(_page(_byline(inner))) == ["Michael Trott"]


def test_unlinked_names_are_read_from_the_text():
    assert _names(_page(_byline("Ed Zaborowski and Jane Roe" + DATE))) == ["Ed Zaborowski", "Jane Roe"]


def test_name_keeps_out_a_parenthesised_school():
    assert _names(_page(_byline(_link("Ed Zaborowski") + " (Franklin Road Academy)" + DATE))) == ["Ed Zaborowski"]


def test_abstract_is_the_description_without_formula_images():
    abstract = _parse(_page(_byline(_link("George Beck") + DATE)))["abstract"]
    assert abstract == ("A symmetry of a figure moves a copy of the figure to coincide with its original position. If "
                        "and are symmetries, so is their product.")


def test_abstract_keeps_the_hidden_more_paragraphs():
    abstract = _parse(_page(_byline(_link("Seth J. Chandler") + DATE), description=MORE))["abstract"]
    assert abstract == ("The qualifications of an incoming academic class depend on admission and matriculation.\n"
                        "The grayish curve is the probability of being offered admission.\n"
                        "Change the curves by dragging the locators.")


def test_short_description_is_read():
    # the meta-tag readers keep only descriptions over 200 characters, so these were lost
    description = ('<div id="section-description" class="description"><p id="descriptionSectionParagraph">The red '
                   'wheel turns once and the radii of the wheels add to one.</p></div>')
    out = _parse(_page(_byline(_link("Michael Schreiber") + DATE), description=description))
    assert out["abstract"] == "The red wheel turns once and the radii of the wheels add to one."


def test_new_fields_are_not_returned():
    soup = BeautifulSoup(_page(_byline(_link("George Beck") + DATE)), "lxml")
    parsed = WolframDemonstrations(soup).parse()
    assert set(parsed) == {"authors", "abstract"}


def test_head_broken_by_a_stray_quote_is_still_claimed():
    # lxml closes <head> at the bad keywords tag and moves the title and stylesheet links into <body>
    html = _page(_byline(_link("Sándor Kabai") + " and " + _link("Szaniszló Bérczi") + DATE)).replace(
        '<meta charset="utf-8">', '<meta name="keywords" content="<a href=" http: mathworld.wolfram.com '
        "roulette.html'></head><body class=\"demonstration\">Roulette&apos;/&gt;<meta charset=\"utf-8\">", 1)
    assert _names(html) == ["Sándor Kabai", "Szaniszló Bérczi"]


def test_site_not_found_page_is_not_claimed():
    html = ('<html><head><title>Wolfram Demonstrations Project</title><meta name="description" content="Explore '
            'thousands of free applications across science, mathematics, engineering, technology, business, art, '
            'finance, social sciences, and more."><link rel="stylesheet" href="/app-files/assets/css/global.css">'
            '</head><body><p>Oops, the page you\'re looking for can\'t be found.</p></body></html>')
    parser = WolframDemonstrations(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert _parse(html)["authors"] == []


def test_look_alike_byline_on_another_site_is_not_claimed():
    html = ('<html><head><title>Rotating Cubes - Interactive Math Gallery</title>'
            '<link rel="stylesheet" href="/assets/css/demonstration.css"></head><body>'
            + _byline(_link("George Beck") + DATE) + DESCRIPTION + '</body></html>')
    parser = WolframDemonstrations(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()
    assert "George Beck" not in [a["name"] for a in _parse(html)["authors"]]
