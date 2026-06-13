from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.generic import GenericPublisherParser


def _parse(html):
    return GenericPublisherParser(BeautifulSoup(html, "lxml")).parse()


def test_structured_abstract_section_recovers_truncated_techrxiv_meta():
    abstract = (
        "The escalating threat of malicious software necessitates innovative "
        "detection methodologies to protect critical digital infrastructures. "
        "The Contextual Anomaly Graph Analysis framework emerges as a novel "
        "approach, leveraging graph-based anomaly detection to identify "
        "ransomware activities within complex network environments. "
        "Comprehensive evaluations demonstrate high detection accuracy across "
        "diverse ransomware variants with minimal false positive rates."
    )
    html = f"""
    <html>
      <head>
        <meta name="dc.Description" content="The escalating threat of malicious software emerg..." />
        <meta name="dc.Creator" content="Mooar Simon" />
      </head>
      <body>
        <section id="abstract" property="abstract" typeof="Text" role="doc-abstract">
          <h2 property="name">Abstract</h2>
          <p>{abstract}</p>
        </section>
      </body>
    </html>
    """

    out = _parse(html)

    assert out["authors"][0]["name"] == "Mooar Simon"
    assert out["abstract"] == abstract


def test_structured_abstract_section_rejects_short_navigation_stub():
    html = """
    <html>
      <body>
        <section id="abstract" property="abstract" role="doc-abstract">
          <h2>Abstract</h2>
          <p>Abstract</p>
        </section>
      </body>
    </html>
    """

    out = _parse(html)

    assert out["abstract"] is None


def test_preprints_visible_star_marks_corresponding_author():
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://www.preprints.org/manuscript/202110.0392/v2" />
        <meta name="citation_author" content="Francesca Noardo" />
        <meta name="citation_author" content="Dogus Guler" />
        <meta name="citation_author" content="Judith Fauth" />
      </head>
      <body>
        <div class="manuscript-authors">
          Francesca Noardo<sup>*</sup>, Dogus Guler<sup></sup>, Judith Fauth<sup></sup>
        </div>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True, False, False]


def test_generic_plain_text_starred_byline_marks_corresponding_author():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <p>Jane Smith*, Bob Jones</p>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_generic_sup_starred_byline_marks_corresponding_author():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <div class="article-authors">
          Jane Smith<sup>*</sup>, Bob Jones
        </div>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_generic_affiliation_label_plus_star_marks_corresponding_author():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <div class="authors">
          Jane Smith<sup>1,*</sup>, Bob Jones<sup>2</sup>
        </div>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_generic_starred_single_author_defaults_to_corresponding_without_note():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
      </head>
      <body>
        <p>Jane Smith<sup>*</sup></p>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True]


def test_generic_starred_byline_positive_footnote_marks_corresponding_author():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <p class="byline">Jane Smith<sup>*</sup>, Bob Jones</p>
        <p>* Corresponding author: jane@example.org</p>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_generic_starred_byline_equal_contribution_note_blocks_corresponding():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <p class="byline">Jane Smith<sup>*</sup>, Bob Jones</p>
        <p>* These authors contributed equally.</p>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [None, None]


def test_generic_starred_byline_present_address_note_blocks_corresponding():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <p class="authors">Jane Smith<sup>*</sup>, Bob Jones</p>
        <p>* Present address: Department of Biology, Example University.</p>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [None, None]


def test_generic_all_authors_starred_without_positive_note_does_not_overmark():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Jane Smith" />
        <meta name="citation_author" content="Bob Jones" />
      </head>
      <body>
        <p class="authors">Jane Smith<sup>*</sup>, Bob Jones<sup>*</sup></p>
        <p><a href="mailto:?subject=Recommended article">Email this article</a></p>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [None, None]


def test_explicit_author_popover_marks_corresponding_author():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Mary Rice" />
      </head>
      <body>
        <div class="author-popover">
          <strong>Mary Rice</strong>
          <p>Corresponding Author: mary.rice@example.org</p>
          <a>Author Profile</a>
        </div>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True]


def test_explicit_essoar_author_block_marks_only_named_author():
    html = """
    <html>
      <head>
        <meta name="dc.Creator" content="Indhu Varatharajan" />
        <meta name="dc.Creator" content="Claudia Stangarone" />
      </head>
      <body>
        <div class="accordion-tabbed__tab-mobile accordion__closed">
          <a class="author-name" title="Indhu Varatharajan">
            <span class="author-name-content">Indhu Varatharajan</span>
          </a>
          <div class="author-info accordion-tabbed__content">
            <span class="corresponding-author">Corresponding Author</span>
            <span class="submitting-author">- Submitting Author</span>
            <div class="author-affiliation">Institute of Planetary Research</div>
          </div>
        </div>
        <div class="accordion-tabbed__tab-mobile accordion__closed">
          <a class="author-name" title="Claudia Stangarone">
            <span class="author-name-content">Claudia Stangarone</span>
          </a>
          <div class="author-info accordion-tabbed__content">
            <div class="author-affiliation">Institute of Planetary Research</div>
          </div>
        </div>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [True, False]


def test_generic_share_mailto_does_not_mark_corresponding_author():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Alice First" />
        <meta name="citation_author" content="Bob Second" />
      </head>
      <body>
        <a href="mailto:?subject=Recommended article">Email this article</a>
        <footer>Contact support@example.org for site questions.</footer>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [None, None]


def test_generic_broad_page_correspondence_text_does_not_overmark():
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Alice First" />
        <meta name="citation_author" content="Bob Second" />
      </head>
      <body>
        <section>
          <h2>Authors</h2>
          <p>Alice First and Bob Second contributed to this paper.</p>
          <p>Corresponding author information is unavailable from this page.</p>
        </section>
      </body>
    </html>
    """

    out = _parse(html)

    assert [a["is_corresponding"] for a in out["authors"]] == [None, None]
