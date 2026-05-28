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
