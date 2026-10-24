"""Elsevier society sites on the newer template (jaad.org, jaacap.org, ijoms.com ...) put the abstract in
<div id="abstracts" data-extent="frontmatter">, sometimes as bare paragraphs. Parseland used to fall back to
og:description, which these sites cut to the abstract's first sentences (oxjob #1794)."""
from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV

FULL = (
    "Internet gaming disorder (IGD) was listed in the DSM-5 as a condition that needed further research. "
    "Since then, video gaming has become pervasive. This presentation aims to review current research on "
    "video game addiction in transitional-age youth and discuss interventions."
)


def _abstract(html):
    return ElsevierBV(BeautifulSoup(html, "lxml")).parse_abstract()


def test_bare_paragraph_frontmatter_beats_truncated_description():
    html = f"""
    <html><head>
      <meta name="citation_publisher" content="Elsevier"/>
      <meta property="og:description" content="Internet gaming disorder (IGD) was listed in the DSM-5 as a condition that needed further research."/>
    </head><body>
      <div id="abstracts" data-extent="frontmatter"><div class="core-container">
        <div id="p0010" role="paragraph">{FULL}</div>
      </div></div>
      <section id="bodymatter" data-extent="bodymatter"><p>Body text that is not the abstract.</p></section>
    </body></html>
    """
    assert _abstract(html) == FULL


def test_sectioned_frontmatter_takes_author_abstract_not_editor_summary_or_highlights():
    html = f"""
    <html><body>
      <div id="abstracts" data-extent="frontmatter">
        <section id="editor-abstract" role="doc-abstract"><h2>Editor's summary</h2><div role="paragraph">Not this.</div></section>
        <section id="author-highlights-abstract" role="doc-abstract"><h2>Highlights</h2><ul><li>Nor this.</li></ul></section>
        <section id="author-abstract" role="doc-abstract"><h2>Abstract</h2><div role="paragraph">{FULL}</div></section>
        <section id="graphical-abstract" role="doc-abstract"><h2>Graphical abstract</h2></section>
      </div>
    </body></html>
    """
    assert _abstract(html) == FULL


def test_frontmatter_without_an_abstract_section_yields_nothing():
    html = """
    <html><body>
      <div id="abstracts" data-extent="frontmatter">
        <section id="editor-abstract" role="doc-abstract"><h2>Editor's summary</h2><div role="paragraph">Not an abstract.</div></section>
      </div>
    </body></html>
    """
    assert not _abstract(html)
