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


def test_bmj_marks_contrib_email_author_corresponding() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://www.bmj.com/content/326/7397/1036">
      </head>
      <body>
        <ol class="contributor-list">
          <li>
            <span class="name">Mike Thomas</span>
            <span class="contrib-email">(mikethomas@doctors.org.uk)</span>
          </li>
          <li><span class="name">David Price</span></li>
        </ol>
      </body>
    </html>
    """

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.1136/bmj.326.7397.1036",
    )

    assert [a["is_corresponding"] for a in parsed["authors"]] == [True, False]


def test_bmj_matches_correspondence_initials_to_author_name() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://ard.bmj.com/content/58/8/503">
      </head>
      <body>
        <ol class="contributor-list">
          <li><span class="name">Caralee J Schaefer</span></li>
          <li><span class="name">W Dwayne Lawrence</span></li>
          <li><span class="name">Paul H Wooley</span></li>
        </ol>
        <ol>
          <li class="corresp">Dr P H Wooley, Department of Orthopaedic Surgery</li>
        </ol>
      </body>
    </html>
    """

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.1136/ard.58.8.503",
    )

    assert [a["is_corresponding"] for a in parsed["authors"]] == [False, False, True]
