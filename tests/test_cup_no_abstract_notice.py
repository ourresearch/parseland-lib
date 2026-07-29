"""CUP no-abstract preview notices must never become the abstract.

CUP pages without an abstract put an access notice inside div.abstract:
  "An abstract is not available for this content so a preview has been
   provided. Please use the Get access link above for information on how to
   access this content." (and the "Summary A summary is not available..."
variant on summary-styled pages). A guard in CUP.parse() was inverted and
ASSIGNED the notice as the abstract — during the reparse campaign this wrote
the notice into ~872K works (oxjob reparse-all-landing-pages,
cup-preview-junk-dois.txt).

These pin: (1) the abstract-variant notice yields no abstract; (2) the
summary-variant notice yields no abstract; (3) a real div.abstract is still
extracted (eBook fallback unchanged); (4) a notice arriving via the abstract
meta tag is discarded, letting a real visible abstract win.

Hand-crafted HTML — no Taxicab, no network.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.cup import CUP

CAMBRIDGE_OG = '<meta property="og:url" content="https://www.cambridge.org/core/x" />'

NOTICE_ABSTRACT = (
    "An abstract is not available for this content so a preview has been "
    "provided. Please use the Get access link above for information on how "
    "to access this content."
)
NOTICE_SUMMARY = (
    "Summary A summary is not available for this content so a preview has "
    "been provided. Please use the Get access link above for information on "
    "how to access this content."
)
REAL_ABSTRACT = (
    "We develop a model of optimal land allocation in a developing economy "
    "that features three possible land uses: agriculture, primary and "
    "secondary forests, with public-good contributions differing by type."
)


def _parse(head_extra: str, body: str):
    html = f"<html><head>{CAMBRIDGE_OG}{head_extra}</head><body>{body}</body></html>"
    parser = CUP(BeautifulSoup(html, features="lxml"))
    return parser.parse()


def _author_div():
    return (
        '<div class="author"><dt>Jane Doe</dt>'
        '<div class="d-sm-flex">Example University</div></div>'
    )


def test_abstract_notice_yields_no_abstract():
    result = _parse("", _author_div() + f'<div class="abstract">{NOTICE_ABSTRACT}</div>')
    assert not result["abstract"]


def test_summary_notice_yields_no_abstract():
    result = _parse("", _author_div() + f'<div class="abstract">{NOTICE_SUMMARY}</div>')
    assert not result["abstract"]


def test_real_visible_abstract_still_extracted():
    result = _parse("", _author_div() + f'<div class="abstract">Abstract {REAL_ABSTRACT}</div>')
    assert result["abstract"] == REAL_ABSTRACT


def test_notice_in_meta_abstract_discarded_for_visible():
    head = f'<meta name="citation_abstract" content="{NOTICE_ABSTRACT}" />'
    result = _parse(head, _author_div() + f'<div class="abstract">Abstract {REAL_ABSTRACT}</div>')
    assert result["abstract"] == REAL_ABSTRACT
