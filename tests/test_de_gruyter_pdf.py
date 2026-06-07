"""De Gruyter PDF URL extraction regressions.

De Gruyter document pages often expose the article/chapter URL as
``/document/doi/<doi>/html`` and render the PDF viewer from scripts or a
``.pdf-container`` rather than an ``<a href>``. The PDF route is the same
document path with ``/pdf``.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import (
    find_de_gruyter_pdf_link,
    normalize_de_gruyter_pdf_url,
    parse_publisher_fulltext_location,
)
from parseland_lib.parse import parse_page


def test_find_de_gruyter_pdf_link_from_og_document_url():
    doi = "10.1515/9780748642328-009"
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyter.com/document/doi/{doi}/html" />
      </head>
      <body>
        <div id="documentContent" data-doi="{doi}" data-accessrestricted="true"></div>
      </body>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")

    assert find_de_gruyter_pdf_link(soup) == (
        f"https://www.degruyterbrill.com/document/doi/{doi}/pdf"
    )


def test_find_de_gruyter_pdf_link_from_pdf_container():
    doi = "10.1515/9783839454886-fm"
    html = (
        "<html><body>"
        f'<div class="pdf-container" data-url="/document/doi/{doi}/pdf?stream=true"></div>'
        "</body></html>"
    )

    soup = BeautifulSoup(html, "lxml")

    assert find_de_gruyter_pdf_link(soup) == (
        f"https://www.degruyterbrill.com/document/doi/{doi}/pdf"
    )


def test_normalize_de_gruyter_pdf_url_uses_brill_host_and_stable_path():
    doi = "10.1515/9780271089737-toc"
    raw = f"https://www.degruyter.com/document/doi/{doi}/pdf/firstPage?stream=true"

    assert normalize_de_gruyter_pdf_url(raw) == (
        f"https://www.degruyterbrill.com/document/doi/{doi}/pdf"
    )


def test_parse_publisher_fulltext_location_constructs_de_gruyter_pdf():
    doi = "10.1515/1553-779X.3019"
    resolved = f"https://www.degruyter.com/document/doi/{doi}/html"
    html = f"""
    <html>
      <head><meta property="og:url" content="{resolved}" /></head>
      <body>
        <div id="documentContent" data-doi="{doi}" data-accessrestricted="true"></div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")

    result = parse_publisher_fulltext_location(soup, resolved)

    assert result["pdf_url"] == (
        f"https://www.degruyterbrill.com/document/doi/{doi}/pdf"
    )


def test_parse_page_sniffs_de_gruyter_document_url_from_doi_router():
    doi = "10.1515/9783112318904-040"
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyter.com/document/doi/{doi}/html" />
      </head>
      <body>
        <span class="contributor">Example Author</span>
        <div class="pdf-container" data-url="/document/doi/{doi}/pdf/firstPage"></div>
      </body>
    </html>
    """

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["urls"] == [
        {
            "url": f"https://www.degruyterbrill.com/document/doi/{doi}/pdf",
            "content_type": "pdf",
        }
    ]
