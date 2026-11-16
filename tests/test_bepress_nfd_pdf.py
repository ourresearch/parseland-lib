"""bepress / Digital Commons PDF meta and decomposed-accent anchors. Oxjob #937 (Zendesk 8439).

PhareSST (pharesst.irsst.qc.ca, IRSST's Digital Commons site) gave no pdf_url for its reports:
1. its only PDF meta is bepress_citation_pdf_url (Digital Commons pages carry no plain citation_pdf_url), which
   get_pdf_in_meta skipped;
2. its button reads "Te&#769;le&#769;charger": e + U+0301 (NFD), which never equals the precomposed "télécharger"
   the anchor check looks for. With ~70 links on the page, the button also fell past the finder's 50-link cap.

Hand-crafted HTML modelled on https://pharesst.irsst.qc.ca/rapports-scientifique/987/ (doi 10.70010/uzad9010), no
network.
"""
from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.pdf import find_pdf_link, get_pdf_in_meta
from parseland_lib.parse import parse_page

PDF = "https://pharesst.irsst.qc.ca/cgi/viewcontent.cgi?article=1986&context=rapports-scientifique"
URL = "https://pharesst.irsst.qc.ca/rapports-scientifique/987/"


def _page(meta="", button="Te&#769;le&#769;charger", nav_links=0, title_attr=""):
    # navigation like the live page's: a few PDF-shaped links (guides, forms), the rest plain
    nav = "".join(f'<li><a href="https://pharesst.irsst.qc.ca/{"guide-%d.pdf" % i if i < 5 else "browse/%d" % i}">'
                  f'Collection {i}</a></li>' for i in range(nav_links))
    return f"""
    <html><head>
      <title>"Effet sur la qualité de l'air" by Magali-Wen St-Germain</title>
      {meta}
    </head><body>
      <ul id="nav">{nav}</ul>
      <div id="title"><h1><a href="{PDF.replace('&', '&amp;')}">Effet sur la qualité de l'air</a></h1></div>
      <div class="aside download-button">
        <a id="pdf" class="btn" href="{PDF.replace('&', '&amp;')}"{title_attr} target="_blank">
          <i class="icon-download-alt" aria-hidden="true"></i>
          {button}
        </a>
      </div>
    </body></html>
    """


BEPRESS_META = f'<meta name="bepress_citation_pdf_url" content="{PDF.replace("&", "&amp;")}">'


def _find(html):
    link = find_pdf_link(URL, BeautifulSoup(html, parser="lxml", features="lxml"))
    return link.href if link is not None else None


def test_bepress_meta_is_the_pdf():
    link = get_pdf_in_meta(_page(meta=BEPRESS_META))
    assert link is not None and link.href == PDF


def test_plain_citation_pdf_url_wins_over_bepress():
    plain = '<meta name="citation_pdf_url" content="https://example.org/article.pdf">'
    link = get_pdf_in_meta(_page(meta=BEPRESS_META + plain))
    assert link.href == "https://example.org/article.pdf"


def test_bepress_meta_link_counts_as_a_meta_link():
    # same anchor as a plain citation_pdf_url, so is_known_bad_link's bad-meta rules still apply to it
    assert get_pdf_in_meta(_page(meta=BEPRESS_META)).anchor == "<meta citation_pdf_url>"


def test_decomposed_telecharger_button_is_the_pdf():
    # no meta, no PDF-shaped href, no title: only the anchor text can say it
    assert _find(_page()) == PDF


def test_precomposed_telecharger_button_still_works():
    assert _find(_page(button="Télécharger")) == PDF


def test_pharesst_page_with_many_links_gets_its_pdf():
    # the live page: bepress meta, NFD button with a "PDF (2.7 MB)" title, and enough links ahead of the button
    # (PDF-shaped ones sort first) to push it past the finder's 50-link cap; the meta link is found before the cap
    html = _page(meta=BEPRESS_META, nav_links=60, title_attr=' title="PDF (2.7&nbsp;MB) opens in new window"')
    assert _find(html) == PDF
    pdfs = [u["url"] for u in parse_page(html, "doi", URL)["urls"] if u["content_type"] == "pdf"]
    assert pdfs == [PDF]
