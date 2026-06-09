from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.springer import Springer


def _parser(html: str) -> Springer:
    return Springer(BeautifulSoup(html, "lxml"))


def test_dispatches_bsl_by_canonical_and_uses_description() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://mijn.bsl.nl/example/123"/>
        <meta name="application-name" content="mijn-bsl"/>
        <meta property="og:description"
              content="Osteoporose wordt gedefinieerd als een systemische aandoening van het skelet met een verhoogd fractuurrisico."/>
      </head>
      <body><h1>Osteoporose en fractuurpreventie</h1></body>
    </html>
    """

    assert _parser(html).is_publisher_specific_parser() is True
    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1007/example")

    assert parsed["abstract"].startswith("Osteoporose wordt gedefinieerd")


def test_dispatches_springer_medizin_by_canonical() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://www.springermedizin.de/foo/bar/123"/>
        <meta property="og:description"
              content="Nach einer Brachytherapie wegen eines Prostatakarzinoms kommt es öfter zu sekundären Malignomen als nach einer radikalen Prostatektomie."/>
      </head>
      <body><h1>Prostatakarzinom</h1></body>
    </html>
    """

    assert _parser(html).is_publisher_specific_parser() is True
    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1007/example")

    assert "Prostatakarzinoms" in parsed["abstract"]


def test_springer_materials_marker_dispatches_and_extracts_main_abstract() -> None:
    html = """
    <html>
      <head>
        <title>Viscosity of methyl heptanoate - SpringerMaterials</title>
        <meta name="description"
              content="Landolt-Börnstein - Group IV Physical Chemistry | Volume 25 | SpringerMaterials 2008"/>
      </head>
      <body>
        <div class="main-content">
          SpringerMaterials
          <h1>Viscosity of methyl heptanoate</h1>
          <h2>Abstract</h2>
          <p>This document is part of Volume 25 "Viscosity of Pure Organic Liquids and Binary Liquid Mixtures" of Landolt-Börnstein Group IV "Physical Chemistry".</p>
          <p>Get Access PDF</p>
          <p>Impact of COVID-19 pandemic</p>
        </div>
      </body>
    </html>
    """

    assert _parser(html).is_publisher_specific_parser() is True
    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1007/example")

    assert parsed["abstract"].startswith("This document is part of Volume 25")
    assert "Get Access PDF" not in parsed["abstract"]


def test_springer_materials_extracts_authors_and_affiliations() -> None:
    html = """
    <html>
      <head>
        <title>Silicon-29 NMR data of C20H58O2S3Si8 - SpringerMaterials</title>
      </head>
      <body>
        <dl>
          <dt class="definition-term">
            Authors
            <dd id="authors" class="definition-description">
              <ul>
                <li>
                  H.C. Marsmann
                  <sup title="Department für Chemie, Universität Paderborn">
                    (103_1796)
                  </sup>
                </li>
                <li>
                  F. Uhlig
                  <sup title="Institute of Inorganic Chemistry, Graz University of Technology">
                    (105_1796)
                  </sup>
                </li>
              </ul>
            </dd>
          </dt>
          <dt class="definition-term author-affiliation">Author Affiliation</dt>
          <dd class="definition-description author-affiliation">
            <ul>
              <li>103_1796 Department für Chemie, Universität Paderborn, Paderborn, Germany</li>
              <li>105_1796 Institute of Inorganic Chemistry, Graz University of Technology, Graz, Austria</li>
            </ul>
          </dd>
        </dl>
      </body>
    </html>
    """

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1007/example")

    assert [author["name"] for author in parsed["authors"]] == [
        "H.C. Marsmann",
        "F. Uhlig",
    ]
    assert parsed["authors"][0]["affiliations"][0]["name"] == (
        "Department für Chemie, Universität Paderborn, Paderborn, Germany"
    )
    assert parsed["authors"][1]["affiliations"][0]["name"] == (
        "Institute of Inorganic Chemistry, Graz University of Technology, Graz, Austria"
    )


def test_reference_work_entry_definition_fallback_skips_boilerplate() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/referencework/10.1007/example"/>
        <meta property="og:url" content="https://link.springer.com/referenceworkentry/10.1007/example_1"/>
      </head>
      <body>
        <article>
          <div class="c-article-section__content">
            n A solution in which the concentration of solute is less than its solubility.
          </div>
          <section>
            <h2>Rights and permissions</h2>
            <div class="c-article-section__content">Reprints and permissions</div>
          </section>
        </article>
      </body>
    </html>
    """

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1007/example")

    assert parsed["abstract"].startswith("A solution in which")
    assert not parsed["abstract"].startswith("n ")


def test_nature_summary_fallback_uses_first_substantive_content_block() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://www.nature.com/articles/nrendo.2012.71"/>
        <meta property="og:url" content="https://www.nature.com/articles/nrendo.2012.71"/>
      </head>
      <body>
        <article>
          <section><h2>ORIGINAL RESEARCH PAPER</h2></section>
          <div class="c-article-section__content">
            High circulating levels of immunocomplexes containing oxidized LDLs or advanced glycation end product LDLs are associated with an increased risk of progression of retinopathy in patients with type 1 diabetes mellitus.
          </div>
          <section>
            <h2>Rights and permissions</h2>
            <div class="c-article-section__content">Reprints and permissions</div>
          </section>
        </article>
      </body>
    </html>
    """

    parsed = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1038/example")

    assert parsed["abstract"].startswith("High circulating levels")


def test_unrelated_host_still_does_not_dispatch() -> None:
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://bbrc.in/article/123"/>
        <meta property="og:url" content="https://bbrc.in/article/123"/>
      </head>
      <body><article><p>Unrelated publisher content.</p></article></body>
    </html>
    """

    assert _parser(html).is_publisher_specific_parser() is False
