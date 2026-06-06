"""In-process tests for Wiley abstract extraction (iter-2).

Pins the iter-2 fixes for `Wiley.get_abstract`:
  1. `section[class*=abstract]` is now a primary fallback after the
     h2-Abstract path. Modern Wiley pages put the abstract in
     `<section class="article-section__abstract">` whose text may include
     a leading "Abstract" header plus a trailing language code (e.g.
     "Abstracten" when the locale span is adjacent in source). Grabbing
     only the section's `<p>` children avoids that header noise.
  2. Length gate on the section fallback is intentionally low (>= 15
     chars): the semantic class name is the strong signal. Book-chapter
     pages legitimately have very short abstracts like
     "Review: (74 refs.)" (17 chars).
  3. `parse_abstract_meta_tags()` (base class) is the next fallback —
     handles citation_abstract / og:description / dc.description /
     description meta tags.
  4. `div.article__body p` fallback is gated to <= 5 paragraphs to
     handle editorial / journal-intro templates where the entire body
     IS the abstract. On full research articles (> 5 paragraphs) the
     fallback is intentionally skipped — joining every paragraph of a
     research article body produced the multi-thousand-char "abstracts"
     that polluted the iter-1 output.
  5. Final return is `None` when nothing matches. The pre-iter-2 fallback
     of unconditionally joining `div.article__body p` would ship the
     entire article body downstream as if it were the abstract.

All fixtures are minimal hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.wiley import Wiley


WILEY_HEAD = (
    '<meta property="og:url" '
    'content="https://onlinelibrary.wiley.com/doi/10.1002/example" />'
)


def _wrap(body: str, head: str = WILEY_HEAD) -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


def test_section_abstract_paragraph_extraction_skips_header_noise():
    """Regression: modern Wiley pages emit
    `<section class="article-section__abstract">` containing a header and
    one or more `<p>` children. Grabbing the section's full `.text` picks
    up "Abstract" + a trailing language code (e.g. "Abstracten" when the
    locale span is adjacent in source). The fix is to extract only `<p>`
    children, skipping the header."""
    body = """
    <section class="article-section__abstract">
      <header><h2>Abstract<span class="locale">en</span></h2></header>
      <p>Spatial management is a valuable strategy to advance regional
      goals for nature conservation. One challenge of spatial management
      is navigating the prioritization of multiple features.</p>
    </section>
    """
    soup = BeautifulSoup(_wrap(body), "lxml")
    out = Wiley(soup).get_abstract()
    assert out is not None
    assert out.startswith("Spatial management"), out[:60]
    assert "Abstracten" not in out
    assert "locale" not in out


def test_section_abstract_short_book_chapter():
    """Regression: book-chapter pages legitimately have very short
    abstracts. `10.1002/chin.198608340` was "Review: (74 refs.)" — 17
    chars. The section fallback gate must be permissive (>= 15) since
    the semantic class name is the strong signal."""
    body = """
    <section class="article-section__abstract">
      <p>Review: (74 refs.)</p>
    </section>
    """
    soup = BeautifulSoup(_wrap(body), "lxml")
    assert Wiley(soup).get_abstract() == "Review: (74 refs.)"


def test_meta_citation_abstract_fallback():
    """Regression: when neither h2-Abstract nor section[class*=abstract]
    markup exists but the page has a `<meta name="citation_abstract">`,
    the base class `parse_abstract_meta_tags()` should fire (length > 200
    required by the helper)."""
    long_text = (
        "Background. Reduced plasma Protein S levels were first reported "
        "to be involved in venous thromboembolism in 1984. PS deficiency "
        "has been well established as a risk factor for venous "
        "thromboembolism. PS is a vitamin K dependent plasma protein "
        "with anticoagulant properties through both APC-dependent and "
        "APC-independent pathways. This study reports findings from a "
        "cohort of 412 patients."
    )
    head = (
        WILEY_HEAD
        + f'<meta name="citation_abstract" content="{long_text}" />'
    )
    body = "<div></div>"
    soup = BeautifulSoup(_wrap(body, head=head), "lxml")
    out = Wiley(soup).get_abstract()
    assert out is not None and out.startswith("Background"), out[:60] if out else None


def test_article_body_editorial_fallback_fires_on_short_body():
    """Regression: older Wiley editorials / journal-intro pages
    (10.1002/jpln.202370065, 10.1002/uog.24515) have no Abstract heading,
    no section[class*=abstract] markup, and no useful meta. The entire
    body IS the abstract. The article-body fallback must fire when
    paragraph count is <= 5."""
    body = """
    <div class="article__body">
      <p>Maintaining the scientific standards of an international
      journal is an important task and the ultimate responsibility of
      the editors. This task can only be accomplished with the support
      of a broad community of scientists.</p>
      <p>This editorial highlights three submissions selected for
      publication in this issue.</p>
    </div>
    """
    soup = BeautifulSoup(_wrap(body), "lxml")
    out = Wiley(soup).get_abstract()
    assert out is not None
    assert "Maintaining the scientific standards" in out


def test_dispatch_uses_wiley_for_abstract_without_modern_author_block():
    """Older Wiley pages may have no `loa-authors` block but still carry a
    Wiley-owned abstract body. The dispatcher should keep that publisher
    parser output instead of falling through to the generic parser/no output."""
    body = """
    <div class="article__body">
      <p>Maintaining the scientific standards of an international
      journal is an important task and the ultimate responsibility of
      the editors. This task can only be accomplished with the support
      of a broad community of scientists.</p>
      <p>This editorial highlights three submissions selected for
      publication in this issue.</p>
    </div>
    """
    out = parse_page(_wrap(body), namespace="doi", resolved_url="https://doi.org/10.1002/example")
    assert out["authors"] == []
    assert out["abstract"] is not None
    assert "Maintaining the scientific standards" in out["abstract"]


def test_dispatch_ignores_wiley_page_without_abstract_signal():
    body = "<main><p>Download PDF</p></main>"
    out = parse_page(_wrap(body), namespace="doi", resolved_url="https://doi.org/10.1002/example")
    assert out["authors"] == []
    assert out["abstract"] is None


def test_article_body_fallback_skipped_on_full_research_article():
    """Regression: full research articles have many paragraphs in
    `div.article__body` covering intro + methods + results + discussion +
    conclusions + references. Iter-1 unconditionally joined them all,
    producing multi-thousand-char "abstracts" that failed the threshold
    match (10.1111/j.1466-7657.2010.00842.x parsed at 8314 chars vs 1701
    gold). With > 5 paragraphs the fallback must NOT fire."""
    body = "<div class='article__body'>" + (
        "<p>Paragraph content that would otherwise be returned but for "
        "the paragraph-count gate. This paragraph is long enough that "
        "joining all six would easily exceed the length threshold.</p>"
        * 6
    ) + "</div>"
    soup = BeautifulSoup(_wrap(body), "lxml")
    assert Wiley(soup).get_abstract() is None


def test_returns_none_when_no_abstract_markup():
    """Regression: when nothing matches, return None rather than
    fabricate an abstract from the full article body. Pre-iter-2 the
    final fallback was `div.article__body p` joined — for pages where
    that contained the whole article body (not an abstract), parser
    produced wrong content. Now returns None instead."""
    body = "<div></div>"
    soup = BeautifulSoup(_wrap(body), "lxml")
    assert Wiley(soup).get_abstract() is None


def test_primary_h2_abstract_path_still_works():
    """Sanity: the legacy `<h2>Abstract</h2>` + next-sibling path that
    handles most modern Wiley pages must still work."""
    body = """
    <h2>Abstract</h2>
    <div>This study investigates the role of luteolin in melanoma
    metastasis. Results show that luteolin inhibits cellular
    proliferation in A375 and B16-F10 cells. This abstract is long
    enough (over a hundred chars) to satisfy the length gate.</div>
    """
    soup = BeautifulSoup(_wrap(body), "lxml")
    out = Wiley(soup).get_abstract()
    assert out is not None
    assert out.startswith("This study investigates")


def test_graphical_abstract_skipped_when_real_abstract_present():
    """Regression: when both a graphical-abstract heading and a real
    Abstract heading exist, the graphical variant must be skipped."""
    body = """
    <h2 class="graphical">Abstract</h2>
    <figure>graphical-only content</figure>
    <h2>Abstract</h2>
    <div>This is the real abstract describing the work in detail with
    enough characters to satisfy the parser's length gate easily.</div>
    """
    soup = BeautifulSoup(_wrap(body), "lxml")
    out = Wiley(soup).get_abstract()
    assert out is not None
    assert "real abstract" in out
