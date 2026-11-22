"""sui generis Verlag book pages give their own book's PDF, never another book's. Oxjob #937.

Every book page on suigeneris-verlag.ch (DOIs 10.38107/NNN, e.g. https://suigeneris-verlag.ch/buecher/056) carries
the whole catalogue: one div.book_content.content_slug_<NNN> block per book, each with its own "OA-PDF laden" link
(a.download_oa). Only div.detail_page_buecher's data-book attribute names the page's own book, and og:url is the home
page, so a doi.org address sniffs to that. The finder took the first PDF, the newest book's: oa_pdf-080 for all 80
books on the live pages of 21 Nov 2026.

Hand-crafted HTML modelled on the live page, no network.
"""
from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.pdf import find_pdf_link
from parseland_lib.parse import parse_page

HOME = "https://suigeneris-verlag.ch"
PDF_080 = f"{HOME}/img/uploads/pdf/oa_pdf-080-1794909525.pdf"
PDF_056 = f"{HOME}/img/uploads/pdf/oa_pdf-056-1729605309.pdf"
PDF_055 = f"{HOME}/img/uploads/pdf/oa_pdf-strafrechtliche-dopingbekampfung-in-der-schweiz-1727795957.pdf"


def _block(slug, pdf=None):
    link = (f'<a href="{pdf}" target="_blank" class="red_link download_oa" data-type="books" data-id="85">'
            f'<strong>OA-PDF laden</strong></a>') if pdf else ""
    return f"""
      <a class="book_row" data-slug="{slug}"><div class="column_right"><strong>Book {slug}</strong></div></a>
      <div class="book_content content_slug_{slug}" data-bg_color="" data-bg_img="">
        <h2><div class="scrollable"><p>Book {slug}</p></div></h2>
        <div class="book_content_inner"><div class="links">
          <a href="{HOME}/shop/{slug}" class="red_link">Print bestellen</a>
          {link}
        </div></div>
      </div>"""


def _page(book, og_url=HOME, catalogue=None):
    catalogue = catalogue if catalogue is not None else [
        ("080", PDF_080), ("artikelsammlung-2025", None), ("056", PDF_056), ("055", PDF_055)]
    blocks = "".join(_block(slug, pdf) for slug, pdf in catalogue)
    return f"""
    <html><head>
      <title>sui generis Verlag</title>
      <meta property="og:site_name" content="sui generis Verlag" />
      <meta property="og:url" content="{og_url}" />
    </head><body><div id="wrapper">
      <div class="detail_page detail_page_buecher minus_margin  open_book " data-book="{book}">
        <div class="outer_categories outer_categories_books"><a class="do_filter inactive">Grundlagen</a></div>
        <div class="book_list">{blocks}</div>
      </div>
    </div></body></html>
    """


def _find(html, url=HOME):
    link = find_pdf_link(url, BeautifulSoup(html, parser="lxml", features="lxml"))
    return link.href if link is not None else None


def test_book_page_gives_its_own_pdf_not_the_first():
    assert _find(_page("056")) == PDF_056
    assert _find(_page("056"), url=f"{HOME}/buecher/056") == PDF_056


def test_pdf_named_by_title_is_found_too():
    assert _find(_page("055")) == PDF_055


def test_book_without_its_own_link_gives_none_never_another_books():
    assert _find(_page("artikelsammlung-2025")) is None
    assert _find(_page("099")) is None  # no block for this book on the page


def test_other_sites_are_untouched():
    # the same markup on another host is not a sui generis page: the generic finder runs as before
    html = _page("056", og_url="https://example.org/books/056")
    assert _find(html, url="https://example.org/books/056") == PDF_080


def test_parse_page_from_a_doi_address():
    for url in ("https://doi.org/10.38107/056", f"{HOME}/buecher/056"):
        pdfs = [u["url"] for u in parse_page(_page("056"), "doi", url)["urls"] if u.get("content_type") == "pdf"]
        assert pdfs == [PDF_056], url
