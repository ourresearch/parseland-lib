"""
In-process tests for ElsevierBV against the modern <div class="author-group">
template. These pin the iter 2 parser fix (oxjob #203).

Each test uses a small hand-crafted HTML fragment that mirrors the structure
of a real ScienceDirect modern-template page. No Taxicab, no network.

If these tests regress, the iter 2 parser improvement has been broken.
"""
from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV


MODERN_LABELED = """
<html><body>
<div class="author-group" id="author-group">
  <a class="anchor anchor-secondary anchor-underline" href="/author/1/n-vourdas">
    <span class="anchor-text-container"><span class="anchor-text">
      <span class="react-xocs-alternative-link">
        <span class="given-name">N.</span> <span class="text surname">Vourdas</span>
      </span>
      <span class="author-ref"><sup>a</sup></span>
    </span></span>
  </a>
  <a class="anchor" href="/author/2/e-gogolides">
    <span class="anchor-text-container"><span class="anchor-text">
      <span class="react-xocs-alternative-link">
        <span class="given-name">E.</span> <span class="text surname">Gogolides</span>
      </span>
      <span class="author-ref"><sup>a</sup></span>
    </span></span>
  </a>
</div>
<dl class="affiliation"><dt><sup>a</sup></dt><dd>Institute of Microelectronics, NCSR Demokritos</dd></dl>
<script>window.__PRELOADED_STATE__ = {"authors": {
  "content": [{"$$": [
    {"#name":"author","$$":[{"#name":"surname","_":"Vourdas"},{"#name":"cross-ref","$":{"refid":"aff1"}}]},
    {"#name":"author","$$":[{"#name":"surname","_":"Gogolides"},{"#name":"cross-ref","$":{"refid":"aff1"}},{"#name":"cross-ref","$":{"refid":"cor1"}}]}
  ]}],
  "affiliations": {"aff1": {"$$": [{"#name":"textfn","_":"Institute of Microelectronics, NCSR Demokritos"}]}}
}};</script>
</body></html>
"""


MODERN_UNLABELED = """
<html><body>
<div class="author-group" id="author-group">
  <button data-xocs-content-type="author"><span class="button-link-text">
    <span class="react-xocs-alternative-link">
      <span class="given-name">Giulia</span> <span class="text surname">Alessandri</span>
    </span>
    <svg class="icon icon-person react-xocs-author-icon" title="Correspondence author icon"></svg>
  </span></button>
  <button data-xocs-content-type="author"><span class="button-link-text">
    <span class="react-xocs-alternative-link">
      <span class="given-name">Anna</span> <span class="text surname">Daddi</span>
    </span>
  </span></button>
</div>
<dl class="affiliation"><dt></dt><dd>Scuola Superiore Sant'Anna, Pisa, Italy</dd></dl>
</body></html>
"""


def test_authors_found_matches_modern_div_author_group():
    """Regression for iter 2: authors_found() must detect <div class="author-group">."""
    soup = BeautifulSoup(MODERN_LABELED, "lxml")
    assert ElsevierBV(soup).authors_found() is True


def test_authors_found_still_matches_legacy_li_author():
    """Backward compatibility: the legacy <li class="author"> path still works."""
    soup = BeautifulSoup('<html><body><li class="author">X</li></body></html>', "lxml")
    assert ElsevierBV(soup).authors_found() is True


def test_authors_found_false_on_unrelated_markup():
    soup = BeautifulSoup("<html><body><p>nothing</p></body></html>", "lxml")
    assert ElsevierBV(soup).authors_found() is False


def test_parse_modern_labeled_extracts_authors_and_affiliations():
    """Labeled <dl><dt>a</dt> layout + JSON enrichment yields both authors with
    affiliations, and Gogolides flagged as corresponding via the cor1 cross-ref."""
    soup = BeautifulSoup(MODERN_LABELED, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 2

    by_name = {a.name: a for a in authors}
    assert "N. Vourdas" in by_name
    assert "E. Gogolides" in by_name

    # Both authors share aff1 ("Institute of Microelectronics, NCSR Demokritos")
    for a in authors:
        assert any("Microelectronics" in aff for aff in a.affiliations)

    # Gogolides is corresponding (cor1 ref), Vourdas is not
    assert by_name["E. Gogolides"].is_corresponding is True
    assert by_name["N. Vourdas"].is_corresponding is False


def test_parse_modern_unlabeled_single_shared_affiliation():
    """Unlabeled <dl><dt></dt> (empty label) means all authors share the one
    affiliation. The icon-person SVG flags Alessandri as corresponding."""
    soup = BeautifulSoup(MODERN_UNLABELED, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 2

    by_name = {a.name: a for a in authors}
    assert "Giulia Alessandri" in by_name
    assert "Anna Daddi" in by_name

    # Both authors get the single shared affiliation
    for a in authors:
        assert any("Scuola Superiore" in aff for aff in a.affiliations)

    # Alessandri has icon-person => corresponding
    assert by_name["Giulia Alessandri"].is_corresponding is True
    # Daddi has no corresp signal
    assert by_name["Anna Daddi"].is_corresponding is False


def test_parse_uppercase_cor_refid_still_detected():
    """Some older Elsevier pages emit refid='COR1' in uppercase. The JSON
    matcher must be case-insensitive."""
    html = """
    <html><body>
      <div class="author-group"><a class="anchor"><span class="anchor-text">
        <span class="given-name">B.</span> <span class="text surname">Mattiasson</span>
      </span></a></div>
      <script>window.__PRELOADED_STATE__ = {"authors": {
        "content": [{"$$": [
          {"#name":"author","$$":[{"#name":"surname","_":"Mattiasson"},{"#name":"cross-ref","$":{"refid":"COR1"}}]}
        ]}],
        "affiliations": {}
      }};</script>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    result = ElsevierBV(soup).parse()
    assert len(result["authors"]) == 1
    assert result["authors"][0].is_corresponding is True
