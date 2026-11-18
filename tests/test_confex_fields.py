"""Confex webprogram abstract pages (oxjob #2338, Parseland swarm).

Markup is cut down from stored GSA abstract pages (gsa.confex.com/gsa/<meeting>/webprogram/Paper<n>.html, DOIs
10.1130/abs/...). The page prints the whole byline in div.paperauthors and the abstract in div.abstract; its
citation_author tags name only the presenting author (none at all before 2018), so the generic parser found one author
and no abstract. Two byline styles: numbered ("NAME<sup>1</sup> ... (1)Affiliation, (2)Affiliation") and unnumbered,
where each author, or a run of authors that share it, is followed by the affiliation.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.confex import Confex

URL = "https://gsa.confex.com/gsa/2022AM/webprogram/Paper380201.html"
HEAD = '<link href="stylesheets/webprogram.css" rel="stylesheet" type="text/css">'
ABSTRACT = ("<div>During the Late Eocene, moderate uplift of the southern North American Cordillera triggered "
            "aridification of central North America due to the development of a regional rain shadow. Regional drying "
            "was reflected in a wave of loess deposition that started at approximately 36 Ma.</span></p>\n"
            "<p><span>From Early Eocene to Oligocene, floodplains transitioned from relatively static with well-developed "
            "paleosols to highly dynamic environments, and marine carbonates record a rise in <sup>87</sup>Sr.</span></p>"
            "</div>")


def _page(byline, abstract=ABSTRACT, head=HEAD, metas=""):
    return (f"<!DOCTYPE html><html><head>{head}<title>Abstract: A TITLE (GSA Connects 2022)</title>{metas}</head>"
            f'<body class="paper"><div class="page"><div class="content"><div class="number">Paper No. 1-1</div>'
            f'<h1 class="meetingTitle subtitle clearfix">A TITLE</h1>'
            f'<div class="paperauthors">\n\t{byline}</div><br>'
            f'<div class="abstract">\n\t\t\n\t{abstract}</div>'
            f'<div class="footer"><div class="reference">Geological Society of America <em>Abstracts with Programs.</em> '
            f"Vol. 54, No. 5<br>doi: 10.1130/abs/2022AM-380201</div>"
            f'<div class="copyright">&copy; Copyright 2022 The Geological Society of America (GSA), all rights reserved. '
            f"Permission is hereby granted to the author(s) of this abstract to reproduce and distribute it freely.</div>"
            f"</div></div></div></body></html>")


def _parse(html):
    return parse_page(html.encode(), "doi", URL)


def _authors(html):
    return [(a["name"], [x["name"] for x in a["affiliations"]]) for a in _parse(html)["authors"]]


NUMBERED = ("<b>CHANG, Queenie</b><sup>1</sup>, HREN, Michael T.<sup>2</sup>, LUFFMAN, David B.<sup>1</sup> and "
            "TERRY Jr., Dennis O.<sup>3</sup>, (1)Department of Earth and Environmental Sciences, Denison University, "
            "100 W College St., Granville, OH 43023, (2)Department of Geosciences, University of Connecticut, Storrs, CT "
            "06269, (3)Department of Earth &amp; Environmental Science, Temple University, Philadelphia, PA 19122; "
            "INSTAAR, CU Boulder, 4001 Discovery Drive, Boulder, CO 80309")


def test_numbered_byline_links_each_author_to_their_affiliations():
    assert _authors(_page(NUMBERED)) == [
        ("Queenie CHANG", ["Department of Earth and Environmental Sciences, Denison University, 100 W College St., "
                           "Granville, OH 43023"]),
        ("Michael T. HREN", ["Department of Geosciences, University of Connecticut, Storrs, CT 06269"]),
        ("David B. LUFFMAN", ["Department of Earth and Environmental Sciences, Denison University, 100 W College St., "
                              "Granville, OH 43023"]),
        ("Dennis O. TERRY Jr.", ["Department of Earth & Environmental Science, Temple University, Philadelphia, PA 19122",
                                 "INSTAAR, CU Boulder, 4001 Discovery Drive, Boulder, CO 80309"]),
    ]


def test_unnumbered_byline_each_author_then_their_affiliation_and_no_email():
    byline = ("<b>BROWN, Sarah R.</b>, National Energy Technology Lab, 3610 Collins Ferry Road, Morgantown, WV 26505, "
              "ANDREWS, Graham D.M., Department of Geology and Geography, West Virginia University, Morgantown, WV 26506 "
              "and MUSGRAVE, Robert, School of Geosciences, University of Sydney, Sydney,  2006, Australia, "
              "srbrown19@gmail.com")
    assert _authors(_page(byline)) == [
        ("Sarah R. BROWN", ["National Energy Technology Lab, 3610 Collins Ferry Road, Morgantown, WV 26505"]),
        ("Graham D.M. ANDREWS", ["Department of Geology and Geography, West Virginia University, Morgantown, WV 26506"]),
        ("Robert MUSGRAVE", ["School of Geosciences, University of Sydney, Sydney, 2006, Australia"]),
    ]


def test_a_run_of_authors_shares_the_affiliation_after_it():
    byline = ("<b>TREADO, Lucy E.</b>, HASTINGS, Alexander K. and JAMES, Aryanna L., Virginia Museum of Natural History, "
              "21 Starling Ave, Martinsville, VA 24112, lucy.treado@vmnh.virginia.gov")
    aff = ["Virginia Museum of Natural History, 21 Starling Ave, Martinsville, VA 24112"]
    assert _authors(_page(byline)) == [("Lucy E. TREADO", aff), ("Alexander K. HASTINGS", aff), ("Aryanna L. JAMES", aff)]


def test_semicolons_separate_one_authors_affiliations():
    byline = ("<b>KLEINHANS, Lewis</b>, Denver Region Exploration Geologists' Society (DREGS), Lakewood, CO 80228; "
              "Colorado Scientific Society (CSS), Lakewood, CO 80215 and FISHER, Lisa, Escalante Resources Group, "
              "Denver, CO 80202")
    assert _authors(_page(byline)) == [
        ("Lewis KLEINHANS", ["Denver Region Exploration Geologists' Society (DREGS), Lakewood, CO 80228",
                             "Colorado Scientific Society (CSS), Lakewood, CO 80215"]),
        ("Lisa FISHER", ["Escalante Resources Group, Denver, CO 80202"]),
    ]


def test_an_acronym_in_an_affiliation_is_not_an_author():
    byline = ("<b>SMITH, Jane A.</b>, Earth System Research Laboratory, NOAA, Boulder, CO 80305 and LEE, Wan, USGS, "
              "Menlo Park, CA 94025")
    assert _authors(_page(byline)) == [
        ("Jane A. SMITH", ["Earth System Research Laboratory, NOAA, Boulder, CO 80305"]),
        ("Wan LEE", ["USGS, Menlo Park, CA 94025"]),
    ]


def test_the_abstract_block_is_read_whole_with_its_paragraphs():
    abstract = _parse(_page(NUMBERED))["abstract"]
    assert abstract.startswith("During the Late Eocene, moderate uplift")
    assert "approximately 36 Ma." in abstract and abstract.endswith("record a rise in 87Sr.")
    # parse() keeps the paragraphs apart (parse_page's shared clean-up joins lines; the gate ignores whitespace)
    parsed = Confex(BeautifulSoup(_page(NUMBERED), "lxml")).parse()
    assert "approximately 36 Ma.\nFrom Early Eocene to Oligocene" in parsed["abstract"]


def test_no_author_is_marked_corresponding():
    # the bold name is the presenting author and the e-mail ends the byline for no one in particular: neither is a
    # corresponding-author mark by the rubric
    byline = ("<b>CONDIE, Kent C.</b>, Department of Earth and Environmental Science, New Mexico Institute of Mining and "
              "Technology, Socorro, NM 87801, kcondie@nmt.edu")
    assert not any(a["is_corresponding"] for a in _parse(_page(byline))["authors"])


def test_the_byline_wins_over_the_presenting_authors_meta_tags():
    metas = ('<meta name="citation_author_institution" content="Denison University">'
             '<meta name="citation_author" content="Chang, Queenie">'
             '<meta name="citation_title" content="A TITLE"><meta name="citation_publisher" content="GSA">')
    assert len(_parse(_page(NUMBERED, metas=metas))["authors"]) == 4


def test_parse_returns_no_back_matter():
    parsed = Confex(BeautifulSoup(_page(NUMBERED), "lxml")).parse()
    assert not parsed.get("references") and not parsed.get("acknowledgments") and not parsed.get("funding_statement")


def test_a_look_alike_page_without_the_webprogram_stylesheet_is_not_claimed():
    # another site that happens to use the same class names, and Confex's newer meeting app (a shell of meta tags)
    look_alike = _page(NUMBERED, head='<link href="/css/site.css" rel="stylesheet">')
    parser = Confex(BeautifulSoup(look_alike, "lxml"))
    assert not parser.is_publisher_specific_parser() and not parser.authors_found()
    app = ('<html><head><base href="https://gsa.confex.com/gsa/2023CD/meetingapp.cgi/">'
           '<meta name="citation_author" content="Tsung-Jui Wu"><meta name="citation_title" content="A TITLE">'
           '<script src="https://app.confex.com/meetingapp/204/js/app.js"></script></head>'
           '<body><div class="loadingPage">please wait while the program loads.</div></body></html>')
    assert not Confex(BeautifulSoup(app, "lxml")).authors_found()


def test_a_webprogram_page_that_is_not_an_abstract_is_not_claimed():
    session = (f"<html><head>{HEAD}</head><body><div class=\"content\"><h2>Session 12</h2>"
               "<div class=\"papers\">a list of papers</div></div></body></html>")
    assert not Confex(BeautifulSoup(session, "lxml")).authors_found()
