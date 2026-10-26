"""Elsevier society sites on the newer template (jaad.org, jaacap.org, ijoms.com ...) put the abstract in
<div id="abstracts" data-extent="frontmatter">, sometimes as bare paragraphs. Parseland used to fall back to
og:description, which these sites cut to the abstract's first sentences (oxjob #1794)."""
import pytest
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
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


def test_full_meta_synopsis_beats_a_one_line_frontmatter_key_point():
    # theclinics.com: the frontmatter holds one key point; og:description holds the whole synopsis.
    synopsis = FULL + " Familiarity with the relevant anatomy and imaging findings is essential for diagnosis."
    html = f"""
    <html><head>
      <meta name="citation_publisher" content="Elsevier"/>
      <meta property="og:description" content="{synopsis}"/>
    </head><body>
      <div id="abstracts" data-extent="frontmatter"><div class="core-container">
        <div id="p0020" role="paragraph">Characteristic soft tissue injuries may be associated with instability.</div>
      </div></div>
    </body></html>
    """
    assert not _abstract(html)


# Meeting-abstract pages that show no abstract (26 Oct End 2 End: ~5.8K Elsevier society works got one of these
# as a first abstract; oxjob #1794). Their og:description is the same short line, which the meta floor rejects.
def _bare(frontmatter_inner, og=None):
    og_tag = f'<meta property="og:description" content="{og}"/>' if og else ""
    return f"""
    <html><head><meta name="citation_publisher" content="Elsevier"/>{og_tag}</head><body>
      <div id="abstracts" data-extent="frontmatter"><div class="core-container">{frontmatter_inner}</div></div>
      <section id="bodymatter" data-extent="bodymatter"><p>Get full text access. Log in, subscribe or purchase.</p></section>
    </body></html>
    """


def test_graphical_abstract_alone_is_not_an_abstract():
    # JACC: the block holds only the graphical abstract's figure and its toolbar
    html = _bare("""
      <div id="graphical-abstract" role="doc-abstract"><div>Corresponding Author</div>
        <div class="figure-wrap"><figure id="undfig1" class="graphic"><img src="ga.jpg"/>
          <div class="core-figure-tools"><a>Open in Viewer</a><a>Download figure</a><a>Download PowerPoint</a></div>
        </figure></div></div>""")
    assert not _abstract(html)


def test_graphical_abstract_toolbar_is_dropped_from_bare_paragraphs():
    html = _bare(f"""<div id="p0010" role="paragraph">{FULL}</div>
      <div id="graphical-abstract" role="doc-abstract"><figure><div class="core-figure-tools">Download figure</div></figure></div>""")
    assert _abstract(html) == FULL


@pytest.mark.parametrize("line", [
    "I understand.",
    "Presenter: Nora Singh BA | Hartford Hospital",
    "Wake Forest University School of Medicine, USA.",
    "Radiotherapy and radiobiology",
])
def test_one_short_bare_line_is_not_an_abstract(line):
    assert not _abstract(_bare(f'<div id="p0010" role="paragraph">{line}</div>', og=line))


@pytest.mark.parametrize("line", [
    "I understand.",
    "Presenter: Nora Singh BA | Hartford Hospital",
    "Author Block: Mikayla Deckard, BS, Soliana Kahassai, MS, BS, Sam Cotton, PhD, Claudiu Moisa, MD, University of "
    "Louisville School of Medicine, Louisville, Kentucky",
])
def test_parse_page_gives_no_abstract_for_a_bare_byline(line):
    html = _bare(f'<div id="p0010" role="paragraph">{line}</div>', og=line)
    assert not parse_page(html, "doi", "https://www.hpbonline.org/article/S1365-182X(26)00458-2/fulltext")["abstract"]


def test_short_real_purpose_sentence_is_kept():
    # meeting abstracts whose page shows only the first section still give it (100-200 characters)
    purpose = ("The purpose of this study is to evaluate whether observation or intervention impacts recurrence free "
               "survival after close pathologic margins in squamous cell carcinoma of the vulva.")
    assert _abstract(_bare(f'<div id="p0010" role="paragraph">{purpose}</div>', og=purpose)) == purpose
