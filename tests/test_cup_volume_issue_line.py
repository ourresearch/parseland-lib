"""A Cambridge Core page's citation line in og:description is not its abstract (oxjob #2604).

On pages with no abstract (book reviews, notes, obituaries) Cambridge Core's og:description and description meta are
"<title, or the reviewed book's citation> - Volume 87 Issue 1-2", and citation_abstract is a link to a first-page
image. The meta reader took the description (it is over 200 characters when the citation is long), so ~206K works
showed it as their abstract.

These pin: (1) the line gives no abstract; (2) the "- Volume N" form without an issue too; (3) a page that also has a
visible abstract gets that abstract; (4) an article whose og:description is its real abstract keeps it.

Hand-crafted HTML: no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.cup import CUP

CAMBRIDGE_OG = '<meta property="og:url" content="https://www.cambridge.org/core/x" />'
FIRST_PAGE = ('<meta name="citation_abstract" content="https://static.cambridge.org/content/id/'
              'urn%3Acambridge.org%3Aid%3Aarticle%3AS0035869X00107117/resource/name/firstPage-S0035869X00107117a.jpg" />')
REVIEW_LINE = (
    "Landlord and Peasant in Persia: A Study of Land Tenure and Land Revenue Administration. By A. K. S. Lambton. "
    "Royal Institute of International Affairs. London: Oxford University Press, 1953. pp. xxxi + 459. 42s. "
    "- Volume 87 Issue 1-2"
)
VOLUME_ONLY_LINE = (
    "Roman Gaul and Germany. By Anthony King. London: British Museum Publications, 1990. Pp. 240, 171 illus. "
    "ISBN 0 7141 2058 5. £14.95. Exploring Roman Britain at Silchester, a reviewed volume. - Volume 38"
)
REAL_ABSTRACT = (
    "We develop a model of optimal land allocation in a developing economy that features three possible land uses: "
    "agriculture, primary and secondary forests, with public-good contributions differing by type, and show that "
    "reforestation is costly because it undermines land title security."
)


def _meta(content):
    return (f'<meta property="og:description" content="{content}" />'
            f'<meta name="description" content="{content}" />')


def _parse(head_extra: str, body: str = ""):
    html = f"<html><head>{CAMBRIDGE_OG}{head_extra}</head><body>{body}</body></html>"
    return CUP(BeautifulSoup(html, features="lxml")).parse()


def test_review_citation_line_is_no_abstract():
    assert not _parse(FIRST_PAGE + _meta(REVIEW_LINE))["abstract"]


def test_volume_only_line_is_no_abstract():
    assert not _parse(FIRST_PAGE + _meta(VOLUME_ONLY_LINE))["abstract"]


def test_visible_abstract_wins_over_the_line():
    result = _parse(FIRST_PAGE + _meta(REVIEW_LINE), f'<div class="abstract">Abstract {REAL_ABSTRACT}</div>')
    assert result["abstract"] == REAL_ABSTRACT


def test_real_meta_abstract_kept():
    assert _parse(_meta(REAL_ABSTRACT))["abstract"] == REAL_ABSTRACT
