"""OpenEdition (books./journals.openedition.org) PDF-link handling. Oxjob #786.

A page's own PDF, when it has one, sits on the same openedition.org host
(books.openedition.org/<site>/pdf/<id>, journals.openedition.org/<site>/pdf/<id>).
Every .pdf-shaped anchor on another host is a footnote citing a third-party
document, or on Books the "ePub / PDF" buy button that goes to the 7switch store.
The generic finder used to take those, so 2,111 works under 10.4000 carried
someone else's PDF as best_oa_location.pdf_url and in the Content API store.

Hand-crafted HTML modelled on https://books.openedition.org/pupo/43808 — no network.
"""
from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import (
    is_openedition_own_pdf,
    is_openedition_page,
    parse_publisher_fulltext_location,
)
from parseland_lib.parse import parse_page

FOOTNOTE_PDF = "https://inis.iaea.org/collection/NCLCollectionStore/_Public/26/034/26034277.pdf"
BUY_LINK = "https://www.7switch.com/fr/ebook/9782840166207/from/openedition"
OWN_PDF = "https://books.openedition.org/pupo/pdf/43808"


def _books_page(extra_body="", own_pdf=False):
    own = f'<a href="{OWN_PDF}">Lire en PDF</a>' if own_pdf else ""
    return f"""
    <html><head>
      <meta property="og:url" content="https://books.openedition.org/pupo/43808" />
      <link rel="canonical" href="https://books.openedition.org/pupo/43808" />
    </head><body>
      <div class="widget--buy">
        <a class="widget--buy__elec__link" href="{BUY_LINK}">ePub / PDF</a>
      </div>
      {own}
      <div id="chapter-text-column"><p>Le métabolisme artificiel ...</p></div>
      <div id="anchor-footnotes" class="mb-3 scrollspy-target">
        <div class="foot_notes">
          <div id="tei_ftn26" class="footnote">
            <p>26 <a class="external-link" href="{FOOTNOTE_PDF}">{FOOTNOTE_PDF}</a></p>
          </div>
        </div>
      </div>
      {extra_body}
    </body></html>
    """


def _pdf_urls(html, resolved_url):
    out = parse_page(html, "doi", resolved_url)
    return [u["url"] for u in out["urls"] if u["content_type"] == "pdf"]


def test_footnote_and_buy_links_are_not_the_pdf():
    assert _pdf_urls(_books_page(), "https://books.openedition.org/pupo/43808") == []


def test_doi_router_resolved_url_still_gated_via_og_url():
    # parse_page sniffs og:url off a bare doi.org resolved_url; the gate must fire either way.
    assert _pdf_urls(_books_page(), "https://doi.org/10.4000/159wg") == []


def test_books_own_pdf_endpoint_is_kept():
    assert _pdf_urls(_books_page(own_pdf=True), "https://books.openedition.org/pupo/43808") == [OWN_PDF]


def test_journals_own_pdf_is_kept():
    html = """
    <html><head><meta property="og:url" content="https://journals.openedition.org/lectures/1234" /></head>
    <body><a href="https://journals.openedition.org/lectures/pdf/1234">PDF</a></body></html>
    """
    assert _pdf_urls(html, "https://journals.openedition.org/lectures/1234") == [
        "https://journals.openedition.org/lectures/pdf/1234"
    ]


def test_journals_footnote_pdf_is_dropped():
    # e.g. 10.4000/cahierscfv.408 → achemenet.com PDF from a footnote
    html = f"""
    <html><head><meta property="og:url" content="http://journals.openedition.org/cahierscfv/408" /></head>
    <body><div id="text"><p>Article ... <a href="{FOOTNOTE_PDF}">{FOOTNOTE_PDF}</a></p></div></body></html>
    """
    assert _pdf_urls(html, "https://doi.org/10.4000/cahierscfv.408") == []


def test_generic_finder_skips_foot_notes_and_buy_widget_on_any_host():
    # The section exclusions are generic: a non-OpenEdition page with the same markup
    # must not surface the footnote PDF either; without the wrapper it still would.
    resolved = "https://example-press.org/chapter/1"
    wrapped = f"""
    <html><body>
      <div class="foot_notes"><div class="footnote"><a href="{FOOTNOTE_PDF}">{FOOTNOTE_PDF}</a></div></div>
      <div class="widget--buy"><a href="{BUY_LINK}">ePub / PDF</a></div>
    </body></html>
    """
    bare = f'<html><body><a href="{FOOTNOTE_PDF}">{FOOTNOTE_PDF}</a></body></html>'
    assert _pdf_urls(wrapped, resolved) == []
    assert _pdf_urls(bare, resolved) == [FOOTNOTE_PDF]


def test_helpers():
    og_books = '<meta property="og:url" content="https://books.openedition.org/pupo/1"/>'
    og_journals = '<meta property="og:url" content="https://journals.openedition.org/x/1"/>'
    assert is_openedition_own_pdf(OWN_PDF, "books.openedition.org", "")
    assert is_openedition_own_pdf(OWN_PDF, "doi.org", og_books)
    assert not is_openedition_own_pdf(FOOTNOTE_PDF, "books.openedition.org", "")
    assert not is_openedition_own_pdf(BUY_LINK, "books.openedition.org", "")
    # cross-platform is not "own" either: a books page must not claim a journals PDF
    assert not is_openedition_own_pdf("https://journals.openedition.org/x/pdf/1", "books.openedition.org", "")
    assert is_openedition_page("books.openedition.org", "")
    assert is_openedition_page("journals.openedition.org", "")
    assert is_openedition_page("doi.org", og_books)
    assert is_openedition_page("doi.org", og_journals)
    assert not is_openedition_page("doi.org", "")
    assert not is_openedition_page("example.org", '<meta property="og:url" content="https://example.org/notopenedition.org/1"/>')


def test_fulltext_location_direct():
    soup = BeautifulSoup(_books_page(), "lxml")
    loc = parse_publisher_fulltext_location(soup, "https://books.openedition.org/pupo/43808")
    assert not (loc or {}).get("pdf_url")
