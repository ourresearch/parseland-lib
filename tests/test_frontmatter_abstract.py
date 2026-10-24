"""Atypon front-matter abstracts win over a winning parser's cut meta tag (oxjob #1800).

RSNA, Neurology and CABI pages put the full abstract in <div id="abstracts" data-extent="frontmatter">; their
meta descriptions stop at 200 characters or the first section, and whichever generic-style parser claims the page
returns that. Dev: RSNA 296 -> 2,672 chars, Neurology "N/A" -> the structured abstract, CABI none -> its line.
Offline: inline HTML only.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.parser import frontmatter_abstract

FULL = (
    "Background Prediction of high-risk pathologic features such as microvascular invasion has clinical value. "
    "Purpose To develop a scoring model based on gadoxetic acid-enhanced MRI. Materials and Methods In this "
    "retrospective study, 417 patients with hepatocellular carcinoma were included and features were assessed "
    "by two radiologists. Results The model reached an area under the curve of 0.85. Conclusion The model "
    "enabled noninvasive preoperative prediction."
)


def _page(meta_desc, frontmatter_html, citation_abstract=None):
    cit = f'<meta name="citation_abstract" content="{citation_abstract}" />' if citation_abstract else ""
    return f"""<html><head>
      <meta property="og:url" content="https://pubs.example.org/doi/10.1148/radiol.233229" />
      <meta name="citation_title" content="A scoring model" />
      <meta name="citation_author" content="Ada Lovelace" />
      <meta name="citation_author_institution" content="University of London" />
      <meta name="dc.description" content="{meta_desc}" />
      {cit}
    </head><body>
      <div id="abstracts" data-extent="frontmatter">{frontmatter_html}</div>
    </body></html>"""


def test_frontmatter_section_without_heading():
    html = _page(FULL[:200], f'<section id="abstract"><h2>Abstract</h2><p>{FULL}</p></section>'
                             '<section id="graphical-abstract"><h2>Visual Abstract</h2></section>')
    assert frontmatter_abstract(BeautifulSoup(html, "lxml")) == FULL


def test_parse_page_prefers_full_frontmatter_over_cut_meta():
    html = _page(FULL[:200], f'<section id="abstract"><h2>Abstract</h2><p>{FULL}</p></section>')
    assert parse_page(html, "doi", "https://pubs.example.org/doi/10.1148/radiol.233229")["abstract"] == FULL


def test_parse_page_keeps_a_parser_abstract_that_is_as_complete():
    """get_text adds spaces inside inline markup, so the block's text runs a few characters longer: keep the parser's."""
    html = _page(FULL[:200], f'<section id="abstract"><h2>Abstract</h2><p>{FULL} <sup>1</sup></p></section>',
                 citation_abstract=FULL)
    assert parse_page(html, "doi", "https://pubs.example.org/doi/10.1148/radiol.233229")["abstract"] == FULL


def test_no_abstract_section_means_no_frontmatter_abstract():
    html = _page(FULL[:200], '<section id="graphical-abstract"><h2>Visual Abstract</h2></section>')
    assert frontmatter_abstract(BeautifulSoup(html, "lxml")) is None
