"""Atypon front-matter abstracts win over a winning parser's cut meta tag (oxjob #1800).

RSNA, Neurology and CABI pages put the full abstract in <div id="abstracts" data-extent="frontmatter">; their
meta descriptions stop at 200 characters or the first section, and whichever generic-style parser claims the page
returns that. Dev: RSNA 296 -> 2,672 chars, Neurology "N/A" -> the structured abstract, CABI none -> its line.
Offline: inline HTML only.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.parser import frontmatter_abstract, silverchair_abstract

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


SILVER_PAGE = """<html><head>
  <meta property="og:site_name" content="AIP Publishing" />
  <meta name="citation_title" content="Numerical methods for locating stable periodic orbits" />
  <meta name="citation_author" content="Marcinek, Roman" />
  <meta name="citation_author_institution" content="Chemical Physics Department, Weizmann Institute of Science" />
  <meta name="description" content="Monte Carlo methods are combined with a Newton method to construct an efficient numerical procedure for locating stable periodic orbits embedded in a largel" />
</head><body><div class="widget-ArticleFulltext widget-instance-ArticleFulltext_Abstract">
  <section class="abstract"><p>Monte Carlo methods are combined with a Newton method to construct an efficient
  numerical procedure for locating stable periodic orbits embedded in a largely chaotic system in CO<sub>2</sub>.</p>
  <p>We find that the Newton method converges in a few iterations.</p></section>
</div></body></html>"""


def test_silverchair_section_fills_a_missing_abstract():
    """pubs.aip.org: no publisher parser claims the page, the generic one finds authors but no abstract."""
    out = parse_page(SILVER_PAGE, "doi", "https://pubs.aip.org/aip/jcp/article/100/8/5894/480305")
    assert out["abstract"].startswith("Monte Carlo methods are combined")
    assert "CO2" in out["abstract"] and "Newton method converges" in out["abstract"]


def test_silverchair_needs_the_article_widget():
    page = SILVER_PAGE.replace('class="widget-ArticleFulltext widget-instance-ArticleFulltext_Abstract"', "")
    assert silverchair_abstract(BeautifulSoup(page, "lxml")) is None


def test_abstract_section_holding_only_a_figure_is_not_an_abstract():
    # CABI chapters: the "Abstract" section is a figure and its caption (oxjob #1800 EXPLORE § 13; #1794)
    html = _page("", '<section id="abstract"><h2>Abstract</h2><div class="figure-wrap"><figure id="fig3_100" '
                     'class="graphic"><figcaption>Fig. 3 . Mind the Gap: Conventional versus Metronomic '
                     'Chemotherapy.</figcaption></figure></div></section>')
    assert frontmatter_abstract(BeautifulSoup(html, "lxml")) is None
