"""PubFactory journal pages: the corresponding author named in the contributor notes (oxjob #2289).

Markup cut down from stored PubFactory pages (jnccn.org, 17 Nov 2026). No publisher parser claimed these pages, so the
citation_author meta tags won and carried no correspondence flag: the page's "Correspondence:" note in
div.contributor-note > contributor-notes > div.corresp names the corresponding author, and the generic reader's
phrases ("corresponding author", "correspondence to") don't include it. Brill and AMS pages keep their own parsers.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.pubfactory import PubFactory

URL = "https://jnccn.org/view/journals/jnccn/21/1/article-p60.xml"
SERVER = ("<!--Server Information: Hostnames: \t1 - harbor-web-4.irl.pubfactory.net \t2 - 10.200.2.1 "
          "Requested: harbor-web-4.irl.pubfactory.net/10.200.2.1 Port:4433-->")
NAMES = ["Andrea Maurichi", "Francesco Barretta", "Mario Santinami"]


def _page(notes, names=NAMES, server=SERVER, og_url=URL, og_title="A title"):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    byline = "".join(f'<div class="contributor-details"><span class="contributor-details-link">{n}</span></div>'
                     for n in names)
    return (f'<!DOCTYPE html>{server}<html><head><meta property="og:url" content="{og_url}"/>'
            f'<meta property="og:title" content="{og_title}"/>{metas}'
            '<meta name="citation_title" content="A title"/><meta name="citation_doi" content="10.6004/jnccn.2024.7040"/>'
            f'</head><body><div class="contributor-line text-subheading">{byline}</div>'
            f'<div class="contributor-note"><contributor-notes encoding-type="nlm">{notes}</contributor-notes></div>'
            '</body></html>')


def _corr(html, url=URL):
    return [(a["name"], a["is_corresponding"]) for a in parse_page(html.encode(), "doi", url)["authors"]]


NOTE_2024 = ('<div id="fn6"><p><strong>Funding:</strong> A foundation provided financial support.</p></div>'
             '<div class="corresp"><corresp id="cor1"><strong>Correspondence:</strong> Andrea Maurichi, MD, '
             'Fondazione IRCCS Istituto Nazionale dei Tumori di Milano, Milan, Italy. Email: '
             '<a href="mailto:a@example.org">a@example.org</a></corresp></div>')


def test_correspondence_note_marks_the_named_author():
    assert _corr(_page(NOTE_2024)) == [("Andrea Maurichi", True), ("Francesco Barretta", False),
                                       ("Mario Santinami", False)]


def test_older_note_without_bold_label():
    note = ('<div class="corresp"><corresp>Correspondence: Mario Santinami, MD, Melanoma Surgical Unit, Milan, Italy. '
            'E-mail: <a href="mailto:m@example.org">m@example.org</a>\n</corresp></div>')
    assert _corr(_page(note)) == [("Andrea Maurichi", False), ("Francesco Barretta", False),
                                  ("Mario Santinami", True)]


def test_two_notes_mark_two_authors():
    note = ('<div class="corresp"><corresp>Correspondence: Andrea Maurichi, MD, Milan, Italy.</corresp></div>'
            '<div class="corresp"><corresp>Correspondence: Mario Santinami, MD, Milan, Italy.</corresp></div>')
    assert [n for n, c in _corr(_page(note)) if c] == ["Andrea Maurichi", "Mario Santinami"]


def test_note_naming_nobody_in_the_byline_marks_no_one():
    note = '<div class="corresp"><corresp>Correspondence: Editorial Office, NCCN, Plymouth Meeting, PA.</corresp></div>'
    assert _corr(_page(note)) == [(n, None) for n in NAMES]


def test_note_that_is_not_a_correspondence_note_marks_no_one():
    note = '<div class="corresp"><corresp>Andrea Maurichi, MD, Milan, Italy.</corresp></div>'
    assert _corr(_page(note)) == [(n, None) for n in NAMES]


def test_pubfactory_page_without_note_is_left_to_the_meta_tags():
    html = _page('<div id="fn1"><p>Submitted September 4, 2023.</p></div>')
    assert not PubFactory(BeautifulSoup(html, "lxml")).authors_found()
    assert _corr(html) == [(n, None) for n in NAMES]


def test_lookalike_jats_page_from_another_platform_is_not_claimed():
    # a JATS-rendered page with the same div.corresp note but no PubFactory server comment (PMC, HighWire, Atypon)
    html = _page(NOTE_2024, server="<!-- served by another platform -->", og_url="https://example.org/article/1")
    parser = PubFactory(BeautifulSoup(html, "lxml"))
    assert not parser.is_publisher_specific_parser()
    assert not parser.authors_found()


def test_brill_and_ams_pages_keep_their_own_parsers():
    for og_url, og_title in (("https://brill.com/view/journals/x/1/1/article-p1_1.xml", "A title"),
                             ("https://www.degruyterbrill.com/document/doi/10.1515/x/html", "A title"),
                             ("https://example.org/a", "Notices of the American Mathematical Society")):
        parser = PubFactory(BeautifulSoup(_page(NOTE_2024, og_url=og_url, og_title=og_title), "lxml"))
        assert not parser.is_publisher_specific_parser()
        assert not parser.authors_found()


def test_parse_keeps_the_meta_tag_reading_and_adds_only_the_mark():
    parsed = PubFactory(BeautifulSoup(_page(NOTE_2024), "lxml")).parse()
    assert [a["name"] for a in parsed["authors"]] == NAMES
    assert all(a["affiliations"] == [] for a in parsed["authors"])
    assert not {"acknowledgments", "funding_statement", "references"} & parsed.keys()
