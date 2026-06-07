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


def test_parse_page_uses_degruyterbrill_citation_author_meta():
    doi = "10.1515/9789048501229-017"
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyterbrill.com/document/doi/{doi}/html" />
        <link rel="canonical"
              href="https://www.degruyterbrill.com/document/doi/{doi}/html" />
        <meta name="citation_author" content="Ivana Müller" />
        <meta property="article:author" content="Ivana Müller" />
      </head>
      <body>
        <h1 class="title-dgb">Performance Documentation 6: Under My Skin</h1>
      </body>
    </html>
    """

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["authors"] == [
        {"name": "Ivana Müller", "affiliations": [], "is_corresponding": None}
    ]


def test_parse_page_dedupes_degruyter_duplicate_contributors():
    doi = "10.1515/9780822387800-020"
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyterbrill.com/document/doi/{doi}/html" />
      </head>
      <body>
        <span class="contributor">Cesare Lombroso</span>
        <span class="contributor">Cesare Lombroso</span>
      </body>
    </html>
    """

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["authors"] == [
        {"name": "Cesare Lombroso", "affiliations": [], "is_corresponding": False}
    ]


def test_parse_page_uses_de_gruyter_description_meta_for_abstract():
    doi = "10.1524/itit.2011.0637"
    abstract = (
        "Dienste im Internet sind einer wachsenden Anzahl und Diversitaet von "
        "Angriffen ausgesetzt. Herkoemmliche Instrumente der IT-Sicherheit "
        "sind ungeeignet, dieser Bedrohung langfristig entgegen zu wirken, "
        "da sie auf der manuellen Klassifikation bekannter Angriffe beruhen."
    )
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyter.com/document/doi/{doi}/html" />
        <meta name="description" content="Zusammenfassung {abstract}" />
      </head>
      <body><span class="contributor">Example Author</span></body>
    </html>
    """

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["abstract"] == abstract


def test_parse_page_uses_de_gruyter_visible_abstract_fallback():
    doi = "10.1515/humor-2020-0055"
    abstract = (
        "Recently animated sitcoms have generated considerable international "
        "interest because they portray controversial political and social "
        "issues through satire. This fallback preserves the visible abstract "
        "when De Gruyter does not expose a usable description meta tag."
    )
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyter.com/document/doi/{doi}/html" />
      </head>
      <body>
        <span class="contributor">Example Author</span>
        <div class="abstract">Abstract {abstract}</div>
      </body>
    </html>
    """

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["abstract"] == abstract


def test_parse_page_uses_de_gruyter_limited_preview_abstract():
    doi = "10.1515/bot-2019-0082"
    abstract = (
        "Sargassum species form large beds that play an important role in "
        "coastal ecosystems. The beds are abundant and Sargassum is often "
        "used as food and in medicine, so a reliable landing-page abstract "
        "matters for downstream metadata quality."
    )
    html = f"""
    <html>
      <head>
        <meta property="og:url"
              content="https://www.degruyter.com/document/doi/{doi}/html" />
      </head>
      <body>
        <span class="contributor">Example Author</span>
        <div id="text-container">
          Showing a limited preview of this publication: Abstract {abstract}
        </div>
      </body>
    </html>
    """

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["abstract"] == abstract
