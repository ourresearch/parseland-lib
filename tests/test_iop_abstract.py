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


def test_parse_page_dispatches_iop_lower_dc_creator_authors():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="dc.creator" content="Ke-Xin Jin">
    <meta name="dc.creator" content="金科新">
    <meta name="dc.creator" content="Bing-Cheng Luo">
    <meta name="dc.creator" content="罗炳成">
    """
    body = """
    <div class="wd-jnl-art-author-affiliations">
      1 Shaanxi Key Laboratory of Quantum Information and Quantum Optoelectronic Devices,
      Xi'an Jiaotong University, Xi'an 710049, China
    </div>
    <div class="article-text wd-jnl-art-abstract cf">
      <p>This paper reports an IOP legacy page with lower dc.creator metadata.</p>
    </div>
    """

    parsed = parse_page(str(_soup(body, head=head)), "doi", "https://doi.org/10.1088/example")

    assert [author["name"] for author in parsed["authors"]] == ["Ke-Xin Jin", "Bing-Cheng Luo"]
    assert parsed["authors"][0]["affiliations"][0]["name"] == (
        "Shaanxi Key Laboratory of Quantum Information and Quantum Optoelectronic Devices, "
        "Xi'an Jiaotong University, Xi'an 710049, China"
    )
    assert parsed["authors"][1]["affiliations"] == parsed["authors"][0]["affiliations"]


def test_iop_visible_affiliations_assign_indexwise_when_counts_match():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="dc.creator" content="Xiao-Ying Zhou">
    <meta name="dc.creator" content="周小英">
    <meta name="dc.creator" content="Jian-Hua He">
    <meta name="dc.creator" content="何建华">
    """
    body = """
    <div class="wd-jnl-art-author-affiliations">
      1 Department of Mathematics, First University, Beijing, China
      2 Institute of Physics, Second University, Shanghai, China
    </div>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert [author["name"] for author in parsed["authors"]] == ["Xiao-Ying Zhou", "Jian-Hua He"]
    assert parsed["authors"][0]["affiliations"] == [
        "Department of Mathematics, First University, Beijing, China"
    ]
    assert parsed["authors"][1]["affiliations"] == [
        "Institute of Physics, Second University, Shanghai, China"
    ]


def test_iop_legacy_correspondence_note_marks_numbered_author():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="citation_author" content="Dong-Lai Zhang">
    <meta name="citation_author" content="Ai-Min Guo">
    """
    body = """
    <div class="wd-jnl-art-author-affiliations">
      1 National Laboratory of Superconductivity, Beijing, China
      2 Author to whom any correspondence should be addressed.
    </div>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert parsed["authors"][0]["name"] == "Dong-Lai Zhang"
    assert parsed["authors"][0]["is_corresponding"] is None
    assert parsed["authors"][1]["name"] == "Ai-Min Guo"
    assert parsed["authors"][1]["is_corresponding"] is True
    assert parsed["authors"][0]["affiliations"] == [
        "National Laboratory of Superconductivity, Beijing, China"
    ]


def test_iop_modern_author_list_correspondence_note_marks_author():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="citation_author" content="Xinyan Yang">
    <meta name="citation_author_institution" content="School of Energy Science and Engineering">
    <meta name="citation_author" content="Hong Zhao">
    <meta name="citation_author_institution" content="School of Energy Science and Engineering">
    """
    body = """
    <div class="author-list">
      <div class="author-list__author">
        <span class="author-list__name">Xinyan Yang</span>
        <a href="mailto:18280604145@163.com">EMAIL</a>
        <span>Author to whom any correspondence should be addressed</span>
      </div>
      <div class="author-list__author">
        <span class="author-list__name">Hong Zhao</span>
      </div>
    </div>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert parsed["authors"][0]["name"] == "Xinyan Yang"
    assert parsed["authors"][0]["is_corresponding"] is True
    assert parsed["authors"][1]["name"] == "Hong Zhao"
    assert parsed["authors"][1]["is_corresponding"] is None


def test_iop_real_mailto_fallback_marks_matching_author():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="citation_author" content="J-Y Duquesne">
    <meta name="citation_author" content="A Other">
    """
    body = """
    <a href="mailto:jean-yves.duquesne@insp.jussieu.fr">jean-yves.duquesne@insp.jussieu.fr</a>
    <a href="mailto:?subject=Share this article">Share</a>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert parsed["authors"][0]["is_corresponding"] is True
    assert parsed["authors"][1]["is_corresponding"] is None


def test_iop_mailto_matching_is_case_insensitive():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="citation_author" content="Andriana">
    """
    body = """
    <a href="mailto:Andrianamsc@gmail.com">Andrianamsc@gmail.com</a>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert parsed["authors"][0]["is_corresponding"] is True


def test_iop_duplicate_single_mailto_still_marks_matching_author():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="citation_author" content="J-Y Duquesne">
    <meta name="citation_author" content="C Hepburn">
    """
    body = """
    <a href="mailto:jean-yves.duquesne@insp.jussieu.fr">jean-yves.duquesne@insp.jussieu.fr</a>
    <a href="mailto:jean-yves.duquesne@insp.jussieu.fr">jean-yves.duquesne@insp.jussieu.fr</a>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert parsed["authors"][0]["is_corresponding"] is True
    assert parsed["authors"][1]["is_corresponding"] is None


def test_iop_numbered_note_prefers_byline_superscript_over_author_index():
    head = """
    <link rel="stylesheet" href="https://static.iopscience.com/assets/app.css">
    <link rel="canonical" href="https://iopscience.iop.org/article/10.1088/example">
    <meta name="citation_author" content="J Ding">
    <meta name="citation_author" content="R T Ng">
    <meta name="citation_author" content="J McIver">
    """
    body = """
    <div class="article-meta">
      <h1>UniMAP</h1>
      <p>J Ding 3,1,2 , R T Ng 2 and J McIver 1 Published 13 June 2022</p>
      <div class="wd-jnl-art-author-emails">
        <a href="mailto:julianzding@alumni.ubc.ca">julianzding@alumni.ubc.ca</a>
        <a href="mailto:rng@cs.ubc.ca">rng@cs.ubc.ca</a>
        <a href="mailto:mciver@phas.ubc.ca">mciver@phas.ubc.ca</a>
      </div>
      <div class="wd-jnl-art-author-notes">
        <p>3 Author to whom any correspondence should be addressed.</p>
      </div>
    </div>
    """

    parsed = IOP(_soup(body, head=head)).parse()

    assert parsed["authors"][0]["is_corresponding"] is True
    assert parsed["authors"][1]["is_corresponding"] is None
    assert parsed["authors"][2]["is_corresponding"] is None
