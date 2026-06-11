from __future__ import annotations

from parseland_lib.parse import parse_page


def _wrap(body: str) -> str:
    return f"""
    <html>
      <head>
        <link rel="canonical"
              href="https://journals.sagepub.com/doi/10.1177/00220345660450036601" />
      </head>
      <body>{body}</body>
    </html>
    """


def test_semantic_doc_abstract_section_skips_localized_heading() -> None:
    parsed = parse_page(
        _wrap(
            """
            <section id="abstract-es"
                     lang="es"
                     property="abstract"
                     role="doc-abstract"
                     typeof="Text">
              <h2 property="name">Resumen</h2>
              <div role="paragraph">SYNOPSIS IN INTERLINGUA</div>
              <div role="paragraph">
                HISTO-RESPONSA DE MEMBRANAS CHORIOALLANTOIC DE GALLINA A
                MATERIALES DE USO IN IMPLANTATIONES DENTAL. Le evalutation
                de histo-responsas in humanos require le uso de altere
                systemas vital. Le presente reporto es concernite con
                reactiones de tissu epithelial e conjunctive.
              </div>
            </section>
            <section class="core-authors">
              <div typeof="Person">
                <span property="givenName">J.C.</span>
                <span property="familyName">Thonard</span>
              </div>
            </section>
            """
        ),
        namespace="doi",
        resolved_url="https://doi.org/10.1177/00220345660450036601",
    )

    assert parsed["abstract"] is not None
    assert parsed["abstract"].startswith("SYNOPSIS IN INTERLINGUA")
    assert "Resumen" not in parsed["abstract"]
