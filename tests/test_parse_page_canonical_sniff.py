"""Test parse_page's canonical-URL sniff that fixes the doi.org host bug.

Before this fix, when callers passed `resolved_url="https://doi.org/<doi>"`
(common for cached HTML where the actual landing-page URL is unknown), the
downstream PDF-URL joiner produced broken results like
`https://doi.org/doi/pdf/<doi>` because the relative path was joined against
doi.org instead of the publisher's host.

Fix: if `resolved_url` is a bare DOI router URL, sniff the HTML's
<link rel="canonical"> or <meta property="og:url"> to recover the publisher's
URL, then use that for relative-URL joining.
"""

from parseland_lib.parse import (
    _is_doi_router_url,
    _sniff_publisher_url,
    parse_page,
)
from bs4 import BeautifulSoup


class TestIsDoiRouterUrl:
    def test_doi_org(self) -> None:
        assert _is_doi_router_url("https://doi.org/10.1021/foo")
        assert _is_doi_router_url("http://doi.org/10.1021/foo")

    def test_dx_doi_org(self) -> None:
        assert _is_doi_router_url("https://dx.doi.org/10.1021/foo")

    def test_publisher_url(self) -> None:
        assert not _is_doi_router_url("https://pubs.acs.org/doi/10.1021/foo")
        assert not _is_doi_router_url("https://onlinelibrary.wiley.com/doi/10.1002/foo")

    def test_none_and_empty(self) -> None:
        assert not _is_doi_router_url(None)
        assert not _is_doi_router_url("")


class TestSniffPublisherUrl:
    def test_finds_canonical_link(self) -> None:
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://pubs.acs.org/doi/10.1021/example"/>'
            "</head><body/></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert _sniff_publisher_url(soup) == "https://pubs.acs.org/doi/10.1021/example"

    def test_finds_og_url_when_no_canonical(self) -> None:
        html = (
            "<html><head>"
            '<meta property="og:url" content="https://journals.lww.com/x/Fulltext/2024/00000/y.aspx"/>'
            "</head><body/></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert _sniff_publisher_url(soup) == "https://journals.lww.com/x/Fulltext/2024/00000/y.aspx"

    def test_prefers_canonical_over_og(self) -> None:
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://pubs.acs.org/doi/10.1021/preferred"/>'
            '<meta property="og:url" content="https://example.com/og-fallback"/>'
            "</head><body/></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert _sniff_publisher_url(soup) == "https://pubs.acs.org/doi/10.1021/preferred"

    def test_skips_doi_router_canonical(self) -> None:
        # Some publishers set canonical to the DOI link — should fall through.
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://doi.org/10.1021/foo"/>'
            '<meta property="og:url" content="https://pubs.acs.org/doi/10.1021/foo"/>'
            "</head><body/></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert _sniff_publisher_url(soup) == "https://pubs.acs.org/doi/10.1021/foo"

    def test_returns_none_when_no_hints(self) -> None:
        html = "<html><head></head><body/></html>"
        soup = BeautifulSoup(html, "lxml")
        assert _sniff_publisher_url(soup) is None


class TestParsePageDoiRewriteFlow:
    def test_doi_resolved_url_falls_back_to_canonical(self) -> None:
        # Construct a minimal HTML with canonical + a relative PDF link in a
        # meta citation_pdf_url. parse_page should produce a URL on the ACS
        # host, not on doi.org.
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://pubs.acs.org/doi/10.1021/jacs.test"/>'
            '<meta name="citation_pdf_url" content="/doi/pdf/10.1021/jacs.test"/>'
            "</head><body/></html>"
        )
        result = parse_page(html, namespace="doi", resolved_url="https://doi.org/10.1021/jacs.test")
        pdf_urls = [u["url"] for u in result["urls"] if u.get("content_type") == "pdf"]
        # The canonical sniff should produce a URL on pubs.acs.org, NOT doi.org.
        assert pdf_urls, "expected at least one PDF URL"
        bad = [u for u in pdf_urls if u.startswith("https://doi.org/")]
        assert not bad, f"PDF URL should not start with https://doi.org/: {pdf_urls}"

    def test_non_doi_router_resolved_url_is_left_alone(self) -> None:
        # If the caller already passes a publisher URL, sniff must not
        # override it.
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://other.example.com/should-not-be-used"/>'
            '<meta name="citation_pdf_url" content="/doi/pdf/10.1021/jacs.test"/>'
            "</head><body/></html>"
        )
        result = parse_page(
            html, namespace="doi",
            resolved_url="https://pubs.acs.org/doi/10.1021/jacs.test",
        )
        pdf_urls = [u["url"] for u in result["urls"] if u.get("content_type") == "pdf"]
        assert pdf_urls
        # Sniff should NOT have run because resolved_url is already a publisher URL.
        bad = [u for u in pdf_urls if "other.example.com" in u]
        assert not bad, f"sniff must not run when resolved_url is already non-doi.org: {pdf_urls}"
