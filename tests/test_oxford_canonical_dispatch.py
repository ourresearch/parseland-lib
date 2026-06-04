"""Oxford parser must dispatch via canonical link even when og:url is doi.org.

Before this fix, Oxford pages cached with og:url pointing at the DOI router
(dx.doi.org / doi.org) failed `is_publisher_specific_parser`, so the
generic parser handled the page and the abstract section was never read.

The fix: also accept `<link rel="canonical" href="...academic.oup.com...">`
as a publisher signal.
"""

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.oxford import Oxford


def _make(html: str) -> Oxford:
    return Oxford(BeautifulSoup(html, "lxml"))


class TestOxfordDispatch:
    def test_dispatch_via_og_url(self) -> None:
        # Original positive case: og:url already points at academic.oup.com.
        html = (
            "<html><head>"
            '<meta property="og:url" content="https://academic.oup.com/foo/article/123">'
            "</head><body/></html>"
        )
        assert _make(html).is_publisher_specific_parser() is True

    def test_dispatch_via_canonical_when_og_url_is_doi(self) -> None:
        # The cache-survived case that this fix targets.
        html = (
            "<html><head>"
            '<meta property="og:url" content="https://dx.doi.org/10.1093/foo/bar">'
            '<link rel="canonical" href="https://academic.oup.com/foo/article/123">'
            "</head><body/></html>"
        )
        assert _make(html).is_publisher_specific_parser() is True

    def test_no_dispatch_when_neither_matches(self) -> None:
        html = (
            "<html><head>"
            '<meta property="og:url" content="https://example.com/page">'
            '<link rel="canonical" href="https://example.com/page">'
            "</head><body/></html>"
        )
        assert _make(html).is_publisher_specific_parser() is False

    def test_abstract_recovered_after_dispatch_fix(self) -> None:
        # Minimal Oxford-shaped HTML: canonical to academic.oup.com, abstract
        # in `<section class="abstract"><p class="chapter-para">...`.
        html = (
            "<html><head>"
            '<meta property="og:url" content="https://dx.doi.org/10.1093/foo/bar">'
            '<link rel="canonical" href="https://academic.oup.com/foo/article/123">'
            "</head><body>"
            '<section class="abstract"><p class="chapter-para">This is the article abstract text.</p></section>'
            "</body></html>"
        )
        parser = _make(html)
        assert parser.is_publisher_specific_parser() is True
        result = parser.parse()
        assert "This is the article abstract text." in result["abstract"]
