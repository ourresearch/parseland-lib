"""
Regression tests for parseland_lib.parse.parse_page() and find_pdf_link().

Covers the fa98bf1 fix: parse_page() must not raise UnboundLocalError when
called with a namespace other than "doi" or "pmh" (including the common
namespace=None default from the eval harness). The else branch in parse.py
must assign fulltext_location = None so the downstream merge is safe.

These tests are offline — they construct soup from inline HTML strings and
do not hit Taxicab or any network resource.
"""
from __future__ import annotations

import pytest

from parseland_lib.parse import find_pdf_link, parse_page


MINIMAL_HTML = "<html><body><p>hello world</p></body></html>"


@pytest.mark.parametrize("namespace", [None, "", "unknown", "DOI", "Pmh"])
def test_parse_page_unknown_namespace_does_not_raise(namespace):
    """fa98bf1: any namespace outside {"doi", "pmh"} must hit the else
    branch and return a well-formed response with no fulltext_location."""
    result = parse_page(MINIMAL_HTML, namespace)

    assert isinstance(result, dict)
    assert result["authors"] == []
    assert result["abstract"] is None
    assert result["urls"] == []
    assert result["license"] is None
    assert result["version"] is None


def test_parse_page_namespace_doi_returns_structured_response():
    """The doi branch still works after fa98bf1."""
    result = parse_page(MINIMAL_HTML, "doi")

    assert isinstance(result, dict)
    assert set(result.keys()) == {"authors", "urls", "license", "version", "abstract"}
    assert isinstance(result["authors"], list)
    assert isinstance(result["urls"], list)


def test_parse_page_namespace_pmh_returns_structured_response():
    """The pmh branch still works after fa98bf1."""
    result = parse_page(MINIMAL_HTML, "pmh")

    assert isinstance(result, dict)
    assert set(result.keys()) == {"authors", "urls", "license", "version", "abstract"}


def test_parse_page_accepts_resolved_url_kwarg():
    """fa98bf1: parse_page accepts a resolved_url positional/keyword arg.
    Passing it must not change the shape of the response on minimal HTML."""
    result = parse_page(MINIMAL_HTML, "doi", "https://example.com/article/123")

    assert isinstance(result, dict)
    assert "authors" in result


@pytest.mark.parametrize("namespace", [None, "", "unknown"])
def test_find_pdf_link_unknown_namespace_returns_none(namespace):
    """find_pdf_link already had an else: branch before fa98bf1. The parity
    test here pins that contract so the two functions stay in sync."""
    pdf = find_pdf_link(MINIMAL_HTML, namespace, None)
    assert pdf is None


@pytest.mark.parametrize(
    ("doi", "href", "expected"),
    [
        (
            "10.1080/13683500.2023.2214355",
            "/doi/pdf/10.1080/13683500.2023.2214355?download=true",
            "https://www.tandfonline.com/doi/pdf/10.1080/13683500.2023.2214355?download=true",
        ),
        (
            "10.1111/bpa.12253",
            "/doi/pdfdirect/10.1111/bpa.12253?download=true",
            "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/bpa.12253?download=true",
        ),
        (
            "10.1177/001440294401000402",
            "/doi/pdf/10.1177/001440294401000402?download=true",
            "https://journals.sagepub.com/doi/pdf/10.1177/001440294401000402?download=true",
        ),
        (
            "10.1021/jacs.9b13398",
            "/doi/pdf/10.1021/jacs.9b13398",
            "https://pubs.acs.org/doi/pdf/10.1021/jacs.9b13398",
        ),
    ],
)
def test_parse_page_resolves_relative_doi_pdf_links_off_publisher_host(doi, href, expected):
    html = f"<html><body><a href='{href}'>Download</a></body></html>"

    result = parse_page(html, "doi", f"https://doi.org/{doi}")

    assert result["urls"] == [{"url": expected, "content_type": "pdf"}]
