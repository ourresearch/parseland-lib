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
