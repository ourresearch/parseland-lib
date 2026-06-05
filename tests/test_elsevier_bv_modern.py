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


MODERN_APP_JSON_AFFILIATIONS = """
<html><body>
<div class="author-group" id="author-group">
  <button class="button-link workspace-trigger button-link-primary" name="baep-author-id1">
    <span class="button-link-text">
      <span class="given-name">Janelly</span> <span class="text surname">Burgos-Pino</span>
      <span class="author-ref" id="baff1"><sup>a</sup></span>
    </span>
  </button>
  <button class="button-link workspace-trigger button-link-primary" name="baep-author-id2">
    <span class="button-link-text">
      <span class="given-name">Brandon</span> <span class="text surname">Gual-Orozco</span>
      <span class="author-ref" id="baff2"><sup>b</sup></span>
    </span>
  </button>
</div>
<script type="application/json">{
  "authors": {
    "content": [{"#name": "author-group", "$$": [
      {"#name": "author", "$$": [
        {"#name": "given-name", "_": "Janelly"},
        {"#name": "surname", "_": "Burgos-Pino"},
        {"#name": "cross-ref", "$": {"refid": "aff1"}}
      ]},
      {"#name": "author", "$$": [
        {"#name": "given-name", "_": "Brandon"},
        {"#name": "surname", "_": "Gual-Orozco"},
        {"#name": "cross-ref", "$": {"refid": "aff2"}},
        {"#name": "cross-ref", "$": {"refid": "cor1"}}
      ]}
    ]}],
    "affiliations": {
      "aff1": {"$$": [{"#name": "textfn", "_": "Unidad de Biotecnologia, Centro de Investigacion Cientifica de Yucatan, Merida, Mexico"}]},
      "aff2": {"$$": [{"#name": "textfn", "_": "Tecnologico de Monterrey, School of Engineering and Sciences, Monterrey, Mexico"}]}
    }
  }
}</script>
</body></html>
"""


MODERN_APP_JSON_WITH_PRELOADED_STATE = """
<html><body>
<div class="author-group" id="author-group">
  <button class="button-link workspace-trigger button-link-primary">
    <span class="given-name">Janelly</span> <span class="text surname">Burgos-Pino</span>
  </button>
  <button class="button-link workspace-trigger button-link-primary">
    <span class="given-name">Brandon</span> <span class="text surname">Gual-Orozco</span>
  </button>
</div>
<script type="application/json">{
  "authors": {
    "content": [{"#name": "author-group", "$$": [
      {"#name": "author", "$$": [
        {"#name": "surname", "_": "Burgos-Pino"},
        {"#name": "cross-ref", "$": {"refid": "aff1"}},
        {"#name": "cross-ref", "$": {"refid": "cor1"}}
      ]},
      {"#name": "author", "$$": [
        {"#name": "surname", "_": "Gual-Orozco"},
        {"#name": "cross-ref", "$": {"refid": "aff2"}}
      ]}
    ]}],
    "affiliations": {
      "aff1": {"$$": [{"#name": "textfn", "_": "Application JSON affiliation"}]},
      "aff2": {"$$": [{"#name": "textfn", "_": "Application JSON second affiliation"}]}
    }
  }
}</script>
<script>window.__PRELOADED_STATE__ = {"authors": {
  "content": [{"$$": [
    {"#name":"author","$$":[
      {"#name":"surname","_":"Burgos-Pino"},
      {"#name":"cross-ref","$":{"refid":"aff1"}}
    ]},
    {"#name":"author","$$":[
      {"#name":"surname","_":"Gual-Orozco"},
      {"#name":"cross-ref","$":{"refid":"aff2"}},
      {"#name":"cross-ref","$":{"refid":"cor1"}}
    ]}
  ]}],
  "affiliations": {
    "aff1": {"$$": [{"#name":"textfn","_":"Preloaded affiliation"}]},
    "aff2": {"$$": [{"#name":"textfn","_":"Preloaded second affiliation"}]}
  }
}};</script>
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


def test_parse_modern_application_json_is_not_used_without_grounding():
    """Do not trust app JSON author maps until DOI-grounded.

    A broad script[type=application/json] fallback improved a focused fixture
    but regressed the full 10K current-Goldie gate. Keep these payloads as
    Goldie-backfilled evidence candidates, not parser truth.
    """
    soup = BeautifulSoup(MODERN_APP_JSON_AFFILIATIONS, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 2

    by_name = {a.name: a for a in authors}
    assert by_name["Janelly Burgos-Pino"].affiliations == []
    assert by_name["Brandon Gual-Orozco"].affiliations == []
    assert by_name["Brandon Gual-Orozco"].is_corresponding is False


def test_parse_uses_preloaded_state_not_application_json():
    """When both JSON shapes exist, keep __PRELOADED_STATE__ authoritative."""
    soup = BeautifulSoup(MODERN_APP_JSON_WITH_PRELOADED_STATE, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 2

    by_name = {a.name: a for a in authors}
    assert by_name["Janelly Burgos-Pino"].affiliations == ["Preloaded affiliation"]
    assert by_name["Brandon Gual-Orozco"].affiliations == ["Preloaded second affiliation"]
    assert by_name["Janelly Burgos-Pino"].is_corresponding is False
    assert by_name["Brandon Gual-Orozco"].is_corresponding is True


CELL_PRESS_PORTAL = """
<html>
  <head>
    <meta name="citation_author" content="Glenn Kabell" />
    <meta name="citation_author" content="Benjamin J. Scherlag" />
    <meta name="citation_author" content="Ronald R. Hope" />
    <meta name="citation_author" content="Ralph Lazzara" />
  </head>
  <body>
    <div class="core-author-affiliations">
      Affiliations From the Veterans Administration Medical Center,
      University of Oklahoma Health Sciences Center, Oklahoma City, Oklahoma, USA
    </div>
    <span class="corresponding-author">Benjamin J. Scherlag , PhD, FACC</span>
    <div class="core-author-affiliations">
      Affiliations From the Veterans Administration Medical Center,
      University of Oklahoma Health Sciences Center, Oklahoma City, Oklahoma, USA
    </div>
    <div class="core-author-affiliations">
      Affiliations From the Veterans Administration Medical Center,
      University of Oklahoma Health Sciences Center, Oklahoma City, Oklahoma, USA
    </div>
    <div class="core-author-affiliations">
      Affiliations From the Veterans Administration Medical Center,
      University of Oklahoma Health Sciences Center, Oklahoma City, Oklahoma, USA
    </div>
  </body>
</html>
"""


CELL_PRESS_MULTI_AFFS = """
<html>
  <head>
    <meta name="citation_author" content="K.V. Lakshmi" />
    <meta name="citation_author" content="Sergey Milikisiyants" />
    <meta name="citation_author" content="Ruchira Chatterjee" />
  </head>
  <body>
    <div class="core-author-affiliations">
      Affiliations Rensselaer Polytechnic Institute, Troy, NY, USA
    </div>
    <div class="core-author-affiliations">
      Affiliations Rensselaer Polytechnic Institute, Troy, NY, USA
    </div>
    <div class="core-author-affiliations">
      Affiliations Princeton University, Princeton, NJ, USA
    </div>
  </body>
</html>
"""


CELL_PRESS_COUNT_MISMATCH = """
<html>
  <head>
    <meta name="citation_author" content="A. One" />
    <meta name="citation_author" content="B. Two" />
    <meta name="citation_author" content="C. Three" />
  </head>
  <body>
    <!-- only one aff div for three authors — never misalign -->
    <div class="core-author-affiliations">Affiliations Some Place</div>
  </body>
</html>
"""


def test_cell_press_portal_attaches_per_author_affs_and_ca():
    """Cell Press / Elsevier journal portal pages (ajconline.org, cell.com,
    etc.) emit per-author <div class="core-author-affiliations"> blocks in
    document order matching <meta name="citation_author"> tags. The portal
    template prepends a literal 'Affiliations' header word — strip it.
    The corresponding author is wrapped in <span class="corresponding-author">."""
    soup = BeautifulSoup(CELL_PRESS_PORTAL, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 4

    by_name = {a.name: a for a in authors}
    # All four authors got the shared affiliation
    for a in authors:
        assert len(a.affiliations) == 1
        assert "Veterans Administration" in a.affiliations[0]
        # "Affiliations" prefix must be stripped
        assert not a.affiliations[0].lower().startswith("affiliations")

    # Scherlag is the corresponding author via <span class="corresponding-author">
    assert by_name["Benjamin J. Scherlag"].is_corresponding is True
    assert by_name["Glenn Kabell"].is_corresponding is False


def test_cell_press_portal_preserves_distinct_per_author_affs():
    """When per-author affiliation divs hold DIFFERENT institution text, each
    author gets the affiliation at its own document position (not merged)."""
    soup = BeautifulSoup(CELL_PRESS_MULTI_AFFS, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 3

    by_name = {a.name: a for a in authors}
    assert "Rensselaer" in by_name["K.V. Lakshmi"].affiliations[0]
    assert "Rensselaer" in by_name["Sergey Milikisiyants"].affiliations[0]
    assert "Princeton" in by_name["Ruchira Chatterjee"].affiliations[0]


def test_cell_press_portal_skips_when_aff_count_mismatches():
    """Defensive: when the count of core-author-affiliations blocks does not
    match the author count, leave affiliations empty rather than risk
    misalignment."""
    soup = BeautifulSoup(CELL_PRESS_COUNT_MISMATCH, "lxml")
    result = ElsevierBV(soup).parse()
    authors = result["authors"]
    assert len(authors) == 3
    for a in authors:
        assert a.affiliations == []


MULTIPLE_AUTHOR_GROUPS = """
<html><body>
<div class="author-group">
  <button class="button-link button-link-primary">
    <span class="given-name">K.</span> <span class="text surname">Alder</span>
  </button>
</div>
<div class="author-group">
  <button class="button-link button-link-primary">
    <span class="given-name">A.</span> <span class="text surname">Winther</span>
  </button>
</div>
</body></html>
"""


def test_parse_multiple_author_group_divs_collects_all():
    """Older ScienceDirect reprints (e.g. Phys Lett B 1971, Reference Module
    book chapters) wrap EACH author in their own <div class="author-group">
    sibling rather than collecting authors in a single container. The parser
    must iterate ALL author-group divs, not stop at the first."""
    soup = BeautifulSoup(MULTIPLE_AUTHOR_GROUPS, "lxml")
    result = ElsevierBV(soup).parse()
    names = [a.name for a in result["authors"]]
    assert names == ["K. Alder", "A. Winther"]


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
