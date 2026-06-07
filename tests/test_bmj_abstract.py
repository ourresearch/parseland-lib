from parseland_lib.parse import parse_page


def test_bmj_uses_short_citation_abstract() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://www.bmj.com/content/385/bmj.q1056">
        <meta name="citation_abstract" content="<p>Allocating placeholder roles to incoming foundation doctors undermines their value to the NHS, writes Éabha Lynn</p>">
      </head>
      <body>
        <ol class="contributor-list"><li><span class="name">Éabha Lynn</span></li></ol>
      </body>
    </html>
    """

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1136/bmj.q1056")

    assert parsed["abstract"] == (
        "<p>Allocating placeholder roles to incoming foundation doctors "
        "undermines their value to the NHS, writes Éabha Lynn</p>"
    )


def test_bmj_rejects_short_citation_abstract_teasers() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://www.bmj.com/content/385/bmj.q1056">
        <meta name="citation_abstract" content="Short teaser only...">
      </head>
      <body>
        <ol class="contributor-list"><li><span class="name">Éabha Lynn</span></li></ol>
      </body>
    </html>
    """

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1136/bmj.q1056")

    assert parsed["abstract"] is None
