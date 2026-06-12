from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.rsc import RSC


def _html(body: str, og_url: str = "https://pubs.rsc.org/en/content/articlelanding/2024/example") -> str:
    return f"""
    <html>
      <head>
        <meta property="og:url" content="{og_url}">
      </head>
      <body>{body}</body>
    </html>
    """


def test_rsc_dispatches_no_author_graphical_abstract() -> None:
    html = _html(
        """
        <h2 class="article-abstract__heading">Abstract</h2>
        <div><p>A graphical abstract is available for this content</p></div>
        """
    )

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1039/example")

    assert parsed["authors"] == []
    assert parsed["abstract"] == "A graphical abstract is available for this content"


def test_rsc_joins_multi_paragraph_abstracts() -> None:
    html = _html(
        """
        <a class="article__author-link"><a>Jane Doe</a></a>
        <h2 class="article-abstract__heading">Abstract</h2>
        <div>
          <p>First paragraph with the core chemistry result.</p>
          <p>Second paragraph with stereochemical details.</p>
        </div>
        """
    )

    abstract = RSC(BeautifulSoup(html, "lxml")).parse_abstract()

    assert abstract == (
        "First paragraph with the core chemistry result. "
        "Second paragraph with stereochemical details."
    )


def test_rsc_prefers_citation_abstract_over_formula_spaced_visible_text() -> None:
    html = _html(
        """
        <meta name="citation_abstract" content="Formula H2O keeps compact notation.">
        <h2 class="article-abstract__heading">Abstract</h2>
        <div><p>Formula H 2 O keeps compact notation.</p></div>
        """
    )

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1039/example")

    assert parsed["abstract"] == "Formula H2O keeps compact notation."


def test_rsc_suppresses_first_page_placeholder_when_no_abstract_available() -> None:
    html = _html(
        """
        <meta name="citation_abstract" content="No abstract available">
        <h2 class="article-abstract__heading">Abstract</h2>
        <div><p>The first page of this article is displayed as the abstract.</p></div>
        """
    )

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1039/example")

    assert parsed["abstract"] is None


def test_rsc_book_chapter_abstract_fallback() -> None:
    html = _html(
        """
        <div class="book-chapter-abstract">
          <p>Skin lesions and reducing their healing times require more efficient treatments.</p>
        </div>
        """,
        og_url="https://books.rsc.org/books/edited-volume/chapter-abstract/example",
    )

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1039/book-example")

    assert parsed["authors"] == []
    assert parsed["abstract"] == (
        "Skin lesions and reducing their healing times require more efficient treatments."
    )
