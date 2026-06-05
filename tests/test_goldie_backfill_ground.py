from pathlib import Path

from scripts.goldie_backfill_ground import (
    GroundingResult,
    candidate_pdf_url,
    extract_author_names_from_html,
    pdf_url_resolution_is_usable,
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
