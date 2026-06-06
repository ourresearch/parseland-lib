"""In-process tests for Wiley corresponding-author detection.

Pins the iter-1 fixes for the Wiley parser:
  1. Courtesy mailto pattern — every author on a Wiley paper often carries
     a "Email this author" mailto link as a courtesy, not as a CA marker.
     Mailto is only a reliable CA signal when it is a *minority* signal
     (count <= max(1, n_authors / 2)). Otherwise fall back to author-type.
  2. ``article-header__correspondence-to`` block — older Wiley/Blackwell
     pages have no per-author author-type tag and no mailto on the author
     span; CA info only lives in this header div. Match an author whose
     first AND last name both appear in the block text.
  3. ``get_abstract`` must not raise ``KeyError: 'class'`` on h-tags lacking
     a class attribute.

All fixtures are minimal hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.wiley import Wiley


# Every author has a mailto (the "Email this author" courtesy pattern), but
# only one author has the <p class="author-type">Corresponding Author</p> tag.
# The mailto signal is unreliable here and must be ignored — only the
# author-type heading should flag a CA.
COURTESY_MAILTO_PATTERN = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Alice First</a>
        <p>Dept A, Univ X</p>
        <a href="mailto:alice@example.org">Email this author</a>
      </span>
      <span class="accordion__closed">
        <a>Bob Second</a>
        <p class="author-type">Corresponding Author</p>
        <p>Dept B, Univ X</p>
        <a href="mailto:bob@example.org">Email this author</a>
      </span>
      <span class="accordion__closed">
        <a>Carol Third</a>
        <p>Dept C, Univ X</p>
        <a href="mailto:carol@example.org">Email this author</a>
      </span>
    </div>
  </body>
</html>
"""


# Only one author carries a mailto, no author-type tag on anyone. The
# minority-mailto signal IS reliable here: that one author is the CA.
SOLE_MAILTO_IS_CA = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example2" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Alice First</a>
        <p>Dept A, Univ X</p>
      </span>
      <span class="accordion__closed">
        <a>Bob Second</a>
        <p>Dept B, Univ X</p>
        <a href="mailto:bob@example.org">Email this author</a>
      </span>
      <span class="accordion__closed">
        <a>Carol Third</a>
        <p>Dept C, Univ X</p>
      </span>
    </div>
  </body>
</html>
"""


# No per-author signals at all (no author-type tags, no mailtos). The
# corresponding-author info lives only in the article header block.
CORRESP_FROM_HEADER_BLOCK = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1111/example" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Alice First</a>
        <p>Dept A, Univ X</p>
      </span>
      <span class="accordion__closed">
        <a>Bernard Geny</a>
        <p>Institut de Physiologie, Strasbourg, France</p>
      </span>
      <span class="accordion__closed">
        <a>Carol Third</a>
        <p>Dept C, Univ X</p>
      </span>
    </div>
    <div class="article-header__correspondence-to">
      Bernard Geny, Institut de Physiologie, Faculte de Medecine, Strasbourg, France.
    </div>
  </body>
</html>
"""


CORRESP_FROM_SINGLE_TOKEN_HEADER_BLOCK = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1111/example-single" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Leroy-Setrin</a>
        <p>Institut National de la Recherche Agronomique, Monnaie, France</p>
      </span>
      <span class="accordion__closed">
        <a>Chaslus-Dancla</a>
        <p>Institut National de la Recherche Agronomique, Monnaie, France</p>
      </span>
    </div>
    <div class="article-header__correspondence-to">
      ElisabethChaslus-Dancla Institut National de la Recherche Agronomique, Monnaie, France.
    </div>
  </body>
</html>
"""


LEGACY_BROADCAST_AUTHOR_TYPE = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1111/example-broadcast" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>A. Walter</a>
        <p class="author-type">Corresponding Author</p>
        <p>Institute of Animal Nutrition, Giessen, Germany</p>
        <p>Institute of Animal Nutrition, Senckenbergstrasse 5, D-35390 Giessen, Germany</p>
      </span>
      <span class="accordion__closed">
        <a>G. Rjmbach</a>
        <p class="author-type">Corresponding Author</p>
        <p>Institute of Animal Nutrition, Giessen, Germany</p>
        <p>Institute of Animal Nutrition, Senckenbergstrasse 5, D-35390 Giessen, Germany</p>
      </span>
      <span class="accordion__closed">
        <a>E. Most</a>
        <p class="author-type">Corresponding Author</p>
        <p>Institute of Animal Nutrition, Giessen, Germany</p>
        <p>Institute of Animal Nutrition, Senckenbergstrasse 5, D-35390 Giessen, Germany</p>
      </span>
    </div>
  </body>
</html>
"""


PER_AUTHOR_CORRESPONDING_LABEL = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example-label" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Minh-Ky Nguyen</a>
        <p>Faculty of Environment and Natural Resources, Ho Chi Minh City, Vietnam</p>
      </span>
      <span class="accordion__closed">
        <a>D. Duc Nguyen</a>
        <p>Department of Civil & Energy System Engineering, Suwon, South Korea</p>
        <p>Corresponding author: email@example.org</p>
      </span>
    </div>
  </body>
</html>
"""


CONTAINER_CORRESPONDING_LABEL = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example-container" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Minh-Ky Nguyen</a>
        <div class="author-info">
          <p class="author-name">Minh-Ky Nguyen</p>
          <p>Faculty of Environment and Natural Resources, Ho Chi Minh City, Vietnam</p>
        </div>
      </span>
      <span class="accordion__closed">
        <a>D. Duc Nguyen</a>
        <div class="author-info">
          <p class="author-name">D. Duc Nguyen</p>
          <p>Department of Civil & Energy System Engineering, Suwon, South Korea</p>
          Corresponding author:
          <a href="/cdn-cgi/l/email-protection#abcoded">[email protected]</a>
        </div>
      </span>
    </div>
  </body>
</html>
"""


# Multi-CA paper, older template: NO author has the author-type tag (the
# page lacks structured CA metadata entirely), but every author carries a
# mailto. In this case mailto IS the only CA signal and the parser must
# flag all mailto-bearing authors. Distinguishes from the courtesy-pattern
# case where at least one author has an author-type tag (which switches
# off the mailto fallback).
MULTI_CA_NO_AUTHOR_TYPE = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example_multi" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Alice First</a>
        <p>Dept A, Univ X</p>
        <a href="mailto:alice@example.org">Email this author</a>
      </span>
      <span class="accordion__closed">
        <a>Bob Second</a>
        <p>Dept B, Univ X</p>
        <a href="mailto:bob@example.org">Email this author</a>
      </span>
    </div>
  </body>
</html>
"""


# Neither signal — no author-type, no mailto, no correspondence-to block.
# Parser must not invent a CA.
NO_CORRESP_SIGNAL = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example3" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Alice First</a>
        <p>Dept A, Univ X</p>
      </span>
      <span class="accordion__closed">
        <a>Bob Second</a>
        <p>Dept B, Univ X</p>
      </span>
    </div>
  </body>
</html>
"""


# Abstract heading h-tag without a class attribute. The legacy
# ``abstract_heading['class']`` access raised KeyError — must be tolerant.
ABSTRACT_HEADING_NO_CLASS = """
<html>
  <head>
    <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/example4" />
  </head>
  <body>
    <div class="loa-authors">
      <span class="accordion__closed">
        <a>Alice First</a>
        <p>Dept A, Univ X</p>
      </span>
    </div>
    <h2>Abstract</h2>
    <div>This study finds that exhaustive details support an iteration
    pattern in publisher parser improvement. The body of the abstract is
    long enough (over a hundred chars) to satisfy the parser's length gate
    so the function returns the abstract text without raising.</div>
  </body>
</html>
"""


def _ca_names(result):
    return [
        a.name for a in result["authors"]
        if getattr(a, "is_corresponding", False)
    ]


def test_courtesy_mailto_pattern_does_not_overmark():
    """Regression: when every author has an 'Email this author' courtesy
    mailto link, only the one with author-type='Corresponding Author' must
    be flagged. Pre-iter-1 the parser marked all three."""
    soup = BeautifulSoup(COURTESY_MAILTO_PATTERN, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Bob Second"], (
        f"expected only 'Bob Second' as CA but got {ca_names!r}"
    )


def test_multi_ca_no_author_type_flags_all_mailto_bearers():
    """Regression: older Wiley/Blackwell templates omit the author-type tag
    entirely; in that case mailto IS the only CA signal and every mailto-
    bearing author must be flagged. Bundled iter-1's earlier count-threshold
    rule incorrectly killed this case (best.201200045, 9783527670383.ch16
    regressed from F1 1.0 / 0.8 to 0.0). The refined "page_has_structured_ca"
    rule recovers it."""
    soup = BeautifulSoup(MULTI_CA_NO_AUTHOR_TYPE, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert sorted(ca_names) == ["Alice First", "Bob Second"], (
        f"expected both authors as CA via no-author-type fallback but got {ca_names!r}"
    )


def test_sole_mailto_still_marks_ca():
    """Regression: when exactly one author carries a mailto (minority
    signal), the mailto IS a reliable CA marker. Dropping the mailto
    fallback entirely would lose this case."""
    soup = BeautifulSoup(SOLE_MAILTO_IS_CA, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Bob Second"], (
        f"expected only 'Bob Second' as CA via sole-mailto but got {ca_names!r}"
    )


def test_correspondence_to_block_marks_named_author():
    """Iter-1 addition: when an article-header__correspondence-to block
    names an author, that author should be flagged CA even with no
    per-author signal. Recovers FN cases on older Wiley/Blackwell pages."""
    soup = BeautifulSoup(CORRESP_FROM_HEADER_BLOCK, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Bernard Geny"], (
        f"expected 'Bernard Geny' from correspondence-to block but got {ca_names!r}"
    )


def test_correspondence_to_block_marks_single_token_author():
    """Legacy Wiley pages can list only surname-style author names while the
    correspondence header concatenates a forename with the surname. The
    header matcher should still recover that single-token surname author."""
    soup = BeautifulSoup(CORRESP_FROM_SINGLE_TOKEN_HEADER_BLOCK, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["Chaslus-Dancla"], (
        f"expected 'Chaslus-Dancla' from header block but got {ca_names!r}"
    )


def test_broadcast_author_type_marks_only_first_author():
    """Older Wiley pages duplicate a generic 'Corresponding Author' badge
    inside every author block. Treating those badges literally overmarks
    every author; the postal correspondence block belongs to the lead author."""
    soup = BeautifulSoup(LEGACY_BROADCAST_AUTHOR_TYPE, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["A. Walter"], (
        f"expected only the lead author from broadcast badges but got {ca_names!r}"
    )


def test_per_author_corresponding_label_marks_author():
    """Modern Wiley book/article pages sometimes use a plain paragraph
    'Corresponding author:' line rather than an author-type tag."""
    soup = BeautifulSoup(PER_AUTHOR_CORRESPONDING_LABEL, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["D. Duc Nguyen"], (
        f"expected D. Duc Nguyen from corresponding label but got {ca_names!r}"
    )


def test_author_info_corresponding_label_marks_author():
    """Some Wiley pages put the corresponding-author label as a bare text
    node inside author-info next to a protected email link."""
    soup = BeautifulSoup(CONTAINER_CORRESPONDING_LABEL, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == ["D. Duc Nguyen"], (
        f"expected D. Duc Nguyen from author-info label but got {ca_names!r}"
    )


def test_no_signal_does_not_invent_ca():
    """Regression: with no per-author signals and no header block, parser
    must not flag anyone as CA."""
    soup = BeautifulSoup(NO_CORRESP_SIGNAL, "lxml")
    result = Wiley(soup).parse()
    ca_names = _ca_names(result)
    assert ca_names == [], (
        f"expected no CA but got {ca_names!r}"
    )


def test_abstract_heading_without_class_does_not_crash():
    """Regression: ``<h2>Abstract</h2>`` without a class attribute used to
    raise ``KeyError: 'class'`` in get_abstract. Must return the abstract
    text instead."""
    soup = BeautifulSoup(ABSTRACT_HEADING_NO_CLASS, "lxml")
    result = Wiley(soup).parse()
    abstract = result.get("abstract")
    assert abstract is not None
    assert "exhaustive details" in abstract
