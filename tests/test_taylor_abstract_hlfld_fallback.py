"""Focused tests for the Taylor & Francis abstract selector ladder.

Background:
    The Taylor parser historically only extracted abstracts from
    ``div.abstractInFull``. Older / legacy tandfonline.com templates instead
    expose the abstract body via the ``hlFld-Abstract`` container (no
    ``abstractInFull`` child). A separate failure mode came from the
    ``is_publisher_specific_parser`` check: some Taylor pages still carry an
    ``og:url`` pointing at the legacy ``informahealthcare.com`` host while the
    canonical link correctly identifies tandfonline.com. Both cases caused
    ``abstract`` to come back ``None`` despite the abstract text being present
    in the HTML.

These tests pin both fixes:
    1. Falling back to ``hlFld-Abstract`` when ``abstractInFull`` is absent.
    2. Stripping duplicated leading ``Abstract`` / ``ABSTRACT`` / ``RÉSUMÉ``
       headings that appear inside ``hlFld-Abstract``.
    3. Dispatching to the Taylor parser when only the canonical link points to
       tandfonline.com.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.taylor import Taylor


def _parser(html: str) -> Taylor:
    return Taylor(BeautifulSoup(html, "lxml"))


# Minimal authors block — Taylor.parse() requires publicationContentAuthors
# to be present, otherwise it raises before reaching the abstract logic.
_AUTHORS_BLOCK = """
<div class="publicationContentAuthors">
  <div class="entryAuthor">
    <a>Jane Doe</a>
    <span class="overlay">Department of Test, Test University</span>
  </div>
</div>
"""


def test_abstract_in_full_still_wins() -> None:
    """Primary selector still preferred when both wrappers exist."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/abc.123" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        <h2>ABSTRACT</h2>
        <div class="abstractInFull">
          <p>Primary abstract body that should win.</p>
        </div>
      </div>
    </body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser()
    out = parser.parse()
    assert out["abstract"] is not None
    assert "Primary abstract body that should win." in out["abstract"]


def test_hlfld_abstract_fallback_when_abstract_in_full_missing() -> None:
    """hlFld-Abstract recovers the abstract on legacy templates."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/legacy" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        The charopid genus Oreokera is shown to be an invalidly introduced
        taxon. It is herein formally validated and redefined.
      </div>
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is not None
    assert "charopid genus Oreokera" in out["abstract"]


def test_hlfld_abstract_strips_doubled_abstract_heading() -> None:
    """Leading 'ABSTRACTABSTRACT' / 'Abstract\\nAbstract' is stripped."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/dup" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        <h2>ABSTRACT</h2>ABSTRACTApproximately one in three women report sexual trauma.
      </div>
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is not None
    # Both leading "ABSTRACT" labels must be gone; substantive text retained.
    assert out["abstract"].lstrip().lower().startswith("approximately one in three")
    assert "ABSTRACTABSTRACT" not in out["abstract"]


def test_hlfld_abstract_strips_french_resume_heading() -> None:
    """RÉSUMÉ heading is also stripped on French-language Canadian RS articles."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/fr" />
    </head><body>
      {_AUTHORS_BLOCK}
      <div class="hlFld-Abstract">
        RÉSUMÉOn a utilisé des données RADARSAT pour faire le suivi du panache.
      </div>
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is not None
    assert out["abstract"].lstrip().startswith("On a utilisé des données RADARSAT")


def test_author_bio_affiliation_fallback_legacy_tandf_shared_bio() -> None:
    """Older TandF pages put affiliations in Notes on contributors."""
    html = """
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/legacy" />
    </head><body>
      <div class="publicationContentAuthors">
        <div class="entryAuthor">
          <a>G.R. Cresswell</a>
          <span class="overlay">View further author information</span>
        </div>
        <div class="entryAuthor">
          <a>P.C. Tildesley</a>
          <span class="overlay">View further author information</span>
        </div>
      </div>
      <div class="author-infos" id="author-infos">
        <h3 class="section-heading-3">Notes on contributors</h3>
        <div class="addAuthorInfo">
          <span class="AuthorInfoData">
            <h4><span class="NLM_given-names">G.R.</span> Cresswell</h4>
            G.R. Cresswell and P.C. Tildesley are with the
            CSIRO Marine Research Facility in Hobart Tasmania Australia
          </span>
        </div>
        <div class="addAuthorInfo">
          <span class="AuthorInfoData">
            <h4><span class="NLM_given-names">P.C.</span> Tildesley</h4>
            G.R. Cresswell and P.C. Tildesley are with the
            CSIRO Marine Research Facility in Hobart Tasmania Australia
          </span>
        </div>
      </div>
    </body></html>
    """
    out = _parser(html).parse()

    assert out["authors"][0].affiliations == [
        "CSIRO Marine Research Facility in Hobart Tasmania Australia"
    ]
    assert out["authors"][1].affiliations == [
        "CSIRO Marine Research Facility in Hobart Tasmania Australia"
    ]


def test_author_bio_affiliation_fallback_department_at_university() -> None:
    """Bio text recovers department/university affiliations, not email overlays."""
    html = """
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/legacy2" />
    </head><body>
      <div class="publicationContentAuthors">
        <div class="entryAuthor">
          <a>Bruce F. Barker</a>
          <span class="overlay">
            <span class="heading">Correspondence</span>
            barkerb@example.edu
            <a>View further author information</a>
          </span>
        </div>
      </div>
      <div class="author-infos" id="author-infos">
        <h3 class="section-heading-3">Notes on contributors</h3>
        <div class="addAuthorInfo">
          <span class="AuthorInfoData">
            <h4><span class="NLM_given-names">Bruce F.</span> Barker</h4>
            <b>Bruce F. Barker, DDS</b>, is a professor in the
            Department of Oral and Maxillofacial Pathology at the
            University of Missouri-Kansas City School of Dentistry.
          </span>
        </div>
      </div>
    </body></html>
    """
    out = _parser(html).parse()

    assert out["authors"][0].affiliations == [
        "Department of Oral and Maxillofacial Pathology, University of Missouri-Kansas City School of Dentistry"
    ]
    assert out["authors"][0].is_corresponding is True


def test_author_bio_affiliation_fallback_at_university_omits_role() -> None:
    """Role text before an 'at the University' affiliation is not included."""
    html = """
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/legacy3" />
    </head><body>
      <div class="publicationContentAuthors">
        <div class="entryAuthor">
          <a>Ralph A. Smith</a>
          <span class="overlay">View further author information</span>
        </div>
      </div>
      <div class="author-infos" id="author-infos">
        <h3 class="section-heading-3">Notes on contributors</h3>
        <div class="addAuthorInfo">
          <span class="AuthorInfoData">
            <h4>Ralph A. Smith</h4>
            Ralph A. Smith is a professor emeritus of cultural and educational
            policy at the University of Illinois at Urbana-Champaign and editor
            of the Journal of Aesthetic Education.
          </span>
        </div>
      </div>
    </body></html>
    """
    out = _parser(html).parse()

    assert out["authors"][0].affiliations == [
        "University of Illinois at Urbana-Champaign"
    ]


def test_canonical_link_dispatches_when_og_url_is_legacy_host() -> None:
    """Legacy informahealthcare og:url still dispatches if canonical is tandfonline."""
    html = """
    <html><head>
      <meta property="og:url" content="https://www.informahealthcare.com/doi/abs/10.1080/legacy" />
      <link rel="canonical" href="https://www.tandfonline.com/doi/full/10.1080/legacy" />
    </head><body></body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser() is True


def test_dispatch_negative_when_neither_signal_matches() -> None:
    """Unrelated hosts must not match Taylor dispatch."""
    html = """
    <html><head>
      <meta property="og:url" content="https://onlinelibrary.wiley.com/doi/10.1002/whatever" />
      <link rel="canonical" href="https://onlinelibrary.wiley.com/doi/10.1002/whatever" />
    </head><body></body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser() is False


def test_abstract_none_when_no_abstract_wrapper_present() -> None:
    """If both wrappers are missing, do not grab generic og:description."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/none" />
      <meta property="og:description" content="Published in Performance Research Vol. 22." />
    </head><body>
      {_AUTHORS_BLOCK}
    </body></html>
    """
    parser = _parser(html)
    out = parser.parse()
    assert out["abstract"] is None


def test_dc_description_fallback_when_no_abstract_wrapper_present() -> None:
    """dc.Description recovers publisher-provided previews on review pages."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/full/10.1080/review" />
      <meta name="dc.Description"
        content="An exciting and necessary book, this review argues that the
        empress was a major celebrity of eighteenth-century Europe." />
      <meta property="og:description" content="Published in Journal Reviews (Vol. 65, No. 2, 2023)" />
    </head><body>
      {_AUTHORS_BLOCK}
    </body></html>
    """
    out = _parser(html).parse()
    assert out["abstract"] is not None
    assert out["abstract"].startswith("An exciting and necessary book")
    assert "Published in Journal Reviews" not in out["abstract"]


def test_dc_description_citation_snippet_is_not_abstract() -> None:
    """Citation-only dc.Description metadata is not substantive abstract text."""
    html = f"""
    <html><head>
      <meta property="og:url" content="https://www.tandfonline.com/doi/abs/10.1080/citation" />
      <meta name="dc.Description"
        content="(1976). Editorial board. Australian Outlook: Vol. 30, No. 3, pp. ebi-ebii." />
    </head><body>
      {_AUTHORS_BLOCK}
    </body></html>
    """
    out = _parser(html).parse()
    assert out["abstract"] is None


def test_taylorfrancis_chapter_jsonld_dispatch_and_product_abstract() -> None:
    """Taylor eBook chapter pages parse JSON-LD authors and product abstracts."""
    html = """
    <html><head>
      <link rel="canonical"
        href="https://www.taylorfrancis.com/chapters/mono/10.4324/example/chapter-author" />
      <script type="application/ld+json" id="jsonld">
        {
          "@context": "https://schema.org",
          "@type": "Chapter",
          "url": "https://www.taylorfrancis.com/chapters/mono/10.4324/example/chapter-author",
          "author": {"@type": "Person", "givenName": "Nigel", "familyName": "Thacker"},
          "publisher": {"@type": "Organization", "name": "Taylor & Francis"},
          "description": "Short metadata description"
        }
      </script>
      <script type="application/json">
        {&q;product&q;:{&q;chapter&q;:{&q;abstracts&q;:[{&q;type&q;:&q;xml&q;,&q;value&q;:&q;&l;p&g;Full chapter abstract from product JSON.&l;/p&g;&q;}]}}}
      </script>
    </head><body></body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser()
    assert parser.authors_found()

    out = parser.parse()

    assert [author.name for author in out["authors"]] == ["Nigel Thacker"]
    assert out["authors"][0].affiliations == []
    assert out["authors"][0].is_corresponding is False
    assert out["abstract"] == "Full chapter abstract from product JSON."


def test_taylorfrancis_chapter_splits_compressed_jsonld_author_lists() -> None:
    """Chapter JSON-LD may compress multiple authors into one Person object."""
    html = """
    <html><head>
      <link rel="canonical"
        href="https://www.taylorfrancis.com/chapters/edit/10.1201/example/computational-methods-di-prisco-boldini" />
      <script type="application/ld+json" id="jsonld">
        {
          "@context": "https://schema.org",
          "@type": "Chapter",
          "url": "https://www.taylorfrancis.com/chapters/edit/10.1201/example/computational-methods-di-prisco-boldini",
          "author": {
            "@type": "Person",
            "givenName": "C., D., A.",
            "familyName": "di Prisco, Boldini, Desideri"
          },
          "publisher": {"@type": "Organization", "name": "Taylor & Francis"},
          "description": "Chapter-only description fallback."
        }
      </script>
    </head><body></body></html>
    """

    out = _parser(html).parse()

    assert [author.name for author in out["authors"]] == [
        "C. di Prisco",
        "D. Boldini",
        "A. Desideri",
    ]
    assert all(author.affiliations == [] for author in out["authors"])
    assert all(author.is_corresponding is False for author in out["authors"])


def test_taylorfrancis_chapter_uses_jsonld_description_without_product_abstract() -> None:
    """JSON-LD description is a final fallback for eBook chapter pages only."""
    html = """
    <html><head>
      <meta property="og:url"
        content="https://www.taylorfrancis.com/chapters/mono/10.1201/example/chapter-author" />
      <script type="application/ld+json" id="jsonld">
        {
          "@context": "https://schema.org",
          "@type": "Chapter",
          "url": "https://www.taylorfrancis.com/chapters/mono/10.1201/example/chapter-author",
          "author": {"@type": "Person", "givenName": "Preben W.", "familyName": "Jensen"},
          "publisher": {"@type": "Organization", "name": "Taylor & Francis"},
          "description": "Chapter-only description fallback."
        }
      </script>
    </head><body></body></html>
    """
    parser = _parser(html)
    assert parser.is_publisher_specific_parser()

    out = parser.parse()

    assert [author.name for author in out["authors"]] == ["Preben W. Jensen"]
    assert out["abstract"] == "Chapter-only description fallback."


def test_parse_page_returns_taylorfrancis_chapter_without_affiliations() -> None:
    """Publisher-specific Taylor chapter output must not be dropped for no affs."""
    html = """
    <html><head>
      <link rel="canonical"
        href="https://www.taylorfrancis.com/chapters/mono/10.4324/example/chapter-author" />
      <script type="application/ld+json" id="jsonld">
        {
          "@context": "https://schema.org",
          "@type": "Chapter",
          "url": "https://www.taylorfrancis.com/chapters/mono/10.4324/example/chapter-author",
          "author": {"@type": "Person", "givenName": "Nigel", "familyName": "Thacker"},
          "publisher": {"@type": "Organization", "name": "Taylor & Francis"},
          "description": "Chapter description from structured metadata."
        }
      </script>
    </head><body></body></html>
    """

    out = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.4324/example")

    assert out["authors"] == [
        {
            "name": "Nigel Thacker",
            "affiliations": [],
            "is_corresponding": False,
        }
    ]
    assert out["abstract"] == "Chapter description from structured metadata."
