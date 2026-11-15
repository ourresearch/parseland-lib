"""A repository record's description meta tag is its abstract when the page prints it (oxjob #2239).

9c1dc07 stopped the generic parser from reading og:description / description, because WEKO repositories put the
same site blurb there on every record. But on most repository and small-publisher record pages (DSpace, Digital
Commons, figshare, Zenodo) those tags are the only ones holding the record's abstract, and the page prints the same
text: on 180 random stored pages that lost an abstract to 9c1dc07, the gold (Opus 5.5 xhigh, two passes) confirmed
98 printed ones, and reading printed descriptions brings back all 98 while the site blurbs, printed nowhere, stay out.
"""
from bs4 import BeautifulSoup

from parseland_lib.not_abstract import is_not_abstract
from parseland_lib.publisher.parsers.generic import GenericPublisherParser

ABSTRACT = (
    "Phosphorus scarcity, jointly with eutrophication problems and water shortage, are forcing urban wastewater "
    "treatment plants to recover nutrients. This study compares three recovery routes at pilot scale and finds that "
    "struvite precipitation after anaerobic digestion recovers most phosphorus at the lowest cost per kilogram."
)
BLURB = (
    "The Institutional Repository collects, preserves and disseminates the scientific output of the University, "
    "including journal articles, theses, conference papers and datasets, and makes it openly available to the world "
    "through the internet in accordance with the University's open access policy."
)


def parse(html):
    return GenericPublisherParser(BeautifulSoup(html, "lxml")).parse()["abstract"]


def page(desc, body):
    return (f'<html><head><meta name="citation_title" content="Nutrient recovery" />'
            f'<meta property="og:description" content="{desc}" /><meta name="description" content="{desc}" />'
            f"</head><body>{body}</body></html>")


def test_printed_description_is_the_abstract():
    html = page(ABSTRACT, f"<h1>Nutrient recovery</h1><div class='item-abstract'><p>{ABSTRACT}</p></div>")
    assert parse(html) == ABSTRACT


def test_printed_with_different_markup_and_spacing_still_counts():
    body = ABSTRACT.replace("struvite", "<i>struvite</i>").replace(", ", ",\n  ")
    assert parse(page(ABSTRACT, f"<span>{body}</span>")) == ABSTRACT


def test_site_blurb_only_in_the_head_stays_out():
    assert parse(page(BLURB, "<h1>Nutrient recovery</h1><p>Full text not available.</p>")) is None


def test_text_only_inside_a_script_is_not_printed():
    html = page(ABSTRACT, f"<script>window.meta = {{'d': '{ABSTRACT}'}};</script><p>Record</p>")
    assert parse(html) is None


def test_whole_text_in_the_description_is_not_an_abstract():
    story = ABSTRACT * 60  # > 10,000 characters: a short story's whole text, not an abstract
    assert parse(page(story, f"<div>{story}</div>")) is None


def test_citation_abstract_still_wins():
    other = "A different abstract given as article-level metadata, " * 6
    html = page(ABSTRACT, f"<p>{ABSTRACT}</p>").replace(
        "<meta property", f'<meta name="citation_abstract" content="{other.strip()}" /><meta property', 1)
    assert parse(html) == other.strip()


def test_digital_commons_first_paragraph_is_not_an_abstract():
    text = ("(First paragraph) Plucking chickens the kosher way is quite an art. According to the laws of kashrut a "
            "chicken must be slaughtered by a trained shochet, and the feathers are then removed by hand.")
    assert is_not_abstract(text)
    assert parse(page(text, f"<p>{text}</p>")) is None


def test_data_citation_line_is_not_an_abstract():
    assert is_not_abstract(
        "Preßler, Erhard (1992): Tree-ring width of Quercus species from historical object sample 2131B/16A, "
        "Netherlands, Norg. Preßler GmbH - Planung und Bauforschung, Gersten/Germany, PANGAEA, "
        "https://doi.org/10.1594/PANGAEA.148663")
    assert is_not_abstract(
        "Cuevas-Agulló, Emilio (2021): Radiosonde measurements from station Izaña (2021-08) [dataset]. Izaña "
        "Atmospheric Research Center, Meteorological State Agency of Spain, PANGAEA, "
        "https://doi.org/10.1594/PANGAEA.935905")
    assert not is_not_abstract(ABSTRACT + " Data: https://doi.org/10.1594/PANGAEA.935905")


def test_opening_paragraph_of_the_full_text_is_not_an_abstract():
    # JAMA case reports and news posts put the text's first paragraph in the description tag
    html = page(ABSTRACT, f"<div class='article-full-text'><p class='para'>{ABSTRACT}</p><p>More text.</p></div>")
    assert parse(html) is None
    html = page(ABSTRACT, f"<article class='post type-post'><p>{ABSTRACT}</p></article>")
    assert parse(html) is None


def test_abstract_block_inside_the_article_body_still_counts():
    html = page(ABSTRACT, f"<div class='article-body'><p class='articleBody_abstractText'>{ABSTRACT}</p></div>")
    assert parse(html) == ABSTRACT
