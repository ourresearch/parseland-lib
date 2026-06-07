from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.iop import IOP


IOP_HEAD = """
<link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
<meta name="citation_author" content="A. Researcher">
<meta name="citation_author_institution" content="Example Institute">
<link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
"""


def _soup(body, head=IOP_HEAD):
    return BeautifulSoup(f"<html><head>{head}</head><body>{body}</body></html>", "lxml")


def test_iop_visible_abstract_uses_clean_inner_block():
    body = """
    <div class="article-abstract">
      0953-8984/30/39/394002 Abstract
      <div class="article-text wd-jnl-art-abstract cf">
        <p>We consider here the magnetization dynamics induced in a
        ferromagnet by magnetoelastic coupling.</p>
        <p>Such measurements can be performed by time resolved Kerr
        experiments.</p>
      </div>
      Export citation and abstract BibTeX RIS
    </div>
    """

    abstract = IOP(_soup(body)).parse_abstract()

    assert abstract.startswith("We consider here")
    assert "Export citation" not in abstract
    assert "0953-8984" not in abstract
    assert "time resolved Kerr" in abstract


def test_iop_visible_abstract_allows_short_semantic_block():
    body = """
    <div class="article-text wd-jnl-art-abstract cf">
      <p>Sandra Faber has won the 2017 Gruber Foundation Cosmology Prize.</p>
    </div>
    """

    abstract = IOP(_soup(body)).parse_abstract()

    assert abstract == "Sandra Faber has won the 2017 Gruber Foundation Cosmology Prize."


def test_parse_page_dispatches_iop_visible_abstract():
    body = """
    <div class="article-content">
      <div class="article-text wd-jnl-art-abstract cf">
        <p>One of the key concerns in aircraft flight is the accumulation
        of ice on the wing leading edge and nacelle lip-skin.</p>
      </div>
    </div>
    """

    parsed = parse_page(str(_soup(body)), "doi", "https://doi.org/10.1088/example")

    assert parsed["abstract"].startswith("One of the key concerns")
    assert parsed["authors"][0]["name"] == "A. Researcher"


def test_parse_page_dispatches_iop_abstract_without_author_meta():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    """
    body = """
    <div class="article-text wd-jnl-art-abstract cf">
      <p>Sandra Faber has won the 2017 Gruber Foundation Cosmology Prize.</p>
    </div>
    """

    parsed = parse_page(str(_soup(body, head=head)), "doi", "https://doi.org/10.1088/example")

    assert parsed["abstract"] == "Sandra Faber has won the 2017 Gruber Foundation Cosmology Prize."
    assert parsed["authors"] == []
