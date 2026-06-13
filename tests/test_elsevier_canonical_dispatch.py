"""ElsevierBV dispatch accepts canonical-link fallback.

Legacy ScienceDirect /abs/ pages (pre-2000s reprints, Cell Press supplements,
conference abstracts) omit the OneTrust cookielaw script that modern pages
use as the publisher-specific signal. They DO carry
`<link rel="canonical" href="https://www.sciencedirect.com/...">` though,
so accepting that as an alternate dispatch signal recovers parser routing.
"""

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV


def _make(html: str) -> ElsevierBV:
    return ElsevierBV(BeautifulSoup(html, "lxml"))


class TestElsevierDispatch:
    def test_no_dispatch_via_cookielaw_script_alone(self) -> None:
        # OneTrust is shared across publishers; it is not an Elsevier signal by
        # itself.
        html = (
            "<html><head>"
            '<script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js"></script>'
            "</head><body/></html>"
        )
        assert bool(_make(html).is_publisher_specific_parser()) is False

    def test_dispatch_via_cookielaw_with_elsevier_meta(self) -> None:
        html = (
            "<html><head>"
            '<script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js"></script>'
            '<meta name="citation_publisher" content="Elsevier">'
            "</head><body/></html>"
        )
        assert bool(_make(html).is_publisher_specific_parser()) is True

    def test_dispatch_via_canonical_when_no_cookielaw(self) -> None:
        # Legacy /abs/ page case this fix targets.
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://www.sciencedirect.com/science/article/abs/pii/S000304651631453X">'
            "</head><body/></html>"
        )
        assert bool(_make(html).is_publisher_specific_parser()) is True

    def test_no_dispatch_for_ssrn_canonical(self) -> None:
        # ssrn.com under sciencedirect is explicitly excluded so SSRN's
        # dedicated parser handles it.
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=123">'
            "</head><body/></html>"
        )
        assert bool(_make(html).is_publisher_specific_parser()) is False

    def test_no_dispatch_for_unrelated_host(self) -> None:
        html = (
            "<html><head>"
            '<link rel="canonical" href="https://example.com/page">'
            "</head><body/></html>"
        )
        assert bool(_make(html).is_publisher_specific_parser()) is False
