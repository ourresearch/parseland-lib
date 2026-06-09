"""Taylor & Francis PDF URL extraction regressions."""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.legacy_parse_utils.fulltext import (
    find_tandfonline_pdf_link,
    parse_publisher_fulltext_location,
)
from parseland_lib.parse import parse_page


def test_tandfonline_canonical_full_constructs_pdf_url() -> None:
    doi = "10.1080/15459624.2013.817676"
    html = f"""
    <html><head>
      <link rel="canonical" href="https://www.tandfonline.com/doi/full/{doi}" />
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/{doi}" />
    </head><body>
      <a href="/action/showCitFormats?doi=10.1080%2F15459624.2013.817676">
        Download citation
      </a>
    </body></html>
    """

    soup = BeautifulSoup(html, "lxml")
    assert find_tandfonline_pdf_link(soup) == f"https://www.tandfonline.com/doi/pdf/{doi}"

    result = parse_page(html, "doi", f"https://doi.org/{doi}")
    assert result["urls"] == [
        {"url": f"https://www.tandfonline.com/doi/pdf/{doi}", "content_type": "pdf"}
    ]


def test_tandfonline_canonical_abs_constructs_pdf_url() -> None:
    doi = "10.3109/03630269.2014.880352"
    html = f"""
    <html><head>
      <link rel="canonical" href="https://www.tandfonline.com/doi/abs/{doi}" />
    </head><body></body></html>
    """

    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(
        soup,
        f"https://www.tandfonline.com/doi/abs/{doi}",
    )

    assert result["pdf_url"] == f"https://www.tandfonline.com/doi/pdf/{doi}"


def test_tandfonline_abs_link_selected_as_pdf_is_normalized() -> None:
    doi = "10.1080/18125980.2014.893098"
    html = f"""
    <html><head>
      <link rel="canonical" href="https://www.tandfonline.com/doi/abs/{doi}" />
    </head><body>
      <a href="https://www.tandfonline.com/doi/abs/{doi}">Full Text</a>
    </body></html>
    """

    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(
        soup,
        f"https://www.tandfonline.com/doi/abs/{doi}",
    )

    assert result["pdf_url"] == f"https://www.tandfonline.com/doi/pdf/{doi}"


def test_taylorfrancis_book_citation_pdf_url_is_not_blacklisted() -> None:
    pdf_url = (
        "https://api.taylorfrancis.com/content/books/mono/download?"
        "identifierName=doi&identifierValue=10.4324/9780203360866&type=googlepdf"
    )
    html = f"""
    <html><head>
      <link rel="canonical"
        href="https://www.taylorfrancis.com/books/mono/10.4324/9780203360866/example" />
      <meta name="citation_pdf_url" content="{pdf_url}" />
    </head><body></body></html>
    """

    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(
        soup,
        "https://www.taylorfrancis.com/books/mono/10.4324/9780203360866/example",
    )

    assert result["pdf_url"] == pdf_url


def test_non_taylor_full_canonical_does_not_construct_pdf_url() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://example.com/doi/full/10.1080/example" />
    </head><body></body></html>
    """

    soup = BeautifulSoup(html, "lxml")
    result = parse_publisher_fulltext_location(
        soup,
        "https://example.com/doi/full/10.1080/example",
    )

    assert find_tandfonline_pdf_link(soup) is None
    assert result["pdf_url"] is None
