"""A description tag about this item is the abstract of last resort (oxjob #2215, EXPLORE § 5).

DSpace 7, Redalyc, Cureus and IEEE Xplore render the abstract with JavaScript, so the stored page holds it only in
og:description / description. 9c1dc07 kept the generic parser off those tags (a repository's site blurb on every
record page); this reader takes one back only when it shares content words with the item's title and is not a
citation line.
"""
import pytest

from parseland_lib.parse import parse_page

ABSTRACT = ("The location and identification of harmonic sources in radial distribution feeders are essential tasks "
            "since they improve power quality monitoring. We propose a method that needs only a few synchronized "
            "meters and compare it with two earlier approaches on a test feeder with nonlinear loads.")
BLURB = ("UTokyo Repository is the institutional repository of the University of Tokyo. It collects, preserves and "
         "makes available the research output of the university: papers, theses, bulletins and data, free to read "
         "for anyone in the world, as part of the university's commitment to open science and open access.")
CITATION = ("Michael B. Walbank, Harmonic Source Location in Radial Distribution Feeders, Hesperia: The Journal of the "
            "American School of Classical Studies at Athens, Vol. 81, No. 2 (2012), pp. 231-262, with notes on the "
            "inscriptions and their dates, and a list of the documents.")


def page(description, title="Harmonic Source Location in Radial Distribution Feeders", extra=""):
    return (f'<html><head><meta name="citation_title" content="{title}">'
            f'<meta property="og:description" content="{description}">{extra}</head>'
            '<body><div id="app"></div></body></html>')


@pytest.mark.parametrize("namespace", ["pmh", "doi"])
def test_a_description_about_the_item_is_the_abstract(namespace):
    assert parse_page(page(ABSTRACT), namespace)["abstract"] == ABSTRACT


@pytest.mark.parametrize("html", [
    page(BLURB),  # a site blurb: no word of the title
    page(CITATION),  # a citation line carries the whole title
    page(ABSTRACT, extra='<link rel="stylesheet" href="/bloomsbury_assets/x/bootstrap.css">'),  # an entry's opening
    page(ABSTRACT, title="Home"),  # nothing to compare with
], ids=["site-blurb", "citation-line", "bloomsbury", "no-title"])
def test_a_description_not_about_the_item_is_not(html):
    assert parse_page(html, "pmh")["abstract"] in (None, "")
