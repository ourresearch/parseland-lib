from pathlib import Path

import scripts.goldie_backfill_ground as ground
from scripts.goldie_backfill_ground import (
    GroundingResult,
    abstract_followup_url,
    candidate_affiliation_values,
    candidate_pdf_url,
    excerpt_for,
    extract_author_names_from_html,
    pdf_url_resolution_is_usable,
    resolve_abstract_len_candidate,
    resolve_affiliation_candidate,
    resolve_author_count_candidate,
    write_result,
)


def test_candidate_pdf_url_extracts_structured_candidate():
    candidate = {
        "field": "pdf_url",
        "parseland_candidate": {
            "pdf_url": " https://www.sciencedirect.com/science/article/pii/S123/pdf "
        },
    }

    assert candidate_pdf_url(candidate) == "https://www.sciencedirect.com/science/article/pii/S123/pdf"


def test_pdf_url_resolution_requires_pdf_like_final_url():
    assert pdf_url_resolution_is_usable(200, "https://example.org/article/pdfft?x=1")
    assert pdf_url_resolution_is_usable(None, "https://example.org/article.pdf")
    assert not pdf_url_resolution_is_usable(404, "https://example.org/article.pdf")
    assert not pdf_url_resolution_is_usable(200, "https://example.org/article/abs/pii/S123")
    assert not pdf_url_resolution_is_usable(200, "https://example.org/login?next=/article.pdf")


def test_resolve_author_count_candidate_from_ieee_author_names():
    html = (
        '{"doiLink":"https://doi.org/10.1109/example",'
        '"authorNames":"J. Pieper;S. Srinivasan;B. Dom"}'
    )
    candidate = {
        "field": "authors",
        "parseland_candidate": {
            "n_authors": 3,
            "note": "n_authors only",
        },
    }

    resolved, excerpt = resolve_author_count_candidate(html, candidate)

    assert extract_author_names_from_html(html) == ["J. Pieper", "S. Srinivasan", "B. Dom"]
    assert resolved == {
        "authors": [
            {"name": "J. Pieper", "affiliations": [], "is_corresponding": None},
            {"name": "S. Srinivasan", "affiliations": [], "is_corresponding": None},
            {"name": "B. Dom", "affiliations": [], "is_corresponding": None},
        ]
    }
    assert "authorNames" in excerpt


def test_resolve_author_count_candidate_rejects_count_mismatch():
    html = '{"authorNames":"J. Pieper;S. Srinivasan"}'
    candidate = {"field": "authors", "parseland_candidate": {"n_authors": 3}}

    assert resolve_author_count_candidate(html, candidate) is None


def test_resolve_abstract_len_candidate_from_rendered_parse(monkeypatch):
    abstract = " ".join(["Browserbase-rendered abstract evidence"] * 20)

    def fake_parse_page(html, namespace, resolved_url=None):
        assert namespace == "doi"
        assert resolved_url == "https://journals.lww.com/example"
        return {"abstract": abstract}

    monkeypatch.setattr(ground, "parse_page", fake_parse_page)
    candidate = {"field": "abstract", "parseland_candidate": {"abstract_len": len(abstract)}}

    resolved, excerpt = resolve_abstract_len_candidate(
        "<html>rendered page</html>",
        candidate,
        "https://journals.lww.com/example",
    )

    assert resolved == {"abstract": abstract}
    assert excerpt.startswith("Browserbase-rendered abstract evidence")


def test_resolve_abstract_len_candidate_rejects_length_mismatch(monkeypatch):
    monkeypatch.setattr(
        ground,
        "parse_page",
        lambda html, namespace, resolved_url=None: {"abstract": "short " * 40},
    )
    candidate = {"field": "abstract", "parseland_candidate": {"abstract_len": 5000}}

    assert resolve_abstract_len_candidate("<html></html>", candidate, None) is None


def test_candidate_affiliation_values_dedupes_and_cleans_values():
    candidate = {
        "field": "affiliations",
        "parseland_candidate": {
            "affiliations": [
                " Medical School, University of Minnesota, Minneapolis, MN, USA; ",
                "Medical School, University of Minnesota, Minneapolis, MN, USA",
                {"name": "Department of Surgery, Ridgeview Medical Center, Waconia, MN, USA."},
            ],
            "authors": [
                {
                    "affiliations": [
                        "Department of Surgery, Ridgeview Medical Center, Waconia, MN, USA"
                    ]
                }
            ],
        },
    }

    assert candidate_affiliation_values(candidate) == [
        "Medical School, University of Minnesota, Minneapolis, MN, USA",
        "Department of Surgery, Ridgeview Medical Center, Waconia, MN, USA",
    ]


def test_resolve_affiliation_candidate_requires_all_unique_values():
    candidate = {
        "field": "affiliations",
        "parseland_candidate": {
            "affiliations": [
                "Medical School, University of Minnesota, Minneapolis, MN, USA",
                "Medical School, University of Minnesota, Minneapolis, MN, USA",
                "Department of Surgery, Ridgeview Medical Center, Waconia, MN, USA",
            ]
        },
    }
    html = """
    <section property="author">
      <span property="name">Medical School, University of Minnesota, Minneapolis, MN, USA</span>
    </section>
    <section property="author">
      <span property="name">Department of Surgery, Ridgeview Medical Center, Waconia, MN, USA</span>
    </section>
    """

    resolved, excerpt = resolve_affiliation_candidate(html, candidate)

    assert resolved == {
        "affiliations": [
            "Medical School, University of Minnesota, Minneapolis, MN, USA",
            "Department of Surgery, Ridgeview Medical Center, Waconia, MN, USA",
        ]
    }
    assert "Medical School, University of Minnesota" in excerpt
    assert "Department of Surgery, Ridgeview" in excerpt


def test_resolve_affiliation_candidate_rejects_partial_evidence():
    candidate = {
        "field": "affiliations",
        "parseland_candidate": {
            "affiliations": [
                "Dallas, Texas",
                "Arlington, Texas",
            ]
        },
    }

    assert resolve_affiliation_candidate("<html>Dallas, Texas</html>", candidate) is None


def test_corresponding_excerpt_prefers_correspondence_signal():
    candidate = {
        "field": "corresponding",
        "parseland_candidate": {
            "authors": [
                {
                    "name": "Franklin Dexter",
                    "affiliations": [
                        "Department of Anesthesia, University of Iowa",
                        "Address e-mail to [email protected]",
                    ],
                    "is_corresponding": True,
                }
            ]
        },
    }
    html = """
    <html><body>
      <p>Franklin Dexter</p>
      <p>Address e-mail to [email protected]</p>
    </body></html>
    """

    excerpt, selector, confidence = excerpt_for(html, candidate)

    assert "Address e-mail" in excerpt
    assert selector == "correspondence-candidate-text-match"
    assert confidence == "correspondence_candidate_text_match"


def test_corresponding_excerpt_downgrades_author_name_only():
    candidate = {
        "field": "corresponding",
        "parseland_candidate": {
            "authors": [
                {
                    "name": "Franklin Dexter",
                    "affiliations": ["Department of Anesthesia, University of Iowa"],
                    "is_corresponding": True,
                }
            ]
        },
    }
    html = "<html><body><p>Franklin Dexter</p></body></html>"

    excerpt, selector, confidence = excerpt_for(html, candidate)

    assert "Franklin Dexter" in excerpt
    assert selector == "corresponding-author-name-only"
    assert confidence == "corresponding_author_name_only"


def test_corresponding_excerpt_rejects_generic_address_needle():
    candidate = {
        "field": "corresponding",
        "parseland_candidate": {
            "authors": [
                {
                    "name": "Marta Valencia",
                    "affiliations": ["address"],
                    "is_corresponding": True,
                }
            ]
        },
    }
    html = """
    <html><body>
      <p>Marta Valencia</p>
      <label for="email-input">Enter your Email address:</label>
    </body></html>
    """

    excerpt, selector, confidence = excerpt_for(html, candidate)

    assert "Marta Valencia" in excerpt
    assert selector == "corresponding-author-name-only"
    assert confidence == "corresponding_author_name_only"


def test_abstract_followup_url_prefers_lww_meta_url():
    html = (
        '<meta name="wkhealth_abstract_html_url" '
        'content="https://journals.lww.com/example/abstract/2024/01000/title.1.aspx">'
    )

    assert abstract_followup_url("https://journals.lww.com/example/citation/2024/x.aspx", html) == (
        "https://journals.lww.com/example/abstract/2024/01000/title.1.aspx"
    )


def test_abstract_followup_url_falls_back_from_citation_path():
    assert abstract_followup_url(
        "https://journals.lww.com/example/citation/2024/01000/title.1.aspx",
        "<html></html>",
    ) == "https://journals.lww.com/example/abstract/2024/01000/title.1.aspx"


def test_write_result_preserves_verified_pdf_evidence(tmp_path: Path):
    out = tmp_path / "grounded.ndjson"
    candidate = {
        "doi": "10.1000/example",
        "publisher": "elsevier",
        "field": "pdf_url",
        "gold_value": None,
        "parseland_candidate": {"pdf_url": "https://example.org/article/pii/S123/pdf"},
    }
    result = GroundingResult(
        doi="10.1000/example",
        field="pdf_url",
        status="candidate_evidence_needs_referee",
        final_url="https://example.org/article/abs/pii/S123",
        verified_candidate_url="https://example.org/article/pii/S123/pdf",
        verified_candidate_final_url="https://example.org/article/pii/S123/pdfft",
        verified_candidate_status=200,
        verified_candidate_screenshot_path="/tmp/example-pdf.png",
        resolved_candidate={"authors": [{"name": "Example Author"}]},
        resolved_candidate_source="browserbase_rendered_authorNames",
        selector="candidate-pdf-url-navigation",
        confidence="candidate_pdf_url_resolves",
    )

    write_result(out, candidate, result)

    text = out.read_text(encoding="utf-8")
    assert '"verified_candidate_url":"https://example.org/article/pii/S123/pdf"' in text
    assert '"verified_candidate_status":200' in text
    assert '"resolved_candidate_source":"browserbase_rendered_authorNames"' in text
    assert '"grounding_confidence":"candidate_pdf_url_resolves"' in text
