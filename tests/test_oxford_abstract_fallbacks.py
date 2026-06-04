"""Focused tests for Oxford (OUP) abstract fallback selectors.

The default Oxford abstract selector is ``section.abstract p``. A meaningful
fraction of OUP HTML — conference supplement abstracts, reference-work entries,
and a handful of book-chapter templates — omit that wrapper and instead expose
the abstract body via ``.chapter-para`` or only via meta tags. These tests
exercise the fallback ladder we added in ``oxford.py``.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.oxford import Oxford


def _make_parser(html: str) -> Oxford:
    parser = Oxford.__new__(Oxford)
    parser.soup = BeautifulSoup(html, "html.parser")
    return parser


def test_primary_selector_still_wins() -> None:
    html = """
    <html><head>
      <meta property="og:description" content="Abstract. Truncated 160 char snippet." />
    </head><body>
      <section class="abstract">
        <p>Full abstract paragraph one.</p>
        <p>Full abstract paragraph two.</p>
      </section>
      <div class="chapter-para">Should be ignored when section.abstract exists.</div>
    </body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert "Full abstract paragraph one." in abstract
    assert "Full abstract paragraph two." in abstract
    assert "Truncated" not in abstract
    assert "Should be ignored" not in abstract


def test_chapter_para_fallback_for_supplement_template() -> None:
    """Conference/supplement abstracts (e.g. NDT supplements) lack section.abstract
    but expose the abstract via .chapter-para paragraphs."""
    html = """
    <html><head>
      <meta property="og:description" content="Introduction and Aims: Minimal change..." />
    </head><body>
      <div class="chapter-para">Introduction and Aims: Minimal change nephropathy is a common cause of primary nephrotic syndrome.</div>
      <div class="chapter-para">Methods: We reviewed cases at our institution.</div>
      <div class="chapter-para">Results: Outcomes were favourable.</div>
      <div class="chapter-para">Conclusion: Long-term outlook is good.</div>
    </body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert "Introduction and Aims" in abstract
    assert "Methods" in abstract
    assert "Results" in abstract
    assert "Conclusion" in abstract


def test_citation_abstract_meta_fallback() -> None:
    html = """
    <html><head>
      <meta name="citation_abstract" content="This is the full abstract from citation_abstract meta tag." />
      <meta property="og:description" content="Abstract. Truncated." />
    </head><body></body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert abstract == "This is the full abstract from citation_abstract meta tag."


def test_og_description_fallback_strips_abstract_prefix() -> None:
    html = """
    <html><head>
      <meta property="og:description" content="Abstract. The late 1820s and early 1830s were marked by controversy in English Evangelicalism." />
    </head><body></body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert abstract.startswith("The late 1820s")
    assert "Abstract" not in abstract.split(".")[0]


def test_og_description_handles_no_prefix() -> None:
    html = """
    <html><head>
      <meta property="og:description" content="The actual abstract content without prefix." />
    </head><body></body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert abstract == "The actual abstract content without prefix."


def test_name_description_fallback_when_og_missing() -> None:
    html = """
    <html><head>
      <meta name="description" content="AbstractThe meta name=description fallback content." />
    </head><body></body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert abstract == "The meta name=description fallback content."


def test_returns_empty_when_no_signal() -> None:
    html = "<html><head></head><body><p>Unrelated.</p></body></html>"
    parser = _make_parser(html)
    assert parser._extract_abstract() == ""


def test_chapter_para_preferred_over_meta() -> None:
    """When chapter-para exists with substantive content, prefer it over
    the 160-char truncated og:description."""
    html = """
    <html><head>
      <meta property="og:description" content="Abstract. Truncated 160 char snippet of the abstract." />
    </head><body>
      <div class="chapter-para">Full abstract content from chapter-para that is significantly longer than the truncated meta snippet.</div>
    </body></html>
    """
    parser = _make_parser(html)
    abstract = parser._extract_abstract()
    assert "Full abstract content from chapter-para" in abstract
    assert "Truncated 160 char snippet" not in abstract


def test_parse_integration_uses_fallback() -> None:
    """Smoke test: parse() returns the abstract from the fallback when
    section.abstract is missing."""
    html = """
    <html><head></head><body>
      <div class="chapter-para">Fallback abstract via chapter-para.</div>
    </body></html>
    """
    parser = _make_parser(html)
    result = parser.parse()
    assert result["abstract"] == "Fallback abstract via chapter-para."
