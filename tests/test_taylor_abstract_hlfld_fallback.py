"""Focused tests for the Taylor & Francis abstract selector ladder.

Background:
    The Taylor parser historically only extracted abstracts from
    ``div.abstractInFull``. Older / legacy tandfonline.com templates instead
    expose the abstract body via the ``hlFld-Abstract`` container (no
    ``abstractInFull`` child). A separate failure mode came from the
    ``is_publisher_specific_parser`` check: some Taylor pages still carry an
    ``og:url`` pointing at the legacy ``informahealthcare.com`` host while the
    canonical link correctly identifies tandfonline.com. Both cases caused
    ``abstract`` to come back ``None`` despite the abstract text being present
    in the HTML.

These tests pin both fixes:
    1. Falling back to ``hlFld-Abstract`` when ``abstractInFull`` is absent.
    2. Stripping duplicated leading ``Abstract`` / ``ABSTRACT`` / ``RÉSUMÉ``
       headings that appear inside ``hlFld-Abstract``.
    3. Dispatching to the Taylor parser when only the canonical link points to
       tandfonline.com.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.taylor import Taylor


def _parser(html: str) -> Taylor:
    return Taylor(BeautifulSoup(html, "lxml"))


# Minimal authors block — Taylor.parse() requires publicationContentAuthors
# to be present, otherwise it raises before reaching the abstract logic.
_AUTHORS_BLOCK = """
<div class="publicationContentAuthors">
  <div class="entryAuthor">
    <a>Jane Doe</a>
    <span class="overlay">Department of Test, Test University</span>
  </div>
</div>
"""


def test_abstract_in_full_still_wins() -> None:
    """Primary selector still preferred when both wrappers exist."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/abc.123" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        <h2>ABSTRACT</h2>
        <div class="abstractInFull">
          <p>Primary abstract body that should win.</p>
        </div>
      </div>
    </body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser()
    out = parser.parse()
    assert out["abstract"] is not None
    assert "Primary abstract body that should win." in out["abstract"]


def test_hlfld_abstract_fallback_when_abstract_in_full_missing() -> None:
    """hlFld-Abstract recovers the abstract on legacy templates."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/legacy" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        The charopid genus Oreokera is shown to be an invalidly introduced
        taxon. It is herein formally validated and redefined.
      </div>
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is not None
    assert "charopid genus Oreokera" in out["abstract"]


def test_hlfld_abstract_strips_doubled_abstract_heading() -> None:
    """Leading 'ABSTRACTABSTRACT' / 'Abstract\\nAbstract' is stripped."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/dup" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        <h2>ABSTRACT</h2>ABSTRACTApproximately one in three women report sexual trauma.
      </div>
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is not None
    # Both leading "ABSTRACT" labels must be gone; substantive text retained.
    assert out["abstract"].lstrip().lower().startswith("approximately one in three")
    assert "ABSTRACTABSTRACT" not in out["abstract"]


def test_hlfld_abstract_strips_french_resume_heading() -> None:
    """RÉSUMÉ heading is also stripped on French-language Canadian RS articles."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/fr" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        RÉSUMÉOn a utilisé des données RADARSAT pour faire le suivi du panache.
      </div>
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is not None
    assert out["abstract"].lstrip().startswith("On a utilisé des données RADARSAT")


def test_canonical_link_dispatches_when_og_url_is_legacy_host() -> None:
    """Legacy informahealthcare og:url still dispatches if canonical is tandfonline."""
    html = """
    <html><head>
      <meta property="og:url" content="https://www.informahealthcare.com/doi/abs/10.1080/legacy" />
      <link rel="canonical" href="https://www.tandfonline.com/doi/full/10.1080/legacy" />
    </head><body></body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser() is True


def test_dispatch_negative_when_neither_signal_matches() -> None:
    """Unrelated hosts must not match Taylor dispatch."""
    html = """
    <html><head>
      <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/whatever" />
      <link rel="canonical" href="https://onlinelibrary.wiley.com/doi/10.1002/whatever" />
    </head><body></body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser() is False


def test_abstract_none_when_no_abstract_wrapper_present() -> None:
    """If both wrappers are missing, abstract is None (don't grab og:description)."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/none" />
      <meta property="og:description" content="Published in Performance Research Vol. 22." />
    </head><body>
      {_AUTHORS_BLOCK}
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is None
