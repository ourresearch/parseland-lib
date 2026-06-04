"""Springer book-chapter abstract via meta og:description fallback.

Many legacy SpringerLink book / encyclopedia chapter pages emit no JSON-LD
``description`` and no DOM ``section[data-title=Abstract|Introduction]`` /
``section.Section1`` block. The chapter abstract on those pages is only
present in ``og:description`` / ``<meta name=description>``. Without a meta
fallback the parser returns ``None`` and we lose ~57 Springer rows in the
whole-Goldie eval.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.springer import Springer


def _parse(html: str) -> dict:
    return Springer(BeautifulSoup(html, "lxml")).parse()


def test_meta_og_description_used_when_no_dom_abstract() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/x"/>
        <meta property="og:description"
              content="Rickettsial disease, caused by Rochalimaea Quintana, resembling epidemic typhus in that is transmitted by lice and is prevalent during wars and under unsanitary conditions."/>
        <meta name="description"
              content="Rickettsial disease, caused by Rochalimaea Quintana, resembling epidemic typhus in that is transmitted by lice and is prevalent during wars and under unsanitary conditions."/>
      </head>
      <body><h1>Trench Fever</h1></body>
    </html>
    """
    result = _parse(html)
    assert result["abstract"] is not None
    assert "Rickettsial disease" in result["abstract"]


def test_longer_of_og_and_description_wins() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/x"/>
        <meta property="og:description"
              content="Short blurb that is just long enough to clear the eighty character minimum threshold here."/>
        <meta name="description"
              content="A substantially longer description that includes more of the chapter abstract and therefore should win the length tiebreak between the two meta tags."/>
      </head>
      <body></body>
    </html>
    """
    result = _parse(html)
    assert result["abstract"] is not None
    assert result["abstract"].startswith("A substantially longer description")


def test_meta_fallback_skipped_when_under_minimum_length() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/x"/>
        <meta property="og:description" content="Too short."/>
        <meta name="description" content="Also short."/>
      </head>
      <body></body>
    </html>
    """
    result = _parse(html)
    assert result["abstract"] is None


def test_dom_abstract_still_wins_over_meta_fallback() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/chapter/10.1007/x"/>
        <meta property="og:description"
              content="Stale meta description should NOT be returned because a real DOM Abstract section exists on this page already."/>
      </head>
      <body>
        <section class="Abstract">
          <h2 class="Heading">Abstract</h2>
          <p>The real DOM abstract paragraph that the parser must prefer over the meta description blurb above.</p>
        </section>
      </body>
    </html>
    """
    result = _parse(html)
    assert result["abstract"] is not None
    assert "real DOM abstract" in result["abstract"]
    assert "Stale meta" not in result["abstract"]
