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


def test_bmj_uses_data_layer_contributor_when_contributor_list_is_empty() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://emj.bmj.com/content/32/1/85.1">
      </head>
      <body>
        <script>
          window.dataLayer = window.dataLayer || [];
          window.dataLayer.push({
            "content": {
              "hwContributors": "Richard Body",
              "hwCorpusCode": "emermed"
            }
          });
        </script>
        <ol class="contributor-list" id="contrib-group-1"></ol>
      </body>
    </html>
    """

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.1136/emermed-2014-204467",
    )

    assert [a["name"] for a in parsed["authors"]] == ["Richard Body"]


def test_bmj_parses_legacy_inline_author_paragraph() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://www.bmj.com/content/326/7381/172">
      </head>
      <body>
        <article>
          <div class="article extract-view">
            <p>A 33 year old woman presented with vesicular erythema.</p>
            <p>N Nicolaou, specialist registrar, G A Johnston, consultant,
               department of dermatology, Leicester Royal Infirmary, Leicester LE2 7LX</p>
          </div>
        </article>
      </body>
    </html>
    """

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.1136/bmj.326.7381.172",
    )

    assert [a["name"] for a in parsed["authors"]] == ["N Nicolaou", "G A Johnston"]
    assert parsed["authors"][0]["affiliations"] == [
        {
            "name": "department of dermatology, Leicester Royal Infirmary, Leicester LE2 7LX"
        }
    ]


def test_bmj_normalizes_symbol_affiliation_references() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://sti.bmj.com/content/93/Suppl_2/A88.2">
      </head>
      <body>
        <ol class="contributor-list">
          <li><span class="name">QQ Wang</span><a class="xref-aff" href="#aff-2"><sup>2§</sup></a></li>
        </ol>
        <ol class="affiliation-list">
          <li class="aff"><address><sup>2</sup>Institute of Dermatology, Nanjing, China</address></li>
        </ol>
      </body>
    </html>
    """

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.1136/sextrans-2017-053264.224",
    )

    assert parsed["authors"][0]["affiliations"] == [
        {"name": "Institute of Dermatology, Nanjing, China"}
    ]


def test_bmj_keeps_primary_affiliation_when_correspondence_has_address() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://jcp.bmj.com/content/60/9/1058">
      </head>
      <body>
        <ol class="contributor-list">
          <li><span class="name">L Venkatraman</span><span class="xref-aff">1</span></li>
        </ol>
        <ol class="affiliation-list">
          <li class="aff"><address><sup>1</sup>Department of Histopathology, Royal Victoria Hospital</address></li>
        </ol>
        <ol>
          <li class="corresp">Correspondence to: Dr L Venkatraman,
            Royal Group of Hospitals Trust, Grosvenor Road</li>
        </ol>
      </body>
    </html>
    """

    parsed = parse_page(
        html,
        namespace="doi",
        resolved_url="https://doi.org/10.1136/jcp.2005.035352",
    )

    assert parsed["authors"][0]["affiliations"] == [
        {"name": "Department of Histopathology, Royal Victoria Hospital"}
    ]
    assert parsed["authors"][0]["is_corresponding"] is True
